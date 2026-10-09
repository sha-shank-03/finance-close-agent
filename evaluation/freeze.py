"""Integrity check only; does not import actor, score labels or modify the corpus."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check_freeze():
    freeze = json.loads((ROOT / "evaluation/heldout-freeze.json").read_text(encoding="utf-8"))
    records = freeze["records"]
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    if hashlib.sha256(encoded).hexdigest() != freeze["aggregate_sha256"] or len(records) != 32 or len({item["case_id"] for item in records}) != 32 or len({item["stratum"] for item in records}) != 8:
        raise ValueError("Held-out freeze manifest changed or counts disagree")
    files = 0
    for record in records:
        for name, wanted in record["files"].items():
            path = ROOT / name
            if not path.resolve().is_relative_to(ROOT) or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != wanted:
                raise ValueError("Frozen source or label changed: " + name)
            files += 1
    actual = {p.relative_to(ROOT).as_posix() for directory in [ROOT / "evaluation/cases/heldout", ROOT / "evaluation/labels/heldout"] for p in directory.rglob("*") if p.is_file()}
    declared = {name for record in records for name in record["files"]}
    if actual != declared:
        raise ValueError("Undeclared or missing held-out files")
    return {"passed": True, "case_count": 32, "strata": 8, "files_checked": files, "aggregate_sha256": freeze["aggregate_sha256"], "frozen_at": freeze["frozen_at"], "scoring_executed": False}


if __name__ == "__main__":
    print(json.dumps(check_freeze()))
