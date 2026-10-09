"""Strict money and identifier boundaries; no floating-point accounting."""

import hashlib
import json
import re
from datetime import date
from decimal import Decimal


class InvalidInput(ValueError):
    pass


class ForbiddenAction(ValueError):
    pass


class SchemaViolation(ForbiddenAction):
    """Only syntactic tool errors may receive one model correction attempt."""


class IncompleteRun(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=unique, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON")))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def object_hash(value):
    return digest(canonical(value).encode("utf-8"))


def cents(value):
    if not isinstance(value, str) or not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?", value):
        raise InvalidInput("Money must be a finite plain decimal string with at most two places")
    result = int(Decimal(value) * 100)
    if abs(result) > 100_000_000_000:
        raise InvalidInput("Money exceeds the supported bound")
    return result


def identifier(value, *, optional=False):
    if optional and value == "":
        return value
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value):
        raise InvalidInput("Invalid identifier")
    return value


def iso_date(value):
    try:
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise InvalidInput("Invalid ISO date") from exc
    if parsed.isoformat() != value:
        raise InvalidInput("Dates must use YYYY-MM-DD")
    return parsed


def reference(value):
    if not isinstance(value, str) or len(value) > 128:
        raise InvalidInput("Invalid payment reference")
    return re.sub(r"[ _-]", "", value.strip().upper())


def evidence_id(path, source_hash, locator):
    return "ev-" + object_hash([path, source_hash, locator])


def journal_is_balanced(lines):
    return sum(line["amount_cents"] * (1 if line["side"] == "debit" else -1) for line in lines) == 0
