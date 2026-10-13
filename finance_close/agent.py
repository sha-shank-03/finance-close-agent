"""Persisted, bounded single-case provider loop with host-owned residual coverage."""

import json
import time

from .domain import ForbiddenAction, IncompleteRun, SchemaViolation, canonical, object_hash
from .ollama import ProviderFailure
from .providers import provider_config
from .store import utc_now
from .tools import Tools, wire_schemas


def cover_residuals(store, incomplete=False, tools_factory=Tools):
    with store.transaction():
        store.db.execute("DELETE FROM exceptions WHERE reason='UNMATCHED_LEDGER' AND ledger_line_id IN (SELECT line_id FROM matches)")
        for row in store.db.execute("SELECT line_id,signed_cents,data FROM ledger WHERE account='cash' AND line_id NOT IN (SELECT line_id FROM matches)").fetchall():
            line = json.loads(row["data"])
            if line["currency"] != "USD" or not line["in_period"]:
                continue
            key = "exception-" + object_hash([row["line_id"], "UNMATCHED_LEDGER"])
            store.db.execute("INSERT OR IGNORE INTO exceptions VALUES (?,NULL,?,?,?,?)", (key, row["line_id"], "UNMATCHED_LEDGER", abs(row["signed_cents"]), canonical([line["evidence"]["amount"]])))
        if incomplete:
            for row in store.db.execute("SELECT bank_id FROM cases WHERE state='OPEN'").fetchall():
                tools = tools_factory(store, row[0])
                bank = store.bank(row[0])
                ids = [bank["evidence"]["amount"], bank["evidence"]["reference"]]
                for reason in tools.required_flags():
                    tools.add_exception(reason, ids)
                if not store.db.execute("SELECT 1 FROM matches WHERE bank_id=?", (row[0],)).fetchone() and not store.db.execute("SELECT 1 FROM proposals WHERE bank_id=?", (row[0],)).fetchone():
                    tools.add_exception("UNMATCHED_CASH", ids)


