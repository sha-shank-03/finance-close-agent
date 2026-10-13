"""Lease-gated, owned loopback Gateway double and public CLI U1 controls.

This authored replay tests protocol/host behavior; it is not live inference,
unseen evaluation, external sandbox integration or general accounting accuracy.
Importing this module does not open sockets or start children.
"""

import argparse
import copy
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from finance_close.providers import ScriptedProvider
from .gateway_verify import verify

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "fixtures/u1/proposal"
CANARY = "SYNTHETIC_REDACTION_CANARY_U1_8791"


def response(payload, sequence, fault):
    """Derive the next replay decision only from actual wire observations."""
    user = payload["messages"][1]["content"]
    bank_id, snapshot = re.fullmatch(r"Investigate bank_id=([^;]+); snapshot=([0-9a-f]+)", user).groups()
    history, calls = [], {}
    for item in payload["messages"][2:]:
        if item["role"] == "assistant":
            call = item["tool_calls"][0]
            calls[call["id"]] = call
        elif item["role"] == "tool":
            call = calls[item["tool_call_id"]]
            observation = json.loads(item["content"])
            history.append({"decision":{"tool":call["function"]["name"],
                                        "arguments":json.loads(call["function"]["arguments"])},
                            "status":observation["status"],"result":observation["result"]})
    decision = ScriptedProvider().next_decision({"bank_id":bank_id,"snapshot_version":snapshot,"history":history})
    if fault == "false_finish":
        decision = {"tool":"finish_case","arguments":{"bank_id":bank_id}}
    elif fault == "repeat":
        decision = {"tool":"inspect_transaction","arguments":{"bank_id":bank_id}}
    elif fault == "host_denied":
        decision = {"tool":"draft_entry","arguments":{"bank_id":bank_id,"rule_id":CANARY,"evidence_ids":[]}}
    elif fault == "unknown_tool":
        decision = {"tool":CANARY,"arguments":{"bank_id":bank_id}}
    call = {"id":"call_double_"+str(sequence),"type":"function","function":{
        "name":decision["tool"],"arguments":json.dumps(decision["arguments"],separators=(",",":"))}}
    value = {"id":"chatcmpl-double-"+str(sequence),"object":"chat.completion",
             "model":"test/u1-double","choices":[{"index":0,"finish_reason":"tool_calls",
             "message":{"role":"assistant","content":None,"tool_calls":[call]}}],
             "usage":{"prompt_tokens":200,"completion_tokens":50,"total_tokens":250}}
    if fault == "wrong_model": value["model"] = "test/unapproved"
    if fault == "multiple_tools": value["choices"][0]["message"]["tool_calls"].append(copy.deepcopy(call))
    return json.dumps(value,separators=(",",":")).encode()


