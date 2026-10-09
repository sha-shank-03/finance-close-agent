"""Booked AP history and separate unposted reservations; bank rows are not history."""

import json


def invoice_key(invoice):
    return invoice["vendor_id"] + ":" + invoice["id"]


def balance(store, key, exclude_bank=None):
    row = store.db.execute("SELECT data FROM invoices WHERE invoice_key=?", (key,)).fetchone()
    if row is None:
        return None
    invoice = json.loads(row[0])
    manifest = json.loads(store.meta("manifest"))
    history, ids = [], set()
    for row in store.db.execute("SELECT data FROM ledger WHERE account='accounts_payable' ORDER BY line_id"):
        line = json.loads(row[0])
        if line["vendor_id"] + ":" + line["invoice_id"] == key and line["currency"] == "USD" and line["date"] <= manifest["period_end"]:
            history.append(line)
            ids.update(line["evidence"][field] for field in ["entry_id", "line_id", "date", "account", "side", "amount", "currency", "vendor_id", "invoice_id"])
    recognized = sum(line["amount_cents"] for line in history if line["side"] == "credit")
    settled = sum(line["amount_cents"] for line in history if line["side"] == "debit")
    reservations = [dict(row) for row in store.db.execute("SELECT r.*,p.bank_id,p.review_state FROM reservations r JOIN proposals p ON p.id=r.proposal_id WHERE r.invoice_key=? AND p.review_state IN ('PENDING','APPROVED') ORDER BY r.proposal_id", (key,)) if row["bank_id"] != exclude_bank]
    reserved = sum(row["amount_cents"] for row in reservations)
    for copy in invoice["copies"]:
        ids.update(ev for field, ev in copy["evidence"].items() if field != "Notes")
    if manifest["history_evidence"]:
        ids.add(manifest["history_evidence"])
    bounded = len(ids) <= 57
    complete = key in manifest["ap_history_complete"] and recognized == invoice["amount_cents"] and invoice["currency"] == "USD" and bounded
    return {"invoice_key": key, "recognized_cents": recognized, "settled_cents": settled, "booked_balance_cents": recognized - settled, "reserved_cents": reserved, "available_cents": recognized - settled - reserved, "history_complete": complete, "conflicting": invoice["conflicting"], "history_line_ids": [line["line_id"] for line in history], "reservations": reservations, "evidence_ids": sorted(ids) if bounded else [], "snapshot_version": store.meta("snapshot_hash")}
