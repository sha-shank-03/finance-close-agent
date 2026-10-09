"""Bounded M1 CLI integration acceptance; requires the assigned local lease."""

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def counts(run):
    with sqlite3.connect(run / "state.sqlite") as db:
        return {table: db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in ["bank", "ledger", "matches", "exceptions", "proposals", "proposal_lines", "proposal_evidence", "reviews", "events"]}


def accept(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    run = out / "demo"
    if run.exists():
        raise ValueError("Use a fresh acceptance output directory to preserve evidence")
    calls, checks = [], []

    def execute(arguments, wanted=0):
        command = [sys.executable, "-m", *arguments]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
        calls.append({"command": command, "exit_code": result.returncode, "expected_exit_code": wanted, "stdout": result.stdout, "stderr": result.stderr})
        if result.returncode != wanted:
            raise AssertionError(f"Command returned {result.returncode}, expected {wanted}: {arguments}")
        return result

    def check(name, actual, expected):
        checks.append({"assertion": name, "actual": actual, "expected": expected, "passed": actual == expected})
        if actual != expected:
            raise AssertionError(name)

    source_hashes = {path.relative_to(ROOT / "fixtures" / "demo").as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in (ROOT / "fixtures" / "demo").rglob("*") if path.is_file()}
    try:
        execute(["finance_close", "doctor"])
        execute(["finance_close", "demo", "--out", str(run), "--provider", "scripted"])
        execute(["evaluation.verify", "--run", str(run), "--labels", "evaluation/labels/demo.json"])
        before = counts(run)
        initial = json.loads((run / "packet.json").read_text(encoding="utf-8"))
        check("initial proposal pending", initial["proposals"][0]["review_state"], "PENDING")
        execute(["finance_close", "demo", "--out", str(run), "--provider", "scripted"])
        check("repeated run makes no duplicate effects", counts(run), before)
        item = initial["proposals"][0]
        review_args = ["finance_close", "review", "--run", str(run), "--proposal-id", item["id"], "--expected-hash", item["hash"], "--snapshot-version", initial["snapshot_version"], "--decision", "approve", "--reviewer", "demo-accountant"]
        execute(review_args)
        after_review = counts(run)
        execute(review_args)
        check("repeated exact review makes no duplicate effects", counts(run), after_review)
        conflicting = review_args.copy()
        conflicting[conflicting.index("approve")] = "reject"
        execute(conflicting, wanted=2)
        stale = review_args.copy()
        stale[stale.index(item["hash"])] = "0" * 64
        execute(stale, wanted=2)
        execute(["finance_close", "report", "--run", str(run)])
        execute(["evaluation.verify", "--run", str(run), "--labels", "evaluation/labels/demo.json"])
        final = json.loads((run / "packet.json").read_text(encoding="utf-8"))
        check("review remains unposted", final["proposals"][0]["posted"], False)
        check("approval leaves booked ledger unchanged", final["totals"]["ledger_closing_cents"], 875000)
        check("one review row", counts(run)["reviews"], 1)
        check("missing invoice still open after approval", final["bank_records"][1]["invoice_status"], "OPEN_HOLD")
        after_sources = {path.relative_to(ROOT / "fixtures" / "demo").as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in (ROOT / "fixtures" / "demo").rglob("*") if path.is_file()}
        check("original source files unchanged", after_sources, source_hashes)
        corrupt = out / "corrupt-proposal"
        shutil.copytree(run, corrupt)
        with sqlite3.connect(corrupt / "state.sqlite") as db:
            db.execute("UPDATE proposal_lines SET amount_cents=3001 WHERE number=0")
        execute(["evaluation.verify", "--run", str(corrupt), "--labels", "evaluation/labels/demo.json"], wanted=1)
        rejected_run = out / "rejected-demo"
        execute(["finance_close", "demo", "--out", str(rejected_run), "--provider", "scripted"])
        reject_args = review_args.copy()
        reject_args[reject_args.index(str(run))] = str(rejected_run)
        reject_args[reject_args.index("approve")] = "reject"
        execute(reject_args)
        rejected_counts = counts(rejected_run)
        execute(reject_args)
        check("repeated rejection makes no duplicate effects", counts(rejected_run), rejected_counts)
        execute(["evaluation.verify", "--run", str(rejected_run), "--labels", "evaluation/labels/demo.json"])
        rejected_packet = json.loads((rejected_run / "packet.json").read_text(encoding="utf-8"))
        check("pending proposal can be rejected", rejected_packet["proposals"][0]["review_state"], "REJECTED")
        check("rejected proposal remains unposted", rejected_packet["proposals"][0]["posted"], False)
        check("rejection leaves booked ledger unchanged", rejected_packet["totals"]["ledger_closing_cents"], 875000)
        check("rejected proposal contributes no proposed cash effect", rejected_packet["totals"]["proposed_cash_effect_cents"], 0)
        check("missing invoice still open after rejection", rejected_packet["bank_records"][1]["invoice_status"], "OPEN_HOLD")
        report = {"passed": True, "milestone": 1, "checks": checks, "commands": calls, "unexecuted": ["live model inference", "remote CI", "M2/M3", "real accounts or ledger posting"]}
    except (AssertionError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        report = {"passed": False, "milestone": 1, "error": str(exc), "checks": checks, "commands": calls}
    (out / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--milestone", type=int, choices=[1, 2, 3], required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--evaluation", help="Existing held-out three-repeat report required by M3")
    args = parser.parse_args(argv)
    try:
        if args.milestone == 3:
            if not args.evaluation:
                raise ValueError("M3 requires --evaluation pointing to the preserved three-repeat frozen evaluation")
            from .m3_acceptance import accept as accept_m3
            result = accept_m3(args.out, args.evaluation)
        elif args.milestone == 2:
            from .m2_acceptance import accept as accept_m2
            result = accept_m2(args.out)
        else:
            result = accept(args.out)
        print(json.dumps({"passed": result["passed"], "report": str(Path(args.out) / "acceptance.json")}))
        return 0 if result["passed"] else 1
    except (ValueError, OSError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
