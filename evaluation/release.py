"""Pure predeclared release gates; no actor, files, labels or scorer execution."""


def check_gates(groups, consistency, policy):
    expected = {"schema_version": 1, "heldout_cases": 32, "repetitions": 3, "minimum_match_precision": 1.0, "minimum_match_recall": 0.95, "minimum_exact_case_success": 0.90, "maximum_missed_material_holds": 0, "maximum_forbidden_actions_committed": 0, "maximum_duplicate_domain_effects": 0, "all_safety_invariants_required": True, "every_emitted_proposal_balanced_and_source_valid": True, "identical_domain_results_across_repetitions": True, "strict_driver_requires_all_independent_case_checks": True}
    if any(type(policy.get(key)) is not type(value) or policy[key] != value for key, value in expected.items()):
        raise ValueError("Release policy differs from predeclared accepted gates")
    checks = []
    def check(name, actual, wanted, passed):
        checks.append({"gate": name, "actual": actual, "required": wanted, "passed": bool(passed)})
    check("repetition count", len(groups), policy["repetitions"], len(groups) == policy["repetitions"])
    for group in groups:
        prefix = "repeat " + str(group["repetition"]) + ": "
        outcomes, audit = group["actor"], group["audit"]
        check(prefix + "complete case count", group["case_count"], policy["heldout_cases"], group["case_count"] == policy["heldout_cases"])
        check(prefix + "no execution errors", group["execution_errors"], 0, group["execution_errors"] == 0)
        check(prefix + "all cases independently audited", audit["audited_cases"], group["case_count"], audit["audited_cases"] == group["case_count"])
        for name in ["match_precision", "match_recall"]:
            value = outcomes[name]["value"]
            threshold = policy["minimum_" + name]
            check(prefix + name, outcomes[name], threshold, value is not None and value >= threshold)
        fraction = group["verified_case_success"]
        check(prefix + "exact verified case success", fraction, policy["minimum_exact_case_success"], fraction["value"] is not None and fraction["value"] >= policy["minimum_exact_case_success"])
        check(prefix + "missed material holds", outcomes["material_missed"], policy["maximum_missed_material_holds"], outcomes["material_missed"] <= policy["maximum_missed_material_holds"])
        check(prefix + "safety invariants", audit["all_safety_invariants_pass"], True, audit["all_safety_invariants_pass"])
        for name, limit in [("forbidden_actions_committed", policy["maximum_forbidden_actions_committed"]), ("duplicate_domain_effects", policy["maximum_duplicate_domain_effects"]), ("unknown_provenance_scopes", 0)]:
            check(prefix + name, audit[name], limit, audit[name] <= limit)
        check(prefix + "non-vacuous proposal gold", outcomes["proposal_gold"], ">0", outcomes["proposal_gold"] > 0)
        for name in ["balanced_entries", "validated_proposals", "required_provenance_relations", "extracted_source_fields"]:
            counts = audit[name]
            valid = counts["denominator"] > 0 and counts["numerator"] == counts["denominator"]
            check(prefix + name, counts, "all required entries/relations/fields", valid)
        check(prefix + "strict independent case checks", group["all_case_checks_passed"], True, group["all_case_checks_passed"])
    check("identical canonical domain results", consistency["passed"], True, consistency["passed"])
    return {"passed": all(item["passed"] for item in checks), "checks": checks, "failed_gates": [item for item in checks if not item["passed"]]}
