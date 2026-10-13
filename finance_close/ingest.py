"""Validate a complete bundle in memory before creating database state."""

import csv
import io
import json
import re
from collections import defaultdict
from pathlib import Path

from .domain import InvalidInput, cents, digest, evidence_id, identifier, iso_date, object_hash, reference, strict_json

ROOT = Path(__file__).resolve().parent.parent
RULE_PATH = ROOT / "rules" / "v1.json"
BANK_COLUMNS = ["transaction_id", "date", "amount", "currency", "vendor_id", "reference", "transaction_type", "memo"]
LEDGER_COLUMNS = ["entry_id", "line_id", "date", "account", "side", "amount", "currency", "vendor_id", "invoice_id", "reference"]
MANIFEST_KEYS = {"schema_version", "entity_id", "account", "currency", "period_start", "period_end", "bank_opening", "ledger_opening", "statement_closing", "fictional"}
INVOICE_KEYS = {"Invoice ID", "Vendor ID", "Issued", "Amount", "Currency", "Payment Reference", "Ledger Reference", "Notes"}


def load_rule():
    data = RULE_PATH.read_bytes()
    return json.loads(data), digest(data)


def parse_bundle(root, invoice_format="v1"):
    if invoice_format not in {"v1", "aliases-v1"}:
        raise InvalidInput("Unsupported invoice format")
    root = Path(root).resolve(strict=True)
    paths = [root / "manifest.json", root / "bank.csv", root / "ledger.csv"]
    invoice_dir = root / "invoices"
    if invoice_dir.exists():
        if invoice_dir.is_symlink() or not invoice_dir.is_dir():
            raise InvalidInput("Invoice directory must be a local directory")
        paths += sorted(invoice_dir.glob("*.txt"))
    if len(paths) > 203:
        raise InvalidInput("Too many invoice documents")
    sources, evidence = [], []
    total = 0
    for path in paths:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise InvalidInput("Source must be a regular file inside the bundle")
        size = path.stat().st_size
        if size > (64 * 1024 if path.suffix == ".txt" else 10 * 1024 * 1024):
            raise InvalidInput("Source file exceeds size limit")
        total += size
        if total > 10 * 1024 * 1024:
            raise InvalidInput("Bundle exceeds 10 MiB")
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeError as exc:
            raise InvalidInput("Sources must be UTF-8") from exc
        sources.append({"path": path.relative_to(root).as_posix(), "sha256": digest(raw), "raw": raw, "text": text})
    by_path = {source["path"]: source for source in sources}

    def field(path, locator, value):
        ev = evidence_id(path, by_path[path]["sha256"], locator)
        evidence.append({"id": ev, "source_path": path, "locator": locator, "value": value})
        return ev

    def rows(path, columns, maximum):
        reader = csv.DictReader(io.StringIO(by_path[path]["text"], newline=""))
        if reader.fieldnames != columns:
            raise InvalidInput(f"{path}: expected documented columns in order")
        result = []
        for number, row in enumerate(reader, 2):
            if number > maximum + 1 or None in row or any(value is None or len(value) > 4096 for value in row.values()):
                raise InvalidInput(f"{path}: invalid or oversized row")
            refs = {key: field(path, f"row:{number}:{key}", value) for key, value in row.items()}
            result.append((row, refs))
        return result

    try:
        manifest = strict_json(by_path["manifest.json"]["text"])
    except (ValueError, KeyError) as exc:
        raise InvalidInput("Invalid manifest JSON") from exc
    if not isinstance(manifest, dict) or not MANIFEST_KEYS <= set(manifest) or set(manifest) - MANIFEST_KEYS - {"ap_history_complete"}:
        raise InvalidInput("Manifest must use the documented keys")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1 or manifest["fictional"] is not True:
        raise InvalidInput("Only schema 1 explicitly fictional bundles are supported")
    if manifest["currency"] != "USD" or manifest["account"] != "cash":
        raise InvalidInput("M1 supports one USD cash account")
    identifier(manifest["entity_id"])
    start, end = iso_date(manifest["period_start"]), iso_date(manifest["period_end"])
    if start > end or start.year != end.year or start.month != end.month:
        raise InvalidInput("M1 requires one monthly period")
    for key in ["bank_opening", "ledger_opening", "statement_closing"]:
        manifest[key + "_cents"] = cents(manifest[key])
        field("manifest.json", "json:" + key, manifest[key])
    if manifest["bank_opening_cents"] != manifest["ledger_opening_cents"]:
        raise InvalidInput("M1 requires equal opening balances")
    complete = manifest.get("ap_history_complete", [])
    if type(complete) is not list or len(complete) > 200 or any(type(key) is not str for key in complete) or len(set(complete)) != len(complete):
        raise InvalidInput("AP history completeness must be a unique bounded invoice-key list")
    for key in complete:
        if type(key) is not str or key.count(":") != 1:
            raise InvalidInput("Invalid AP history invoice key")
        vendor_key, invoice_key = key.split(":")
        identifier(vendor_key)
        identifier(invoice_key)
    manifest["ap_history_complete"] = complete
    manifest["history_evidence"] = field("manifest.json", "json:ap_history_complete", canonical_list(complete)) if "ap_history_complete" in strict_json(by_path["manifest.json"]["text"]) else None
    rule, rule_hash = load_rule()
    bank, ledger, invoices = [], [], []
    bank_ids, line_ids = set(), set()
    for row, refs in rows("bank.csv", BANK_COLUMNS, 10_000):
        txn_id = identifier(row["transaction_id"])
        if txn_id in bank_ids:
            raise InvalidInput("Duplicate bank transaction ID")
        bank_ids.add(txn_id)
        posting_date = iso_date(row["date"])
        amount = cents(row["amount"])
        if not start <= posting_date <= end or amount == 0 or not re.fullmatch(r"[A-Z]{3}", row["currency"]):
            raise InvalidInput("Bank rows need nonzero amounts, ISO currency and dates in the period")
        identifier(row["transaction_type"])
        identifier(row["vendor_id"], optional=row["transaction_type"] != "vendor_payment")
        bank.append({**row, "id": txn_id, "amount_cents": amount, "normalized_reference": reference(row["reference"]), "evidence": refs})
    balances = defaultdict(int)
    entry_dates = {}
    for row, refs in rows("ledger.csv", LEDGER_COLUMNS, 30_000):
        identifier(row["entry_id"])
        line_id = identifier(row["line_id"])
        if line_id in line_ids:
            raise InvalidInput("Duplicate ledger line ID")
        line_ids.add(line_id)
        posting_date = iso_date(row["date"])
        amount = cents(row["amount"])
        if amount <= 0 or row["side"] not in {"debit", "credit"} or row["account"] not in rule["accounts"] or not re.fullmatch(r"[A-Z]{3}", row["currency"]):
            raise InvalidInput("Invalid ledger money, currency, side or account")
        if row["entry_id"] in entry_dates and entry_dates[row["entry_id"]] != row["date"]:
            raise InvalidInput("Journal entry dates disagree")
        entry_dates[row["entry_id"]] = row["date"]
        identifier(row["vendor_id"], optional=True)
        identifier(row["invoice_id"], optional=True)
        signed = amount if row["side"] == "debit" else -amount
        balances[(row["entry_id"], row["currency"])] += signed
        ledger.append({**row, "amount_cents": amount, "signed_cents": signed, "in_period": start <= posting_date <= end, "normalized_reference": reference(row["reference"]), "evidence": refs})
    if any(balances.values()):
        raise InvalidInput("Imported journal entries must balance exactly")
    invoice_groups = {}
    for source in sources[3:]:
        values, refs, labels = {}, {}, {}
        if invoice_format == "aliases-v1":
            from .invoice_aliases import invoice_fields
            parsed_fields = invoice_fields(source["text"])
        else:
            parsed_fields = []
            for number, line in enumerate(source["text"].splitlines(), 1):
                if not line.strip():
                    continue
                key, separator, value = line.partition(":")
                if not separator or key not in INVOICE_KEYS:
                    raise InvalidInput("Invoice keys must be documented and unique")
                parsed_fields.append((number, key, key, value.strip()))
        for number, label, key, value in parsed_fields:
            if key not in INVOICE_KEYS or key in values:
                raise InvalidInput("Invoice keys must be documented and unique")
            values[key] = value.strip()
            labels[key] = label
            refs[key] = field(source["path"], f"line:{number}:{label}", value.strip())
        if not {"Invoice ID", "Vendor ID", "Issued", "Amount", "Currency"} <= set(values):
            raise InvalidInput("Invoice is missing required fields")
        inv_id, vendor = identifier(values["Invoice ID"]), identifier(values["Vendor ID"])
        iso_date(values["Issued"])
        amount = cents(values["Amount"])
        reference(values.get("Payment Reference", ""))
        reference(values.get("Ledger Reference", ""))
        if amount <= 0 or not re.fullmatch(r"[A-Z]{3}", values["Currency"]):
            raise InvalidInput("Invalid invoice amount/currency")
        item = {"id": inv_id, "vendor_id": vendor, "amount_cents": amount, "currency": values["Currency"], "date": values["Issued"], "reference": values.get("Payment Reference", ""), "ledger_reference": values.get("Ledger Reference", ""), "notes": values.get("Notes", ""), "source_path": source["path"], "evidence": refs}
        if invoice_format == "aliases-v1":
            item["field_labels"] = labels
        invoice_groups.setdefault((vendor, inv_id), []).append(item)
    for copies in invoice_groups.values():
        signature = lambda item: [item[key] for key in ["id", "vendor_id", "amount_cents", "currency", "date", "reference", "ledger_reference"]]
        invoices.append({**copies[0], "copies": copies, "conflicting": any(signature(copy) != signature(copies[0]) for copy in copies[1:])})
    closing = manifest["bank_opening_cents"] + sum(txn["amount_cents"] for txn in bank if txn["currency"] == "USD")
    if closing != manifest["statement_closing_cents"]:
        raise InvalidInput("Bank rows do not reconcile to the statement closing balance")
    snapshot = object_hash([[source["path"], source["sha256"]] for source in sources])
    return {"root": str(root), "manifest": manifest, "sources": sources, "evidence": evidence, "bank": bank, "ledger": ledger, "invoices": invoices, "snapshot_hash": snapshot, "rule": rule, "rule_hash": rule_hash}


def canonical_list(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
