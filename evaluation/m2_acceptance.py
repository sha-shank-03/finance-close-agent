"""M2 leased integration: public CLI recovery, review, protocol and negative controls."""

import json
import shutil
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from .freeze import check_freeze

ROOT = Path(__file__).resolve().parent.parent


def counts(run):
    with sqlite3.connect(run / "state.sqlite") as db:
        return {table: db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in ["bank", "ledger", "matches", "exceptions", "proposals", "proposal_lines", "proposal_evidence", "reservations", "reviews", "events", "provider_attempts"]}


def accept(out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError("Use a fresh M2 acceptance directory")
    out.mkdir(parents=True)
    commands, checks = [], []
    def execute(arguments, wanted=0):
        command = [sys.executable, "-m", *arguments]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
        commands.append({"command": command, "exit_code": completed.returncode, "expected_exit_code": wanted, "stdout": completed.stdout, "stderr": completed.stderr})
        if completed.returncode != wanted:
            raise AssertionError("Unexpected command exit: " + str(arguments))
        return completed
    def check(name, actual, wanted=True):
        checks.append({"assertion": name, "actual": actual, "expected": wanted, "passed": actual == wanted})
        if actual != wanted:
            raise AssertionError(name)
    source = ROOT / "fixtures/dev/D04"
    labels = "evaluation/labels/dev/D04.json"
    def run_args(run):
        return ["finance_close", "run", "--input", str(source), "--out", str(run), "--provider", "scripted"]
    def verify_args(run):
        return ["evaluation.verify", "--run", str(run), "--labels", labels]
    try:
        check("frozen held-out integrity without scoring", check_freeze()["passed"])
        run = out / "ap"
        execute(run_args(run))
        execute(verify_args(run))
        initial = json.loads((run / "packet.json").read_text(encoding="utf-8"))
        original_counts = counts(run)
        execute(run_args(run))
        check("completed repeat does not repeat domain effects or calls", counts(run), original_counts)
        proposal = initial["proposals"][0]
        args = ["finance_close", "review", "--run", str(run), "--proposal-id", proposal["id"], "--expected-hash", proposal["hash"], "--snapshot-version", initial["snapshot_version"], "--decision", "approve", "--reviewer", "synthetic-reviewer"]
        stale = args.copy()
        stale[stale.index(proposal["hash"])] = "0" * 64
        execute(stale, 2)
        execute(args)
        reviewed_counts = counts(run)
        execute(args)
        check("repeat AP approval has no duplicate effects", counts(run), reviewed_counts)
        execute(verify_args(run))
        approved = json.loads((run / "packet.json").read_text(encoding="utf-8"))
        check("approved AP remains unposted", approved["proposals"][0]["posted"], False)
        check("approval preserves actual booked cash", approved["totals"]["ledger_closing_cents"], initial["totals"]["ledger_closing_cents"])
        check("approval keeps AP reservation", approved["ap_balances"][0]["reserved_cents"], 100000)
        reject_run = out / "reject-ap"
        execute(run_args(reject_run))
        reject = args.copy()
        reject[reject.index(str(run))] = str(reject_run)
        reject[reject.index("approve")] = "reject"
        execute(reject)
        reject_counts = counts(reject_run)
        execute(reject)
        check("repeat AP rejection has no duplicate effects", counts(reject_run), reject_counts)
        execute(verify_args(reject_run))
        rejected = json.loads((reject_run / "packet.json").read_text(encoding="utf-8"))
        check("rejection releases active reservation", rejected["ap_balances"][0]["reserved_cents"], 0)
        check("rejection preserves reservation audit", reject_counts["reservations"], 1)
        check("rejection preserves booked AP", rejected["ap_balances"][0]["booked_balance_cents"], 100000)
        for conflicting in [False, True]:
            race_run = out / ("conflicting-review-race" if conflicting else "identical-review-race")
            execute(run_args(race_run))
            first_args = args.copy()
            first_args[first_args.index(str(run))] = str(race_run)
            second_args = first_args.copy()
            if conflicting:
                second_args[second_args.index("approve")] = "reject"
            children = []
            try:
                for review_args in [first_args, second_args]:
                    command = [sys.executable, "-m", *review_args]
                    children.append((command, subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)))
                exits = []
                for command, child in children:
                    stdout, stderr = child.communicate(timeout=15)
                    exits.append(child.returncode)
                    commands.append({"command": command, "exit_code": child.returncode, "expected_exit_code": "one 0/one 2" if conflicting else 0, "stdout": stdout, "stderr": stderr})
            finally:
                for _, child in children:
                    if child.poll() is None:
                        child.kill()  # Only this harness's owned child.
                        child.communicate(timeout=5)
            check("serialized concurrent review exits: " + str(conflicting), sorted(exits), [0, 2] if conflicting else [0, 0])
            check("one committed concurrent review: " + str(conflicting), counts(race_run)["reviews"], 1)
            execute(verify_args(race_run))
        cancelled_run = out / "cancel-resume"
        execute(run_args(cancelled_run) + ["--test-cancel-after-tools", "1"], 3)
        cancelled_packet = json.loads((cancelled_run / "packet.json").read_text(encoding="utf-8"))
        check("cancelled packet remains explicitly incomplete", cancelled_packet["run_state"], "CANCELLED")
        check("cancellation covers all unresolved bank residuals", sum(item["reason"] == "UNMATCHED_CASH" for item in cancelled_packet["exceptions"]), 2)
        execute(run_args(cancelled_run))
        execute(verify_args(cancelled_run))
        check("cancellation resume preserves one proposal", counts(cancelled_run)["proposals"], 1)
        for fault in ["after-proposal-commit", "before-packet-rename"]:
            interrupted = out / fault
            execute(run_args(interrupted) + ["--test-fault", fault], 85)
            check("durable single proposal at " + fault, counts(interrupted)["proposals"], 1)
            execute(run_args(interrupted))
            execute(verify_args(interrupted))
            check("recovery equals uninterrupted domain state: " + fault, {key: counts(interrupted)[key] for key in original_counts if key not in {"events", "provider_attempts"}}, {key: original_counts[key] for key in original_counts if key not in {"events", "provider_attempts"}})
            recovered = json.loads((interrupted / "packet.json").read_text(encoding="utf-8"))
            check("recovered same full proposal hash: " + fault, recovered["proposals"][0]["hash"], proposal["hash"])
        changed_input = out / "changed-input"
        shutil.copytree(source, changed_input)
        changed_run = out / "stale-source"
        execute(["finance_close", "run", "--input", str(changed_input), "--out", str(changed_run), "--provider", "scripted"])
        bank_csv = changed_input / "bank.csv"
        bank_csv.write_bytes(bank_csv.read_bytes() + b"\n")
        changed_review = args.copy()
        changed_review[changed_review.index(str(run))] = str(changed_run)
        execute(changed_review, 2)
        check("source change writes no review", counts(changed_run)["reviews"], 0)
        # Each mutation is made to a fresh copy. The source run and labels remain intact.
        mutations = {
            "proposal-amount": "UPDATE proposal_lines SET amount_cents=amount_cents+1 WHERE number=0",
            "missing-proposal": "DELETE FROM proposals",
            "wrong-match": "UPDATE matches SET bank_id='B-D04'",
            "reservation-overcommit": "UPDATE reservations SET amount_cents=100001",
            "missing-evidence": "DELETE FROM proposal_evidence WHERE rowid=(SELECT MIN(rowid) FROM proposal_evidence)",
            "other-source-evidence": "UPDATE proposal_evidence SET evidence_id=(SELECT id FROM evidence WHERE source_path='bank.csv' AND value='A-D04' LIMIT 1) WHERE rowid=(SELECT MIN(rowid) FROM proposal_evidence)",
        }
        for name, sql in mutations.items():
            corrupt = out / ("negative-" + name)
            shutil.copytree(run, corrupt)
            with sqlite3.connect(corrupt / "state.sqlite") as db:
                db.execute(sql)
            result = execute(verify_args(corrupt), 1)
            failure = json.loads(result.stdout)
            check("independent verifier detects " + name, failure.get("failure_count", 0) > 0 or "error" in failure)
        missing_run = out / "missing-invoice"
        execute(["finance_close", "run", "--input", "fixtures/dev/D02", "--out", str(missing_run), "--provider", "scripted"])
        with sqlite3.connect(missing_run / "state.sqlite") as db:
            db.execute("DELETE FROM exceptions WHERE reason='MISSING_INVOICE'")
        execute(["evaluation.verify", "--run", str(missing_run), "--labels", "evaluation/labels/dev/D02.json"], 1)
        check("missing invoice negative control executed", True)
        # A full scripted run must not open a network socket. This is integration, not a unit.
        from finance_close.cli import run_bundle
        offline = out / "network-forbidden"
        with patch.object(socket, "socket", side_effect=AssertionError("Scripted mode opened a network socket")):
            run_bundle(source, offline)
        execute(verify_args(offline))
        check("scripted integration needs no network socket", True)
        execute(["evaluation.protocol", "--out", str(out / "protocol")])
        check("owned real HTTP protocol double passed", True)
        check("held-out corpus unchanged after all integration", check_freeze()["passed"])
        report = {"passed": True, "milestone": 2, "checks": checks, "commands": commands, "unexecuted": ["M3 held-out scoring", "live model inference", "remote CI", "real-account or posting operations"]}
    except (AssertionError, ValueError, OSError, KeyError, sqlite3.Error, subprocess.TimeoutExpired) as exc:
        report = {"passed": False, "milestone": 2, "error": str(exc), "checks": checks, "commands": commands}
    (out / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
