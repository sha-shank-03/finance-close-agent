"""One sequential offline CI-equivalent command plan, shared by hosted YAML and local runs."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def command_plan(out):
    out = Path(out)
    evaluation = out / "heldout"
    return [
        ["finance_close", "doctor"],
        ["evaluation.freeze"],
        ["unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
        ["finance_close", "demo", "--out", str(out / "demo"), "--provider", "scripted"],
        ["evaluation.verify", "--run", str(out / "demo"), "--labels", "evaluation/labels/demo.json"],
        ["evaluation.run", "--split", "heldout", "--repeat", "3", "--provider", "scripted", "--baseline", "exact-reference", "--allow-heldout", "--evidence-phase", "public-ci-reproduction", "--out", str(evaluation)],
        ["evaluation.acceptance", "--milestone", "3", "--evaluation", str(evaluation), "--out", str(out / "acceptance")],
    ]


def run_ci(out, allow_heldout=False):
    if not allow_heldout:
        raise ValueError("Final CI includes held-out scoring and requires explicit --allow-heldout authorization")
    out = Path(out).resolve()
    if out.exists():
        raise ValueError("Use a fresh CI-equivalent output directory")
    out.mkdir(parents=True)
    calls = []
    started = time.monotonic()
    passed = True
    for arguments in command_plan(out):
        command = [sys.executable, "-m", *arguments]
        begin = time.monotonic()
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
            call = {"command": command, "expected_exit_code": 0, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "elapsed_seconds": time.monotonic() - begin}
        except subprocess.TimeoutExpired as exc:
            call = {"command": command, "expected_exit_code": 0, "exit_code": 124, "stdout": (exc.stdout or b"").decode("utf-8", errors="replace") if type(exc.stdout) is bytes else exc.stdout or "", "stderr": (exc.stderr or b"").decode("utf-8", errors="replace") if type(exc.stderr) is bytes else exc.stderr or "", "elapsed_seconds": time.monotonic() - begin, "error": "Owned command exceeded timeout"}
        calls.append(call)
        passed = passed and call["exit_code"] == 0
        report = {"passed": passed, "completed_steps": len(calls), "expected_steps": 7, "commands": calls, "first_failed_command": next((item for item in calls if item["exit_code"] != 0), None), "elapsed_seconds": time.monotonic() - started, "evidence_type": "local offline CI-equivalent when run locally; hosted execution must be evidenced separately"}
        (out / "ci.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if not passed:
            break
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--allow-heldout", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_ci(args.out, args.allow_heldout)
        print(json.dumps({"passed": report["passed"], "completed_steps": report["completed_steps"], "expected_steps": report["expected_steps"], "first_failed_command": report["first_failed_command"]}))
        return 0 if report["passed"] and report["completed_steps"] == 7 else 1
    except (ValueError, OSError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
