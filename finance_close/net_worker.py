"""Fixed-host HTTP in one owned process; a parent deadline covers blocking I/O.

No process or socket starts on import. Integration checks require a resource lease.
"""

import base64
import http.client
import multiprocessing
import time
from urllib.parse import urlsplit

from .domain import InvalidInput, canonical, strict_json

GATEWAY_URL = "https://ai-gateway.vercel.sh/v1/chat/completions"
REQUEST_BYTES = 65536
RESPONSE_BYTES = 32768
IPC_BYTES = 49152


class TransportFailure(Exception):
    def __init__(self, kind, *, elapsed_seconds=0.0, cleanup_complete=True):
        super().__init__("Gateway transport stopped: " + kind)
        self.kind = kind
        self.elapsed_seconds = elapsed_seconds
        self.cleanup_complete = cleanup_complete


def validate_endpoint(endpoint, mode):
    if mode == "live":
        if endpoint != GATEWAY_URL:
            raise InvalidInput("Live Gateway host/path is fixed")
    elif mode == "local-double":
        try:
            p = urlsplit(endpoint)
            valid = p.scheme == "http" and p.hostname in {"127.0.0.1", "::1"} and \
                p.path == "/v1/chat/completions" and p.port is not None and \
                1 <= p.port <= 65535 and not any([p.query, p.fragment, p.username, p.password])
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise InvalidInput("Double requires a literal loopback Chat Completions endpoint")
    else:
        raise InvalidInput("Unknown Gateway evidence mode")


def _request_worker(shared, ready_length, endpoint, mode, payload, token, timeout):
    """Return bounded body/status only; never serialize headers or exception text."""
    connection = None
    try:
        validate_endpoint(endpoint, mode)
        p = urlsplit(endpoint)
        if type(payload) is not bytes or not 0 < len(payload) <= REQUEST_BYTES:
            raise ValueError("request bound")
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                   "Accept-Encoding": "identity"}
        if mode == "live":
            if type(token) is not str or not 1 <= len(token) <= 512 or \
                    any(ord(c) < 33 or ord(c) > 126 for c in token):
                raise ValueError("invalid token")
            headers["Authorization"] = "Bearer " + token
        elif token is not None:
            raise ValueError("double must not receive credentials")
        cls = http.client.HTTPSConnection if mode == "live" else http.client.HTTPConnection
        connection = cls(p.hostname, p.port or (443 if mode == "live" else 80), timeout=timeout)
        connection.request("POST", p.path, body=payload, headers=headers)
        response = connection.getresponse()
        status = response.status
        if status != 200:
            result = {"status": status, "body": "", "kind": "http_status"}
        elif response.getheader("Content-Type", "").split(";", 1)[0].strip() != "application/json" or \
                response.getheader("Content-Encoding", "identity").lower() not in {"", "identity"}:
            result = {"status": status, "body": "", "kind": "content_type"}
        else:
            body = response.read(RESPONSE_BYTES + 1)
            result = {"status": status, "body": base64.b64encode(body).decode("ascii"),
                      "kind": "oversize_response" if len(body) > RESPONSE_BYTES else "ok"}
        raw = canonical(result).encode("utf-8")
        if len(raw) > IPC_BYTES:
            raise ValueError("IPC bound")
        shared[:len(raw)] = raw
        ready_length.value = len(raw)
    except BaseException:
        # Includes transport/TLS/DNS failures; raw errors can echo a secret.
        try:
            raw = b'{"status":null,"body":"","kind":"transport_uncertain"}'
            shared[:len(raw)] = raw
            ready_length.value = len(raw)
        except (OSError, ValueError):
            pass
    finally:
        if connection is not None:
            connection.close()


def _finish_owned(process, deadline, clock=time.monotonic):
    """Only the retained owned process handle may be terminated; no PID scans."""
    remaining = lambda: max(0.0, deadline - clock())
    if process.is_alive():
        process.join(timeout=min(0.02, remaining()))
    if process.is_alive():
        process.terminate()
        process.join(timeout=min(0.2, remaining()))
    if process.is_alive():
        process.kill()
        process.join(timeout=remaining())
    complete = not process.is_alive()
    if complete:
        process.close()
    return complete


def request_bytes(endpoint, mode, payload, token, timeout, cancelled=None,
                  *, worker_target=None):
    """One POST, zero retries. Return response + measured owned cleanup receipt.

    worker_target is an internal fault-control hook; Gateway never selects it.
    A blocked DNS/TLS/connect/read operation cannot reset the parent clock.
    """
    validate_endpoint(endpoint, mode)
    if type(payload) is not bytes or not 0 < len(payload) <= REQUEST_BYTES:
        raise TransportFailure("request_bound")
    if type(timeout) not in {int, float} or not 0.05 <= timeout <= 15:
        raise TransportFailure("deadline_bound")
    if mode == "local-double" and token is not None:
        raise TransportFailure("credential_forbidden")
    started = time.monotonic()
    deadline = started + timeout
    cleanup_reserve = min(1.0, timeout / 4)
    network_deadline = deadline - cleanup_reserve
    if cancelled and cancelled():
        raise TransportFailure("cancelled")
    context = multiprocessing.get_context("spawn")
    # Lock-free bounded shared bytes avoid a blocking recv_bytes after a pipe
    # header arrives but its body is withheld or a sender dies mid-frame.
    shared = context.RawArray("B", IPC_BYTES)
    ready_length = context.RawValue("i", 0)
    process = context.Process(target=worker_target or _request_worker,
                              args=(shared, ready_length, endpoint, mode, payload, token, timeout), daemon=True)
    launched, cleanup_complete, raw, failure = False, True, None, None
    try:
        process.start()
        launched = True
        while True:
            if cancelled and cancelled():
                failure = "cancelled"
                break
            remaining = network_deadline - time.monotonic()
            if remaining <= 0:
                failure = "deadline_uncertain"
                break
            length = ready_length.value
            if length:
                if not 0 < length <= IPC_BYTES:
                    failure = "transport_uncertain"
                else:
                    raw = bytes(shared[:length])
                break
            if not process.is_alive():
                failure = "transport_uncertain"
                break
            time.sleep(min(0.01, remaining))
    except (OSError, RuntimeError, ValueError):
        failure = "transport_uncertain"
    finally:
        if launched:
            cleanup_complete = _finish_owned(process, deadline)
        else:
            process.close()
    elapsed = time.monotonic() - started
    if not cleanup_complete:
        failure = "owned_cleanup_failed"
    elif elapsed > timeout:
        failure = "deadline_uncertain"
    if failure:
        raise TransportFailure(failure, elapsed_seconds=elapsed, cleanup_complete=cleanup_complete)
    try:
        result = strict_json(raw.decode("utf-8"))
        if type(result) is not dict or set(result) != {"status", "body", "kind"}:
            raise ValueError("invalid IPC")
        if result["kind"] not in {"ok", "http_status", "content_type", "oversize_response", "transport_uncertain"}:
            raise ValueError("invalid IPC")
        body = base64.b64decode(result["body"], validate=True)
        return {"status": result["status"], "body": body, "kind": result["kind"],
                "elapsed_seconds": elapsed, "cleanup_complete": cleanup_complete}
    except (TypeError, ValueError, UnicodeError, AttributeError):
        raise TransportFailure("transport_uncertain", elapsed_seconds=elapsed,
                               cleanup_complete=cleanup_complete) from None
