"""SQLite storage for immutable input and separate workflow/review state."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .domain import InvalidInput, canonical

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources(path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, raw BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY, source_path TEXT NOT NULL REFERENCES sources(path), locator TEXT NOT NULL, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bank(id TEXT PRIMARY KEY, amount_cents INTEGER NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger(line_id TEXT PRIMARY KEY, entry_id TEXT NOT NULL, account TEXT NOT NULL, side TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents>0), signed_cents INTEGER NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS invoices(invoice_key TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cases(bank_id TEXT PRIMARY KEY REFERENCES bank(id), state TEXT NOT NULL DEFAULT 'OPEN');
CREATE TABLE IF NOT EXISTS matches(bank_id TEXT PRIMARY KEY REFERENCES bank(id), line_id TEXT UNIQUE NOT NULL REFERENCES ledger(line_id), evidence_ids TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exceptions(id TEXT PRIMARY KEY, bank_id TEXT REFERENCES bank(id), ledger_line_id TEXT REFERENCES ledger(line_id), reason TEXT NOT NULL, exposure_cents INTEGER NOT NULL, evidence_ids TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, bank_id TEXT UNIQUE NOT NULL REFERENCES bank(id), hash TEXT NOT NULL, content TEXT NOT NULL, review_state TEXT NOT NULL DEFAULT 'PENDING');
CREATE TABLE IF NOT EXISTS proposal_lines(proposal_id TEXT NOT NULL REFERENCES proposals(id), number INTEGER NOT NULL, account TEXT NOT NULL, side TEXT NOT NULL CHECK(side IN ('debit','credit')), amount_cents INTEGER NOT NULL CHECK(amount_cents>0), PRIMARY KEY(proposal_id,number));
CREATE TABLE IF NOT EXISTS proposal_evidence(proposal_id TEXT NOT NULL REFERENCES proposals(id), evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(proposal_id,evidence_id));
CREATE TABLE IF NOT EXISTS reservations(proposal_id TEXT PRIMARY KEY REFERENCES proposals(id), invoice_key TEXT NOT NULL REFERENCES invoices(invoice_key), amount_cents INTEGER NOT NULL CHECK(amount_cents>0));
CREATE TABLE IF NOT EXISTS reviews(proposal_id TEXT PRIMARY KEY REFERENCES proposals(id), proposal_hash TEXT NOT NULL, snapshot_version TEXT NOT NULL, decision TEXT NOT NULL CHECK(decision IN ('approve','reject')), reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, bank_id TEXT NOT NULL REFERENCES bank(id), decision TEXT NOT NULL, result TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS provider_attempts(sequence INTEGER PRIMARY KEY AUTOINCREMENT, bank_id TEXT NOT NULL REFERENCES bank(id), status TEXT NOT NULL, usage TEXT, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS immutable_ledger_update BEFORE UPDATE ON ledger BEGIN SELECT RAISE(ABORT,'Ledger inputs are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_ledger_delete BEFORE DELETE ON ledger BEGIN SELECT RAISE(ABORT,'Ledger inputs are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_bank_update BEFORE UPDATE ON bank BEGIN SELECT RAISE(ABORT,'Bank inputs are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_bank_delete BEFORE DELETE ON bank BEGIN SELECT RAISE(ABORT,'Bank inputs are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_source_update BEFORE UPDATE ON sources BEGIN SELECT RAISE(ABORT,'Source bytes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_source_delete BEFORE DELETE ON sources BEGIN SELECT RAISE(ABORT,'Source bytes are immutable'); END;
"""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=2)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def meta(self, key):
        row = self.db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key, value):
        self.db.execute("INSERT INTO metadata VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    def initialize(self, bundle):
        existing = self.meta("snapshot_hash")
        if existing:
            if existing != bundle["snapshot_hash"] or self.meta("rule_hash") != bundle["rule_hash"]:
                raise InvalidInput("Existing output belongs to different inputs or rules; use a new output directory")
            return False
        with self.transaction():
            for key, value in {"schema_version": "2", "snapshot_hash": bundle["snapshot_hash"], "rule_hash": bundle["rule_hash"], "input_root": bundle["root"], "manifest": canonical(bundle["manifest"]), "rule": canonical(bundle["rule"]), "run_state": "READY", "provider": "scripted", "model_calls": "0", "inference_calls": "0", "provider_config_hash": "", "run_elapsed_seconds": "0"}.items():
                self.set_meta(key, value)
            self.db.executemany("INSERT INTO sources VALUES (?,?,?)", [(s["path"], s["sha256"], s["raw"]) for s in bundle["sources"]])
            self.db.executemany("INSERT INTO evidence VALUES (?,?,?,?)", [(e["id"], e["source_path"], e["locator"], e["value"]) for e in bundle["evidence"]])
            for txn in bundle["bank"]:
                self.db.execute("INSERT INTO bank VALUES (?,?,?)", (txn["id"], txn["amount_cents"], canonical(txn)))
                self.db.execute("INSERT INTO cases(bank_id) VALUES (?)", (txn["id"],))
            self.db.executemany("INSERT INTO ledger VALUES (?,?,?,?,?,?,?)", [(line["line_id"], line["entry_id"], line["account"], line["side"], line["amount_cents"], line["signed_cents"], canonical(line)) for line in bundle["ledger"]])
            self.db.executemany("INSERT INTO invoices VALUES (?,?)", [(inv["vendor_id"] + ":" + inv["id"], canonical(inv)) for inv in bundle["invoices"]])
        return True

    def bank(self, bank_id):
        row = self.db.execute("SELECT data FROM bank WHERE id=?", (bank_id,)).fetchone()
        if not row:
            raise InvalidInput("Unknown bank record")
        return json.loads(row[0])

    def ledger(self, line_id):
        row = self.db.execute("SELECT data FROM ledger WHERE line_id=?", (line_id,)).fetchone()
        if not row:
            raise InvalidInput("Unknown ledger line")
        return json.loads(row[0])

    def history(self, bank_id):
        return [{"decision": json.loads(r["decision"]), "result": json.loads(r["result"]), "status": r["status"]} for r in self.db.execute("SELECT * FROM events WHERE bank_id=? ORDER BY sequence", (bank_id,))]

    def event(self, bank_id, decision, result, status="ok"):
        self.db.execute("INSERT INTO events(bank_id,decision,result,status,created_at) VALUES (?,?,?,?,?)", (bank_id, canonical(decision), canonical(result), status, utc_now()))
