"""Prepared leased integration batch; authored local HTTP double, never QBO.

Import is inert. Run only after main grants a named U2-A resource lease.
"""

import argparse
import copy
import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from finance_close.qbo import QboAdapter, QboFailure, ReadRequest, Scope, canonical
from finance_close.qbo_transport import IPC_BYTES, OwnedQboTransport, owned_get
from .qbo_u2a_contract import config, records, wire


class State:
    def __init__(self):
        self.mode, self.counts, self.observed, self.busy = "success", {}, [], threading.Event()


def handler_type(state):
    values = records()
    paths = {ReadRequest("999",kind,key,"").path:(kind,key) for kind,key in values}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass

        def do_GET(self):
            state.busy.set()
            try:
                state.observed.append({"method":"GET", "path_allowed":self.path in paths,
                    "path_sha256":hashlib.sha256(self.path.encode()).hexdigest(),
                    "authorization_present":self.headers.get("Authorization") is not None})
                if self.path not in paths: self.send_error(404); return
                key = paths[self.path]
                state.counts[key] = state.counts.get(key,0)+1
                mode = state.mode
                if mode.startswith("status-"):
                    self.send_response(int(mode.split("-")[1])); self.end_headers()
                    self.wfile.write(b'SECRET-CANARY'); return
                if mode == "redirect":
                    self.send_response(302); self.send_header("Location","https://evil.invalid/SECRET-CANARY")
                    self.end_headers(); return
                if mode == "headers": time.sleep(1.5); return
                if mode == "body":
                    self.send_response(200); self.send_header("Content-Type","application/json")
                    self.send_header("Content-Length","100000"); self.end_headers()
                    self.wfile.write(b'{"Bill":'); self.wfile.flush(); time.sleep(1.5); return
                entity = copy.deepcopy(values[key])
                if mode == "drift" and key == ("Bill","101") and state.counts[key] == 2:
                    entity["PrivateNote"] = "CHANGED-BUSINESS-CANARY"
                if mode == "currency": entity["CurrencyRef"] = {"value":"EUR"}
                if mode == "unknown-link" and key[0] == "BillPayment": entity["Line"][0]["LinkedTxn"][0]["TxnId"] = "99999"
                body = wire(key[0],entity)
                if mode == "duplicate": body = b'{"Bill":{},"Bill":{},"time":"2026-09-30T00:00:00Z"}'
                if mode == "truncated": body = b'{"Bill":'
                if mode == "query": body = b'{"QueryResponse":{},"time":"2026-09-30T00:00:00Z"}'
                if mode == "oversize": body = b' ' * 2048
                self.send_response(200)
                self.send_header("Content-Type","text/html" if mode == "content-type" else "application/json")
                self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
            except (ConnectionError,OSError): pass
            finally: state.busy.clear()

        def do_POST(self): self.send_error(405)
    return Handler


def blocked_worker(*args): time.sleep(30)


def invalid_ready_worker(shared,ready,*args): ready.value = IPC_BYTES+1


def partial_ipc_worker(shared,ready,*args):
    shared[:8] = b'{"status'
    ready.value = 8


