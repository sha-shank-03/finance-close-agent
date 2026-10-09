"""Pure synthetic reporting/gate tests; no fixtures, actor, SQL, subprocess or HTTP execution."""

import copy
import json
import unittest

from evaluation.ci import command_plan
from evaluation.metrics import canonical_domain, rate
from evaluation.release import check_gates
from evaluation.report import build_report, consistency_report
from evaluation.scoring import breakdown, outcome_differences, score_outcomes


POLICY = {"schema_version": 1, "heldout_cases": 32, "repetitions": 3, "minimum_match_precision": 1.0, "minimum_match_recall": 0.95, "minimum_exact_case_success": 0.90, "maximum_missed_material_holds": 0, "maximum_forbidden_actions_committed": 0, "maximum_duplicate_domain_effects": 0, "all_safety_invariants_required": True, "every_emitted_proposal_balanced_and_source_valid": True, "identical_domain_results_across_repetitions": True, "strict_driver_requires_all_independent_case_checks": True}


def synthetic_cases():
    outcome = {"domain_outcomes_exact": True, "match_tp": 1, "match_predicted": 1, "match_gold": 1, "hold_tp": 1, "hold_predicted": 1, "hold_gold": 1, "proposal_tp": 1, "proposal_predicted": 1, "proposal_gold": 1, "material_gold": 1, "material_missed": 0}
    audit = {"balanced_entries": rate(1, 1), "validated_proposals": rate(1, 1), "required_provenance_relations": rate(5, 5), "extracted_source_fields": rate(20, 20), "unknown_provenance_scopes": 0, "forbidden_actions_committed": 0, "duplicate_domain_effects": 0, "safety_invariants_pass": True}
    return [{"case_id": "SYNTHETIC-" + str(number), "repetition": repetition, "stratum": "UNIT-" + str(number % 8), "passed": True, "actor": copy.deepcopy(outcome), "baseline": copy.deepcopy(outcome), "audit": copy.deepcopy(audit), "domain_sha256": "stable-" + str(number), "first_failed_assertion": None, "holds_by_reason": {"MISSING_INVOICE": {"tp": 1, "predicted": 1, "gold": 1}}, "proposals_by_rule": {"TEST_RULE": {"tp": 1, "predicted": 1, "gold": 1}}} for repetition in [1, 2, 3] for number in range(32)]