def investigate(store, provider, cancelled=None, after_tool_commit=None, tools_factory=Tools):
    if provider.mode == "gateway":
        from .gateway_loop import investigate_gateway
        return investigate_gateway(store, provider, cancelled, after_tool_commit)
    if provider.mode not in {"scripted", "ollama"}:
        raise ForbiddenAction("Unsupported provider mode")
    config_hash = object_hash(provider_config(provider))
    old_config = store.meta("provider_config_hash")
    if old_config and old_config != config_hash:
        raise ForbiddenAction("Resume provider configuration differs from the original run")
    if store.meta("run_state") == "PACKET_READY":
        return
    limits = json.loads(store.meta("rule"))["limits"]
    elapsed_before = float(store.meta("run_elapsed_seconds") or "0")
    started = time.monotonic()
    def elapsed():
        return elapsed_before + time.monotonic() - started
    with store.transaction():
        store.set_meta("provider_config_hash", config_hash)
        store.set_meta("provider", provider.mode)
        store.set_meta("provider_evidence_mode", getattr(provider, "evidence_mode", "scripted"))
        store.set_meta("run_state", "INVESTIGATING")
    try:
        total_cases = store.db.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        if total_cases > limits["cases_per_run"]:
            raise IncompleteRun("Case budget exceeded; no rows silently dropped")
        cases = store.db.execute("SELECT bank_id FROM cases WHERE state='OPEN' ORDER BY bank_id").fetchall()
        for row in cases:
            bank_id, tools = row[0], tools_factory(store, row[0])
            repeated = {}
            for item in store.history(bank_id):
                if item["status"] == "ok":
                    key = object_hash(item["decision"])
                    repeated[key] = repeated.get(key, 0) + 1
            retry_counts = {"transport": 0, "schema": 0}
            forbidden_seen = False
            for attempt in store.db.execute("SELECT status FROM provider_attempts WHERE bank_id=?", (bank_id,)):
                if attempt[0] in retry_counts:
                    retry_counts[attempt[0]] += 1
                forbidden_seen = forbidden_seen or attempt[0] == "forbidden"
            while store.db.execute("SELECT state FROM cases WHERE bank_id=?", (bank_id,)).fetchone()[0] != "DONE":
                if forbidden_seen:
                    raise IncompleteRun("A forbidden action is not retried on resume")
                if any(count > 1 for count in retry_counts.values()):
                    raise IncompleteRun("Persisted provider retry/correction budget exhausted")
                if cancelled and cancelled():
                    raise KeyboardInterrupt("Cancellation requested")
                history = store.history(bank_id)
                attempts = store.db.execute("SELECT COUNT(*) FROM provider_attempts WHERE bank_id=?", (bank_id,)).fetchone()[0]
                total = store.db.execute("SELECT COUNT(*) FROM provider_attempts").fetchone()[0]
                successful_tools = sum(item["status"] == "ok" for item in history)
                if attempts >= limits["decisions_per_case"] or successful_tools >= limits["tools_per_case"] or total >= limits["decisions_per_run"] or elapsed() >= limits["deadline_seconds"]:
                    raise IncompleteRun("Decision/time budget exhausted")
                with store.transaction():
                    cursor = store.db.execute("INSERT INTO provider_attempts(bank_id,status,created_at) VALUES (?,'started',?)", (bank_id, utc_now()))
                    sequence = cursor.lastrowid
                    store.set_meta("run_elapsed_seconds", elapsed())
                    if provider.mode == "ollama":
                        store.set_meta("inference_calls", int(store.meta("inference_calls")) + 1)
                        if getattr(provider, "evidence_mode", "live_local_unverified") != "protocol_test_double":
                            store.set_meta("model_calls", int(store.meta("model_calls")) + 1)
                decision, attempt_status = None, "ok"
                try:
                    decision = provider.next_decision({"bank_id": bank_id, "history": history, "tool_schemas": wire_schemas(), "snapshot_version": store.meta("snapshot_hash"), "remaining_seconds": limits["deadline_seconds"] - elapsed()})
                    if cancelled and cancelled():
                        raise KeyboardInterrupt("Cancellation requested")
                    if elapsed() >= limits["deadline_seconds"]:
                        raise IncompleteRun("Decision/time budget exhausted")
                    key = object_hash(decision)
                    repeated[key] = repeated.get(key, 0) + 1
                    if repeated[key] > 2:
                        raise IncompleteRun("Repeated decision made no progress")
                    tools.dispatch(decision)
                except ProviderFailure as exc:
                    attempt_status = "transport" if exc.retryable else "schema"
                    retry_counts[attempt_status] += 1
                    with store.transaction():
                        store.event(bank_id, {"tool": "provider_response", "arguments": {}}, {"error": str(exc)}, status="rejected")
                    if retry_counts[attempt_status] > 1:
                        raise IncompleteRun("Provider retry/correction budget exhausted") from exc
                except SchemaViolation as exc:
                    attempt_status = "schema"
                    retry_counts["schema"] += 1
                    with store.transaction():
                        store.event(bank_id, decision if isinstance(decision, dict) else {"invalid_decision_type": type(decision).__name__}, {"error": str(exc)}, status="rejected")
                    if provider.mode == "scripted" or retry_counts["schema"] > 1:
                        raise IncompleteRun("Provider action rejected; unresolved state preserved") from exc
                except (ForbiddenAction, TypeError, ValueError) as exc:
                    attempt_status = "forbidden"
                    with store.transaction():
                        store.event(bank_id, decision if isinstance(decision, dict) else {"invalid_decision_type": type(decision).__name__}, {"error": str(exc)}, status="rejected")
                    raise IncompleteRun("Provider action rejected without retry; unresolved state preserved") from exc
                except KeyboardInterrupt:
                    attempt_status = "cancelled"
                    raise
                except IncompleteRun:
                    attempt_status = "budget"
                    raise
                finally:
                    with store.transaction():
                        store.db.execute("UPDATE provider_attempts SET status=?,usage=? WHERE sequence=?", (attempt_status, canonical(getattr(provider, "last_usage", None)), sequence))
                        store.set_meta("run_elapsed_seconds", elapsed())
                if attempt_status == "ok" and after_tool_commit:
                    after_tool_commit(store, bank_id)
        cover_residuals(store, tools_factory=tools_factory)
        with store.transaction():
            store.set_meta("run_state", "PACKET_READY")
    except KeyboardInterrupt:
        cover_residuals(store, incomplete=True, tools_factory=tools_factory)
        with store.transaction():
            store.set_meta("run_state", "CANCELLED")
        raise
    except IncompleteRun:
        cover_residuals(store, incomplete=True, tools_factory=tools_factory)
        with store.transaction():
            store.set_meta("run_state", "BUDGET_EXHAUSTED")
        raise
    finally:
        with store.transaction():
            store.set_meta("run_elapsed_seconds", elapsed())
