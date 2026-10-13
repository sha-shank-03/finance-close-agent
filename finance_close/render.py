"""Static, escaped evidence packet. Booked and proposed cash remain separate."""

import html
import json
import os
from pathlib import Path

from .domain import canonical
from .ap import balance


def packet(store):
    db = store.db
    manifest = json.loads(store.meta("manifest"))
    bank_values = {r['id']: r['amount_cents'] for r in db.execute("SELECT * FROM bank") if json.loads(r['data'])['currency'] == 'USD'}
    cash_values = {r['line_id']: r['signed_cents'] for r in db.execute("SELECT * FROM ledger WHERE account='cash'") if json.loads(r['data'])['currency'] == 'USD' and json.loads(r['data'])['in_period']}
    matches = dict(db.execute("SELECT bank_id,line_id FROM matches"))
    bank_total, ledger_total = sum(bank_values.values()), sum(cash_values.values())
    unmatched_bank = sum(amount for key, amount in bank_values.items() if key not in matches)
    unmatched_ledger = sum(amount for key, amount in cash_values.items() if key not in matches.values())
    exceptions = [dict(row) for row in db.execute("SELECT * FROM exceptions ORDER BY id")]
    for item in exceptions:
        item["evidence_ids"] = json.loads(item["evidence_ids"])
        item["status"] = "OPEN"
    bank_records = []
    for row in db.execute("SELECT b.*,c.state FROM bank b JOIN cases c ON c.bank_id=b.id ORDER BY b.id"):
        bank = json.loads(row["data"])
        match = db.execute("SELECT line_id FROM matches WHERE bank_id=?", (row["id"],)).fetchone()
        proposed = db.execute("SELECT id FROM proposals WHERE bank_id=?", (row["id"],)).fetchone()
        reasons = [item["reason"] for item in exceptions if item["bank_id"] == row["id"]]
        hold = any(reason in {'MISSING_INVOICE','CONFLICTING_EVIDENCE','INCOMPLETE_HISTORY','OVERPAYMENT'} for reason in reasons)
        bank_records.append({"id": row["id"], "date": bank["date"], "amount_cents": row["amount_cents"], "currency": bank["currency"], "reference": bank["reference"], "memo": bank["memo"], "cash_status": "MATCHED" if match else "PROPOSED_UNPOSTED" if proposed else "UNMATCHED", "ledger_line_id": match[0] if match else None, "invoice_status": "OPEN_HOLD" if hold else "SUPPORTED" if bank["transaction_type"] == "vendor_payment" else "NOT_REQUIRED", "exception_reasons": reasons, "case_state": row["state"]})
    proposals = []
    for row in db.execute("SELECT * FROM proposals ORDER BY id"):
        content = json.loads(row["content"])
        proposals.append({**content, "id": row["id"], "hash": row["hash"], "review_state": row["review_state"]})
    evidence = [dict(row) for row in db.execute("SELECT e.*,s.sha256 FROM evidence e JOIN sources s ON s.path=e.source_path ORDER BY e.id")]
    bank_close = manifest["bank_opening_cents"] + bank_total
    ledger_close = manifest["ledger_opening_cents"] + ledger_total
    value = {"schema_version": 2, "title": "Fictional reconciliation packet — proposals remain unposted", "snapshot_version": store.meta("snapshot_hash"), "rule_hash": store.meta("rule_hash"), "run_state": store.meta("run_state"), "period": [manifest["period_start"], manifest["period_end"]], "currency": "USD", "provider": {"mode": store.meta("provider"), "model_calls": int(store.meta("model_calls")), "decision_count": db.execute("SELECT COUNT(*) FROM events").fetchone()[0], "tool_calls": db.execute("SELECT COUNT(*) FROM events WHERE status='ok'").fetchone()[0], "evidence_claim": "scripted workflow integration; no model inference"}, "totals": {"bank_closing_cents": bank_close, "ledger_closing_cents": ledger_close, "booked_difference_cents": bank_close - ledger_close, "unmatched_bank_cents": unmatched_bank, "unmatched_ledger_cents": unmatched_ledger, "bridge_residual_cents": bank_close - ledger_close - (unmatched_bank - unmatched_ledger), "proposed_cash_effect_cents": sum(-line["amount_cents"] if line["side"] == "credit" else line["amount_cents"] for item in proposals if item["review_state"] != "REJECTED" for line in item["lines"] if line["account"] == "cash")}, "bank_records": bank_records, "exceptions": exceptions, "proposals": proposals, "evidence": evidence, "sources": [dict(row) for row in db.execute("SELECT path,sha256 FROM sources ORDER BY path")], "reviews": [dict(row) for row in db.execute("SELECT * FROM reviews ORDER BY proposal_id")], "ledger_posting_supported": False}

    value["ap_balances"] = [balance(store, row[0]) for row in db.execute("SELECT invoice_key FROM invoices ORDER BY invoice_key")]
    value["excluded_bank_currencies"] = sorted({json.loads(row[0])["currency"] for row in db.execute("SELECT data FROM bank") if json.loads(row[0])["currency"] != "USD"})
    attempts = [{**dict(row), "usage": json.loads(row["usage"]) if row["usage"] else None} for row in db.execute("SELECT * FROM provider_attempts ORDER BY sequence")]
    value["provider"].update({"inference_calls": int(store.meta("inference_calls") or 0), "attempts": attempts, "evidence_mode": store.meta("provider_evidence_mode") or "scripted", "config_hash": store.meta("provider_config_hash")})
    value["provider"]["evidence_claim"] = "scripted workflow; no model inference" if value["provider"]["mode"] == "scripted" else "local protocol double; no live model quality claim" if value["provider"]["evidence_mode"] == "protocol_test_double" else "live local provider; quality unverified"
    if value["provider"]["mode"] == "gateway":
        value["provider"].update({"prompt_version": store.meta("gateway_prompt_version"),
                                  "code_hash": store.meta("gateway_code_hash"),
                                  "run_id": store.meta("gateway_run_id"),
                                  "failure_class": store.meta("gateway_failure_class"),
                                  "evidence_claim": "Gateway function-call local double; synthetic decisions/usage, no live model quality claim" if value["provider"]["evidence_mode"] == "local-double" else "Gateway live inference; independent outcome verification required"})
    return value



