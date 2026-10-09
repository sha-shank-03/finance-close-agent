"""Pure reporting helpers; explicit denominators and canonical final-state fingerprints."""

import hashlib
import json


def rate(numerator, denominator):
    if type(numerator) is not int or type(denominator) is not int or numerator < 0 or denominator < 0 or numerator > denominator:
        raise ValueError("Rate counts must be nonnegative integers with numerator <= denominator")
    return {"numerator": numerator, "denominator": denominator, "value": numerator / denominator if denominator else None, "zero_denominator": "not applicable" if denominator == 0 else None}


def canonical_domain(packet):
    """Exclude timestamps, elapsed time and provider endpoint/trace noise, retain domain facts."""
    def ordered(items):
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    value = {"snapshot_version": packet["snapshot_version"], "rule_hash": packet["rule_hash"], "run_state": packet["run_state"], "totals": packet["totals"], "bank_records": ordered(packet["bank_records"]), "exceptions": ordered(packet["exceptions"]), "proposals": ordered(packet["proposals"]), "ap_balances": ordered(packet.get("ap_balances", [])), "sources": ordered(packet["sources"]), "ledger_posting_supported": packet["ledger_posting_supported"]}
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "domain": value}


def combine_audits(audits):
    rates = ["balanced_entries", "validated_proposals", "required_provenance_relations", "extracted_source_fields"]
    result = {key: rate(sum(item[key]["numerator"] for item in audits), sum(item[key]["denominator"] for item in audits)) for key in rates}
    result.update({"audited_cases": len(audits), "unknown_provenance_scopes": sum(item["unknown_provenance_scopes"] for item in audits), "forbidden_actions_committed": sum(item["forbidden_actions_committed"] for item in audits), "duplicate_domain_effects": sum(item["duplicate_domain_effects"] for item in audits), "all_safety_invariants_pass": bool(audits) and all(item["safety_invariants_pass"] for item in audits)})
    return result


def first_failure(cases):
    return next(({"case_id": item["case_id"], "repetition": item["repetition"], "first_failed_assertion": item.get("first_failed_assertion"), "error": item.get("error"), "baseline_error": item.get("baseline_error"), "outcome_differences": item.get("outcome_differences")} for item in cases if not item["passed"]), None)
