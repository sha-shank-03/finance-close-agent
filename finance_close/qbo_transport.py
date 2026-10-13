"""Inert, fixed-scope GET transport. Actual socket/process checks need a lease."""

import base64
import http.client
import json
import multiprocessing
import time
from urllib.parse import urlsplit

from .net_worker import _finish_owned
from .qbo import MAX_RESPONSE_BYTES, SANDBOX_ORIGIN, QboFailure, ReadRequest, Scope, canonical

IPC_BYTES = 2 * MAX_RESPONSE_BYTES


def validate_scope(scope):
    """Reject bypassing Scope.parse with a manually constructed dataclass."""
    try:
        if type(scope) is not Scope: raise ValueError()
        cfg = {"schema_version":1,"origin":SANDBOX_ORIGIN,"api_version":"v3","minor_version":75,
            "currency":"USD","realm_id":scope.realm_id,"as_of_date":scope.as_of_date,
            "bills":{b.id:{"vendor_id":b.vendor_id,"invoice_key":b.invoice_key,"sync_token":b.sync_token} for b in scope.bills},
            "payments":dict(scope.payments),"vendor_map":dict(scope.vendor_map)}
        for field in ["max_records","max_requests","max_response_bytes","max_total_bytes","deadline_seconds","request_seconds"]:
            cfg[field]=getattr(scope,field)
        if Scope.parse(cfg)!=scope: raise ValueError()
    except (ValueError,TypeError,AttributeError): raise QboFailure("invalid_config") from None


def validate_origin(origin, mode):
    if mode == "external-sandbox":
        if origin != SANDBOX_ORIGIN: raise QboFailure("scope_denied")
    elif mode == "local-http-double":
        try:
            p = urlsplit(origin)
            valid = p.scheme == "http" and p.hostname in {"127.0.0.1", "::1"} and \
                p.port is not None and 1 <= p.port <= 65535 and p.path in {"", "/"} and \
                not any([p.query, p.fragment, p.username, p.password])
        except (ValueError, TypeError): valid = False
        if not valid: raise QboFailure("scope_denied")
    else: raise QboFailure("invalid_config")