def money(amount):
    return f"{'-' if amount < 0 else ''}${abs(amount) // 100:,}.{abs(amount) % 100:02d}"


def render_html(value):
    esc = lambda text: html.escape(str(text), quote=True)
    totals = value["totals"]
    rows = "".join(f"<tr><td>{esc(r['id'])}</td><td>{money(r['amount_cents']) if r.get('currency', 'USD') == 'USD' else esc(str(r['amount_cents']) + ' cents ' + r['currency'])}</td><td>{esc(r['cash_status'])}</td><td>{esc(r['invoice_status'])}</td><td>{esc(', '.join(r['exception_reasons']))}</td><td>{esc(r['memo'])}</td></tr>" for r in value["bank_records"])
    proposals = []
    for item in value["proposals"]:
        lines = "".join(f"<li>{esc(line['side'])} {esc(line['account'])}: {money(line['amount_cents'])}</li>" for line in item["lines"])
        refs = " ".join(f'<a href="#{esc(ev)}">source field</a>' for ev in item["evidence_ids"])
        proposals.append(f"<article><h3>{esc(item['rule_id'])} — {esc(item['review_state'])}, UNPOSTED</h3><p>Bank record {esc(item['bank_id'])}</p><ul>{lines}</ul><p>{refs}</p><p>Proposal hash: <code>{esc(item['hash'])}</code></p></article>")
    holds = "".join(f"<li>{esc(item['bank_id'] or item['ledger_line_id'])}: {esc(item['reason'])}, OPEN, exposure {money(item['exposure_cents'])}</li>" for item in value["exceptions"])
    sources = "".join(f"<tr id='{esc(item['id'])}'><td>{esc(item['source_path'])}</td><td>{esc(item['locator'])}</td><td>{esc(item['value'])}</td><td><code>{esc(item['sha256'])}</code></td></tr>" for item in value["evidence"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>Fictional reconciliation packet</title><style>body{{font:16px system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;color:#172c38}}h1,h2{{color:#12384a}}table{{width:100%;border-collapse:collapse;margin:20px 0}}td,th{{border:1px solid #ccd6dc;padding:9px;text-align:left;overflow-wrap:anywhere}}code{{font-size:12px;overflow-wrap:anywhere}}article{{background:#f0f5f7;padding:16px;margin:16px 0}}.note{{background:#fff4cf;padding:14px}}</style></head><body><h1>Fictional reconciliation packet</h1><p class="note">{esc(value["provider"]["evidence_claim"])}. Every proposal and review remains UNPOSTED. This packet does not certify a completed financial close.</p><p>Period: {esc(' to '.join(value['period']))}. Snapshot: <code>{esc(value['snapshot_version'])}</code></p><h2>Booked cash and reconciliation bridge</h2><p>Bank closing: <strong>{money(totals['bank_closing_cents'])}</strong>. Immutable ledger closing: <strong>{money(totals['ledger_closing_cents'])}</strong>.</p><p>Booked difference {money(totals['booked_difference_cents'])} = unmatched bank {money(totals['unmatched_bank_cents'])} − unmatched ledger {money(totals['unmatched_ledger_cents'])}. Bridge residual: {money(totals['bridge_residual_cents'])}.</p><p>Separate unposted proposed cash effect: {money(totals['proposed_cash_effect_cents'])}. Booked balances above exclude proposals.</p><h2>All bank records</h2><table><thead><tr><th>ID</th><th>Amount</th><th>Cash status</th><th>Invoice evidence</th><th>Open reasons</th><th>Memo</th></tr></thead><tbody>{rows}</tbody></table><h2>Open evidence and residual holds</h2><ul>{holds or '<li>No open holds</li>'}</ul><h2>Proposals for review</h2>{''.join(proposals) or '<p>No proposals</p>'}<h2>Field-level evidence</h2><table><thead><tr><th>Source</th><th>Locator</th><th>Original field value</th><th>SHA-256</th></tr></thead><tbody>{sources}</tbody></table></body></html>"""


def write_packet(store, out, before_rename=None):
    out = Path(out)
    value = packet(store)
    for name, text in [("packet.json", json.dumps(value, indent=2, ensure_ascii=False) + "\n"), ("packet.html", render_html(value))]:
        temp = out / (name + ".tmp")
        temp.write_text(text, encoding="utf-8")
        if before_rename:
            before_rename()
        os.replace(temp, out / name)
    trace = [{"sequence": r["sequence"], "bank_id": r["bank_id"], "decision": json.loads(r["decision"]), "result": json.loads(r["result"]), "status": r["status"], "created_at": r["created_at"]} for r in store.db.execute("SELECT * FROM events ORDER BY sequence")]
    (out / "trace.json").write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    if store.meta("provider") == "gateway":
        from .gateway_journal import export_metrics
        export_metrics(store, out)
    return value
