"""Owned loopback HTTP double. Requires an integration lease; not live inference."""

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from finance_close.cli import run_bundle
from finance_close.providers import OllamaProvider, ScriptedProvider

from .verify import verify

ROOT = Path(__file__).resolve().parent.parent


def accept_protocol(out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError("Use a fresh protocol output directory")
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if self.path != "/api/chat" or not 0 < size <= 65536:
                    self.send_error(400)
                    return
                request = json.loads(self.rfile.read(size))
                messages = request["messages"]
                first = messages[1]["content"]
                bank_id = first.split("bank_id=", 1)[1].split(";", 1)[0]
                snapshot = first.split("snapshot=", 1)[1]
                history, last = [], None
                for message in messages[2:]:
                    if message["role"] == "assistant":
                        function = message["tool_calls"][0]["function"]
                        last = {"tool": function["name"], "arguments": function["arguments"]}
                    elif message["role"] == "tool":
                        observation = json.loads(message["content"])
                        history.append({"decision": last, **observation})
                decision = ScriptedProvider().next_decision({"bank_id": bank_id, "snapshot_version": snapshot, "history": history})
                requests.append({"path": self.path, "bank_id": bank_id, "history_count": len(history), "request": request, "selected_tool": decision["tool"]})
                value = {"model": request["model"], "done": True, "message": {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": decision["tool"], "arguments": decision["arguments"]}}]}, "prompt_eval_count": len(messages), "eval_count": 1}
                raw = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except (KeyError, ValueError, TypeError) as exc:
                self.send_error(400, str(exc))
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/api/chat"
        provider = OllamaProvider("local-protocol-double", endpoint=endpoint, protocol_double=True)
        run_bundle(ROOT / "fixtures/dev/D04", out, provider)
        independent = verify(out, ROOT / "evaluation/labels/dev/D04.json", provider_mode="ollama", provider_evidence="protocol_test_double")
        packet = json.loads((out / "packet.json").read_text(encoding="utf-8"))
        checks = {"independent_domain_verification": independent["passed"], "multiple_observation_rounds": any(item["history_count"] >= 4 for item in requests), "schema_and_nonstreaming_wire": all(item["request"]["stream"] is False and item["request"]["tools"] for item in requests), "zero_live_model_calls": packet["provider"]["model_calls"] == 0, "attempt_count_matches_owned_requests": packet["provider"]["inference_calls"] == len(requests), "proposals_unposted": len(packet["proposals"]) == 1 and packet["proposals"][0]["posted"] is False}
        report = {"passed": all(checks.values()), "checks": checks, "request_count": len(requests), "requests": requests, "independent_verification": independent, "evidence_type": "real loopback HTTP protocol double driven by scripted observations; no live-model quality evidence; token counts are synthetic"}
        (out / "protocol.json").write_text(json.dumps(report, indent=2, default=list) + "\n", encoding="utf-8")
        return report
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        report = accept_protocol(args.out)
        print(json.dumps({"passed": report["passed"], "request_count": report["request_count"], "checks": report["checks"]}))
        return 0 if report["passed"] else 1
    except (ValueError, OSError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