def exited_worker(*args): return


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=["contract-http","deadline"],required=True)
    parser.add_argument("--out",required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists(): raise ValueError("Use a fresh U2-A integration directory")
    out.mkdir(parents=True)
    state = State(); server = HTTPServer(("127.0.0.1",0),handler_type(state))
    server.timeout = .05
    thread = threading.Thread(target=server.serve_forever,kwargs={"poll_interval":.05},daemon=True)
    origin = "http://127.0.0.1:"+str(server.server_port)
    started = time.monotonic(); checks, cases, events = [], [], []
    cleanup = False
    thread.start()

    def check(name,condition):
        checks.append({"name":name,"passed":bool(condition)})
        if not condition: raise AssertionError(name)

    def ready(mode):
        deadline = time.monotonic()+3
        while state.busy.is_set() and time.monotonic()<deadline: time.sleep(.01)
        check("previous handler finished before next control",not state.busy.is_set())
        state.mode, state.counts = mode, {}

    def capture_case(mode,expected=None,changes=None):
        ready(mode); cfg = config(); cfg.update(changes or {})
        scope = Scope.parse(cfg)
        transport = OwnedQboTransport(scope,loopback_origin=origin)
        adapter = QboAdapter(cfg,transport=transport,mode="local-http-double")
        before, count = time.monotonic(), len(state.observed)
        failure, document = None, None
        try: document = adapter.capture().as_dict()
        except QboFailure as exc: failure = exc.kind
        elapsed = time.monotonic()-before
        record = {"control":mode,"expected_failure":expected,"observed_failure":failure,
            "requests_attempted":adapter.requests,"observed_http_requests":len(state.observed)-count,
            "active_seconds":elapsed,"state":adapter.state,"events":len(adapter.events)}
        cases.append(record); events.extend(adapter.events)
        check(mode+" expected outcome",failure in expected if type(expected) is list else failure == expected)
        check(mode+" no automatic retries",all(e["automatic_http_retries"]==0 for e in adapter.events))
        check(mode+" all dispatched children cleaned",all(e["cleanup_complete"] is True for e in adapter.events))
        if mode.startswith("status-") or mode == "redirect": check(mode+" single GET",adapter.requests==1 and record["observed_http_requests"]==1)
        if document is not None:
            (out/"capture.json").write_text(canonical(document)+"\n",encoding="utf-8")
            check("native partial cents",document["bills"][0]["total_cents"]==100000 and
                  [p["total_cents"] for p in document["bill_payments"]]==[20000,40000] and
                  document["partial_payment_summary"][0]["snapshot_balance_cents"]==40000)
            check("always incomplete AP history",document["ap_history_complete"] is False and document["ledger_imported"] is False and document["posting_supported"] is False)
            check("same fixed IDs reread",adapter.requests==6 and len(state.observed)-count==6)
        return record

    try:
        if args.stage == "contract-http":
            capture_case("success")
            for status,kind in [(401,"auth_required"),(403,"permission_denied"),(404,"record_missing"),
                                (429,"rate_limited"),(500,"server_error"),(503,"server_error")]:
                capture_case("status-"+str(status),kind)
            for mode,kind in [("redirect","http_error"),("currency","unsupported_currency"),
                              ("unknown-link","scope_denied"),("duplicate","schema_error"),
                              ("truncated","schema_error"),("query","schema_error"),
                              ("drift","snapshot_drift"),("content-type","response_rejected"),
                              ("oversize","response_rejected")]:
                capture_case(mode,kind,{"max_response_bytes":1024} if mode=="oversize" else None)
        else:
            scope = Scope.parse(config()); request = ReadRequest("999","Bill","101",scope.hash)
            for mode,target,expected,cancel in [
                ("headers",None,"deadline_uncertain",False),("body",None,"deadline_uncertain",False),
                ("headers",None,"cancelled",True),("blocked-phase",blocked_worker,"deadline_uncertain",False),
                ("invalid-ready",invalid_ready_worker,"transport_uncertain",False),
                ("partial-ipc",partial_ipc_worker,"transport_uncertain",False),
                ("exited-worker",exited_worker,"transport_uncertain",False)]:
                ready(mode); before=time.monotonic(); failure=None; cleaned=None
                try:
                    owned_get(scope,request,origin,"local-http-double",None,1.,
                              cancelled=(lambda:time.monotonic()-before>=.4) if cancel else None,
                              worker_target=target)
                except QboFailure as exc:
                    failure=exc.kind; cleaned=getattr(exc,"cleanup_complete",None)
                elapsed=time.monotonic()-before
                cases.append({"control":mode,"expected_failure":expected,"observed_failure":failure,
                    "active_seconds":elapsed,"deadline_seconds":1.,"overrun_seconds":max(0,elapsed-1.),
                    "cleanup_complete":cleaned,"simulation":target is not None})
                check(mode+" exact failure",failure==expected)
                check(mode+" within deadline plus two seconds",elapsed<=3.)
                check(mode+" owned child cleaned",cleaned is True)
            capture_case("success",["deadline","deadline_uncertain"],{"deadline_seconds":.5,"request_seconds":.5})
        check("only fixed literal-loopback GET paths",all(o["method"]=="GET" and o["path_allowed"] for o in state.observed))
        check("no Authorization on double",all(not o["authorization_present"] for o in state.observed))
        check("canaries absent from saved evidence","CANARY" not in canonical(cases)+canonical(events))
    except Exception:
        # Preserve the first unexpected outcome without raw exception content.
        checks.append({"name":"batch completed","passed":False})
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)
        cleanup=not thread.is_alive()
        checks.append({"name":"owned server/thread cleanup","passed":cleanup})
    receipt = {"schema_version":1,"stage":args.stage,"evidence_mode":"local-http-double",
        "exit_code":0 if all(c["passed"] for c in checks) else 1,
        "conditions":len(checks),"controls":len(cases),"active_seconds":time.monotonic()-started,
        "checks":checks,"cases":cases,"http_observations":state.observed,
        "server_cleanup_complete":cleanup,"maximum_owned_loopback_servers":1,
        "maximum_owned_python_children":1,"external_sandbox_calls":0,"model_calls":0,
        "credential_accessed":False,"automatic_http_retries":0,
        "limitations":["One authored contract; no unseen/corpus/real QBO evidence.",
            "Blocked-phase controls simulate DNS/TLS/loader stalls; no external networking.",
            "No full-tree lifetime RSS measurement; parent process start cannot be preempted by Python."]}
    (out/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    (out/"qbo-events.jsonl").write_text("".join(canonical(e)+"\n" for e in events),encoding="utf-8")
    print(json.dumps({"exit_code":receipt["exit_code"],"controls":len(cases),"conditions":len(checks)}))
    return receipt["exit_code"]


if __name__ == "__main__": raise SystemExit(main())
