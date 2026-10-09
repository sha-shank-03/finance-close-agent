"""Final CLI/state acceptance after separately authorized frozen evaluation."""

import hashlib
import json
import re
from pathlib import Path

from .baseline import exact_reference
from .freeze import check_freeze
from .metrics import canonical_domain
from .report import build_report
from .run import source_hashes
from .scoring import breakdown, outcome_differences, score_outcomes
from .verify import verify

ROOT = Path(__file__).resolve().parent.parent


def source_checks():
    required = ["README.md", "EVIDENCE.md", "CONTRIBUTING.md", "LICENSE", "DATA_LICENSE.md", "THIRD_PARTY_NOTICES.md", "docs/architecture.md", "docs/input-contract.md", "docs/evaluation.md", "docs/ci.md", "docs/limitations.md", "docs/sources.md", ".github/workflows/ci.yml", "pyproject.toml", ".gitignore"]
    checks = []
    def check(name, passed):
        checks.append({"assertion": name, "passed": bool(passed)})
    check("standalone documentation/license/config files present", all((ROOT / name).is_file() for name in required))
    paths = [ROOT / name for name in required] + sorted(ROOT.glob("finance_close/*.py")) + sorted(ROOT.glob("evaluation/*.py")) + sorted(ROOT.glob("tests/*.py"))
    private_path_pattern = r"[A-Za-z]:[\\/](?:Users|Documents)|/" + "Users" + "/|/" + "home" + "/"
    check("shipped source has no personal absolute path", all(not re.search(private_path_pattern, path.read_text(encoding="utf-8")) for path in paths if path.is_file()))
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    uses = re.findall(r"uses:\s*(\S+)", ci)
    check("CI actions pinned to reviewed immutable commits", uses == ["actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"])
    check("CI selected runtime and read-only permission", "python-version: '3.11.9'" in ci and "contents: read" in ci and "secrets." not in ci)
    check("CI invokes the same offline final harness", "python -m evaluation.ci" in ci and "--allow-heldout" in ci)
    check("dependency-free source checkout entrypoint", "dependencies = []" in (ROOT / "pyproject.toml").read_text(encoding="utf-8") and (ROOT / "finance_close/__main__.py").is_file())
    data_notice = (ROOT / "DATA_LICENSE.md").read_text(encoding="utf-8")
    check("fictional held-out data attribution included", "evaluation/cases/" in data_notice and "MIT" in data_notice and "fictional" in data_notice)
    limitations = (ROOT / "docs/limitations.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs/architecture.md").read_text(encoding="utf-8")
    check("actual abrupt-child-exit scope and untested durability documented", "os._exit" in architecture and "power-loss" in limitations and "fsync" in limitations)
    check("unexecuted live/hosted/production claims documented", all(word in limitations for word in ["live inference", "remote CI", "production", "unposted"]))
    broken_links = []
    for path in paths:
        if not path.is_file() or path.suffix != ".md":
            continue
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            target = target.split("#", 1)[0]
            if target and not (path.parent / target).is_file():
                broken_links.append({"file": path.relative_to(ROOT).as_posix(), "target": target})
    check("local documentation links resolve", not broken_links)
    return {"passed": all(item["passed"] for item in checks), "checks": checks, "broken_links": broken_links, "note": "Source inspection only; no remote CI execution, visual render or power-loss test is implied."}


