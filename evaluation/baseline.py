"""Fixed exact-reference cash baseline; no actor or label imports."""

import csv
import json
from datetime import date
from pathlib import Path

from .verify import normalize, raw_cents


def exact_reference(source):
    source = Path(source)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8-sig"))
    with (source / "bank.csv").open(encoding="utf-8-sig", newline="") as file:
        bank = list(csv.DictReader(file))
    with (source / "ledger.csv").open(encoding="utf-8-sig", newline="") as file:
        ledger = [row for row in csv.DictReader(file) if row["account"] == "cash" and row["currency"] == "USD" and manifest["period_start"] <= row["date"] <= manifest["period_end"]]
    edges = []
    for txn in bank:
        if txn["currency"] != "USD" or txn["transaction_type"] not in {"vendor_payment", "bank_fee"} or raw_cents(txn["amount"]) >= 0:
            continue
        for line in ledger:
            signed = raw_cents(line["amount"]) * (1 if line["side"] == "debit" else -1)
            if normalize(txn["reference"]) and normalize(txn["reference"]) == normalize(line["reference"]) and raw_cents(txn["amount"]) == signed and txn["vendor_id"] == line["vendor_id"] and abs((date.fromisoformat(txn["date"]) - date.fromisoformat(line["date"])).days) <= 3:
                edges.append((txn["transaction_id"], line["line_id"]))
    matches = {bank_id: line_id for bank_id, line_id in edges if sum(edge[0] == bank_id for edge in edges) == 1 and sum(edge[1] == line_id for edge in edges) == 1}
    exceptions = [{"bank_id": row["transaction_id"], "ledger_line_id": None, "reason": "UNMATCHED_CASH", "exposure_cents": abs(raw_cents(row["amount"]))} for row in bank if row["transaction_id"] not in matches]
    exceptions.extend({"bank_id": None, "ledger_line_id": row["line_id"], "reason": "UNMATCHED_LEDGER", "exposure_cents": raw_cents(row["amount"])} for row in ledger if row["line_id"] not in matches.values())
    return {"bank_records": [{"id": row["transaction_id"], "cash_status": "MATCHED" if row["transaction_id"] in matches else "UNMATCHED", "ledger_line_id": matches.get(row["transaction_id"])} for row in bank], "exceptions": exceptions, "proposals": [], "evidence_type": "fixed exact-reference cash baseline; no invoice investigation or proposals"}
