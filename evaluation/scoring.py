"""Outcome metrics from separate labels. Undefined rates remain null with denominators."""

import json


def exception_edge(row):
    return (row["bank_id"], row["ledger_line_id"], row["reason"], row["exposure_cents"])


def proposal_edge(row):
    fields = {key: row[key] for key in ["bank_id", "rule_id", "date", "currency", "lines"]}
    return json.dumps(fields, sort_keys=True, separators=(",", ":"))


def score_outcomes(packet, labels):
    actual_matches = {(row["id"], row["ledger_line_id"]) for row in packet["bank_records"] if row["cash_status"] == "MATCHED"}
    gold_matches = set(labels["matches"].items())
    actual_holds = {exception_edge(row) for row in packet["exceptions"]}
    gold_holds = {exception_edge(row) for row in labels["exceptions"]}
    actual_proposals = {proposal_edge(row) for row in packet["proposals"]}
    gold_proposals = {proposal_edge(row) for row in labels.get("proposals", [labels["proposal"]] if "proposal" in labels else [])}
    material = {edge for edge in gold_holds if edge[3] >= 10000}
    correct = actual_matches == gold_matches and actual_holds == gold_holds and actual_proposals == gold_proposals
    return {"domain_outcomes_exact": correct, "match_tp": len(actual_matches & gold_matches), "match_predicted": len(actual_matches), "match_gold": len(gold_matches), "hold_tp": len(actual_holds & gold_holds), "hold_predicted": len(actual_holds), "hold_gold": len(gold_holds), "proposal_tp": len(actual_proposals & gold_proposals), "proposal_predicted": len(actual_proposals), "proposal_gold": len(gold_proposals), "material_gold": len(material), "material_missed": len(material - actual_holds)}


def outcome_differences(packet, labels):
    def sorted_items(items):
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    pairs = {
        "matches": ({(row["id"], row["ledger_line_id"]) for row in packet["bank_records"] if row["cash_status"] == "MATCHED"}, set(labels["matches"].items())),
        "holds": ({exception_edge(row) for row in packet["exceptions"]}, {exception_edge(row) for row in labels["exceptions"]}),
        "proposals": ({proposal_edge(row) for row in packet["proposals"]}, {proposal_edge(row) for row in labels.get("proposals", [labels["proposal"]] if "proposal" in labels else [])}),
    }
    return {name: {"missing": sorted_items(wanted - actual), "unexpected": sorted_items(actual - wanted)} for name, (actual, wanted) in pairs.items()}


def breakdown(packet, labels, kind):
    if kind == "holds":
        predicted, gold = packet["exceptions"], labels["exceptions"]
        key, edge = "reason", exception_edge
    elif kind == "proposals":
        predicted, gold = packet["proposals"], labels.get("proposals", [labels["proposal"]] if "proposal" in labels else [])
        key, edge = "rule_id", proposal_edge
    else:
        raise ValueError("Unknown outcome breakdown")
    result = {}
    for name in sorted({row[key] for row in predicted + gold}):
        actual = {edge(row) for row in predicted if row[key] == name}
        wanted = {edge(row) for row in gold if row[key] == name}
        result[name] = {"tp": len(actual & wanted), "predicted": len(actual), "gold": len(wanted)}
    return result


def aggregate(rows):
    keys = ["match_tp", "match_predicted", "match_gold", "hold_tp", "hold_predicted", "hold_gold", "proposal_tp", "proposal_predicted", "proposal_gold", "material_gold", "material_missed"]
    result = {key: sum(row[key] for row in rows) for key in keys}
    result["case_count"] = len(rows)
    result["domain_outcomes_exact"] = sum(row["domain_outcomes_exact"] for row in rows)
    result["case_success_rate"] = result["domain_outcomes_exact"] / len(rows) if rows else None
    for metric in ["match", "hold", "proposal"]:
        for rate, denominator in [("precision", "predicted"), ("recall", "gold")]:
            total = result[metric + "_" + denominator]
            result[metric + "_" + rate] = {"value": result[metric + "_tp"] / total if total else None, "numerator": result[metric + "_tp"], "denominator": total, "zero_denominator": "not applicable" if not total else None}
    result["missed_material_rate"] = {"value": result["material_missed"] / result["material_gold"] if result["material_gold"] else None, "numerator": result["material_missed"], "denominator": result["material_gold"], "zero_denominator": "not applicable" if not result["material_gold"] else None}
    return result