def accept(out, evaluation_run):
    out, evaluation_run = Path(out).resolve(), Path(evaluation_run).resolve()
    if out.exists():
        raise ValueError("Use a fresh M3 acceptance output directory")
    out.mkdir(parents=True)
    checks, rechecks = [], []
    def check(name, actual, wanted):
        checks.append({"assertion": name, "actual": actual, "expected": wanted, "passed": actual == wanted})
        if actual != wanted:
            raise AssertionError(name)
    try:
        frozen = check_freeze()
        check("frozen corpus integrity", frozen["passed"], True)
        original = json.loads((evaluation_run / "evaluation.json").read_text(encoding="utf-8"))
        check("strict frozen evaluation passed", original["passed"], True)
        check("independent examples, not repeated sample count", original["independent_case_count"], 32)
        check("three repetitions", original["repetitions"], 3)
        check("96 attempted outcomes", original["attempted_case_count"], 96)
        check("held-out split", original["split"], "heldout")
        policy_bytes = (ROOT / "evaluation/release-gates.json").read_bytes()
        policy = json.loads(policy_bytes)
        check("unchanged predeclared gate policy", original["release_policy_sha256"], hashlib.sha256(policy_bytes).hexdigest())
        check("acting policy unchanged during evaluation", original["acting_policy_unchanged_during_evaluation"], True)
        check("same acting source at final review", original["actor_source_sha256_after"], source_hashes())
        manifest = json.loads((ROOT / "evaluation/heldout-freeze.json").read_text(encoding="utf-8"))
        wanted = {(item["case_id"], number) for item in manifest["records"] for number in [1, 2, 3]}
        check("all unique frozen case/repetition identities", {(item["case_id"], item["repetition"]) for item in original["cases"]}, wanted)
        check("no duplicate case/repetition rows", len(original["cases"]), len(wanted))
        refreshed = []
        for entry in original["cases"]:
            run = evaluation_run / ("repeat-" + str(entry["repetition"])) / entry["case_id"]
            labels_path = ROOT / "evaluation/labels/heldout" / (entry["case_id"] + ".json")
            labels = json.loads(labels_path.read_text(encoding="utf-8"))
            packet = json.loads((run / "packet.json").read_text(encoding="utf-8"))
            independent = verify(run, labels_path)
            domain = canonical_domain(packet)
            check("case still independently verifies: " + entry["case_id"] + "/" + str(entry["repetition"]), independent["passed"], True)
            check("case canonical state unchanged", domain["sha256"], entry["domain_sha256"])
            baseline = exact_reference(ROOT / "evaluation/cases/heldout" / entry["case_id"])
            item = {**entry, "audit": independent["audit"], "actor": score_outcomes(packet, labels), "baseline": score_outcomes(baseline, labels), "holds_by_reason": breakdown(packet, labels, "holds"), "proposals_by_rule": breakdown(packet, labels, "proposals"), "baseline_holds_by_reason": breakdown(baseline, labels, "holds"), "baseline_proposals_by_rule": breakdown(baseline, labels, "proposals"), "outcome_differences": outcome_differences(packet, labels), "passed": independent["passed"]}
            refreshed.append(item)
            rechecks.append({"case_id": entry["case_id"], "repetition": entry["repetition"], "assertions": independent["assertions"], "failure_count": independent["failure_count"], "audit": independent["audit"]})
        recomputed = build_report(refreshed, "heldout", 3, frozen, policy)
        check("recomputed release gates", recomputed["release_gates"]["passed"], True)
        for key in ["actor", "baseline", "audit", "verified_case_success", "per_repetition", "per_stratum", "consistency"]:
            check("report agrees with final raw states: " + key, recomputed[key], original[key])
        docs = source_checks()
        check("standalone source/documentation checks", docs["passed"], True)
        from .acceptance import accept as accept_m1
        from .m2_acceptance import accept as accept_m2
        m1 = accept_m1(out / "m1-regression")
        check("final M1 public CLI regression", m1["passed"], True)
        m2 = accept_m2(out / "m2-regression")
        check("final M2 public CLI safety/recovery/protocol regression", m2["passed"], True)
        check("frozen corpus unchanged after final acceptance", check_freeze()["passed"], True)
        report = {"passed": True, "milestone": 3, "checks": checks, "rechecked_cases": rechecks, "source_checks": docs, "nested_m1_cli_calls": len(m1["commands"]), "nested_m2_cli_calls": len(m2["commands"]), "evaluation": {key: original[key] for key in ["evidence_phase", "actor", "baseline", "audit", "first_failure", "release_gates", "consistency"]}, "unexecuted": ["remote CI", "live inference", "professional accounting validation", "power-loss/fsync durability", "production accounts/posting", "publication"]}
    except (AssertionError, ValueError, OSError, KeyError, TypeError) as exc:
        report = {"passed": False, "milestone": 3, "error": str(exc), "type": type(exc).__name__, "checks": checks, "first_failed_check": next((item for item in checks if not item["passed"]), None), "rechecked_cases": rechecks}
    (out / "acceptance.json").write_text(json.dumps(report, indent=2, default=lambda value: sorted(value) if isinstance(value, set) else str(value)) + "\n", encoding="utf-8")
    return report
