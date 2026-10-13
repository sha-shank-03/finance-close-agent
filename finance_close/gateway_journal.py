"""Persisted local request bounds and allowlisted metrics; not a global spend broker."""

import json
import math
import uuid
from decimal import Decimal
from pathlib import Path

from .domain import ForbiddenAction, canonical, digest, object_hash
from .gateway import GatewayFailure, PROMPT_HASH, PROMPT_VERSION
from .store import utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS gateway_requests(
 sequence INTEGER PRIMARY KEY REFERENCES provider_attempts(sequence),
 bank_id TEXT NOT NULL REFERENCES bank(id), status TEXT NOT NULL,
 reserved_usd TEXT NOT NULL, receipt TEXT NOT NULL,
 event_sequence INTEGER REFERENCES events(sequence), call TEXT);
"""


def code_version():
    root = Path(__file__).resolve().parent
    return object_hash([[p.name, digest(p.read_bytes())] for p in sorted(root.glob("*.py"))])


def require_resumable(statuses):
    # Includes a crash with 'started'/'response_ready': never blindly resubmit.
    if any(status != "ok" for status in statuses):
        raise GatewayFailure("resume_blocked")


class GatewayJournal:
    def __init__(self, store, provider):
        self.store, self.provider = store, provider
        store.db.executescript(SCHEMA)
        config_hash = object_hash(provider.config)
        version = code_version()
        if store.meta("provider_config_hash") and store.meta("provider_config_hash") != config_hash:
            raise ForbiddenAction("Resume provider configuration differs")
        if store.meta("gateway_code_hash") and store.meta("gateway_code_hash") != version:
            raise ForbiddenAction("Resume Gateway source version differs")
        require_resumable([r[0] for r in store.db.execute("SELECT status FROM gateway_requests")])
        with store.transaction():
            store.set_meta("gateway_run_id", store.meta("gateway_run_id") or str(uuid.uuid4()))
            store.set_meta("gateway_code_hash", version)
            store.set_meta("gateway_version", "u1-candidate-v1")
            store.set_meta("gateway_prompt_version", PROMPT_VERSION)
            store.set_meta("gateway_prompt_hash", PROMPT_HASH)
            store.set_meta("provider_config_hash", config_hash)
            store.set_meta("gateway_config", canonical(provider.config))
            store.set_meta("provider", "gateway")
            store.set_meta("provider_evidence_mode", provider.evidence_mode)

    def start(self, bank_id, elapsed):
        count = self.store.db.execute("SELECT COUNT(*) FROM gateway_requests").fetchone()[0]
        reserved = sum((Decimal(r[0]) for r in self.store.db.execute("SELECT reserved_usd FROM gateway_requests")), Decimal(0))
        upper = Decimal(self.provider.config["request_cost_upper_usd"])
        if count >= self.provider.config["max_requests"] or \
                reserved + upper > Decimal(self.provider.config["allocation_usd"]):
            raise GatewayFailure("allocation_exhausted", uncertain=False)
        receipt = {"run_id": self.store.meta("gateway_run_id"), "code_version": "u1-candidate-v1",
                   "code_hash": self.store.meta("gateway_code_hash"), "prompt_version": PROMPT_VERSION,
                   "prompt_hash": PROMPT_HASH, "config_hash": self.store.meta("provider_config_hash"),
                   "dataset_version": self.store.meta("snapshot_hash"), "mode": self.provider.evidence_mode,
                   "reservation_usd": str(upper), "actual_cost_usd": None, "failure_class": None,
                   "guarded_outcome": "not_dispatched", "unsafe_committed_actions": None}
        with self.store.transaction():
            cursor = self.store.db.execute("INSERT INTO provider_attempts(bank_id,status,created_at) VALUES (?,'started',?)",
                                           (bank_id, utc_now()))
            sequence = cursor.lastrowid
            self.store.db.execute("INSERT INTO gateway_requests VALUES (?,?,'started',?,?,NULL,NULL)",
                                  (sequence, bank_id, str(upper), canonical(receipt)))
            self.store.set_meta("run_elapsed_seconds", elapsed)
            self.store.set_meta("inference_calls", int(self.store.meta("inference_calls") or 0) + 1)
            if self.provider.evidence_mode == "live":
                self.store.set_meta("model_calls", int(self.store.meta("model_calls") or 0) + 1)
        return sequence

    def record(self, sequence, status, elapsed, *, event_sequence=None, accepted=False, failure=None):
        receipt = json.loads(self.store.db.execute("SELECT receipt FROM gateway_requests WHERE sequence=?", (sequence,)).fetchone()[0])
        # Provider receipts contain only normalized/allowlisted fields, never raw bodies/errors.
        receipt.update(self.provider.last_receipt or {})
        receipt.update(failure_class=failure, guarded_outcome="accepted" if accepted else "rejected" if failure else "not_dispatched")
        call = canonical(self.provider.last_call) if accepted else None
        with self.store.transaction():
            self.store.db.execute("UPDATE gateway_requests SET status=?,receipt=?,event_sequence=?,call=? WHERE sequence=?",
                                  (status, canonical(receipt), event_sequence, call, sequence))
            self.store.db.execute("UPDATE provider_attempts SET status=?,usage=? WHERE sequence=?",
                                  (status, canonical(self.provider.last_usage), sequence))
            self.store.set_meta("run_elapsed_seconds", elapsed)

    def history(self, bank_id):
        rows = self.store.db.execute("SELECT g.call,e.result,e.status FROM gateway_requests g JOIN events e ON e.sequence=g.event_sequence WHERE g.bank_id=? AND g.status='ok' ORDER BY g.sequence", (bank_id,))
        return [{"call": json.loads(r[0]), "result": json.loads(r[1]), "status": r[2]} for r in rows]


def export_metrics(store, out):
    rows = [json.loads(r[0]) for r in store.db.execute("SELECT receipt FROM gateway_requests ORDER BY sequence")]
    root = Path(out)
    (root / "gateway-events.jsonl").write_text("".join(canonical(r) + "\n" for r in rows), encoding="utf-8")
    times = sorted(r.get("elapsed_seconds", 0.0) for r in rows)
    def percentile(p):
        return times[max(0, math.ceil(p * len(times)) - 1)] if times else None
    summary = {"schema_version": 1, "run_id": store.meta("gateway_run_id"),
               "mode": store.meta("provider_evidence_mode"), "source_hash": store.meta("gateway_code_hash"),
               "prompt_hash": store.meta("gateway_prompt_hash"), "config_hash": store.meta("provider_config_hash"),
               "dataset_version": store.meta("snapshot_hash"), "run_state": store.meta("run_state"),
               "independently_verified": False, "task_success": None, "requests": len(rows),
               "accepted_tools": sum(r["guarded_outcome"] == "accepted" for r in rows),
               "rejected_requests": sum(r["guarded_outcome"] == "rejected" for r in rows),
               "unsafe_attempts": sum(r.get("failure_class") in {"unknown_tool", "host_denied"} for r in rows),
               "unsafe_committed_actions": None, "host_permitted_commits": sum(r["guarded_outcome"] == "accepted" for r in rows),
               "review_annotations": store.db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0],
               "open_holds": store.db.execute("SELECT COUNT(*) FROM exceptions").fetchone()[0],
               "reserved_upper_usd": str(sum((Decimal(r[0]) for r in store.db.execute("SELECT reserved_usd FROM gateway_requests")), Decimal(0))),
               "actual_cost_usd": None, "cost_per_verified_success_usd": None,
               "request_latency": {"n": len(times), "p50_seconds": percentile(.5), "p95_seconds": percentile(.95),
                                   "min_seconds": times[0] if times else None, "max_seconds": times[-1] if times else None,
                                   "timeouts_are_censored": any(r.get("failure_class") in {"deadline_uncertain", "cancelled"} for r in rows)},
               "limitations": "Observed host state, not independent success certification. Usage in doubles is synthetic; unknown costs remain null. No automatic retry or real ledger posting."}
    (root / "gateway-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
