"""Sequential scripted evaluation with raw failures, fixed baseline and independent checks."""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from .baseline import exact_reference
from .freeze import check_freeze
from .metrics import canonical_domain
from .report import build_report
from .scoring import breakdown, outcome_differences, score_outcomes
from .verify import verify

ROOT = Path(__file__).resolve().parent.parent
EMPTY = {"bank_records": [], "exceptions": [], "proposals": []}


def source_hashes():
    paths = sorted([*ROOT.glob("finance_close/*.py"), *ROOT.glob("rules/*.json")])
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def evaluate(split, out, allow_heldout=False, repeat=1, evidence_phase="first-frozen-pass"):
    if split not in {"dev", "heldout"} or type(repeat) is not int or repeat not in {1, 2, 3}:
        raise ValueError("Unsupported split or repeat count")
    if split == "heldout" and not allow_heldout:
        raise ValueError("Held-out evaluation requires separate authorization and --allow-heldout")
    frozen = check_freeze()
    manifest = json.loads((ROOT / "evaluation/heldout-freeze.json").read_text(encoding="utf-8"))
    strata = {item["case_id"]: item["stratum"] for item in manifest["records"]}
    source_dir = ROOT / ("fixtures/dev" if split == "dev" else "evaluation/cases/heldout")
    label_dir = ROOT / "evaluation/labels" / split
    out = Path(out).resolve()
    protected = [ROOT / "fixtures", ROOT / "evaluation/cases", ROOT / "evaluation/labels"]
    if out.exists() or any(out.is_relative_to(path) or path.is_relative_to(out) for path in protected):
        raise ValueError("Use a fresh output directory outside all fixture and label trees")
    out.mkdir(parents=True)
    policy_bytes = (ROOT / "evaluation/release-gates.json").read_bytes()
    policy = json.loads(policy_bytes)
    actor_before = source_hashes()
    started = time.monotonic()
    cases = []
    for repetition, source in [(number, source) for number in range(1, repeat + 1) for source in sorted(source_dir.iterdir()) if source.is_dir()]:
        run = out / source.name if repeat == 1 else out / ("repeat-" + str(repetition)) / source.name
        run.mkdir(parents=True)
        labels = json.loads((label_dir / (source.name + ".json")).read_text(encoding="utf-8"))
        entry = {"case_id": source.name, "repetition": repetition, "stratum": strata[source.name] if split == "heldout" else labels["feature"], "passed": False, "actor": score_outcomes(EMPTY, labels), "actor_packet_scored": False, "baseline": score_outcomes(EMPTY, labels), "audit": None, "domain_sha256": None, "holds_by_reason": breakdown(EMPTY, labels, "holds"), "proposals_by_rule": breakdown(EMPTY, labels, "proposals"), "outcome_differences": outcome_differences(EMPTY, labels)}
        baseline = EMPTY
        try:
            baseline = exact_reference(source)
            entry["baseline"] = score_outcomes(baseline, labels)
            (run / "baseline.json").write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            entry["baseline_error"] = {"type": type(exc).__name__, "message": str(exc)}
        command = [sys.executable, "-m", "finance_close", "run", "--input", str(source), "--out", str(run), "--provider", "scripted"]
        entry["actor_command"] = command
        case_started = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
            entry["actor_exit_code"] = completed.returncode
            (run / "actor.stdout.txt").write_text(completed.stdout, encoding="utf-8")
            (run / "actor.stderr.txt").write_text(completed.stderr, encoding="utf-8")
            if completed.returncode != 0:
                entry["error"] = {"type": "ActorExit", "message": "Actor returned " + str(completed.returncode), "stderr": completed.stderr}
            if (run / "packet.json").is_file():
                packet = json.loads((run / "packet.json").read_text(encoding="utf-8"))
                entry["actor"] = score_outcomes(packet, labels)
                entry["actor_packet_scored"] = True
                independent = verify(run, label_dir / (source.name + ".json"))
                (run / "verification.json").write_text(json.dumps(independent, indent=2, default=list) + "\n", encoding="utf-8")
                domain = canonical_domain(packet)
                (run / "canonical-domain.json").write_text(json.dumps(domain, indent=2) + "\n", encoding="utf-8")
                entry.update({"passed": completed.returncode == 0 and independent["passed"] and entry["actor"]["domain_outcomes_exact"] and "baseline_error" not in entry, "verification_assertions": independent["assertions"], "verification_failures": independent["failure_count"], "first_failed_assertion": independent["first_failed_assertion"], "audit": independent["audit"], "domain_sha256": domain["sha256"], "outcome_differences": outcome_differences(packet, labels), "holds_by_reason": breakdown(packet, labels, "holds"), "proposals_by_rule": breakdown(packet, labels, "proposals"), "decisions": packet["provider"]["decision_count"], "model_calls": packet["provider"]["model_calls"]})
            else:
                entry.setdefault("error", {"type": "MissingPacket", "message": "Actor did not produce packet.json"})
        except subprocess.TimeoutExpired as exc:
            entry["error"] = {"type": type(exc).__name__, "message": str(exc)}
            entry["actor_exit_code"] = 124
            entry["passed"] = False
            for name, data in [("actor.stdout.timeout.bin", exc.stdout), ("actor.stderr.timeout.bin", exc.stderr)]:
                (run / name).write_bytes(data.encode("utf-8") if type(data) is str else data or b"")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            entry["error"] = {"type": type(exc).__name__, "message": str(exc)}
            entry["passed"] = False
        entry.update({"elapsed_seconds": time.monotonic() - case_started, "baseline_holds_by_reason": breakdown(baseline, labels, "holds"), "baseline_proposals_by_rule": breakdown(baseline, labels, "proposals")})
        cases.append(entry)
        # Preserve the first failure and all prior cases even if the evaluator is interrupted.
        (out / "case-results.json").write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    report = build_report(cases, split, repeat, frozen, policy)
    actor_after = source_hashes()
    report.update({"elapsed_seconds": time.monotonic() - started, "evidence_phase": evidence_phase, "actor_source_sha256_before": actor_before, "actor_source_sha256_after": actor_after, "acting_policy_unchanged_during_evaluation": actor_before == actor_after, "release_policy": policy, "release_policy_sha256": hashlib.sha256(policy_bytes).hexdigest(), "baseline_source_sha256": hashlib.sha256((ROOT / "evaluation/baseline.py").read_bytes()).hexdigest(), "evidence_type": "authored synthetic scripted outcomes; repeats establish reproducibility, not independent samples or live-model quality", "unexecuted": ["live model quality", "professional accounting validation", "power-loss durability", "remote CI", "real accounts or posting"]})
    report["passed"] = report["passed"] and actor_before == actor_after and check_freeze()["passed"]
    (out / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["dev", "heldout"], required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--provider", choices=["scripted"], default="scripted")
    parser.add_argument("--baseline", choices=["exact-reference"], default="exact-reference")
    parser.add_argument("--allow-heldout", action="store_true")
    parser.add_argument("--repeat", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument("--evidence-phase", choices=["first-frozen-pass", "frozen-policy-reproduction", "regression-after-exposure", "public-ci-reproduction"], default="first-frozen-pass")
    args = parser.parse_args(argv)
    try:
        result = evaluate(args.split, args.out, args.allow_heldout, args.repeat, args.evidence_phase)
        print(json.dumps({key: result[key] for key in ["passed", "split", "independent_case_count", "repetitions", "attempted_case_count", "execution_errors", "actor", "baseline", "audit", "first_failure"]}))
        return 0 if result["passed"] else 1
    except (ValueError, OSError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
