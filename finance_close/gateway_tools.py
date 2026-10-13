"""Additional explanatory observations; all accounting authority stays in Tools."""

from .tools import Tools


class GatewayTools(Tools):
    def search_evidence(self, bank_id):
        result = super().search_evidence(bank_id)
        hits = self.invoice_hits()
        result["invoice_resolution"] = {
            "status": "MISSING" if not hits else "AMBIGUOUS" if len(hits) > 1 else
                      "CONFLICTING" if hits[0]["conflicting"] else "UNIQUE",
            "method": "exact vendor ID and observed invoice/reference linkage",
            "reference_aliases": [{"invoice_key": inv["vendor_id"] + ":" + inv["id"],
                                   "bank_reference": inv["reference"],
                                   "ledger_reference": inv["ledger_reference"],
                                   "field_labels": inv.get("field_labels", {})}
                                  for inv in hits[:5]],
            "hand_off_required": len(hits) != 1 or bool(hits and hits[0]["conflicting"]),
            "authority": "aliases do not authorize fuzzy identity, amounts, posting or approval",
        }
        return result
