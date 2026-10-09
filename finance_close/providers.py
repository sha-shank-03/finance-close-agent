"""Observation-driven scripted policy and a genuine local wire provider boundary."""

from typing import Protocol

from .domain import object_hash
from .ollama import OllamaProvider, ProviderFailure


class DecisionProvider(Protocol):
    mode: str
    def next_decision(self, context: dict) -> dict:
        """Choose one strict-schema tool using this case's observations."""


def provider_config(provider):
    return getattr(provider, "config", {"mode": provider.mode, "implementation": type(provider).__name__, "version": 2})


class ScriptedProvider:
    mode = "scripted"
    config = {"mode": "scripted", "policy_version": 2}

    def next_decision(self, context):
        bank_id = context["bank_id"]
        history = [item for item in context["history"] if item["status"] == "ok"]
        by_tool = {item["decision"]["tool"]: item["result"] for item in history}
        def call(tool, **arguments):
            return {"tool": tool, "arguments": {"bank_id": bank_id, **arguments}}
        if "inspect_transaction" not in by_tool:
            return call("inspect_transaction")
        bank = by_tool["inspect_transaction"]["record"]
        if "list_cash_candidates" not in by_tool:
            return call("list_cash_candidates")
        observed = by_tool["list_cash_candidates"]
        candidates = observed["candidates"]
        exact = [item for item in candidates if item["exact"]]
        if len(exact) == 1 and exact[0]["available"] and exact[0]["unique_bank"] and not observed.get("truncated", False) and "match_cash" not in by_tool:
            line = exact[0]
            return call("match_cash", line_id=line["line_id"], evidence_ids=sorted(set(line["reference_evidence_ids"] + [bank["evidence"]["amount"], line["evidence"]["amount"]])))
        if bank["transaction_type"] == "vendor_payment":
            if "search_evidence" not in by_tool:
                return call("search_evidence")
            invoices = by_tool["search_evidence"]["invoices"]
            if invoices and "read_evidence" not in by_tool:
                return call("read_evidence", evidence_id=invoices[0]["evidence"]["Invoice ID"])
            if len(invoices) == 1 and not invoices[0]["conflicting"]:
                if "inspect_invoice_balance" not in by_tool:
                    return call("inspect_invoice_balance", invoice_key=invoices[0]["vendor_id"] + ":" + invoices[0]["id"])
                facts = by_tool["inspect_invoice_balance"]["balance"]
                flags = by_tool["inspect_invoice_balance"]["guard_flags"]
                if not candidates and not flags and facts["history_complete"] and facts["available_cents"] >= abs(bank["amount_cents"]) and "draft_entry" not in by_tool:
                    ids = facts["evidence_ids"] + [bank["evidence"][key] for key in ["transaction_id", "date", "amount", "currency", "transaction_type", "vendor_id", "reference"]]
                    return call("draft_entry", rule_id="MISSING_AP_PAYMENT_V1", evidence_ids=sorted(set(ids)))
        elif bank["transaction_type"] == "bank_fee" and not candidates and not observed.get("guard_flags") and "draft_entry" not in by_tool:
            return call("draft_entry", rule_id="BANK_FEE_V1", evidence_ids=[bank["evidence"][key] for key in ["transaction_id", "date", "amount", "currency", "transaction_type"]])
        flags = next((item["result"]["guard_flags"] for item in reversed(history) if "guard_flags" in item["result"]), [])
        if "route_exception" not in by_tool and (flags or "match_cash" not in by_tool and "draft_entry" not in by_tool):
            return call("route_exception", reason=flags[0] if flags else "UNMATCHED_CASH", evidence_ids=[bank["evidence"]["amount"], bank["evidence"]["reference"]])
        return call("finish_case")
