"""Independent raw-source/SQLite checker for the authored U1 AP proposal journey.

Imports no actor, parser, tools, rule validators or accounting helpers.
"""

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote


def money(text):
    if not re.fullmatch(r"-?(0|[1-9][0-9]*)(\.[0-9]{1,2})?", text):
        raise ValueError("Invalid source money")
    return int(Decimal(text) * 100)


def hash_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def verify(run, source, review_state="PENDING"):
    run, source = Path(run).resolve(), Path(source).resolve()
    paths = [source / name for name in ["manifest.json", "bank.csv", "ledger.csv"]] + sorted((source / "invoices").glob("*.txt"))
    raw = {p.relative_to(source).as_posix(): p.read_bytes() for p in paths}
    manifest = json.loads(raw["manifest.json"])
    bank = list(csv.DictReader(raw["bank.csv"].decode().splitlines()))
    ledger = list(csv.DictReader(raw["ledger.csv"].decode().splitlines()))
    fields = {}
    for line in raw["invoices/original.txt"].decode().splitlines():
        key, _, value = line.partition(":"); fields[key] = value.strip()
    if len(bank) != 1:
        raise ValueError("U1 checker supports its one-bank-row authored journey only")
    txn = bank[0]
    amount = -money(txn["amount"])
    invoice_key = fields["Vendor Code"] + ":" + fields["Invoice Number"]
    sign = lambda row: money(row["amount"]) * (1 if row["side"] == "debit" else -1)
    ap_booked = -sum(sign(r) for r in ledger if r["account"] == "accounts_payable" and r["invoice_id"] == fields["Invoice Number"] and r["vendor_id"] == fields["Vendor Code"])
    cash = sum(sign(r) for r in ledger if r["account"] == "cash" and manifest["period_start"] <= r["date"] <= manifest["period_end"])
    source_hashes = {name: hashlib.sha256(data).hexdigest() for name, data in raw.items()}
    snapshot = hash_json([[name, source_hashes[name]] for name in raw])
    checks = {}
    db = sqlite3.connect("file:" + quote((run / "state.sqlite").as_posix(), safe="/:") + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        meta = dict(db.execute("SELECT key,value FROM metadata"))
        checks["explicit_fictional_usd_source"] = manifest["fictional"] is True and manifest["currency"] == "USD"
        checks["exact_invoice_total_and_partial_history"] = money(fields["Invoice Total"]) == 100000 and ap_booked == 80000 and amount == 60000
        checks["explicit_complete_history"] = invoice_key in manifest["ap_history_complete"]
        checks["exact_reference_alias"] = re.sub(r"[ _-]", "", fields["Bank Reference"].upper()) == re.sub(r"[ _-]", "", txn["reference"].upper())
        checks["source_hash_snapshot"] = meta["snapshot_hash"] == snapshot
        checks["sources_unchanged"] = all(r["raw"] == raw[r["path"]] and r["sha256"] == source_hashes[r["path"]] for r in db.execute("SELECT * FROM sources")) and db.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == len(raw)
        expected_ledger = {(r["line_id"], r["entry_id"], r["account"], r["side"], money(r["amount"]), sign(r)) for r in ledger}
        checks["ledger_immutable_raw_values"] = {tuple(r) for r in db.execute("SELECT line_id,entry_id,account,side,amount_cents,signed_cents FROM ledger")} == expected_ledger
        ledger_by_id = {r["line_id"]:r for r in ledger}
        checks["ledger_parsed_identity_unchanged"] = all(
            all(json.loads(r["data"])[key] == ledger_by_id[r["line_id"]][key]
                for key in ["line_id","entry_id","date","account","side","currency","vendor_id","invoice_id","reference"])
            for r in db.execute("SELECT line_id,data FROM ledger"))
        checks["bank_immutable_raw_values"] = [tuple(r) for r in db.execute("SELECT id,amount_cents FROM bank")] == [(txn["transaction_id"], -amount)]
        bank_data = json.loads(db.execute("SELECT data FROM bank").fetchone()[0])
        checks["bank_parsed_identity_unchanged"] = bank_data["id"] == txn["transaction_id"] and all(
            bank_data[key] == txn[key] for key in ["date","currency","vendor_id","reference","transaction_type","memo"])
        checks["rule_hash_from_original_bytes"] = meta["rule_hash"] == hashlib.sha256(
            (Path(__file__).resolve().parent.parent/"rules/v1.json").read_bytes()).hexdigest()
        checks["no_booked_cash_or_ap_change"] = cash == 0 and db.execute("SELECT SUM(signed_cents) FROM ledger WHERE account='accounts_payable'").fetchone()[0] == -ap_booked
        rows = db.execute("SELECT * FROM proposals").fetchall()
        checks["exactly_one_required_proposal"] = len(rows) == 1
        checks["no_false_completion_or_hold"] = meta["run_state"] == "PACKET_READY" and db.execute("SELECT COUNT(*) FROM exceptions").fetchone()[0] == 0
        checks["zero_live_model_calls"] = meta["provider"] == "gateway" and meta["provider_evidence_mode"] == "local-double" and meta["model_calls"] == "0"
        if len(rows) == 1:
            proposal = rows[0]; content = json.loads(proposal["content"])
            lines = [dict(r) for r in db.execute("SELECT account,side,amount_cents FROM proposal_lines WHERE proposal_id=? ORDER BY number", (proposal["id"],))]
            wanted = [{"account":"accounts_payable","side":"debit","amount_cents":amount}, {"account":"cash","side":"credit","amount_cents":amount}]
            checks["exact_balanced_lines"] = lines == wanted == content["lines"] and sum(r["amount_cents"]*(1 if r["side"]=="debit" else -1) for r in lines) == 0
            checks["content_hash"] = proposal["hash"] == hash_json(content)
            checks["pending_or_exact_human_review"] = proposal["review_state"] == review_state
            checks["unposted_only"] = content["posted"] is False and content["rule_id"] == "MISSING_AP_PAYMENT_V1" and content["bank_id"] == txn["transaction_id"] and content["invoice_key"] == invoice_key
            checks["content_bound_to_source"] = content["snapshot_version"] == snapshot and content["rule_hash"] == meta["rule_hash"]
            reservations = [tuple(r) for r in db.execute("SELECT proposal_id,invoice_key,amount_cents FROM reservations")]
            checks["exact_reservation_not_booked"] = reservations == [(proposal["id"],invoice_key,amount)] and ap_booked-amount == 20000
            refs = {r[0] for r in db.execute("SELECT evidence_id FROM proposal_evidence WHERE proposal_id=?", (proposal["id"],))}
            checks["declared_evidence_links_exact"] = refs == set(content["evidence_ids"])
            required_locators = {("bank.csv","row:2:"+key) for key in
                                 ["transaction_id","date","amount","currency","transaction_type","vendor_id","reference"]}
            required_locators.add(("manifest.json","json:ap_history_complete"))
            for index,row in enumerate(ledger,2):
                if row["account"] == "accounts_payable":
                    required_locators.update(("ledger.csv",f"row:{index}:"+key) for key in
                                            ["entry_id","line_id","date","account","side","amount","currency","vendor_id","invoice_id"])
            for index,line in enumerate(raw["invoices/original.txt"].decode().splitlines(),1):
                label,_,_ = line.partition(":")
                if label != "Notes": required_locators.add(("invoices/original.txt",f"line:{index}:"+label))
            checks["all_required_source_evidence_exact"] = refs == {
                "ev-"+hash_json([path,source_hashes[path],locator]) for path,locator in required_locators}
            fields_seen = []
            for evidence in db.execute("SELECT * FROM evidence"):
                wanted_id = "ev-" + hash_json([evidence["source_path"],source_hashes[evidence["source_path"]],evidence["locator"]])
                locator = evidence["locator"].split(":",2)
                if locator[0] == "row":
                    source_rows = bank if evidence["source_path"] == "bank.csv" else ledger
                    wanted_value = source_rows[int(locator[1])-2][locator[2]]
                elif locator[0] == "line":
                    source_line = raw[evidence["source_path"]].decode().splitlines()[int(locator[1])-1]
                    label, _, wanted_value = source_line.partition(":")
                    checks["original_label:"+evidence["id"]] = label == locator[2]
                    wanted_value = wanted_value.strip()
                elif locator[0] == "json":
                    wanted_value = manifest[locator[1]]
                    if isinstance(wanted_value,list):
                        wanted_value = json.dumps(sorted(wanted_value),separators=(",",":"))
                    else:
                        wanted_value = str(wanted_value)
                else:
                    raise ValueError("Unknown raw provenance locator")
                if evidence["id"] in refs:
                    fields_seen.append((evidence["source_path"],evidence["locator"],evidence["value"]))
                checks["evidence_id:"+evidence["id"]] = evidence["id"] == wanted_id
                checks["evidence_value:"+evidence["id"]] = evidence["value"] == wanted_value
            checks["invoice_total_and_bank_amount_provenance"] = ("invoices/original.txt","line:4:Invoice Total","1000.00") in fields_seen and ("bank.csv","row:2:amount","-600.00") in fields_seen
            reviews = db.execute("SELECT * FROM reviews").fetchall()
            checks["review_outside_model"] = (len(reviews)==0 if review_state=="PENDING" else len(reviews)==1 and reviews[0]["decision"]=="approve" and reviews[0]["proposal_hash"]==proposal["hash"] and reviews[0]["snapshot_version"]==snapshot)
        requests = db.execute("SELECT * FROM gateway_requests ORDER BY sequence").fetchall()
        checks["requests_and_native_observations_persisted"] = len(requests)>=6 and all(r["status"]=="ok" and r["call"] and r["event_sequence"] for r in requests)
        allowed = {"inspect_transaction","list_cash_candidates","search_evidence","read_evidence",
                   "inspect_invoice_balance","match_cash","draft_entry","route_exception","finish_case"}
        observations = True
        for request in requests:
            if not request["call"] or not request["event_sequence"]:
                observations=False;continue
            call=json.loads(request["call"])
            event=db.execute("SELECT * FROM events WHERE sequence=?",(request["event_sequence"],)).fetchone()
            decision={"tool":call["function"]["name"],"arguments":json.loads(call["function"]["arguments"])}
            observations &= bool(event and event["bank_id"]==txn["transaction_id"] and event["status"]=="ok" and
                                 json.loads(event["decision"])==decision and decision["tool"] in allowed and
                                 decision["arguments"]["bank_id"]==txn["transaction_id"])
        checks["native_calls_link_exact_host_events"] = observations
        checks["one_attempt_per_request_no_retry"] = db.execute("SELECT COUNT(*) FROM provider_attempts").fetchone()[0] == len(requests)
        checks["synthetic_usage_unknown_actual_cost"] = all(json.loads(r["receipt"]).get("usage_synthetic") is True and json.loads(r["receipt"]).get("actual_cost_usd") is None for r in requests)
        packet = json.loads((run / "packet.json").read_text(encoding="utf-8"))
        checks["packet_booked_and_proposed_separate"] = packet["totals"]["bank_closing_cents"] == money(manifest["bank_opening"])-amount and packet["totals"]["ledger_closing_cents"] == money(manifest["ledger_opening"])+cash and packet["totals"]["proposed_cash_effect_cents"] == -amount and packet["ledger_posting_supported"] is False
        checks["packet_agrees_with_queue"] = len(packet["proposals"])==1 and packet["proposals"][0]["review_state"]==review_state and packet["proposals"][0]["posted"] is False
        if len(rows)==1:
            checks["packet_proposal_exact_content"] = packet["proposals"] == [{**content,"id":proposal["id"],"hash":proposal["hash"],"review_state":review_state}]
    finally:
        db.close()
    return {"passed": all(checks.values()), "assertions": len(checks), "checks": checks,
            "failures": [k for k,v in checks.items() if not v], "evidence_mode":"local-double",
            "independent_actor_imports":0,"live_model_calls":0,"unsafe_committed_actions":0 if all(checks.values()) else None,
            "scope":"One exposed authored U1 journey, not general accounting quality or unseen/model evaluation."}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",required=True);parser.add_argument("--input",required=True)
    parser.add_argument("--review-state",choices=["PENDING","APPROVED"],default="PENDING")
    parser.add_argument("--out",required=True)
    args=parser.parse_args(argv)
    try: report=verify(args.run,args.input,args.review_state)
    except (ValueError,KeyError,IndexError,OSError,sqlite3.Error,TypeError): report={"passed":False,"error":"Independent raw-state/source check failed"}
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({"passed":report['passed'],"assertions":report.get('assertions'),"failures":report.get('failures')}))
    return 0 if report['passed'] else 1


if __name__=="__main__": raise SystemExit(main())
