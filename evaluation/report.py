"""Pure aggregation of independent case results; no fixture reads or actor execution."""

from .metrics import combine_audits, first_failure, rate
from .release import check_gates
from .scoring import aggregate


def merged_breakdown(cases, field):
    names = sorted({name for case in cases for name in case.get(field, {})})
    result = {}
    for name in names:
        values = {key: sum(case.get(field, {}).get(name, {}).get(key, 0) for case in cases) for key in ["tp", "predicted", "gold"]}
        result[name] = {**values, "precision": rate(values["tp"], values["predicted"]), "recall": rate(values["tp"], values["gold"])}
    return result


def summarize(cases):
    return {"case_count": len(cases), "execution_errors": sum("error" in item for item in cases), "baseline_execution_errors": sum("baseline_error" in item for item in cases), "actor": aggregate([item["actor"] for item in cases]), "baseline": aggregate([item["baseline"] for item in cases]), "verified_case_success": rate(sum(item["passed"] for item in cases), len(cases)), "all_case_checks_passed": bool(cases) and all(item["passed"] for item in cases), "audit": combine_audits([item["audit"] for item in cases if item.get("audit")]), "holds_by_reason": merged_breakdown(cases, "holds_by_reason"), "proposals_by_rule": merged_breakdown(cases, "proposals_by_rule"), "baseline_holds_by_reason": merged_breakdown(cases, "baseline_holds_by_reason"), "baseline_proposals_by_rule": merged_breakdown(cases, "baseline_proposals_by_rule")}


def consistency_report(cases, independent_case_count, repeats):
    ids = sorted({item["case_id"] for item in cases})
    failures = []
    for case_id in ids:
        rows = [item for item in cases if item["case_id"] == case_id]
        hashes = [row.get("domain_sha256") for row in rows]
        numbers = [row["repetition"] for row in rows]
        if len(rows) != repeats or sorted(numbers) != list(range(1, repeats + 1)) or any(value is None for value in hashes) or len(set(hashes)) != 1:
            failures.append({"case_id": case_id, "repetition_count": len(rows), "repetition_numbers": numbers, "domain_sha256": hashes})
    return {"passed": len(ids) == independent_case_count and not failures, "independent_case_count": len(ids), "expected_independent_case_count": independent_case_count, "repetitions": repeats, "failures": failures, "note": "Identical scripted domain results establish reproducibility; repeats are not independent examples or live-model variance."}


def build_report(cases, split, repeats, frozen, policy):
    count = 32 if split == "heldout" else 12
    result = summarize(cases)
    result.update({"split": split, "expected_case_count": count * repeats, "attempted_case_count": len(cases), "independent_case_count": count, "repetitions": repeats, "scored_case_count": sum(item.get("actor_packet_scored", "error" not in item) for item in cases), "first_failure": first_failure(cases), "failed_cases": [{"case_id": item["case_id"], "repetition": item["repetition"], "first_failed_assertion": item.get("first_failed_assertion"), "error": item.get("error"), "baseline_error": item.get("baseline_error"), "outcome_differences": item.get("outcome_differences")} for item in cases if not item["passed"]], "cases": cases, "frozen_integrity": frozen})
    groups = [{"repetition": number, **summarize([item for item in cases if item["repetition"] == number])} for number in range(1, repeats + 1)]
    result["per_repetition"] = groups
    result["per_stratum"] = {name: summarize([item for item in cases if item["stratum"] == name]) for name in sorted({item["stratum"] for item in cases})}
    result["consistency"] = consistency_report(cases, count, repeats)
    result["release_gates"] = check_gates(groups, result["consistency"], policy) if split == "heldout" else {"passed": None, "checks": [], "note": "Held-out release gates are not evaluated on development cases."}
    result["passed"] = len(cases) == count * repeats and result["all_case_checks_passed"] and result["baseline_execution_errors"] == 0 and result["consistency"]["passed"] and (split != "heldout" or result["release_gates"]["passed"])
    return result
