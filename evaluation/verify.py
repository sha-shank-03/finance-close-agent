"""Independent raw-source, SQLite and packet checks; imports no actor implementation."""

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
from datetime import date
from pathlib import Path

from .metrics import rate


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def hash_object(value):
    return hash_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def raw_cents(text):
    if type(text) is not str or not re.fullmatch(r"-?[0-9]+(?:\.[0-9]{1,2})?", text):
        raise ValueError("Invalid raw fixture money")
    whole, _, fraction = text.lstrip("-").partition(".")
    value = int(whole) * 100 + int((fraction + "00")[:2])
    return -value if text.startswith("-") else value


def normalize(text):
    return re.sub(r"[ _-]", "", text.strip()).upper()


def order_exceptions(items):
    return sorted(items, key=lambda row: (row["bank_id"] or "", row["ledger_line_id"] or "", row["reason"]))


def verify(run, labels, provider_mode="scripted", provider_evidence=None):
    run = Path(run).resolve()
    expected = json.loads(Path(labels).read_text(encoding="utf-8"))
    packet = json.loads((run / "packet.json").read_text(encoding="utf-8"))
    db = sqlite3.connect((run / "state.sqlite").as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    checks = []
    def check(name, actual, wanted):
        checks.append({"assertion": name, "passed": actual == wanted, "actual": actual, "expected": wanted})
    try:
        metadata = dict(db.execute("SELECT key,value FROM metadata"))
        sources = {row["path"]: dict(row) for row in db.execute("SELECT * FROM sources")}
        root = Path(metadata["input_root"])
        source_fields, invoice_groups = {}, {}
        raw_bank, raw_ledger, manifest = [], [], None
        for name, source in sources.items():
            check("stored source hash: " + name, hash_bytes(source["raw"]), source["sha256"])
            check("original source unchanged: " + name, hash_bytes((root / name).read_bytes()), source["sha256"])
            text = source["raw"].decode("utf-8-sig")
            if name == "manifest.json":
                manifest = json.loads(text)
                for field in ["bank_opening", "ledger_opening", "statement_closing", "ap_history_complete"]:
                    if field in manifest:
                        source_fields[(name, "json:" + field)] = json.dumps(manifest[field], sort_keys=True, separators=(",", ":"), ensure_ascii=False) if type(manifest[field]) is list else manifest[field]
            elif name in {"bank.csv", "ledger.csv"}:
                rows = list(csv.DictReader(io.StringIO(text)))
                if name == "bank.csv":
                    raw_bank = rows
                else:
                    raw_ledger = rows
                for number, row in enumerate(rows, 2):
                    for key, value in row.items():
                        source_fields[(name, f"row:{number}:{key}")] = value
            elif name.startswith("invoices/"):
                values = {}
                for number, line in enumerate(text.splitlines(), 1):
                    if not line.strip():
                        continue
                    key, _, value = line.partition(":")
                    values[key] = value.strip()
                    source_fields[(name, f"line:{number}:{key}")] = value.strip()
                invoice_groups.setdefault(values["Vendor ID"] + ":" + values["Invoice ID"], []).append((name, values))
        ordered = ["manifest.json", "bank.csv", "ledger.csv"] + sorted(name for name in sources if name.startswith("invoices/"))
        snapshot = hash_object([[name, sources[name]["sha256"]] for name in ordered])
        check("snapshot binds all original sources", metadata["snapshot_hash"], snapshot)
        check("packet snapshot", packet["snapshot_version"], snapshot)
        check("packet rule hash", packet["rule_hash"], metadata["rule_hash"])
        check("current versioned policy hash", metadata["rule_hash"], hash_bytes((Path(__file__).resolve().parent.parent / "rules/v1.json").read_bytes()))
        check("bank row count", len(raw_bank), expected["bank_records"])
        check("ledger row count", len(raw_ledger), expected["ledger_lines"])
        bank_by_id = {row["transaction_id"]: row for row in raw_bank}
        ledger_by_id = {row["line_id"]: row for row in raw_ledger}
        bank_values = {key: raw_cents(row["amount"]) for key, row in bank_by_id.items()}
        check("imported bank amounts equal raw sources", dict(db.execute("SELECT id,amount_cents FROM bank")), bank_values)
        for row in db.execute("SELECT * FROM bank"):
            data, raw = json.loads(row["data"]), bank_by_id[row["id"]]
            check("bank record fields: " + row["id"], {key: data[key] for key in raw}, raw)
            check("bank normalized reference: " + row["id"], data["normalized_reference"], normalize(raw["reference"]))
        projection = {key: [row["entry_id"], row["account"], row["side"], raw_cents(row["amount"]), raw_cents(row["amount"]) * (1 if row["side"] == "debit" else -1)] for key, row in ledger_by_id.items()}
        stored = {row["line_id"]: [row["entry_id"], row["account"], row["side"], row["amount_cents"], row["signed_cents"]] for row in db.execute("SELECT * FROM ledger")}
        check("immutable ledger values equal original input", stored, projection)
        check("database relations have no orphaned references", len(db.execute("PRAGMA foreign_key_check").fetchall()), 0)
        for row in db.execute("SELECT * FROM ledger"):
            data, raw = json.loads(row["data"]), ledger_by_id[row["line_id"]]
            check("ledger record fields: " + row["line_id"], {key: data[key] for key in raw}, raw)
            check("ledger period classification: " + row["line_id"], data["in_period"], manifest["period_start"] <= raw["date"] <= manifest["period_end"])
        usd_bank = {key: value for key, value in bank_values.items() if bank_by_id[key]["currency"] == "USD"}
        cash_values = {key: projection[key][-1] for key, row in ledger_by_id.items() if row["account"] == "cash" and row["currency"] == "USD" and manifest["period_start"] <= row["date"] <= manifest["period_end"]}
        bank_close = raw_cents(manifest["bank_opening"]) + sum(usd_bank.values())
        ledger_close = raw_cents(manifest["ledger_opening"]) + sum(cash_values.values())
        check("bank closing golden outcome", bank_close, expected["bank_closing_cents"])
        check("ledger closing golden outcome", ledger_close, expected["ledger_closing_cents"])
        check("statement closing", raw_cents(manifest["statement_closing"]), bank_close)
        check("packet bank closing", packet["totals"]["bank_closing_cents"], bank_close)
        check("packet ledger closing excludes proposals", packet["totals"]["ledger_closing_cents"], ledger_close)
        matches = dict(db.execute("SELECT bank_id,line_id FROM matches"))
        check("independently labeled match edges", matches, expected["matches"])
        unmatched_bank = sorted(set(bank_values) - set(matches))
        unmatched_ledger = sorted(set(cash_values) - set(matches.values()))
        check("all unmatched bank residual IDs including unsupported", unmatched_bank, expected["unmatched_bank_ids"])
        check("all unmatched ledger residual IDs", unmatched_ledger, expected["unmatched_ledger_ids"])
        bank_residual = sum(usd_bank.get(key, 0) for key in unmatched_bank)
        ledger_residual = sum(cash_values[key] for key in unmatched_ledger)
        check("independent USD reconciliation bridge", bank_close - ledger_close, bank_residual - ledger_residual)
        check("packet booked difference", packet["totals"]["booked_difference_cents"], bank_close - ledger_close)
        check("packet bank residual", packet["totals"]["unmatched_bank_cents"], bank_residual)
        check("packet ledger residual", packet["totals"]["unmatched_ledger_cents"], ledger_residual)
        check("packet bridge residual", packet["totals"]["bridge_residual_cents"], 0)
        fields = ["bank_id", "ledger_line_id", "reason", "exposure_cents"]
        exceptions = order_exceptions([{key: row[key] for key in fields} for row in db.execute("SELECT * FROM exceptions")])
        check("specific open exception outcomes", exceptions, order_exceptions(expected["exceptions"]))
        check("packet exposes every database exception", order_exceptions([{key: row[key] for key in fields} for row in packet["exceptions"]]), exceptions)
        check("all packet exceptions remain open", all(row["status"] == "OPEN" for row in packet["exceptions"]), True)
        records = {row["id"]: row for row in packet["bank_records"]}
        check("packet bank coverage", sorted(records), sorted(bank_values))
        check("independent invoice holds", sorted(row["id"] for row in records.values() if row["invoice_status"] == "OPEN_HOLD"), expected["invoice_hold_ids"])
        evidence = {row["id"]: dict(row) for row in db.execute("SELECT * FROM evidence")}
        ev_for_field = {}
        for ev_id, ev in evidence.items():
            source = sources[ev["source_path"]]
            check("evidence identity: " + ev_id, ev_id, "ev-" + hash_object([ev["source_path"], source["sha256"], ev["locator"]]))
            check("original field relation: " + ev_id, ev["value"], source_fields[(ev["source_path"], ev["locator"])])
            ev_for_field[(ev["source_path"], ev["locator"])] = ev_id
        check("all original fields preserved", set(ev_for_field), set(source_fields))
        check("packet evidence equals database", {row["id"]: {key: row[key] for key in ["id", "source_path", "locator", "value"]} for row in packet["evidence"]}, evidence)
        valid_evidence_ids = {ev_id for ev_id, ev in evidence.items() if ev["source_path"] in sources and (ev["source_path"], ev["locator"]) in source_fields and ev_id == "ev-" + hash_object([ev["source_path"], sources[ev["source_path"]]["sha256"], ev["locator"]]) and source_fields[(ev["source_path"], ev["locator"])] == ev["value"]}
        valid_extracted_fields = {(evidence[ev_id]["source_path"], evidence[ev_id]["locator"]) for ev_id in valid_evidence_ids}
        input_integrity = all(item["passed"] for item in checks if item["assertion"].startswith(("stored source hash:", "original source unchanged:", "snapshot binds", "packet snapshot", "packet rule hash", "current versioned policy hash", "imported bank amounts", "bank record fields:", "immutable ledger values", "ledger record fields:")))
        def row_evidence(source, rows, identity_field, identity, fields):
            number = next(number for number, raw in enumerate(rows, 2) if raw[identity_field] == identity)
            return {ev_for_field[(source, f"row:{number}:{field}")] for field in fields}
        for edge in db.execute("SELECT * FROM matches"):
            bank_raw, line_raw = bank_by_id[edge["bank_id"]], ledger_by_id[edge["line_id"]]
            required = row_evidence("bank.csv", raw_bank, "transaction_id", edge["bank_id"], ["reference", "amount"]) | row_evidence("ledger.csv", raw_ledger, "line_id", edge["line_id"], ["reference", "amount"])
            same_reference = bool(normalize(bank_raw["reference"])) and normalize(bank_raw["reference"]) == normalize(line_raw["reference"])
            if not same_reference:
                key = bank_raw["vendor_id"] + ":" + line_raw["invoice_id"]
                copies = invoice_groups.get(key, [])
                alias = next(((name, values) for name, values in copies if normalize(values.get("Payment Reference", "")) == normalize(bank_raw["reference"]) and normalize(values.get("Ledger Reference", "")) == normalize(line_raw["reference"]) and bool(normalize(line_raw["reference"]))), None)
                check("explicit source reference alias: " + edge["bank_id"], alias is not None, True)
                if alias:
                    required.update(ev_id for (source_name, locator), ev_id in ev_for_field.items() if source_name == alias[0] and locator.endswith((":Payment Reference", ":Ledger Reference")))
            check("exact match evidence relations: " + edge["bank_id"], set(json.loads(edge["evidence_ids"])), required)
            check("matched source currencies", [bank_raw["currency"], line_raw["currency"]], ["USD", "USD"])
            check("matched exact signed amount", raw_cents(bank_raw["amount"]), raw_cents(line_raw["amount"]) * (1 if line_raw["side"] == "debit" else -1))
            check("matched date window", abs((date.fromisoformat(bank_raw["date"]) - date.fromisoformat(line_raw["date"])).days) <= 3, True)
            check("matched same vendor", bank_raw["vendor_id"], line_raw["vendor_id"])
            check("matched current-period cash", line_raw["line_id"] in cash_values, True)
        raw_ap = {}
        for row in raw_ledger:
            if row["account"] == "accounts_payable" and row["currency"] == "USD" and row["date"] <= manifest["period_end"]:
                key = row["vendor_id"] + ":" + row["invoice_id"]
                raw_ap[key] = raw_ap.get(key, 0) + raw_cents(row["amount"]) * (1 if row["side"] == "credit" else -1)
        for key, amount in expected.get("ap_balances", {}).items():
            check("independent booked AP golden balance: " + key, raw_ap.get(key, 0), amount)
        proposals = db.execute("SELECT * FROM proposals").fetchall()
        golds = expected.get("proposals", [expected["proposal"]] if "proposal" in expected else [])
        gold_by_bank = {gold["bank_id"]: gold for gold in golds}
        check("explicit expected proposal count (zero is not a quality rate)", len(proposals), len(golds))
        check("packet proposal count", len(packet["proposals"]), len(golds))
        check("exact proposal bank identities", sorted(row["bank_id"] for row in proposals), sorted(gold_by_bank))
        packet_proposals = {item["id"]: item for item in packet["proposals"]}
        active_reserved = {}
        for reservation in db.execute("SELECT r.*,p.review_state,p.content FROM reservations r JOIN proposals p ON p.id=r.proposal_id"):
            content = json.loads(reservation["content"])
            check("AP reservation identity and amount: " + reservation["proposal_id"], [reservation["invoice_key"], reservation["amount_cents"]], [content.get("invoice_key"), content["lines"][0]["amount_cents"]])
            if reservation["review_state"] in {"PENDING", "APPROVED"}:
                active_reserved[reservation["invoice_key"]] = active_reserved.get(reservation["invoice_key"], 0) + reservation["amount_cents"]
        for key, reserved in active_reserved.items():
            check("pending/approved AP reservations do not overcommit: " + key, reserved <= raw_ap.get(key, 0), True)
        for facts in packet.get("ap_balances", []):
            key = facts["invoice_key"]
            check("packet booked AP excludes bank/proposals: " + key, facts["booked_balance_cents"], raw_ap.get(key, 0))
            check("packet separate active AP reservation: " + key, facts["reserved_cents"], active_reserved.get(key, 0))
            check("packet AP availability: " + key, facts["available_cents"], raw_ap.get(key, 0) - active_reserved.get(key, 0))
        cash_effect = 0
        balanced_count = validated_count = provenance_count = provenance_total = unknown_scopes = 0
        for row in proposals:
            proposal_check_start = len(checks)
            content = json.loads(row["content"])
            lines = [{key: line[key] for key in ["account", "side", "amount_cents"]} for line in db.execute("SELECT * FROM proposal_lines WHERE proposal_id=? ORDER BY number", (row["id"],))]
            balanced = bool(lines) and all(type(line["amount_cents"]) is int and line["amount_cents"] > 0 and line["side"] in {"debit", "credit"} for line in lines) and sum(line["amount_cents"] if line["side"] == "debit" else -line["amount_cents"] for line in lines) == 0
            balanced_count += int(balanced)
            check("balanced positive proposal", balanced, True)
            gold = gold_by_bank.get(row["bank_id"])
            if gold is None:
                unknown_scopes += 1
                check("unexpected proposal has no permitted labeled scope: " + row["bank_id"], False, True)
                continue  # Unexpected identities already fail exact proposal coverage above.
            raw = bank_by_id[row["bank_id"]]
            check("proposal exact labeled fields: " + row["bank_id"], {key: content.get(key) for key in gold}, gold)
            check("proposal hash binds full content", row["hash"], hash_object(content))
            check("proposal snapshot binding", content["snapshot_version"], snapshot)
            check("proposal rule binding", content["rule_hash"], metadata["rule_hash"])
            check("proposal never posted", content["posted"], False)
            check("actual proposal lines equal gold", lines, gold["lines"])
            check("actual lines equal hashed content", lines, content["lines"])
            check("host bank amount", [line["amount_cents"] for line in lines], [abs(raw_cents(raw["amount"]))] * 2)
            refs = sorted(r[0] for r in db.execute("SELECT evidence_id FROM proposal_evidence WHERE proposal_id=?", (row["id"],)))
            check("proposal relations equal hashed evidence", refs, content["evidence_ids"])
            required = row_evidence("bank.csv", raw_bank, "transaction_id", row["bank_id"], ["transaction_id", "date", "amount", "currency", "transaction_type"])
            if content["rule_id"] == "BANK_FEE_V1":
                check("explicit bank fee authority", raw["transaction_type"], "bank_fee")
                check("fee has no AP reservation", db.execute("SELECT COUNT(*) FROM reservations WHERE proposal_id=?", (row["id"],)).fetchone()[0], 0)
            elif content["rule_id"] == "MISSING_AP_PAYMENT_V1":
                key = content["invoice_key"]
                copies = invoice_groups[key]
                inv = copies[0][1]
                check("AP source identity matches bank vendor", inv["Vendor ID"], raw["vendor_id"])
                check("AP source reference matches bank", normalize(inv.get("Payment Reference", "")), normalize(raw["reference"]))
                check("explicit completeness assertion", key in manifest.get("ap_history_complete", []), True)
                recognition = sum(raw_cents(line["amount"]) for line in raw_ledger if line["vendor_id"] + ":" + line["invoice_id"] == key and line["account"] == "accounts_payable" and line["currency"] == "USD" and line["date"] <= manifest["period_end"] and line["side"] == "credit")
                check("AP recognition equals invoice", recognition, raw_cents(inv["Amount"]))
                signatures = [[values["Invoice ID"], values["Vendor ID"], raw_cents(values["Amount"]), values["Currency"], values["Issued"], values.get("Payment Reference", ""), values.get("Ledger Reference", "")] for _, values in copies]
                check("AP invoice copies unconflicted", all(sig == signatures[0] for sig in signatures), True)
                required.update(row_evidence("bank.csv", raw_bank, "transaction_id", row["bank_id"], ["vendor_id", "reference"]))
                required.add(ev_for_field[("manifest.json", "json:ap_history_complete")])
                for name, _ in copies:
                    required.update(ev_id for (source_name, locator), ev_id in ev_for_field.items() if source_name == name and not locator.endswith(":Notes"))
                for line in raw_ledger:
                    if line["vendor_id"] + ":" + line["invoice_id"] == key and line["account"] == "accounts_payable" and line["currency"] == "USD" and line["date"] <= manifest["period_end"]:
                        required.update(row_evidence("ledger.csv", raw_ledger, "line_id", line["line_id"], ["entry_id", "line_id", "date", "account", "side", "amount", "currency", "vendor_id", "invoice_id"]))
                check("exact AP reservation exists", db.execute("SELECT COUNT(*) FROM reservations WHERE proposal_id=?", (row["id"],)).fetchone()[0], 1)
                reservation = db.execute("SELECT invoice_key,amount_cents FROM reservations WHERE proposal_id=?", (row["id"],)).fetchone()
                check("AP proposal's exact reservation", list(reservation) if reservation else None, [key, abs(raw_cents(raw["amount"]))])
                check("AP proposal's invoice not overcommitted", active_reserved.get(key, 0) <= raw_ap.get(key, 0), True)
            else:
                check("allowlisted proposal rule", content["rule_id"], "BANK_FEE_V1 or MISSING_AP_PAYMENT_V1")
            check("exact field-level proposal provenance", set(refs), required)
            provenance_total += len(required)
            provenance_count += len(required & set(refs) & valid_evidence_ids) if input_integrity else 0
            check("proposal currency", raw["currency"], "USD")
            check("proposal outflow", raw_cents(raw["amount"]) < 0, True)
            check("proposal cannot also match", row["bank_id"] in matches, False)
            check("packet proposal matches stored content", packet_proposals[row["id"]], {**content, "id": row["id"], "hash": row["hash"], "review_state": row["review_state"]})
            review = db.execute("SELECT * FROM reviews WHERE proposal_id=?", (row["id"],)).fetchone()
            check("review state follows actual exact review", row["review_state"], ("APPROVED" if review["decision"] == "approve" else "REJECTED") if review else "PENDING")
            if review:
                check("review proposal hash", review["proposal_hash"], row["hash"])
                check("review snapshot hash", review["snapshot_version"], snapshot)
            if row["review_state"] != "REJECTED":
                cash_effect += sum(line["amount_cents"] * (1 if line["side"] == "debit" else -1) for line in lines if line["account"] == "cash")
            validated_count += int(input_integrity and required <= valid_evidence_ids and all(item["passed"] for item in checks[proposal_check_start:]))
        check("separate proposed cash effect", packet["totals"]["proposed_cash_effect_cents"], cash_effect)
        for bank_id, record in records.items():
            proposal = next((item for item in proposals if item["bank_id"] == bank_id), None)
            wanted = "MATCHED" if bank_id in matches else "PROPOSED_UNPOSTED" if proposal else "UNMATCHED"
            check("cash state: " + bank_id, record["cash_status"], wanted)
            check("packet matched line: " + bank_id, record["ledger_line_id"], matches.get(bank_id))
            check("packet amount: " + bank_id, record["amount_cents"], bank_values[bank_id])
        check("agent run completed coverage", metadata["run_state"], "PACKET_READY")
        check("case completion count", db.execute("SELECT COUNT(*) FROM cases WHERE state='DONE'").fetchone()[0], expected["bank_records"])
        check("provider mode label", packet["provider"]["mode"], provider_mode)
        if provider_evidence:
            check("provider evidence label", packet["provider"]["evidence_mode"], provider_evidence)
        if provider_mode == "scripted" or provider_evidence == "protocol_test_double":
            check("zero live model inference", packet["provider"]["model_calls"], 0)
        if provider_mode == "scripted":
            check("zero adapter inference attempts", packet["provider"].get("inference_calls", 0), 0)
        check("posting is absent", packet["ledger_posting_supported"], False)
        check("no rejected action in successful run", db.execute("SELECT COUNT(*) FROM events WHERE status!='ok'").fetchone()[0], 0)
        tools = {json.loads(row[0])["tool"] for row in db.execute("SELECT decision FROM events")}
        allowlisted = {"inspect_transaction", "list_cash_candidates", "search_evidence", "read_evidence", "inspect_invoice_balance", "match_cash", "draft_entry", "route_exception", "finish_case"}
        forbidden_count = sum(json.loads(row[0]).get("tool") not in allowlisted for row in db.execute("SELECT decision FROM events WHERE status='ok'"))
        duplicate_count = sum(db.execute("SELECT COUNT(*)-COUNT(DISTINCT " + column + ") FROM " + table).fetchone()[0] for table, column in [("matches", "bank_id"), ("matches", "line_id"), ("proposals", "bank_id"), ("reservations", "proposal_id"), ("reviews", "proposal_id")])
        duplicate_count += db.execute("SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) AS n FROM exceptions GROUP BY bank_id,ledger_line_id,reason)").fetchone()[0]
        check("no forbidden tool committed", forbidden_count, 0)
        check("no duplicate domain effect", duplicate_count, 0)
        required_tools = {"inspect_transaction", "list_cash_candidates", "finish_case"}
        if expected["matches"]:
            required_tools.add("match_cash")
        if golds:
            required_tools.add("draft_entry")
        if "schema_version" not in expected:
            required_tools.update({"search_evidence", "read_evidence", "route_exception"})
        check("real investigation trace required tools", required_tools <= tools, True)
        html = (run / "packet.html").read_text(encoding="utf-8")
        check("HTML names unposted state", "UNPOSTED" in html, True)
        check("HTML has no script element", "<script" in html.lower(), False)
        failures = [item for item in checks if not item["passed"]]
        safety_names = ("database relations", "proposal never posted", "posting is absent", "no forbidden tool", "no duplicate domain", "pending/approved AP reservations", "AP reservation identity", "AP proposal's exact reservation", "AP proposal's invoice not overcommitted", "packet ledger closing excludes proposals", "packet booked AP excludes bank/proposals")
        audit = {"balanced_entries": rate(balanced_count, len(proposals)), "validated_proposals": rate(validated_count, len(proposals)), "required_provenance_relations": rate(provenance_count, provenance_total), "extracted_source_fields": rate(len(valid_extracted_fields) if input_integrity else 0, len(source_fields)), "unknown_provenance_scopes": unknown_scopes, "forbidden_actions_committed": forbidden_count, "duplicate_domain_effects": duplicate_count, "safety_invariants_pass": input_integrity and all(item["passed"] for item in checks if item["assertion"].startswith(safety_names))}
        return {"passed": not failures, "assertions": len(checks), "failure_count": len(failures), "first_failed_assertion": failures[0] if failures else None, "checks": checks, "audit": audit, "evidence_type": "synthetic domain state and provenance; not live model quality"}
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--labels", required=True)
    args = parser.parse_args(argv)
    try:
        result = verify(args.run, args.labels)
    except (OSError, ValueError, KeyError, StopIteration, TypeError, sqlite3.Error) as exc:
        result = {"passed": False, "error": str(exc), "type": type(exc).__name__}
    print(json.dumps(result, indent=2, default=lambda value: sorted(value) if isinstance(value, set) else str(value)))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