class PureM3Tests(unittest.TestCase):
    def test_rates_preserve_zero_denominator_and_reject_invalid_counts(self):
        self.assertIsNone(rate(0, 0)["value"])
        self.assertEqual(rate(2, 3)["denominator"], 3)
        for counts in [(-1, 1), (2, 1), (True, 1), (0, -1)]:
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                rate(*counts)

    def test_synthetic_repetitions_keep_independent_count_and_all_denominators(self):
        report = build_report(synthetic_cases(), "heldout", 3, {"passed": True}, POLICY)
        self.assertTrue(report["passed"])
        self.assertEqual(report["independent_case_count"], 32)
        self.assertEqual(report["attempted_case_count"], 96)
        self.assertEqual(report["actor"]["match_recall"]["denominator"], 96)
        self.assertEqual(report["audit"]["required_provenance_relations"]["denominator"], 480)
        self.assertEqual(report["audit"]["extracted_source_fields"]["denominator"], 1920)
        self.assertEqual(len(report["per_stratum"]), 8)
        self.assertEqual(report["holds_by_reason"]["MISSING_INVOICE"]["recall"]["denominator"], 96)
        self.assertEqual(report["per_repetition"][0]["case_count"], 32)

    def test_first_failure_is_preserved_despite_repetition_and_threshold_fraction(self):
        cases = synthetic_cases()
        cases[7].update({"passed": False, "first_failed_assertion": {"assertion": "specific hold absent", "passed": False}})
        report = build_report(cases, "heldout", 3, {"passed": True}, POLICY)
        self.assertFalse(report["passed"])
        self.assertEqual(report["first_failure"]["case_id"], "SYNTHETIC-7")
        self.assertEqual(report["first_failure"]["repetition"], 1)
        self.assertGreater(report["verified_case_success"]["value"], 0.90)
        self.assertFalse(report["release_gates"]["passed"])

    def test_execution_error_does_not_drop_case_from_denominator(self):
        cases = synthetic_cases()
        cases[0].update({"passed": False, "error": {"type": "SyntheticError"}, "audit": None, "domain_sha256": None})
        report = build_report(cases, "heldout", 3, {"passed": True}, POLICY)
        self.assertEqual(report["execution_errors"], 1)
        self.assertEqual(report["verified_case_success"]["denominator"], 96)
        self.assertEqual(report["audit"]["audited_cases"], 95)
        self.assertEqual(report["scored_case_count"], 95)
        self.assertFalse(report["passed"])

    def test_unsafe_or_unbalanced_proposal_fails_even_when_core_outcomes_match(self):
        for key, value in [("balanced_entries", rate(0, 1)), ("validated_proposals", rate(0, 1)), ("required_provenance_relations", rate(4, 5)), ("safety_invariants_pass", False), ("forbidden_actions_committed", 1), ("duplicate_domain_effects", 1), ("unknown_provenance_scopes", 1)]:
            cases = synthetic_cases()
            cases[0]["audit"][key] = value
            with self.subTest(key=key):
                self.assertFalse(build_report(cases, "heldout", 3, {"passed": True}, POLICY)["passed"])

    def test_lowered_policy_thresholds_are_rejected(self):
        policy = copy.deepcopy(POLICY)
        policy["minimum_match_precision"] = 0.99
        with self.assertRaisesRegex(ValueError, "predeclared"):
            build_report(synthetic_cases(), "heldout", 3, {"passed": True}, policy)

    def test_missing_or_changed_repetition_fails_consistency(self):
        cases = synthetic_cases()
        self.assertFalse(consistency_report(cases[:-1], 32, 3)["passed"])
        cases[-1]["domain_sha256"] = "changed"
        self.assertFalse(consistency_report(cases, 32, 3)["passed"])

    def test_duplicate_repetition_identity_is_not_reproducibility_evidence(self):
        cases = synthetic_cases()
        cases[-1]["repetition"] = 2
        self.assertFalse(consistency_report(cases, 32, 3)["passed"])

    def test_first_baseline_failure_is_retained(self):
        cases = synthetic_cases()
        cases[0].update({"passed": False, "baseline_error": {"type": "BaselineInputError"}})
        report = build_report(cases, "heldout", 3, {"passed": True}, POLICY)
        self.assertEqual(report["first_failure"]["baseline_error"]["type"], "BaselineInputError")
        self.assertEqual(report["baseline_execution_errors"], 1)
        self.assertFalse(report["passed"])

    def test_domain_fingerprint_ignores_timing_but_retains_booked_values(self):
        packet = {"snapshot_version": "s", "rule_hash": "r", "run_state": "PACKET_READY", "totals": {"ledger_closing_cents": 100}, "bank_records": [], "exceptions": [], "proposals": [], "ap_balances": [], "sources": [], "ledger_posting_supported": False, "provider": {"elapsed": 1}}
        first = canonical_domain(packet)["sha256"]
        packet["provider"]["elapsed"] = 99
        self.assertEqual(canonical_domain(packet)["sha256"], first)
        packet["totals"]["ledger_closing_cents"] = 101
        self.assertNotEqual(canonical_domain(packet)["sha256"], first)

    def test_specific_reason_and_exposure_do_not_receive_generic_hold_credit(self):
        labels = {"matches": {}, "exceptions": [{"bank_id": "S", "ledger_line_id": None, "reason": "MISSING_INVOICE", "exposure_cents": 10000}], "proposals": []}
        packet = {"bank_records": [], "exceptions": [{"bank_id": "S", "ledger_line_id": None, "reason": "UNMATCHED_CASH", "exposure_cents": 10000}], "proposals": []}
        result = score_outcomes(packet, labels)
        self.assertEqual(result["hold_tp"], 0)
        self.assertEqual(result["material_missed"], 1)
        diff = outcome_differences(packet, labels)
        self.assertEqual(diff["holds"]["missing"][0][2], "MISSING_INVOICE")
        self.assertEqual(breakdown(packet, labels, "holds")["MISSING_INVOICE"]["gold"], 1)

    def test_material_denominator_includes_all_gold_reason_types(self):
        labels = {"matches": {}, "exceptions": [{"bank_id": "S", "ledger_line_id": None, "reason": "UNSUPPORTED_TRANSACTION", "exposure_cents": 10000}], "proposals": []}
        result = score_outcomes({"bank_records": [], "exceptions": [], "proposals": []}, labels)
        self.assertEqual((result["material_gold"], result["material_missed"]), (1, 1))

    def test_ci_plan_is_offline_sequential_and_explicitly_opted_into_heldout(self):
        commands = command_plan("UNIT-ONLY-PATH")
        self.assertEqual(len(commands), 7)
        self.assertEqual(commands[5][commands[5].index("--repeat") + 1], "3")
        self.assertIn("--allow-heldout", commands[5])
        self.assertEqual(commands[-1][commands[-1].index("--milestone") + 1], "3")
        self.assertFalse(any("ollama" in command for command in commands))
        self.assertIn("scripted", commands[3])


if __name__ == "__main__":
    unittest.main()
