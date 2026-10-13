"""Pure QBO contracts: injected memory/HTTP classes only, no real I/O."""

import copy
import json
import unittest
from dataclasses import replace
from decimal import Decimal
from unittest.mock import patch

from evaluation.qbo_u2a_contract import config, records, wire
from finance_close.qbo import QboAdapter, QboFailure, ReadRequest, Scope, canonical, money, parse_json
from finance_close.qbo_transport import OwnedQboTransport, _worker, owned_get, validate_origin


class Clock:
    def __init__(self): self.now = 0.
    def __call__(self): return self.now
    def wait(self, seconds): self.now += seconds


class Memory:
    def __init__(self, clock, values=None, mutate=None):
        self.clock, self.values, self.mutate = clock, values or records(), mutate
        self.calls, self.counts = [], {}

    def __call__(self, request, timeout, cancelled):
        key = request.entity, request.id
        self.calls.append((request, timeout))
        self.counts[key] = self.counts.get(key, 0) + 1
        value = copy.deepcopy(self.values[key])
        if self.mutate: self.mutate(value, key, self.counts[key])
        self.clock.wait(.01)
        return {"status": 200, "body": wire(request.entity, value), "kind": "ok", "cleanup_complete": True}


class PureQbo(unittest.TestCase):
    def make(self, cfg=None, values=None, mutate=None, callback=None, **kwargs):
        clock = Clock()
        transport = Memory(clock, values, mutate) if callback is None else callback(clock)
        adapter = QboAdapter(cfg or config(), transport=transport, clock=clock, wait=clock.wait, **kwargs)
        return adapter, transport, clock

    def failure(self, adapter, kind):
        with self.assertRaises(QboFailure) as result: adapter.capture()
        self.assertEqual(kind, result.exception.kind)
        self.assertEqual("HALTED", adapter.state)
        self.assertNotIn("CANARY", str(result.exception) + canonical(adapter.events))

    def test_partial_payments_exact_cents_and_no_close_authority(self):
        adapter, transport, clock = self.make()
        capture = adapter.capture(); doc = capture.as_dict()
        self.assertEqual(100000, doc["bills"][0]["total_cents"])
        self.assertEqual([20000, 40000], [p["total_cents"] for p in doc["bill_payments"]])
        summary = doc["partial_payment_summary"][0]
        self.assertEqual((60000, 40000, 40000), (summary["selected_payment_cents"], summary["remaining_if_selected_only_cents"], summary["snapshot_balance_cents"]))
        self.assertTrue(summary["selected_scope_agrees_with_balance"])
        self.assertEqual((False, False, False), (doc["ap_history_complete"], doc["ledger_imported"], doc["posting_supported"]))
        self.assertEqual("EXTERNAL_HISTORY_NOT_CERTIFIED", doc["hold"])
        self.assertEqual((6, 0, 1), (doc["requests"], doc["query_pages"], doc["rows_per_response"]))
        paths = [r.path for r,t in transport.calls]
        self.assertEqual(paths[:3], paths[3:])
        self.assertEqual("/v3/company/999/bill/101?minorversion=75", paths[0])
        self.assertTrue(all("/billpayment/" in p for p in paths[1:3]))
        self.assertGreaterEqual(clock.now, 2.5)
        self.assertTrue(all(e["automatic_http_retries"] == 0 and e["model_calls"] == 0 for e in adapter.events))

    def test_redacted_export_and_field_provenance(self):
        adapter, _, _ = self.make(); capture = adapter.capture()
        self.assertNotIn("CANARY", capture.document + capture.events)
        self.assertNotIn("evil.invalid", capture.document + capture.events)
        bill = capture.as_dict()["bills"][0]
        self.assertTrue(any(p["json_path"] == "$.Bill.Balance" and p["response_sha256"] == bill["response_sha256"] for p in bill["field_provenance"]))
        altered = capture.as_dict(); altered["bills"][0]["total_cents"] = 1
        self.assertEqual(100000, capture.as_dict()["bills"][0]["total_cents"])

    def test_missing_payments_cannot_claim_history(self):
        cfg = config(); cfg["payments"] = {}
        adapter, transport, _ = self.make(cfg)
        doc = adapter.capture().as_dict()
        self.assertEqual(2, len(transport.calls))
        self.assertFalse(doc["partial_payment_summary"][0]["selected_scope_agrees_with_balance"])
        self.assertFalse(doc["ap_history_complete"])

    def test_multi_bill_unambiguous_allocation(self):
        cfg, values = config(), records()
        cfg["bills"]["102"] = {"vendor_id": "10", "invoice_key": "V-U2:I-SECOND", "sync_token": "0"}
        values["Bill", "102"] = dict(copy.deepcopy(values["Bill", "101"]), Id="102", TotalAmt=500., Balance=400.)
        values["BillPayment", "201"]["TotalAmt"] = 300.
        values["BillPayment", "201"]["Line"].append({"Amount": 100., "LinkedTxn": [{"TxnId": "102", "TxnType": "Bill"}]})
        adapter, transport, _ = self.make(cfg, values)
        doc = adapter.capture().as_dict()
        self.assertEqual([60000, 10000], [b["selected_payment_cents"] for b in doc["partial_payment_summary"]])
        self.assertEqual(8, len(transport.calls))

    def test_invalid_config_never_calls_transport(self):
        changes = {"origin": "https://quickbooks.api.intuit.com", "realm_id": "999/../1", "minor_version": True,
                   "api_version": "v4", "currency": "EUR", "max_records": True, "max_requests": 51,
                   "max_response_bytes": 1048577, "max_total_bytes": 5242881, "deadline_seconds": float("nan"),
                   "request_seconds": 16, "as_of_date": "20260930", "schema_version": 2,
                   "token": "SECRET-CANARY", "query": "SELECT * FROM Invoice", "endpoint": "https://evil.invalid"}
        for field, value in changes.items():
            with self.subTest(field=field):
                cfg = config(); cfg[field] = value
                with self.assertRaises(QboFailure) as result: QboAdapter(cfg, transport=lambda *a: self.fail("called"))
                self.assertEqual("invalid_config", result.exception.kind)

    def test_invalid_id_crosswalk_and_record_caps(self):
        for change in [lambda c: c["bills"].update({"101?query=x": c["bills"].pop("101")}),
                       lambda c: c["vendor_map"].update({"11": "V-U2"}),
                       lambda c: c["bills"]["101"].update(invoice_key="WRONG:I-U2"),
                       lambda c: c["bills"]["101"].update(sync_token="-1"),
                       lambda c: c.update(max_records=2),
                       lambda c: c.update(max_response_bytes=1000, max_total_bytes=256)]:
            cfg = config(); change(cfg)
            with self.assertRaises(QboFailure): Scope.parse(cfg)

    def test_read_request_scope_is_fixed(self):
        scope = Scope.parse(config())
        for args in [("1", "Bill", "101", scope.hash), ("999", "Invoice", "101", scope.hash),
                     ("999", "Bill", "102", scope.hash), ("999", "Bill", "101", "forged")]:
            with self.assertRaises(QboFailure): ReadRequest(*args).validate(scope)

    def test_host_config_mutation_does_not_expand_scope(self):
        cfg = config(); adapter, _, _ = self.make(cfg)
        cfg["realm_id"] = "1"; cfg["bills"]["101"]["invoice_key"] = "OTHER:OTHER"
        doc = adapter.capture().as_dict()
        self.assertEqual("V-U2:I-U2", doc["bills"][0]["invoice_key"])

    def test_required_fields_missing(self):
        for field in ["SyncToken", "CurrencyRef", "VendorRef", "TxnDate", "TotalAmt", "Balance", "MetaData"]:
            def mutate(value, key, count):
                if key[0] == "Bill": value.pop(field)
            adapter, _, _ = self.make(mutate=mutate)
            self.failure(adapter, "schema_error")

    def test_identity_sparse_and_deleted_records(self):
        for field, value, kind in [("Id", "999", "incomplete_record"), ("domain", "OTHER", "incomplete_record"),
                                   ("sparse", True, "incomplete_record"), ("status", "Deleted", "incomplete_record"),
                                   ("SyncToken", "1", "stale_version")]:
            adapter, _, _ = self.make(mutate=lambda record,key,count: record.update({field:value}))
            self.failure(adapter, kind)

    def test_currency_fx_and_vendor_scope(self):
        for change, kind in [(lambda v: v.update(CurrencyRef={"value":"EUR"}), "unsupported_currency"),
                             (lambda v: v.update(ExchangeRate=1.1), "unsupported_currency"),
                             (lambda v: v.update(VendorRef={"value":"11"}), "scope_denied")]:
            adapter, _, _ = self.make(mutate=lambda v,k,c: change(v))
            self.failure(adapter, kind)

    def test_decimal_is_exact_and_never_rounded(self):
        self.assertEqual(123, money(Decimal("1.23")))
        self.assertEqual(100000, money(1000))
        for value in [Decimal("1.001"), Decimal("1.000"), Decimal("NaN"), -1, True, 1.23, "1.23"]:
            with self.assertRaises(QboFailure): money(value)
        for value in [True, "1000.00", 1000.001]:
            adapter, _, _ = self.make(mutate=lambda v,k,c: v.update(TotalAmt=value))
            self.failure(adapter, "schema_error")

    def test_zero_total_and_balance_conflict(self):
        for changes, kind in [({"TotalAmt":0}, "incomplete_record"), ({"Balance":1001}, "schema_error")]:
            adapter, _, _ = self.make(mutate=lambda v,k,c: v.update(changes))
            self.failure(adapter, kind)

    def test_unknown_remote_link_never_fetched(self):
        def mutate(v,k,c):
            if k[0] == "BillPayment": v["Line"][0]["LinkedTxn"][0]["TxnId"] = "999999"
        adapter, transport, _ = self.make(mutate=mutate)
        self.failure(adapter, "scope_denied")
        self.assertEqual(["101", "201"], [r.id for r,t in transport.calls])

    def test_non_bill_and_multilink_allocations_rejected(self):
        for kind in ["Invoice", "VendorCredit", "JournalEntry"]:
            def mutate(v,k,c):
                if k[0] == "BillPayment": v["Line"][0]["LinkedTxn"][0]["TxnType"] = kind
            adapter, _, _ = self.make(mutate=mutate); self.failure(adapter, "unsupported_link")
        def multiple(v,k,c):
            if k[0] == "BillPayment": v["Line"][0]["LinkedTxn"] *= 2
        adapter, _, _ = self.make(mutate=multiple); self.failure(adapter, "ambiguous_allocation")

    def test_duplicate_and_nonfinite_allocation(self):
        for change, kind in [(lambda v: v["Line"].append(copy.deepcopy(v["Line"][0])), "ambiguous_allocation"),
                             (lambda v: v["Line"][0].update(Amount=0), "incomplete_record"),
                             (lambda v: v["Line"][0].update(Amount=199.99), "allocation_mismatch"),
                             (lambda v: v["Line"][0]["LinkedTxn"][0].update(TxnLineId="1"), "unsupported_link"),
                             (lambda v: v.update(Line=[]), "row_bound"),
                             (lambda v: v.update(PayType="Cash"), "schema_error")]:
            adapter, _, _ = self.make(mutate=lambda v,k,c: change(v) if k[0]=="BillPayment" else None)
            self.failure(adapter, kind)

    def test_payments_cannot_predate_bill_or_exceed_total(self):
        for change, kind in [(lambda v: v.update(TxnDate="2026-08-01"), "date_conflict"),
                             (lambda v: (v.update(TotalAmt=1200.), v["Line"][0].update(Amount=1200.)), "overallocated")]:
            adapter, _, _ = self.make(mutate=lambda v,k,c: change(v) if k==( "BillPayment", "201") else None)
            self.failure(adapter, kind)

    def test_sync_token_and_private_text_drift(self):
        for field, value, kind in [("SyncToken","1","stale_version"), ("Balance",399.99,"snapshot_drift"),
                                   ("PrivateNote","CHANGED-BUSINESS-CANARY","snapshot_drift")]:
            adapter, _, _ = self.make(mutate=lambda v,k,c: v.update({field:value}) if k==( "Bill", "101") and c==2 else None)
            self.failure(adapter, kind)

    def test_wrapper_time_can_advance_without_entity_drift(self):
        def callback(clock):
            original = Memory(clock)
            def changed(request, timeout, cancelled):
                result = original(request, timeout, cancelled)
                doc = json.loads(result["body"])
                doc["time"] = "2026-09-30T12:00:01+00:00"
                result["body"] = json.dumps(doc).encode(); return result
            return changed
        adapter, _, _ = self.make(callback=callback)
        self.assertEqual("CAPTURED", (adapter.capture(), adapter.state)[1])

    def test_http_failures_are_single_attempt(self):
        for status, kind in [(401,"auth_required"),(403,"permission_denied"),(404,"record_missing"),
                             (429,"rate_limited"),(500,"server_error"),(503,"server_error"),(302,"http_error")]:
            def callback(clock):
                return lambda *a: {"status":status,"body":b'SECRET-CANARY',"kind":"http_status","cleanup_complete":True}
            adapter, _, _ = self.make(callback=callback); self.failure(adapter, kind)
            self.assertEqual(1, adapter.requests)
            self.assertIsNone(adapter.events[0]["response_sha256"])

    def test_unknown_transport_errors_redacted(self):
        for exc in [RuntimeError("SECRET-CANARY"), QboFailure("SECRET-CANARY"), KeyboardInterrupt()]:
            def callback(clock):
                def fail(*a): raise exc
                return fail
            adapter, _, _ = self.make(callback=callback)
            self.failure(adapter, "cancelled" if isinstance(exc, KeyboardInterrupt) else "transport_uncertain")

    def test_incomplete_cleanup_and_content_type_fail(self):
        for changes, kind in [({"cleanup_complete":False}, "transport_uncertain"), ({"kind":"content_type"}, "response_rejected")]:
            def callback(clock):
                original = Memory(clock)
                def changed(*args):
                    result = original(*args); result.update(changes); return result
                return changed
            adapter, _, _ = self.make(callback=callback); self.failure(adapter, kind)

    def test_duplicate_nan_truncated_and_query_envelopes(self):
        for raw in [b'{"Bill":{},"Bill":{}}', b'{"Bill":NaN}', b'{"Bill":', b'{"QueryResponse":{},"time":"2026-09-30T00:00:00Z"}', b'\xff']:
            def callback(clock): return lambda *a: {"status":200,"body":raw,"kind":"ok","cleanup_complete":True}
            adapter, _, _ = self.make(callback=callback); self.failure(adapter, "schema_error")
        self.assertEqual(Decimal("1.23"), parse_json(b'{"a":1.23}')["a"])

    def test_byte_and_request_caps(self):
        for changes, kind in [({"max_response_bytes":256}, "byte_bound"),
                             ({"max_total_bytes":1500,"max_response_bytes":1500}, "byte_bound"),
                             ({"max_requests":1}, "request_bound")]:
            cfg = config(); cfg.update(changes); adapter, _, _ = self.make(cfg)
            self.failure(adapter, kind)

    def test_total_deadline_and_cancellation(self):
        cfg = config(); cfg["deadline_seconds"] = .5
        adapter, _, _ = self.make(cfg); self.failure(adapter, "deadline")
        adapter, transport, _ = self.make(cancelled=lambda: True); self.failure(adapter, "cancelled")
        self.assertEqual(0, len(transport.calls))

    def test_late_callback_is_never_accepted(self):
        cfg = config(); cfg["request_seconds"] = .05
        def callback(clock):
            original = Memory(clock)
            def late(*args):
                result = original(*args); clock.wait(.1); return result
            return late
        adapter, _, _ = self.make(cfg, callback=callback); self.failure(adapter, "deadline_uncertain")

    def test_single_use_after_success_or_failure(self):
        for fail in [False, True]:
            cfg = config(); cfg["max_requests"] = 1 if fail else 50
            adapter, transport, _ = self.make(cfg)
            if fail: self.failure(adapter, "request_bound")
            else: adapter.capture()
            count = len(transport.calls)
            with self.assertRaises(QboFailure) as result: adapter.capture()
            self.assertEqual("repeat_blocked", result.exception.kind)
            self.assertEqual(count, len(transport.calls))

    def test_external_gate_and_local_credential_gate_are_inert(self):
        scope = Scope.parse(config()); loaded = []
        loader = lambda: loaded.append(True)
        with self.assertRaises(QboFailure): OwnedQboTransport(scope, mode="external-sandbox", token_loader=loader)
        with self.assertRaises(QboFailure): OwnedQboTransport(scope, token_loader=loader, loopback_origin="http://127.0.0.1:1234")
        transport = OwnedQboTransport(scope, mode="external-sandbox", allow_external=True, token_loader=loader)
        self.assertTrue(transport.external_authorized)
        self.assertEqual([], loaded)
        with self.assertRaises(QboFailure): QboAdapter(config(), transport=lambda *a: None, mode="external-sandbox")

    def test_loopback_origin_and_preflight_before_launch(self):
        for origin in ["http://localhost:1234", "http://127.0.0.1:1234/query", "http://127.0.0.1:1234?x=1", "https://evil.invalid", None]:
            with self.assertRaises(QboFailure): validate_origin(origin,"local-http-double")
        scope = Scope.parse(config()); request = ReadRequest("999","Invoice","101",scope.hash)
        with patch("finance_close.qbo_transport.multiprocessing.get_context", side_effect=AssertionError("launched")):
            with self.assertRaises(QboFailure): owned_get(scope,request,"http://127.0.0.1:1234","local-http-double",None,1)
            request = ReadRequest("999","Bill","101",scope.hash)
            with self.assertRaises(QboFailure): owned_get(scope,request,"http://127.0.0.1:1234","local-http-double","SECRET-CANARY",1)
            with self.assertRaises(QboFailure): owned_get(scope,request,"http://127.0.0.1:1234","local-http-double",None,1,cancelled=lambda:True)

    def test_huge_unknown_decimal_has_bounded_hash_representation(self):
        def callback(clock):
            original = Memory(clock)
            def extra(*a):
                result = original(*a); result["body"] = result["body"].replace(b'"sparse":false',b'"sparse":false,"Unknown":1e100000000')
                return result
            return extra
        adapter, _, _ = self.make(callback=callback)
        self.assertEqual(6, adapter.capture().as_dict()["requests"])

    def test_worker_get_path_and_error_body_redaction_in_memory(self):
        class Response:
            status = 401
            def getheader(self,*a): return "application/json"
            def read(self,*a): raise AssertionError("error body must not be read")
        calls = []
        class Connection:
            def __init__(self,*args,**kwargs): pass
            def request(self,*args,**kwargs): calls.append((args,kwargs))
            def getresponse(self): return Response()
            def close(self): calls.append("closed")
        class Ready: value = 0
        scope = Scope.parse(config()); request = ReadRequest("999","Bill","101",scope.hash)
        shared, ready = bytearray(2097152), Ready()
        with patch("finance_close.qbo_transport.http.client.HTTPConnection",Connection):
            _worker(shared,ready,scope,request,"http://127.0.0.1:1234","local-http-double",None,1)
        result = json.loads(bytes(shared[:ready.value]))
        self.assertEqual({"status":401,"body":"","kind":"http_status"},result)
        self.assertEqual(("GET",request.path), calls[0][0])
        self.assertNotIn("Authorization", calls[0][1]["headers"])
        self.assertEqual("closed",calls[-1])

    def test_manually_constructed_scope_cannot_bypass_bounds(self):
        scope = Scope.parse(config())
        for invalid in [replace(scope,realm_id="999/../../invoice"), replace(scope,max_response_bytes=999999999),
                        replace(scope,payments=(("201?query=x","0"),)), replace(scope,vendor_map=(("10","V-U2"),("11","V-U2")))]:
            with self.assertRaises(QboFailure): OwnedQboTransport(invalid,loopback_origin="http://127.0.0.1:1234")

    def test_clock_and_cancel_errors_are_sanitized_and_halt(self):
        def bad(): raise RuntimeError("SECRET-CANARY")
        for kwargs in [{"clock":bad},{"cancelled":bad}]:
            adapter = QboAdapter(config(),transport=lambda *a:self.fail("called"),**kwargs)
            self.failure(adapter,"transport_uncertain")

    def test_approved_vendor_map_still_binds_each_bill(self):
        cfg = config(); cfg["vendor_map"]["11"] = "V-OTHER"
        adapter, _, _ = self.make(cfg,mutate=lambda v,k,c: v.update(VendorRef={"value":"11"}))
        self.failure(adapter,"scope_denied")

    def test_nested_fields_wrong_type_and_metadata_without_timezone(self):
        for changes in [{"VendorRef":[]},{"CurrencyRef":None},{"MetaData":{"LastUpdatedTime":"2026-09-10T12:00:00"}},
                        {"TxnDate":"2026-10-01"}]:
            adapter, _, _ = self.make(mutate=lambda v,k,c:v.update(changes))
            self.failure(adapter,"schema_error")

    def test_unknown_field_numeric_to_string_drift_is_detected(self):
        adapter, _, _ = self.make(mutate=lambda v,k,c:v.update(Unknown=1.23 if c==1 else "1.23"))
        self.failure(adapter,"snapshot_drift")


if __name__ == "__main__": unittest.main()
