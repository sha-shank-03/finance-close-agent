"""Observation-only fixed workflow; no fixture, label, evaluator or file reads."""

from .tools import Tools

VERSION = "deterministic-v2.1"


class U2bTools(Tools):
    """Same original authority, with a conservative unsupported-identity hold.

    External selected records never assert ledger/history completeness. A host
    may attach a capture as context, but it is not imported or used for amounts.
    """
    def __init__(self, store, bank_id, external_capture=None):
        super().__init__(store, bank_id)
        self.external_capture = external_capture

    def required_flags(self):
        flags = set(super().required_flags())
        bank, candidates = self.store.bank(self.bank_id), self.candidates()
        if bank["currency"] == "USD" and bank["amount_cents"] < 0 and candidates and \
                not any(c["exact"] or c["reference_evidence_ids"] for c in candidates):
            flags.add("AMBIGUOUS_MATCH")
        if self.external_capture is not None:
            flags.add("EXTERNAL_HISTORY_NOT_CERTIFIED")
        return sorted(flags)


class DeterministicV2:
    mode = "scripted"
    evidence_mode = "deterministic-v2"
    config = {"mode": "scripted", "policy_version": VERSION, "authority": "u2b-tools-v1"}

    def next_decision(self, context):
        bank_id = context["bank_id"]
        history = [h for h in context["history"] if h["status"] == "ok"]
        observations = {h["decision"]["tool"]: h["result"] for h in history}
        def call(tool, **args): return {"tool":tool,"arguments":{"bank_id":bank_id,**args}}
        if "inspect_transaction" not in observations: return call("inspect_transaction")
        bank = observations["inspect_transaction"]["record"]
        if "list_cash_candidates" not in observations: return call("list_cash_candidates")
        listed = observations["list_cash_candidates"]
        candidates = listed["candidates"]
        invoices = []
        if bank["transaction_type"] == "vendor_payment":
            if "search_evidence" not in observations: return call("search_evidence")
            searched = observations["search_evidence"]
            invoices = searched["invoices"]
            # Inspect each returned copy's identity. Neither source order nor a
            # duplicate's first copy selects a match or authoritative amount.
            read_ids = {h["decision"]["arguments"]["evidence_id"] for h in history if h["decision"]["tool"] == "read_evidence"}
            ids = sorted({copy["evidence"]["Invoice ID"] for inv in invoices for copy in inv.get("copies",[inv])})
            for ev in ids:
                if ev not in read_ids and len(history)<7: return call("read_evidence",evidence_id=ev)
            if len(invoices)==1 and not invoices[0]["conflicting"] and searched.get("invoice_count",1)==1:
                if "inspect_invoice_balance" not in observations:
                    return call("inspect_invoice_balance",invoice_key=invoices[0]["vendor_id"]+":"+invoices[0]["id"])
        exact = [c for c in candidates if c["exact"]]
        if len(exact)==1 and exact[0]["available"] and exact[0]["unique_bank"] and not listed.get("truncated",False) and "match_cash" not in observations:
            c=exact[0]
            return call("match_cash",line_id=c["line_id"],evidence_ids=sorted(set(c["reference_evidence_ids"]+[bank["evidence"]["amount"],c["evidence"]["amount"]])))
        flags = sorted({f for h in history for f in h["result"].get("guard_flags",[])})
        if not candidates and not flags and "draft_entry" not in observations:
            required=[bank["evidence"][f] for f in ["transaction_id","date","amount","currency","transaction_type"]]
            if bank["transaction_type"]=="bank_fee": return call("draft_entry",rule_id="BANK_FEE_V1",evidence_ids=required)
            facts=observations.get("inspect_invoice_balance",{}).get("balance")
            if facts and facts["history_complete"] and not facts["conflicting"] and facts["available_cents"]>=abs(bank["amount_cents"]):
                required+=facts["evidence_ids"]+[bank["evidence"][f] for f in ["vendor_id","reference"]]
                return call("draft_entry",rule_id="MISSING_AP_PAYMENT_V1",evidence_ids=sorted(set(required)))
        resolved="match_cash" in observations or "draft_entry" in observations
        if "route_exception" not in observations and (flags or not resolved):
            return call("route_exception",reason=flags[0] if flags else "UNMATCHED_CASH",evidence_ids=[bank["evidence"]["amount"],bank["evidence"]["reference"]])
        return call("finish_case")
