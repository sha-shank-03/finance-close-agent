"""Exact-content proposal review; approval never posts journal lines."""

import json
from pathlib import Path

from .domain import ForbiddenAction, digest, object_hash
from .ingest import load_rule
from .store import utc_now
from .ap import balance


def review_proposal(store, proposal_id, expected_hash, snapshot_version, decision, reviewer):
    if decision not in {"approve", "reject"} or not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 80:
        raise ForbiddenAction("Review requires approve/reject and a bounded reviewer label")
    if store.meta("run_state") != "PACKET_READY":
        raise ForbiddenAction("Only a completed investigation packet may be reviewed")
    with store.transaction():
        row = store.db.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
        if not row:
            raise ForbiddenAction("Unknown proposal")
        content = json.loads(row["content"])
        if snapshot_version != store.meta("snapshot_hash") or content["snapshot_version"] != snapshot_version:
            raise ForbiddenAction("Stale snapshot version")
        if expected_hash != row["hash"] or object_hash(content) != expected_hash:
            raise ForbiddenAction("Stale or altered proposal content")
        if load_rule()[1] != store.meta("rule_hash") or content["rule_hash"] != store.meta("rule_hash"):
            raise ForbiddenAction("Rules changed since proposal creation")
        root = Path(store.meta("input_root"))
        for source in store.db.execute("SELECT path,sha256,raw FROM sources"):
            path = root / source["path"]
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                raise ForbiddenAction("Source no longer exists inside the original bundle")
            if digest(source["raw"]) != source["sha256"] or digest(path.read_bytes()) != source["sha256"]:
                raise ForbiddenAction("Source changed since proposal creation")
        lines = [{"account": line["account"], "side": line["side"], "amount_cents": line["amount_cents"]} for line in store.db.execute("SELECT * FROM proposal_lines WHERE proposal_id=? ORDER BY number", (proposal_id,))]
        refs = [r[0] for r in store.db.execute("SELECT evidence_id FROM proposal_evidence WHERE proposal_id=? ORDER BY evidence_id", (proposal_id,))]
        if lines != content["lines"] or refs != content["evidence_ids"] or content["posted"] is not False:
            raise ForbiddenAction("Stored proposal lines/evidence changed")
        bank = store.bank(row["bank_id"])
        rule = json.loads(store.meta("rule"))
        debit = rule["fee_account"] if content["rule_id"] == "BANK_FEE_V1" else rule["ap_account"] if content["rule_id"] == "MISSING_AP_PAYMENT_V1" else None
        expected_lines = [{"account": debit, "side": "debit", "amount_cents": abs(bank["amount_cents"])}, {"account": rule["cash_account"], "side": "credit", "amount_cents": abs(bank["amount_cents"])}]
        if not debit or lines != expected_lines or content["date"] != bank["date"] or content["currency"] != bank["currency"]:
            raise ForbiddenAction("Proposal differs from host-derived amount/accounts/date")
        reservation = store.db.execute("SELECT * FROM reservations WHERE proposal_id=?", (proposal_id,)).fetchone()
        if content["rule_id"] == "MISSING_AP_PAYMENT_V1":
            facts = balance(store, content["invoice_key"])
            if not reservation or reservation["invoice_key"] != content["invoice_key"] or reservation["amount_cents"] != abs(bank["amount_cents"]) or not facts or not facts["history_complete"] or facts["conflicting"] or facts["available_cents"] < 0:
                raise ForbiddenAction("AP reservation/history changed or overcommitted")
        elif reservation:
            raise ForbiddenAction("Fee proposal must not reserve AP")
        old = store.db.execute("SELECT * FROM reviews WHERE proposal_id=?", (proposal_id,)).fetchone()
        if old:
            if old["decision"] != decision or old["reviewer"] != reviewer or old["proposal_hash"] != expected_hash:
                raise ForbiddenAction("Conflicting review; create a new explicit proposal version")
            return {"proposal_id": proposal_id, "review_state": row["review_state"], "posted": False, "repeated": True}
        store.db.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?)", (proposal_id, expected_hash, snapshot_version, decision, reviewer, utc_now()))
        state = "APPROVED" if decision == "approve" else "REJECTED"
        store.db.execute("UPDATE proposals SET review_state=? WHERE id=?", (state, proposal_id))
        return {"proposal_id": proposal_id, "review_state": state, "posted": False, "repeated": False}
