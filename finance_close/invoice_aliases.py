"""Explicit text field aliases, not inferred amounts or generic invoice extraction."""

from .domain import InvalidInput

VERSION = "invoice-label-aliases-v1"
ALIASES = {
    "Invoice ID": "Invoice ID", "Invoice Number": "Invoice ID", "Invoice No": "Invoice ID",
    "Vendor ID": "Vendor ID", "Vendor Code": "Vendor ID",
    "Issued": "Issued", "Invoice Date": "Issued",
    "Amount": "Amount", "Invoice Total": "Amount", "Total Amount": "Amount",
    "Currency": "Currency", "Payment Reference": "Payment Reference",
    "Bank Reference": "Payment Reference", "Ledger Reference": "Ledger Reference",
    "Book Reference": "Ledger Reference", "Notes": "Notes",
}


def invoice_fields(text):
    """Return canonical keys plus original line labels for hashed provenance.

    'Amount Due' is deliberately unsupported: it may mean an unpaid balance,
    which cannot replace the original invoice total in AP recognition.
    """
    if type(text) is not str or len(text.encode("utf-8")) > 65536:
        raise InvalidInput("Invoice text exceeds the supported bound")
    result = []
    seen = set()
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        label, separator, value = line.partition(":")
        key = ALIASES.get(label)
        if not separator or key is None or key in seen or len(value) > 4096:
            raise InvalidInput("Unsupported or duplicate canonical invoice field")
        seen.add(key)
        result.append((number, label, key, value.strip()))
    return result