class Double:
    def __init__(self):
        self.fault, self.requests, self.authorizations = None, [], 0
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                self.connection.settimeout(2)
                length = int(self.headers.get("Content-Length","0"))
                if self.path != "/v1/chat/completions" or not 0 < length <= 65536:
                    self.send_error(400);return
                body = self.rfile.read(length)
                payload = json.loads(body)
                owner.authorizations += int("Authorization" in self.headers)
                owner.requests.append({"sequence":len(owner.requests)+1,"request_bytes":len(body),
                                       "request_sha256":hashlib.sha256(body).hexdigest(),
                                       "native_tool_observations":sum(m["role"]=="tool" for m in payload["messages"]),
                                       "mode":"local-double","authorization_present":"Authorization" in self.headers})
                status = int(owner.fault) if owner.fault and owner.fault.isdecimal() else 200
                data = (CANARY.encode() if status != 200 else b'{"broken":'+CANARY.encode()
                        if owner.fault == "malformed" else response(payload,len(owner.requests),owner.fault))
                self.send_response(status);self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(data)));self.end_headers()
                self.wfile.write(data)
        self.server = HTTPServer(("127.0.0.1",0),Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,kwargs={"poll_interval":.05},daemon=True)

    def __enter__(self): self.thread.start();return self
    def __exit__(self,*args):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
        if self.thread.is_alive(): raise RuntimeError("Owned double did not stop")


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--out",required=True)
    args=parser.parse_args(argv);out=Path(args.out).resolve()
    if out.exists(): raise ValueError("Use a fresh acceptance output directory")
    out.mkdir(parents=True);commands=[];checks={};started=time.monotonic()
    def command(label,arguments,expected):
        before=time.monotonic()
        result=subprocess.run([sys.executable,"-m",*arguments],cwd=ROOT,capture_output=True,text=True,timeout=60)
        receipt={"label":label,"argv":[sys.executable,"-m",*map(str,arguments)],"expected_exit":expected,
                 "actual_exit":result.returncode,"wall_seconds":time.monotonic()-before}
        commands.append(receipt)
        (out/(label+".log")).write_text(result.stdout+result.stderr,encoding="utf-8")
        (out/"commands.jsonl").write_text("".join(json.dumps(r)+"\n" for r in commands),encoding="utf-8")
        if result.returncode != expected: raise AssertionError("Unexpected exit: "+label)
    def independent(label,run,state="PENDING",expected=True):
        command(label,["evaluation.gateway_verify","--run",str(run),"--input",str(SOURCE),
                       "--review-state",state,"--out",str(out/(label+".json"))],0 if expected else 1)
        checks[label]=json.loads((out/(label+".json")).read_text(encoding="utf-8"))["passed"] is expected
    cleanup=False;error=None
    try:
        with Double() as double:
            config={"mode":"local-double","model":"test/u1-double","provider":"test",
                    "endpoint":f"http://127.0.0.1:{double.server.server_port}/v1/chat/completions",
                    "timeout_seconds":5,"max_requests":12,"allocation_usd":"0","request_cost_upper_usd":"0"}
            config_path=out/"double-config.json";config_path.write_text(json.dumps(config,indent=2)+"\n",encoding="utf-8")
            def run(label,path,expected=0,source=SOURCE,extra=()):
                command(label,["finance_close","run","--input",str(source),"--out",str(path),
                               "--provider","gateway","--gateway-config",str(config_path),
                               "--invoice-format","aliases-v1",*extra],expected)
            journey=out/"journey";run("proposal",journey);independent("pending",journey)
            packet=json.loads((journey/"packet.json").read_text(encoding="utf-8"));proposal=packet["proposals"][0]
            command("approve",["finance_close","review","--run",str(journey),"--proposal-id",proposal["id"],
                    "--expected-hash",proposal["hash"],"--snapshot-version",packet["snapshot_version"],
                    "--decision","approve","--reviewer","fictional-u1-reviewer"],0)
            independent("approved",journey,"APPROVED")
            before=len(double.requests);run("completed_resume",journey)
            checks["completed_resume_no_inference"]=before==len(double.requests)
            for fault in ["401","402","403","429","500","503","malformed","unknown_tool",
                          "wrong_model","multiple_tools","host_denied","repeat"]:
                double.fault=fault;folder=out/("negative-"+fault)
                before=len(double.requests);run(fault,folder,4)
                checks[fault+"_one_request_per_decision"]=len(double.requests)-before==(2 if fault=="repeat" else 1)
                before=len(double.requests);run(fault+"_resume",folder,4)
                checks[fault+"_resume_no_retry"]=before==len(double.requests)
                db=sqlite3.connect(folder/"state.sqlite")
                try:
                    checks[fault+"_no_proposal"]=db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]==0
                    checks[fault+"_booked_unchanged"]=db.execute("SELECT SUM(signed_cents) FROM ledger WHERE account='accounts_payable'").fetchone()[0]==-80000
                    checks[fault+"_cost_unknown"]=all(json.loads(r[0])["actual_cost_usd"] is None for r in db.execute("SELECT receipt FROM gateway_requests"))
                finally: db.close()
                checks[fault+"_redacted"]=all(CANARY.encode() not in p.read_bytes() for p in folder.rglob("*") if p.is_file())
                checks[fault+"_error_redacted"]=CANARY not in (out/(fault+".log")).read_text(encoding="utf-8")
            double.fault="false_finish";false_run=out/"false-finish";run("false_finish",false_run)
            independent("false_finish_rejected_independently",false_run,expected=False)
            double.fault=None
            for fault in ["after-proposal-commit","before-packet-rename"]:
                folder=out/fault;run(fault,folder,85,extra=["--test-fault",fault]);before=len(double.requests)
                run(fault+"_recover",folder);independent(fault+"_verified",folder)
                checks[fault+"_no_duplicate"]=len(double.requests)-before==(1 if fault=="after-proposal-commit" else 0)
            ambiguous=out/"ambiguous-input";shutil.copytree(SOURCE,ambiguous)
            original=(ambiguous/"invoices/original.txt").read_text(encoding="utf-8")
            (ambiguous/"invoices/other.txt").write_text(original.replace("I-U1","I-U1-OTHER"),encoding="utf-8")
            ambiguity_run=out/"ambiguity";run("ambiguity",ambiguity_run,source=ambiguous)
            packet=json.loads((ambiguity_run/"packet.json").read_text(encoding="utf-8"))
            checks["ambiguous_alias_handoff"]=not packet["proposals"] and "CONFLICTING_EVIDENCE" in {r["reason"] for r in packet["exceptions"]}
            for mutation in ["one-cent","deleted-proposal","forged-provenance"]:
                folder=out/("corruption-"+mutation);shutil.copytree(journey,folder)
                db=sqlite3.connect(folder/"state.sqlite")
                try:
                    if mutation=="one-cent": db.execute("UPDATE proposal_lines SET amount_cents=amount_cents+1 WHERE number=0")
                    elif mutation=="deleted-proposal": db.execute("DELETE FROM proposals")
                    else: db.execute("UPDATE evidence SET value='0.01' WHERE locator='line:4:Invoice Total'")
                    db.commit()
                finally: db.close()
                independent("detect_"+mutation,folder,"APPROVED",expected=False)
            checks["no_credentials_sent"]=double.authorizations==0
            (out/"double-requests.jsonl").write_text("".join(json.dumps(r)+"\n" for r in double.requests),encoding="utf-8")
        cleanup=True
    except (AssertionError,ValueError,KeyError,OSError,sqlite3.Error,subprocess.TimeoutExpired,RuntimeError):
        error="Bounded U1 acceptance stopped; inspect first preserved command/control receipt"
    report={"passed":error is None and all(checks.values()),"checks":checks,"assertions":len(checks),
            "error":error,"wall_seconds":time.monotonic()-started,"mode":"local-double","live_calls":0,
            "credential_accessed":False,"owned_server_cleanup_complete":cleanup,"automatic_retries":0,
            "scope":"One exposed authored journey with negative controls; no model quality, external sandbox or unseen score."}
    (out/"report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report));return 0 if report["passed"] else 1


if __name__=="__main__": raise SystemExit(main())
