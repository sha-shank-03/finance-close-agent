"""Pure U1 components only: no sockets, processes, full runner, CLI or demo."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from finance_close.domain import ForbiddenAction, InvalidInput, canonical
from finance_close.gateway import GatewayFailure, GatewayProvider, validate_config
from finance_close.gateway_journal import GatewayJournal, require_resumable
from finance_close.gateway_tools import GatewayTools
from finance_close.ingest import ROOT, parse_bundle
from finance_close.invoice_aliases import invoice_fields
from finance_close.net_worker import GATEWAY_URL, TransportFailure, _finish_owned, validate_endpoint
from finance_close.store import Store

CANARY = "SYNTHETIC-CREDENTIAL-CANARY"


def config(**values):
    return {"mode": "local-double", "model": "test/gateway-double", "provider": "test",
            "endpoint": "http://127.0.0.1:45678/v1/chat/completions", **values}


def response(tool="inspect_transaction", args=None, **values):
    return {"id": "chatcmpl-synthetic-1", "object": "chat.completion", "created": 0,
            "model": "test/gateway-double", "choices": [{"index": 0, "finish_reason": "tool_calls",
            "message": {"role": "assistant", "content": None, "tool_calls": [{"id": "call_synthetic_1",
            "type": "function", "function": {"name": tool, "arguments": canonical(args or {"bank_id": "B-U1"})}}]}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}, **values}


def context(**values):
    return {"bank_id": "B-U1", "snapshot_version": "test-snapshot", "history": [], "remaining_seconds": 15, **values}


class WireTests(unittest.TestCase):
    def invoke(self, value, status=200, **options):
        self.calls = []
        def transport(endpoint, mode, payload, token, timeout, cancelled):
            self.calls.append(json.loads(payload))
            self.assertIsNone(token)
            return {"status": status, "kind": "ok" if status == 200 else "http_status",
                    "body": value if type(value) is bytes else canonical(value).encode(), "cleanup_complete": True}
        self.provider = GatewayProvider(config(), transport=transport,
            token_loader=lambda: self.fail("Double read credentials"))
        return self.provider.next_decision(context(**options))

    def test_native_tool_envelope_and_synthetic_receipt(self):
        result = self.invoke(response())
        self.assertEqual(result, {"tool": "inspect_transaction", "arguments": {"bank_id": "B-U1"}})
        self.assertFalse(self.calls[0]["stream"])
        self.assertEqual(self.calls[0]["providerOptions"], {"gateway": {"only": ["test"]}})
        self.assertEqual(self.calls[0]["max_tokens"], 512)
        self.assertTrue(self.provider.last_receipt["usage_synthetic"])
        self.assertIsNone(self.provider.last_receipt["actual_cost_usd"])
        self.assertIsNone(self.provider.last_receipt["provider_observed"])

    def test_observation_uses_exact_native_call_id(self):
        call = response()["choices"][0]["message"]["tool_calls"][0]
        self.invoke(response(), history=[{"call": call, "result": {"guard_flags": ["MISSING_INVOICE"]}, "status": "ok"}])
        messages = self.calls[0]["messages"]
        self.assertEqual(messages[-1]["role"], "tool")
        self.assertEqual(messages[-1]["tool_call_id"], call["id"])
        self.assertIn("MISSING_INVOICE", messages[-1]["content"])
        self.assertNotIn("labels", canonical(messages))

    def test_http_denials_and_server_failure_never_repeat(self):
        for status, kind in [(401,"auth_required"),(402,"budget_denied"),(403,"permission_denied"),
                             (429,"rate_limited"),(500,"provider_5xx"),(503,"provider_5xx")]:
            with self.subTest(status=status), self.assertRaises(GatewayFailure) as raised:
                self.invoke({"error": CANARY}, status=status)
            self.assertEqual(raised.exception.kind, kind)
            self.assertEqual(len(self.calls), 1)
            self.assertNotIn(CANARY, str(raised.exception) + canonical(self.provider.last_receipt))

    def test_unknown_tool_is_not_a_guarded_action(self):
        with self.assertRaises(GatewayFailure) as raised:
            self.invoke(response(tool=CANARY))
        self.assertEqual(raised.exception.kind, "unknown_tool")
        self.assertEqual(self.provider.last_receipt["raw_tool"], "unknown")
        self.assertNotIn(CANARY, canonical(self.provider.last_receipt))

    def test_bad_protocol_controls_are_redacted(self):
        bad = []
        for mutator in [
            lambda r: r.update(model=CANARY),
            lambda r: r["choices"][0].update(finish_reason="length"),
            lambda r: r["choices"][0]["message"].update(content="Close completed: " + CANARY),
            lambda r: r["choices"][0]["message"].update(refusal=CANARY),
            lambda r: r["choices"][0]["message"]["tool_calls"].append(copy.deepcopy(r["choices"][0]["message"]["tool_calls"][0])),
            lambda r: r["choices"][0]["message"]["tool_calls"][0]["function"].update(arguments='{"bank_id":"OTHER"}'),
            lambda r: r["choices"][0]["message"]["tool_calls"][0]["function"].update(arguments='{"bank_id":"B-U1","bank_id":"'+CANARY+'"}'),
            lambda r: r["usage"].update(completion_tokens=513,total_tokens=523),
            lambda r: r["usage"].update(prompt_tokens=True),
            lambda r: r.update(extra=CANARY),
        ]:
            value = response(); mutator(value); bad.append(value)
        bad += [b'{"id":"'+CANARY.encode()+b'"', b'{"id":"a","id":"b"}', b'X'*32769]
        for value in bad:
            with self.subTest(value_type=type(value).__name__), self.assertRaises(GatewayFailure) as raised:
                self.invoke(value)
            self.assertEqual(len(self.calls), 1)
            self.assertNotIn(CANARY, str(raised.exception) + canonical(self.provider.last_receipt))

    def test_missing_double_usage_remains_unknown(self):
        self.invoke(response(usage=None))
        self.assertIsNone(self.provider.last_usage)

    def test_history_and_request_size_stop_before_transport(self):
        with self.assertRaises(GatewayFailure):
            self.invoke(response(), history=[{}]*25)
        self.assertEqual(self.calls, [])
        call=response()["choices"][0]["message"]["tool_calls"][0]
        with self.assertRaises(GatewayFailure):
            self.invoke(response(), history=[{"call":call,"result":{"data":"X"*65536},"status":"ok"}])
        self.assertEqual(self.calls, [])

    def test_uncertain_transport_error_never_echoes_or_repeats(self):
        calls=[]
        def broken(*args):
            calls.append(1); raise OSError(CANARY)
        provider=GatewayProvider(config(),transport=broken)
        with self.assertRaises(GatewayFailure) as raised:
            provider.next_decision(context())
        self.assertEqual(raised.exception.kind,"transport_uncertain")
        self.assertEqual(calls,[1]);self.assertNotIn(CANARY,str(raised.exception))

    def test_cancel_and_cleanup_failure_are_typed(self):
        def cancelled(*args):
            raise TransportFailure("cancelled", elapsed_seconds=.5,cleanup_complete=True)
        provider=GatewayProvider(config(),transport=cancelled)
        with self.assertRaises(GatewayFailure) as raised:
            provider.next_decision(context())
        self.assertEqual(raised.exception.kind,"cancelled")
        self.assertEqual(provider.last_receipt["elapsed_seconds"],.5)

    def test_keyboard_cancellation_is_typed_and_does_not_repeat(self):
        calls=[]
        def interrupted(*args): calls.append(1);raise KeyboardInterrupt
        provider=GatewayProvider(config(),transport=interrupted)
        with self.assertRaises(GatewayFailure) as raised: provider.next_decision(context())
        self.assertEqual(raised.exception.kind,"cancelled")
        self.assertEqual(calls,[1])


class ConfigTests(unittest.TestCase):
    def test_fixed_host_and_literal_loopback_authority(self):
        validate_endpoint(GATEWAY_URL,"live")
        for endpoint, mode in [("https://evil.test/v1/chat/completions","live"),
                               ("http://localhost:45678/v1/chat/completions","local-double"),
                               ("http://127.0.0.1:45678/v1/chat/completions?q=x","local-double"),
                               ("http://user@127.0.0.1:45678/v1/chat/completions","local-double"),
                               ("http://127.0.0.1:45678/redirect","local-double")]:
            with self.subTest(endpoint=endpoint), self.assertRaises(InvalidInput):
                validate_endpoint(endpoint,mode)

    def test_unknown_secret_fields_zero_allocation_and_boolean_caps_rejected(self):
        for values in [{"api_key":CANARY},{"max_requests":True},{"max_output_tokens":513},
                       {"timeout_seconds":float('inf')},{"allocation_usd":"1"}]:
            with self.subTest(fields=list(values)),self.assertRaises(InvalidInput):
                validate_config(config(**values))
        with self.assertRaises(InvalidInput):
            GatewayProvider({"mode":"live","model":"openai/gpt-4.1-mini","provider":"openai"})

    def test_live_config_cannot_load_key_without_explicit_authorization(self):
        live={"mode":"live","model":"openai/gpt-4.1-mini","provider":"openai",
              "allocation_usd":"1","request_cost_upper_usd":"0.1","pricing_version":"main-test",
              "input_token_ceiling":1047576}
        with self.assertRaises(InvalidInput):
            GatewayProvider(live,token_loader=lambda:self.fail("Key read"))
        self.assertEqual(validate_config(live)["endpoint"],GATEWAY_URL)

    def test_owned_cleanup_component_uses_handle_and_bounded_joins(self):
        class Owned:
            alive=True
            def __init__(self): self.operations=[]
            def is_alive(self): return self.alive
            def join(self,timeout): self.operations.append(("join",timeout))
            def terminate(self): self.operations.append(("terminate",));self.alive=False
            def kill(self): self.operations.append(("kill",));self.alive=False
            def close(self):self.operations.append(("close",))
        owned=Owned()
        self.assertTrue(_finish_owned(owned,1,clock=lambda:0))
        self.assertIn(("terminate",),owned.operations)
        self.assertTrue(all(op[1]<=1 for op in owned.operations if op[0]=="join"))


class AliasAndStateTests(unittest.TestCase):
    def setUp(self):
        self.store=Store(":memory:")
        self.bundle=parse_bundle(ROOT/"fixtures/u1/proposal",invoice_format="aliases-v1")
        self.store.initialize(self.bundle)

    def tearDown(self): self.store.close()

    def test_explicit_labels_resolve_with_original_source_provenance(self):
        inv=self.bundle["invoices"][0]
        self.assertEqual(inv["amount_cents"],100000)
        self.assertEqual(inv["field_labels"]["Amount"],"Invoice Total")
        ev=next(e for e in self.bundle["evidence"] if e["id"]==inv["evidence"]["Amount"])
        self.assertEqual(ev["locator"],"line:4:Invoice Total")
        self.assertEqual(ev["value"],"1000.00")
        tools=GatewayTools(self.store,"B-U1")
        resolution=tools.search_evidence("B-U1")["invoice_resolution"]
        self.assertEqual(resolution["status"],"UNIQUE")
        self.assertFalse(resolution["hand_off_required"])

    def test_remaining_balance_label_and_duplicate_alias_are_rejected(self):
        for text in ["Amount Due: 400.00", "Amount: 1000.00\nInvoice Total: 400.00"]:
            with self.assertRaises(InvalidInput): invoice_fields(text)

    def test_host_proposal_is_exact_and_unposted_with_partial_history(self):
        tools=GatewayTools(self.store,"B-U1")
        bank=tools.dispatch({"tool":"inspect_transaction","arguments":{"bank_id":"B-U1"}})["record"]
        tools.dispatch({"tool":"search_evidence","arguments":{"bank_id":"B-U1"}})
        facts=tools.dispatch({"tool":"inspect_invoice_balance","arguments":{"bank_id":"B-U1","invoice_key":"V-U1:I-U1"}})["balance"]
        self.assertEqual(facts["booked_balance_cents"],80000)
        ids=sorted(set(facts["evidence_ids"]+list(bank["evidence"].values())))
        tools.dispatch({"tool":"draft_entry","arguments":{"bank_id":"B-U1","rule_id":"MISSING_AP_PAYMENT_V1","evidence_ids":ids}})
        # SQL/JSON checks do not call proposal amount/balance validators.
        row=self.store.db.execute("SELECT content,review_state FROM proposals").fetchone()
        content=json.loads(row[0]);self.assertEqual(row[1],"PENDING");self.assertIs(content["posted"],False)
        self.assertEqual([(r[0],r[1],r[2]) for r in self.store.db.execute("SELECT account,side,amount_cents FROM proposal_lines ORDER BY number")],[("accounts_payable","debit",60000),("cash","credit",60000)])
        self.assertEqual(self.store.db.execute("SELECT amount_cents FROM reservations").fetchone()[0],60000)
        self.assertEqual(self.store.db.execute("SELECT SUM(signed_cents) FROM ledger WHERE account='accounts_payable'").fetchone()[0],-80000)

    def test_two_invoice_alias_targets_require_handoff_and_cannot_draft(self):
        inv=copy.deepcopy(self.bundle["invoices"][0]);inv["id"]="I-OTHER"
        self.store.db.execute("INSERT INTO invoices VALUES (?,?)",("V-U1:I-OTHER",canonical(inv)))
        tools=GatewayTools(self.store,"B-U1")
        self.assertEqual(tools.search_evidence("B-U1")["invoice_resolution"]["status"],"AMBIGUOUS")
        self.assertIn("CONFLICTING_EVIDENCE",tools.required_flags())
        with self.assertRaises(ForbiddenAction):tools.draft_entry("B-U1","MISSING_AP_PAYMENT_V1",[])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0],0)

    def test_false_finish_preserves_host_holds_without_a_proposal(self):
        tools=GatewayTools(self.store,"B-U1")
        tools.dispatch({"tool":"finish_case","arguments":{"bank_id":"B-U1"}})
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0],0)
        self.assertEqual(self.store.db.execute("SELECT reason FROM exceptions").fetchone()[0],"UNMATCHED_CASH")

    def test_started_request_and_failed_request_block_resume_persistently(self):
        provider=GatewayProvider(config(),transport=lambda *args:self.fail("Network"))
        journal=GatewayJournal(self.store,provider)
        seq=journal.start("B-U1",.01)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM provider_attempts").fetchone()[0],1)
        with self.assertRaises(GatewayFailure): GatewayJournal(self.store,provider)
        provider.last_receipt={"failure_class":"transport_uncertain","actual_cost_usd":None}
        journal.record(seq,"transport_uncertain",.1,failure="transport_uncertain")
        with self.assertRaises(GatewayFailure): GatewayJournal(self.store,provider)
        receipt=json.loads(self.store.db.execute("SELECT receipt FROM gateway_requests").fetchone()[0])
        self.assertIsNone(receipt["actual_cost_usd"])
        for state in ["started","response_ready","auth_required","rate_limited","cancelled"]:
            with self.assertRaises(GatewayFailure):require_resumable(["ok",state])

    def test_request_limit_and_config_binding_persist(self):
        provider=GatewayProvider(config(max_requests=1),transport=lambda *args:self.fail("Network"))
        journal=GatewayJournal(self.store,provider);seq=journal.start("B-U1",.01)
        journal.record(seq,"ok",.02)
        with self.assertRaises(GatewayFailure):journal.start("B-U1",.03)
        with self.assertRaises(ForbiddenAction):GatewayJournal(self.store,GatewayProvider(config(max_requests=2)))

    def test_resume_barrier_marks_crashed_run_without_another_request(self):
        from finance_close.gateway_loop import investigate_gateway
        provider=GatewayProvider(config(),transport=lambda *args:self.fail("Network"))
        journal=GatewayJournal(self.store,provider);journal.start("B-U1",.01)
        self.store.set_meta("run_state","INVESTIGATING")
        with self.assertRaises(GatewayFailure) as stopped:
            investigate_gateway(self.store,provider)
        self.assertEqual(stopped.exception.kind,"resume_blocked")
        self.assertEqual(self.store.meta("run_state"),"PROVIDER_HALTED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM gateway_requests").fetchone()[0],1)
        self.assertEqual(self.store.db.execute("SELECT status FROM gateway_requests").fetchone()[0],"started")
        self.assertEqual(self.store.db.execute("SELECT reason FROM exceptions").fetchone()[0],"UNMATCHED_CASH")


if __name__=="__main__": unittest.main()
