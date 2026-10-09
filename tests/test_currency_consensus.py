"""Pure host classification tests: in-memory facts, no fixtures, SQL, CLI or HTTP."""

import itertools
import json
import unittest
from unittest.mock import Mock

from finance_close.domain import ForbiddenAction
from finance_close.tools import Tools


class FactStore:
    def __init__(self, bank_currency):
        self.record = {"id": "PAYMENT", "currency": bank_currency, "amount_cents": -25000, "transaction_type": "vendor_payment"}
        self.db = Mock()
        self.db.execute.return_value.fetchone.return_value = (1,)

    def bank(self, bank_id):
        return self.record

    def history(self, bank_id):
        return []

    def meta(self, key):
        return json.dumps({"rule_ids": ["BANK_FEE_V1", "MISSING_AP_PAYMENT_V1"]} if key == "rule" else {"ap_history_complete": []})


def fact_tools(currencies, *, bank_currency="USD", conflicting=False, has_cash_candidate=True):
    store = FactStore(bank_currency)
    tools = Tools(store, "PAYMENT")
    candidates = [{"exact": True, "available": True, "unique_bank": True, "amount_conflict": False, "timing": False}] if has_cash_candidate else []
    tools.candidates = Mock(return_value=candidates)
    tools.invoice_hits = Mock(return_value=[{"id": "INVOICE", "vendor_id": "VENDOR", "amount_cents": 25000, "currency": currencies[0], "conflicting": conflicting, "copies": [{"currency": currency} for currency in currencies]}])
    return tools


class CurrencyConsensusTests(unittest.TestCase):
    def test_contradictory_usd_foreign_copies_are_order_independent(self):
        for copies in itertools.permutations(["USD", "EUR"]):
            with self.subTest(copies=copies):
                self.assertEqual(fact_tools(copies, conflicting=True).required_flags(), ["CONFLICTING_EVIDENCE"])

    def test_repeated_copy_does_not_outvote_contradictory_currency(self):
        for copies in sorted(set(itertools.permutations(["USD", "EUR", "EUR"]))):
            with self.subTest(copies=copies):
                self.assertEqual(fact_tools(copies, conflicting=True).required_flags(), ["CONFLICTING_EVIDENCE"])

    def test_different_foreign_currencies_do_not_establish_consensus(self):
        for copies in itertools.permutations(["EUR", "GBP"]):
            with self.subTest(copies=copies):
                self.assertEqual(fact_tools(copies, conflicting=True).required_flags(), ["CONFLICTING_EVIDENCE"])

    def test_consistent_usd_copies_have_no_currency_hold(self):
        for copies in [["USD"], ["USD", "USD"]]:
            with self.subTest(copies=copies):
                self.assertEqual(fact_tools(copies).required_flags(), [])

    def test_unambiguous_foreign_invoice_currency_remains_unsupported(self):
        for copies in [["EUR"], ["EUR", "EUR"], ["GBP", "GBP"]]:
            with self.subTest(copies=copies):
                self.assertEqual(fact_tools(copies).required_flags(), ["UNSUPPORTED_CURRENCY"])

    def test_currency_consensus_survives_a_conflict_in_other_invoice_fields(self):
        self.assertEqual(fact_tools(["EUR", "EUR"], conflicting=True).required_flags(), ["CONFLICTING_EVIDENCE", "UNSUPPORTED_CURRENCY"])

    def test_foreign_bank_remains_unsupported_with_invoice_currency_conflict(self):
        for bank_currency in ["EUR", "GBP"]:
            for copies in itertools.permutations(["USD", "EUR"]):
                with self.subTest(bank_currency=bank_currency, copies=copies):
                    self.assertEqual(fact_tools(copies, bank_currency=bank_currency, conflicting=True).required_flags(), ["CONFLICTING_EVIDENCE", "UNSUPPORTED_CURRENCY"])

    def test_currency_conflict_still_blocks_an_unmatched_ap_proposal(self):
        for copies in itertools.permutations(["USD", "EUR"]):
            tools = fact_tools(copies, conflicting=True, has_cash_candidate=False)
            with self.subTest(copies=copies), self.assertRaises(ForbiddenAction):
                tools.draft_entry("PAYMENT", "MISSING_AP_PAYMENT_V1", [])
            tools.store.db.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
