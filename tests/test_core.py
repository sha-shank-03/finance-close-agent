"""Lightweight component checks; complete CLI integration has a separate gate."""

import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from finance_close.agent import investigate
from finance_close.domain import ForbiddenAction, IncompleteRun, InvalidInput, cents, reference
from finance_close.ingest import ROOT, parse_bundle
from finance_close.providers import ScriptedProvider
from finance_close.render import packet, render_html
from finance_close.review import review_proposal
from finance_close.store import Store
from finance_close.tools import Tools


def call(tool, bank_id, **arguments):
    return {"tool": tool, "arguments": {"bank_id": bank_id, **arguments}}


class MoneyTests(unittest.TestCase):
    def test_decimal_equality_and_one_cent_difference(self):
        self.assertEqual(cents("0.10") + cents("0.20"), cents("0.30"))
        self.assertNotEqual(cents("1000.00"), cents("1000.01"))

    def test_non_decimal_or_excess_scale_rejected(self):
        for value in [0.1, "NaN", "Infinity", "1e2", "1.001", "+1.00", "01.00", "100000000000.00"]:
            with self.subTest(value=value), self.assertRaises(InvalidInput):
                cents(value)

    def test_reference_normalization_is_narrow(self):
        self.assertEqual(reference(" pay-1001 "), "PAY1001")
        self.assertNotEqual(reference("PAY/1001"), reference("PAY-1001"))


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "input"
        shutil.copytree(ROOT / "fixtures" / "demo", self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_import_amounts_and_source_provenance(self):
        value = parse_bundle(self.root)
        self.assertEqual([row["amount_cents"] for row in value["bank"]], [-100000, -25000, -3000])
        self.assertEqual(sum(line["signed_cents"] for line in value["ledger"] if line["account"] == "cash"), -125000)
        self.assertEqual(len(value["sources"]), 4)
        self.assertEqual(len({item["id"] for item in value["evidence"]}), len(value["evidence"]))

    def test_duplicate_bank_identity_rejected(self):
        path = self.root / "bank.csv"
        path.write_text(path.read_text().replace("B003", "B001"), encoding="utf-8")
        with self.assertRaisesRegex(InvalidInput, "Duplicate bank"):
            parse_bundle(self.root)

    def test_unbalanced_journal_rejected(self):
        path = self.root / "ledger.csv"
        path.write_text(path.read_text().replace("debit,1000.00", "debit,1000.01"), encoding="utf-8")
        with self.assertRaisesRegex(InvalidInput, "balance"):
            parse_bundle(self.root)

    def test_partial_amount_import_preserves_missing_history_hold(self):
        path = self.root / "invoices" / "inv-1001.txt"
        path.write_text(path.read_text().replace("Amount: 1000.00", "Amount: 1200.00"), encoding="utf-8")
        bundle = parse_bundle(self.root)
        store = Store(":memory:")
        try:
            store.initialize(bundle)
            self.assertEqual(bundle["invoices"][0]["amount_cents"], 120000)
            tools = Tools(store, "B001")
            bank = tools.dispatch(call("inspect_transaction", "B001"))["record"]
            line = tools.dispatch(call("list_cash_candidates", "B001"))["candidates"][0]
            tools.dispatch(call("match_cash", "B001", line_id=line["line_id"], evidence_ids=[bank["evidence"]["amount"], line["evidence"]["amount"], *line["reference_evidence_ids"]]))
            self.assertIn("INCOMPLETE_HISTORY", tools.required_flags())
        finally:
            store.close()

    def test_statement_disagreement_rejected(self):
        path = self.root / "manifest.json"
        value = json.loads(path.read_text())
        value["statement_closing"] = "8719.99"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(InvalidInput, "statement closing"):
            parse_bundle(self.root)

    def test_duplicate_invoice_field_rejected(self):
        path = self.root / "invoices" / "inv-1001.txt"
        path.write_text(path.read_text() + "Amount: 999.00\n", encoding="utf-8")
        with self.assertRaisesRegex(InvalidInput, "unique"):
            parse_bundle(self.root)

    def test_duplicate_manifest_keys_and_non_string_history_rejected(self):
        path = self.root / "manifest.json"
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace('"fictional": true', '"fictional": true, "fictional": false'), encoding="utf-8")
        with self.assertRaisesRegex(InvalidInput, "manifest JSON"):
            parse_bundle(self.root)
        value = json.loads(original)
        value["ap_history_complete"] = [{}]
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(InvalidInput, "completeness"):
            parse_bundle(self.root)


class ToolAndReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inputs = self.root / "inputs"
        shutil.copytree(ROOT / "fixtures" / "demo", self.inputs)
        self.bundle = parse_bundle(self.inputs)
        self.store = Store(self.root / "state.sqlite")
        self.store.initialize(self.bundle)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def prepare_fee(self):
        tools = Tools(self.store, "B005")
        bank = tools.dispatch(call("inspect_transaction", "B005"))["record"]
        result = tools.dispatch(call("draft_entry", "B005", rule_id="BANK_FEE_V1", evidence_ids=[bank["evidence"][key] for key in ["transaction_id", "date", "amount", "currency", "transaction_type"]]))
        return tools, result

    def test_unknown_tool_and_extra_keys_are_rejected_without_events(self):
        tools = Tools(self.store, "B001")
        for decision in [call("post_ledger", "B001"), call("inspect_transaction", "B001", secret=True), call("inspect_transaction", "B003")]:
            with self.subTest(decision=decision), self.assertRaises(ForbiddenAction):
                tools.dispatch(decision)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)

    def test_unobserved_evidence_has_no_authority(self):
        tools = Tools(self.store, "B005")
        with self.assertRaisesRegex(ForbiddenAction, "not observed"):
            tools.dispatch(call("draft_entry", "B005", rule_id="BANK_FEE_V1", evidence_ids=["ev-invented"]))
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0], 0)

    def test_exact_match_and_missing_invoice_are_separate(self):
        tools = Tools(self.store, "B003")
        bank = tools.dispatch(call("inspect_transaction", "B003"))["record"]
        line = tools.dispatch(call("list_cash_candidates", "B003"))["candidates"][0]
        refs = [bank["evidence"]["amount"], bank["evidence"]["reference"], line["evidence"]["amount"], line["evidence"]["reference"]]
        tools.dispatch(call("match_cash", "B003", line_id=line["line_id"], evidence_ids=refs))
        result = tools.dispatch(call("finish_case", "B003"))
        self.assertEqual(result["cash_status"], "MATCHED")
        self.assertEqual(result["invoice_status"], "OPEN_HOLD")
        self.assertEqual(self.store.db.execute("SELECT reason FROM exceptions").fetchone()[0], "MISSING_INVOICE")

    def test_wrong_cash_line_rejected(self):
        tools = Tools(self.store, "B003")
        bank = tools.dispatch(call("inspect_transaction", "B003"))["record"]
        tools.dispatch(call("list_cash_candidates", "B003"))
        with self.assertRaisesRegex(ForbiddenAction, "exact"):
            tools.dispatch(call("match_cash", "B003", line_id="L001-CASH", evidence_ids=[bank["evidence"]["amount"]]))

    def test_fee_is_balanced_evidence_bound_and_idempotent(self):
        tools, first = self.prepare_fee()
        bank = self.store.bank("B005")
        second = tools.dispatch(call("draft_entry", "B005", rule_id="BANK_FEE_V1", evidence_ids=[bank["evidence"][key] for key in ["transaction_id", "date", "amount", "currency", "transaction_type"]]))
        self.assertEqual(first["hash"], second["hash"])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0], 1)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM proposal_evidence").fetchone()[0], 5)
        self.assertEqual([row[0] for row in self.store.db.execute("SELECT amount_cents FROM proposal_lines ORDER BY number")], [3000, 3000])

    def test_vendor_payment_cannot_be_coded_as_bank_fee(self):
        tools = Tools(self.store, "B001")
        bank = tools.dispatch(call("inspect_transaction", "B001"))["record"]
        with self.assertRaisesRegex(ForbiddenAction, "BANK_FEE_V1"):
            tools.dispatch(call("draft_entry", "B001", rule_id="BANK_FEE_V1", evidence_ids=list(bank["evidence"].values())))

    def test_ledger_snapshot_update_is_prohibited(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.db.execute("UPDATE ledger SET amount_cents=1 WHERE line_id='L001-CASH'")
        self.assertEqual(self.store.db.execute("SELECT amount_cents FROM ledger WHERE line_id='L001-CASH'").fetchone()[0], 100000)

    def test_exact_review_is_idempotent_and_unposted(self):
        _, proposal = self.prepare_fee()
        self.store.set_meta("run_state", "PACKET_READY")  # Focused review component setup, not an end-to-end run.
        args = (self.store, proposal["proposal_id"], proposal["hash"], self.bundle["snapshot_hash"], "approve", "unit-reviewer")
        first, second = review_proposal(*args), review_proposal(*args)
        self.assertFalse(first["posted"])
        self.assertTrue(second["repeated"])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0], 1)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM ledger").fetchone()[0], 4)
        with self.assertRaisesRegex(ForbiddenAction, "Conflicting"):
            review_proposal(*args[:4], "reject", "unit-reviewer")

    def test_stale_hash_and_snapshot_are_rejected(self):
        _, proposal = self.prepare_fee()
        self.store.set_meta("run_state", "PACKET_READY")
        for proposal_hash, snapshot in [("0" * 64, self.bundle["snapshot_hash"]), (proposal["hash"], "0" * 64)]:
            with self.subTest(snapshot=snapshot), self.assertRaises(ForbiddenAction):
                review_proposal(self.store, proposal["proposal_id"], proposal_hash, snapshot, "approve", "unit-reviewer")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0], 0)

    def test_changed_source_blocks_review(self):
        _, proposal = self.prepare_fee()
        self.store.set_meta("run_state", "PACKET_READY")
        path = self.inputs / "bank.csv"
        path.write_text(path.read_text() + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ForbiddenAction, "Source changed"):
            review_proposal(self.store, proposal["proposal_id"], proposal["hash"], self.bundle["snapshot_hash"], "approve", "unit-reviewer")

    def test_html_escapes_untrusted_text(self):
        value = packet(self.store)
        value["bank_records"][0]["memo"] = '<script>alert("post")</script>'
        output = render_html(value)
        self.assertNotIn("<script", output)
        self.assertIn("&lt;script&gt;", output)
        self.assertIn("UNPOSTED", output)

    def test_malformed_decision_terminates_without_domain_effects(self):
        class MalformedProvider:
            mode = "scripted"

            def next_decision(self, context):
                return {"tool": "post_ledger", "arguments": {"bank_id": context["bank_id"]}}

        with self.assertRaises(IncompleteRun):
            investigate(self.store, MalformedProvider())
        self.assertEqual(self.store.meta("run_state"), "BUDGET_EXHAUSTED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM matches").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT status FROM events").fetchone()[0], "rejected")

    def test_repeated_no_progress_decision_is_bounded(self):
        class RepeatingProvider:
            mode = "scripted"

            def next_decision(self, context):
                return call("inspect_transaction", context["bank_id"])

        with self.assertRaisesRegex(IncompleteRun, "no progress"):
            investigate(self.store, RepeatingProvider())
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 2)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM matches").fetchone()[0], 0)


class ProviderTests(unittest.TestCase):
    def test_scripted_decision_changes_after_observation(self):
        provider = ScriptedProvider()
        context = {"bank_id": "TEST-FEE", "history": []}
        first = provider.next_decision(context)
        self.assertEqual(first["tool"], "inspect_transaction")
        context["history"].append({"decision": first, "result": {"record": {"transaction_type": "bank_fee"}}, "status": "ok"})
        self.assertEqual(provider.next_decision(context)["tool"], "list_cash_candidates")
        self.assertEqual(provider.mode, "scripted")


if __name__ == "__main__":
    unittest.main()
