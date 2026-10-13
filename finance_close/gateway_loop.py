"""Strict Gateway loop using original host authority and persisted no-repeat barriers."""

import json
import time

from .domain import ForbiddenAction, IncompleteRun, SchemaViolation, object_hash
from .gateway import GatewayFailure
from .gateway_journal import GatewayJournal
from .gateway_tools import GatewayTools


def investigate_gateway(store, provider, cancelled=None, after_tool_commit=None):
    from .agent import cover_residuals
    try:
        journal = GatewayJournal(store, provider)
    except GatewayFailure as exc:
        # A crash can leave 'started' before the previous loop wrote its halt.
        # Keep that request intact and surface a durable hold without resubmission.
        cover_residuals(store, incomplete=True)
        with store.transaction():
            store.set_meta("run_state", "PROVIDER_HALTED")
            store.set_meta("gateway_failure_class", exc.kind)
        raise
    if store.meta("run_state") == "PACKET_READY":
        return
    limits = json.loads(store.meta("rule"))["limits"]
    prior = float(store.meta("run_elapsed_seconds") or 0)
    started = time.monotonic()
    elapsed = lambda: prior + time.monotonic() - started
    with store.transaction():
        store.set_meta("run_state", "INVESTIGATING")
    try:
        if store.db.execute("SELECT COUNT(*) FROM cases").fetchone()[0] > limits["cases_per_run"]:
            raise IncompleteRun("Case budget exceeded")
        for row in store.db.execute("SELECT bank_id FROM cases WHERE state='OPEN' ORDER BY bank_id").fetchall():
            bank_id, tools = row[0], GatewayTools(store, row[0])
            seen_decisions = {object_hash(item["decision"]) for item in store.history(bank_id) if item["status"] == "ok"}
            while store.db.execute("SELECT state FROM cases WHERE bank_id=?", (bank_id,)).fetchone()[0] != "DONE":
                if cancelled and cancelled():
                    raise KeyboardInterrupt
                attempts = store.db.execute("SELECT COUNT(*) FROM provider_attempts WHERE bank_id=?", (bank_id,)).fetchone()[0]
                total = store.db.execute("SELECT COUNT(*) FROM provider_attempts").fetchone()[0]
                tools_done = sum(item["status"] == "ok" for item in store.history(bank_id))
                if attempts >= limits["decisions_per_case"] or tools_done >= limits["tools_per_case"] or \
                        total >= limits["decisions_per_run"] or elapsed() >= limits["deadline_seconds"]:
                    raise IncompleteRun("Persisted decision/tool/time budget exhausted")
                sequence = journal.start(bank_id, elapsed())
                try:
                    decision = provider.next_decision({"bank_id": bank_id, "history": journal.history(bank_id),
                                                       "snapshot_version": store.meta("snapshot_hash"),
                                                       "remaining_seconds": limits["deadline_seconds"] - elapsed(),
                                                       "cancelled": cancelled})
                    journal.record(sequence, "response_ready", elapsed())
                    if cancelled and cancelled():
                        raise GatewayFailure("cancelled")
                    if elapsed() >= limits["deadline_seconds"]:
                        raise GatewayFailure("deadline_uncertain")
                    key = object_hash(decision)
                    if key in seen_decisions:
                        raise GatewayFailure("repeated_decision")
                    if provider.last_call["id"] in {h["call"]["id"] for h in journal.history(bank_id)}:
                        raise GatewayFailure("duplicate_call_id")
                    result = tools.dispatch(decision)
                    event_sequence = store.db.execute("SELECT MAX(sequence) FROM events").fetchone()[0]
                    journal.record(sequence, "ok", elapsed(), event_sequence=event_sequence, accepted=True)
                    seen_decisions.add(key)
                except (ForbiddenAction, SchemaViolation):
                    journal.record(sequence, "host_denied", elapsed(), failure="host_denied")
                    raise GatewayFailure("host_denied") from None
                except GatewayFailure as exc:
                    journal.record(sequence, exc.kind, elapsed(), failure=exc.kind)
                    raise
                except KeyboardInterrupt:
                    journal.record(sequence, "cancelled", elapsed(), failure="cancelled")
                    raise
                if after_tool_commit:
                    after_tool_commit(store, bank_id)
        cover_residuals(store)
        with store.transaction():
            store.set_meta("run_state", "PACKET_READY")
    except GatewayFailure as exc:
        cover_residuals(store, incomplete=True)
        with store.transaction():
            store.set_meta("run_state", "CANCELLED" if exc.kind == "cancelled" else "PROVIDER_HALTED")
            store.set_meta("gateway_failure_class", exc.kind)
        raise
    except (KeyboardInterrupt, IncompleteRun) as exc:
        cover_residuals(store, incomplete=True)
        with store.transaction():
            store.set_meta("run_state", "CANCELLED" if isinstance(exc, KeyboardInterrupt) else "BUDGET_EXHAUSTED")
        raise
    finally:
        with store.transaction():
            store.set_meta("run_elapsed_seconds", elapsed())
