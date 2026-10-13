"""One authored fictional wire contract, not a corpus or accounting baseline."""

import copy
import json

from finance_close.qbo import SANDBOX_ORIGIN


def config():
    return {"schema_version": 1, "origin": SANDBOX_ORIGIN, "api_version": "v3", "minor_version": 75,
            "currency": "USD", "realm_id": "999", "as_of_date": "2026-09-30",
            "vendor_map": {"10": "V-U2"},
            "bills": {"101": {"vendor_id": "10", "invoice_key": "V-U2:I-U2", "sync_token": "0"}},
            "payments": {"201": "0", "202": "1"}}


def records():
    common = {"VendorRef": {"value": "10", "name": "BUSINESS-TEXT-CANARY"},
              "CurrencyRef": {"value": "USD"}, "domain": "QBO", "sparse": False,
              "MetaData": {"LastUpdatedTime": "2026-09-10T12:00:00+00:00"},
              "PrivateNote": "BUSINESS-TEXT-CANARY https://evil.invalid/query?token=SECRET-CANARY"}
    bill = dict(copy.deepcopy(common), Id="101", SyncToken="0", TxnDate="2026-08-15",
                TotalAmt=1000.00, Balance=400.00)
    first = dict(copy.deepcopy(common), Id="201", SyncToken="0", TxnDate="2026-08-20", TotalAmt=200.00,
                 PayType="Check", Line=[{"Amount": 200.00, "LinkedTxn": [{"TxnId": "101", "TxnType": "Bill"}]}])
    second = dict(copy.deepcopy(common), Id="202", SyncToken="1", TxnDate="2026-09-10", TotalAmt=400.00,
                  PayType="CreditCard", Line=[{"Amount": 400.00, "LinkedTxn": [{"TxnId": "101", "TxnType": "Bill"}]}])
    return {("Bill", "101"): bill, ("BillPayment", "201"): first, ("BillPayment", "202"): second}


def wire(kind, entity, time="2026-09-30T12:00:00+00:00"):
    return json.dumps({kind: entity, "time": time}, separators=(",", ":")).encode()