def _worker(shared, ready_length, scope, request, origin, mode, token, timeout):
    connection = None
    try:
        request.validate(scope)
        validate_origin(origin, mode)
        headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
        if mode == "external-sandbox":
            if type(token) is not str or not 1 <= len(token) <= 4096 or \
                    any(ord(c) < 33 or ord(c) > 126 for c in token): raise ValueError()
            headers["Authorization"] = "Bearer " + token
        elif token is not None: raise ValueError()
        p = urlsplit(origin)
        cls = http.client.HTTPSConnection if mode == "external-sandbox" else http.client.HTTPConnection
        # HTTPSConnection uses the default verified TLS context. No proxies or redirects.
        connection = cls(p.hostname, p.port or 443, timeout=timeout)
        connection.request("GET", request.path, headers=headers)
        response = connection.getresponse()
        status = response.status
        if status != 200:
            result = {"status": status, "body": "", "kind": "http_status"}
        elif response.getheader("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json" or \
                response.getheader("Content-Encoding", "identity").lower() not in {"", "identity"}:
            result = {"status": status, "body": "", "kind": "content_type"}
        else:
            body = response.read(scope.max_response_bytes + 1)
            result = {"status": status, "body": base64.b64encode(body).decode("ascii"),
                      "kind": "oversize_response" if len(body) > scope.max_response_bytes else "ok"}
        raw = canonical(result).encode("utf-8")
        if len(raw) > IPC_BYTES: raise ValueError()
        shared[:len(raw)] = raw
        ready_length.value = len(raw)
    except BaseException:
        # Raw TLS/DNS/HTTP/loader exceptions may contain secrets or business text.
        try:
            raw = b'{"status":null,"body":"","kind":"transport_uncertain"}'
            shared[:len(raw)] = raw
            ready_length.value = len(raw)
        except (ValueError, OSError): pass
    finally:
        if connection is not None: connection.close()


def owned_get(scope, request, origin, mode, token, timeout, cancelled=None, *, worker_target=None):
    """One GET, zero retries. Monotonic parent deadline includes owned cleanup.

    worker_target is an internal fault-control hook, never adapter/model config.
    """
    validate_scope(scope)
    if type(request) is not ReadRequest: raise QboFailure("scope_denied")
    request.validate(scope)
    validate_origin(origin, mode)
    if type(timeout) not in {int, float} or not .05 <= timeout <= 15: raise QboFailure("invalid_config")
    if mode == "local-http-double" and token is not None: raise QboFailure("credential_forbidden")
    owned_loader = worker_target is _token_worker and callable(token)
    if mode == "external-sandbox" and not owned_loader and (type(token) is not str or not 1 <= len(token) <= 4096 or
            any(ord(c) < 33 or ord(c) > 126 for c in token)): raise QboFailure("auth_required")
    started = time.monotonic()
    deadline = started + timeout
    network_deadline = deadline - min(1., timeout / 4)
    if cancelled and cancelled(): raise QboFailure("cancelled")
    context = multiprocessing.get_context("spawn")
    shared = context.RawArray("B", IPC_BYTES)
    ready_length = context.RawValue("i", 0)
    process = context.Process(target=worker_target or _worker,
        args=(shared, ready_length, scope, request, origin, mode, token, timeout), daemon=True)
    launched, cleanup_complete, raw, failure = False, True, None, None
    try:
        process.start()
        launched = True
        while True:
            if cancelled and cancelled(): failure = "cancelled"; break
            remaining = network_deadline - time.monotonic()
            if remaining <= 0: failure = "deadline_uncertain"; break
            length = ready_length.value
            if length:
                if not 0 < length <= IPC_BYTES: failure = "transport_uncertain"
                else: raw = bytes(shared[:length])
                break
            if not process.is_alive(): failure = "transport_uncertain"; break
            time.sleep(min(.01, remaining))
    except KeyboardInterrupt: failure = "cancelled"
    except Exception: failure = "transport_uncertain"
    finally:
        if launched: cleanup_complete = _finish_owned(process, deadline)
        else: process.close()
    elapsed = time.monotonic() - started
    if not cleanup_complete: failure = "owned_cleanup_failed"
    elif elapsed > timeout: failure = "deadline_uncertain"
    if failure:
        exc = QboFailure(failure)
        exc.elapsed_seconds, exc.cleanup_complete = elapsed, cleanup_complete
        raise exc
    try:
        result = json.loads(raw.decode("utf-8"))
        if type(result) is not dict or set(result) != {"status", "body", "kind"} or \
                result["kind"] not in {"ok", "http_status", "content_type", "oversize_response", "transport_uncertain"}:
            raise ValueError()
        body = base64.b64decode(result["body"], validate=True)
        if type(result["status"]) is not int or not 100 <= result["status"] <= 599 or \
                len(body) > scope.max_response_bytes + 1: raise ValueError()
        return {"status": result["status"], "body": body, "kind": result["kind"],
                "elapsed_seconds": elapsed, "cleanup_complete": cleanup_complete}
    except (TypeError, ValueError, UnicodeError, AttributeError):
        exc = QboFailure("transport_uncertain")
        exc.elapsed_seconds, exc.cleanup_complete = elapsed, cleanup_complete
        raise exc from None


class OwnedQboTransport:
    """Host creates this transport. No environment/presence/OAuth operations.

    The external gate is dormant in U2-A. Its loader runs only inside the owned
    child, after an explicit main authorization, and must supply an access token.
    A loader that blocks is covered by the parent deadline; no refresh/retry.
    """
    def __init__(self, scope, *, mode="local-http-double", loopback_origin=None,
                 allow_external=False, token_loader=None):
        validate_scope(scope)
        if mode == "external-sandbox":
            if allow_external is not True or not callable(token_loader): raise QboFailure("external_disabled")
            if loopback_origin is not None: raise QboFailure("invalid_config")
            origin = SANDBOX_ORIGIN
        elif mode == "local-http-double":
            if token_loader is not None or allow_external is not False: raise QboFailure("credential_forbidden")
            origin = loopback_origin
        else: raise QboFailure("invalid_config")
        validate_origin(origin, mode)
        self.scope, self.mode, self.origin = scope, mode, origin
        self.external_authorized = mode == "external-sandbox" and allow_external is True
        self.token_loader = token_loader

    def __call__(self, request, timeout, cancelled=None):
        request.validate(self.scope)
        if self.mode == "external-sandbox":
            # Do not load credentials in the unbounded parent. Only this owned
            # entry point receives the trusted picklable runtime loader.
            return owned_get(self.scope, request, self.origin, self.mode, self.token_loader,
                             timeout, cancelled, worker_target=_token_worker)
        return owned_get(self.scope, request, self.origin, self.mode, None, timeout, cancelled)


def _token_worker(shared, ready_length, scope, request, origin, mode, loader, timeout):
    try:
        request.validate(scope)
        validate_origin(origin, mode)
        if mode != "external-sandbox": raise ValueError()
        token = loader()
    except BaseException:
        raw = b'{"status":401,"body":"","kind":"http_status"}'
        shared[:len(raw)] = raw
        ready_length.value = len(raw)
        return
    _worker(shared, ready_length, scope, request, origin, mode, token, timeout)
