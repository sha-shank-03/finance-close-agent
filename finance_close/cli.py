"""Public CLI for the bounded M1 workflow."""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from .agent import investigate
from .domain import ForbiddenAction, IncompleteRun, InvalidInput
from .ingest import ROOT, parse_bundle
from .providers import OllamaProvider, ScriptedProvider
from .render import write_packet
from .review import review_proposal
from .store import Store


def run_bundle(source, out, provider=None, test_fault=None, test_cancel_after_tools=None):
    source, out = Path(source).resolve(), Path(out).resolve()
    if out.is_relative_to(source) or source.is_relative_to(out):
        raise InvalidInput("Output and input bundle directories must not overlap")
    bundle = parse_bundle(source)
    store = Store(out / "state.sqlite")
    provider = provider or ScriptedProvider()
    if test_cancel_after_tools is not None and (type(test_cancel_after_tools) is not int or not 0 <= test_cancel_after_tools <= 250):
        store.close()
        raise InvalidInput("Test cancellation count must be an integer from 0 to 250")
    def test_cancelled():
        return test_cancel_after_tools is not None and store.db.execute("SELECT COUNT(*) FROM events WHERE status='ok'").fetchone()[0] >= test_cancel_after_tools
    def crash_after_proposal(store, bank_id):
        if test_fault == "after-proposal-commit" and store.db.execute("SELECT 1 FROM proposals WHERE bank_id=?", (bank_id,)).fetchone():
            os._exit(85)
    def crash_before_rename():
        if test_fault == "before-packet-rename":
            os._exit(85)
    try:
        store.initialize(bundle)
        try:
            investigate(store, provider, cancelled=test_cancelled, after_tool_commit=crash_after_proposal)
        except (IncompleteRun, KeyboardInterrupt):
            write_packet(store, out)
            raise
        write_packet(store, out, before_rename=crash_before_rename)
        calls = int(store.meta("model_calls"))
    finally:
        store.close()
    return {"packet": str(out / "packet.html"), "json": str(out / "packet.json"), "database": str(out / "state.sqlite"), "provider": provider.mode, "model_calls": calls}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fictional bank reconciliation; scripted decisions; proposals remain unposted")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    for name in ["demo", "run"]:
        command = commands.add_parser(name)
        command.add_argument("--out", required=True)
        command.add_argument("--provider", choices=["scripted", "ollama"], default="scripted")
        command.add_argument("--model")
        command.add_argument("--endpoint", default="http://127.0.0.1:11434/api/chat")
        command.add_argument("--allow-local-model", action="store_true", help="Explicit opt-in to a separately installed local model; no download is performed")
        command.add_argument("--test-fault", choices=["after-proposal-commit", "before-packet-rename"], help="Integration-only fault injection; exits 85")
        command.add_argument("--test-cancel-after-tools", type=int, help="Integration-only cancellation injection; returns incomplete exit 3")
        if name == "run":
            command.add_argument("--input", required=True)
    command = commands.add_parser("report")
    command.add_argument("--run", required=True)
    command = commands.add_parser("review")
    command.add_argument("--run", required=True)
    for name in ["proposal-id", "expected-hash", "snapshot-version", "reviewer"]:
        command.add_argument("--" + name, required=True)
    command.add_argument("--decision", choices=["approve", "reject"], required=True)
    args = parser.parse_args(argv)
    try:
        if sys.version_info < (3, 11):
            raise InvalidInput("Python 3.11 or newer is required")
        if args.command == "doctor":
            print(json.dumps({"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version, "runtime_dependencies": [], "network": "none", "model_inference": "none"}))
        elif args.command in {"demo", "run"}:
            if args.provider == "ollama" and (not args.allow_local_model or not args.model):
                raise InvalidInput("Ollama requires --model and --allow-local-model; default is offline scripted")
            provider = OllamaProvider(args.model, args.endpoint) if args.provider == "ollama" else ScriptedProvider()
            print(json.dumps(run_bundle(ROOT / "fixtures" / "demo" if args.command == "demo" else args.input, args.out, provider, args.test_fault, args.test_cancel_after_tools)))
        else:
            out = Path(args.run).resolve()
            if not (out / "state.sqlite").is_file():
                raise InvalidInput("Run database does not exist")
            store = Store(out / "state.sqlite")
            try:
                if args.command == "review":
                    result = review_proposal(store, args.proposal_id, args.expected_hash, args.snapshot_version, args.decision, args.reviewer)
                    write_packet(store, out)
                    print(json.dumps(result))
                else:
                    value = write_packet(store, out)
                    print(json.dumps({"run_state": value["run_state"], "totals": value["totals"], "packet": str(out / "packet.html"), "posted": False}))
            finally:
                store.close()
        return 0
    except (InvalidInput, ForbiddenAction, ValueError) as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}), file=sys.stderr)
        return 2
    except (IncompleteRun, KeyboardInterrupt) as exc:
        print(json.dumps({"error": str(exc) or "Cancelled", "type": type(exc).__name__}), file=sys.stderr)
        return 3
    except (OSError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}), file=sys.stderr)
        return 4
