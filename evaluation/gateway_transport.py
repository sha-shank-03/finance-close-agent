"""Lease-gated owned transport controls; only literal loopback networking.

DNS/TLS controls are explicitly simulated blocking phases in the owned child;
they do not establish genuine DNS, TLS, Gateway or external sandbox behavior.
"""

import argparse
import json
import socket
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from finance_close.net_worker import IPC_BYTES, RESPONSE_BYTES, TransportFailure, _request_worker, request_bytes


def blocked_dns(shared,length,endpoint,mode,payload,token,timeout):
    original=socket.getaddrinfo
    def delayed(*args,**kwargs): time.sleep(30);return original(*args,**kwargs)
    socket.getaddrinfo=delayed
    _request_worker(shared,length,endpoint,mode,payload,token,timeout)


def blocked_tls(shared,length,endpoint,mode,payload,token,timeout):
    # Simulated verified-context setup stall, before any connection is attempted.
    original=ssl.create_default_context
    def delayed(*args,**kwargs): time.sleep(30);return original(*args,**kwargs)
    ssl.create_default_context=delayed
    ssl.create_default_context()


def partial_ipc(shared,length,*args):
    shared[:10]=b'{"status":'
    # Intentionally never publish readiness; no pipe frame can block the parent.
    time.sleep(30)


def invalid_ipc(shared,length,*args):
    raw=b'{"status":200,"body":"invalid base64!","kind":"ok"}'
    shared[:len(raw)]=raw;length.value=len(raw)


def invalid_ipc_length(shared,length,*args): length.value=IPC_BYTES+1
def exited_worker(shared,length,*args): return


class SlowDouble:
    def __init__(self,fault):
        self.stop=threading.Event();self.requests=0;owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                self.connection.settimeout(2)
                owner.requests+=1
                try:
                    size=int(self.headers.get("Content-Length","0"))
                    if not 0<size<=65536: return
                    self.rfile.read(size)
                    if fault=="slow_headers": owner.stop.wait(30);return
                    data=b'{}' if fault!="oversize" else b'x'*(RESPONSE_BYTES+1)
                    self.send_response(200)
                    self.send_header("Content-Type","text/plain" if fault=="content_type" else "application/json")
                    self.send_header("Content-Length",str(len(data) if fault!="slow_body" else 100))
                    self.end_headers()
                    if fault=="slow_body":
                        self.wfile.write(b'{');self.wfile.flush();owner.stop.wait(30);return
                    self.wfile.write(data)
                except (OSError,ValueError): pass
        self.server=HTTPServer(("127.0.0.1",0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={"poll_interval":.05},daemon=True)
    def __enter__(self): self.thread.start();return self
    def __exit__(self,*args):
        self.stop.set();self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
        if self.thread.is_alive(): raise RuntimeError("Owned loopback server cleanup failed")


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--out",required=True)
    args=parser.parse_args(argv);out=Path(args.out).resolve()
    if out.exists(): raise ValueError("Use a fresh transport receipt directory")
    out.mkdir(parents=True);receipts=[];checks={};error=None;started=time.monotonic()
    def attempt(name,endpoint,expected,worker=None,cancel=False):
        before=time.monotonic();limit=2.0;failure=None;result=None
        cancelled=(lambda: time.monotonic()-before>=.7) if cancel else None
        try:
            result=request_bytes(endpoint,"local-double",b'{}',None,limit,cancelled,worker_target=worker)
            kind=result["kind"];cleanup=result["cleanup_complete"]
        except TransportFailure as exc:
            failure=exc;kind=exc.kind;cleanup=exc.cleanup_complete
        elapsed=time.monotonic()-before
        receipt={"control":name,"expected":expected,"observed":kind,"configured_total_seconds":limit,
                 "actual_wall_seconds":elapsed,"overrun_seconds":max(0,elapsed-limit),
                 "owned_worker_cleanup_complete":cleanup,"failure_typed":failure is not None,
                 "mode":"local-double","live_calls":0,"credentials_loaded":False,
                 "phase_simulated":name in {"dns_blocked_simulated","tls_blocked_simulated"}}
        receipts.append(receipt)
        (out/"transport.jsonl").write_text("".join(json.dumps(r)+"\n" for r in receipts),encoding="utf-8")
        checks[name]=kind==expected and cleanup is True and elapsed<=limit+2
        if not checks[name]: raise AssertionError("Transport control failed: "+name)
    cleanup=False
    try:
        for fault in ["slow_headers","slow_body","oversize","content_type"]:
            with SlowDouble(fault) as server:
                endpoint=f"http://127.0.0.1:{server.server.server_port}/v1/chat/completions"
                expected={"oversize":"oversize_response","content_type":"content_type"}.get(fault,"deadline_uncertain")
                attempt(fault,endpoint,expected)
                checks[fault+"_single_request"]=server.requests==1
        with SlowDouble("slow_headers") as server:
            endpoint=f"http://127.0.0.1:{server.server.server_port}/v1/chat/completions"
            attempt("cancel_during_wait",endpoint,"cancelled",cancel=True)
        # Fault children either block before connection or publish synthetic IPC.
        # This endpoint is never contacted by these controls (DNS is stalled).
        endpoint="http://127.0.0.1:1/v1/chat/completions"
        for name,target,kind in [("dns_blocked_simulated",blocked_dns,"deadline_uncertain"),
                                ("tls_blocked_simulated",blocked_tls,"deadline_uncertain"),
                                ("partial_ipc",partial_ipc,"deadline_uncertain"),
                                ("invalid_ipc",invalid_ipc,"transport_uncertain"),
                                ("invalid_ipc_length",invalid_ipc_length,"transport_uncertain"),
                                ("worker_exit",exited_worker,"transport_uncertain")]:
            attempt(name,endpoint,kind,target)
        cleanup=True
    except (AssertionError,OSError,ValueError,RuntimeError):
        error="Transport batch stopped on first unresolved control; preserved receipts contain the result"
    report={"passed":error is None and all(checks.values()),"checks":checks,"error":error,
            "wall_seconds":time.monotonic()-started,"owned_cleanup_complete":cleanup,
            "mode":"local-double","live_calls":0,"automatic_retries":0,"credential_accessed":False,
            "limits":{"simultaneous_owned_workers":1,"simultaneous_owned_loopback_servers":1},
            "scope":"Real owned-process loopback header/body controls; simulated DNS/TLS phase stalls; no external integration."}
    (out/"report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report));return 0 if report["passed"] else 1


if __name__=="__main__": raise SystemExit(main())
