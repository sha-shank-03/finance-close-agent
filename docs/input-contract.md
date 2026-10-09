# Fictional input bundle contract

The cash bridge covers one monthly USD account with equal opening balances. All fixtures must declare `fictional:true`. Foreign currencies and unsupported bank types are retained as open holds and excluded from USD arithmetic; they are not converted.

`manifest.json` uses schema 1 and the keys in `fixtures/demo/manifest.json`. Optional `ap_history_complete` is a unique list of `vendor_id:invoice_id` strings. It is an explicit **source assertion** that the supplied per-invoice history through period end is complete, not an inferred fact. An AP proposal additionally requires USD recognition credits exactly equal to the invoice amount. Omitted assertions or inconsistent histories produce holds when AP reasoning is necessary. Hashes establish consistency, not authenticity.

Bank CSV columns, in order:

```text
transaction_id,date,amount,currency,vendor_id,reference,transaction_type,memo
```

Bank rows need nonzero decimal amounts, ISO currency strings and dates in the statement period. `vendor_payment` requires a vendor. Supported automatic actions cover negative USD vendor payments and explicit `bank_fee` records. A fee-like memo does not authorize a fee template. Duplicate bank IDs are invalid. USD rows plus opening cash must equal statement closing cash.

Ledger CSV columns, in order:

```text
entry_id,line_id,date,account,side,amount,currency,vendor_id,invoice_id,reference
```

Positive amounts use debit/credit sides. Accounts are `cash`, `accounts_payable`, `bank_fee_expense`, and `expense`. IDs are unique; dates agree within an entry; every entry balances separately in each currency. Earlier and later ledger rows are retained as context. Only in-period USD cash contributes to closing cash and ledger residuals. Only AP rows through period end contribute to booked per-invoice balances; a bank payment already matched to ledger cash is never counted again.

Invoice text files use required `Invoice ID`, `Vendor ID`, `Issued`, `Amount`, `Currency`; optional `Payment Reference`, `Ledger Reference`, `Notes`. Keys are unique. Payment and ledger references may establish an explicit source alias. Notes remain data. Multiple copies of one vendor/invoice identity are grouped while preserving every source field. Equal canonical monetary/core fields do not duplicate recognition; conflicting core fields produce `CONFLICTING_EVIDENCE` and block AP proposals.

Amounts allow ordinary decimal strings with at most two places, no exponent or float, bounded by 100000000000 cents. One-cent differences never match. Reference normalization removes spaces, hyphens and underscores and folds case. Exact matches additionally require same currency/vendor, current-period cash, a three-day date window and unique bank/ledger ownership. Same amounts without source reference agreement do not match.

`MISSING_AP_PAYMENT_V1` derives Dr accounts_payable / Cr cash from the bank amount. It requires a unique consistent invoice, source reference, complete booked history, no plausible existing cash candidate and sufficient available AP. Pending/approved drafts reserve AP separately; rejection releases their active reservation. Drafts never change actual booked history.

Import limits: 10000 bank rows, 30000 ledger rows, 200 invoice documents, 64 KiB per invoice and 10 MiB total bundle. The loop separately caps 50 cases. A tool may return at most five candidates/invoices, 32 KiB of results and 64 observed evidence IDs. Complete AP provenance must fit 57 IDs plus seven bank fields; larger histories are held for manual investigation. Truncation never authorizes matching or drafting.

UTF-8 (optional BOM) is required. Symlinked sources, duplicate/missing columns, invalid money/dates, oversized sources and unbalanced journals fail before workflow state is initialized. Input/output directories cannot overlap. Original files must remain available for exact review.

```powershell
py -3.11 -m finance_close run --input path/to/fictional-bundle --out artifacts/custom --provider scripted
```

Exit codes: 0 means a generated packet that may contain business holds; 2 invalid input/action/configuration; 3 incomplete/cancelled; 4 filesystem/database failure. The independent verifier returns 1 on a failed check. Integration-only `--test-fault after-proposal-commit` or `before-packet-rename` exits 85; rerun without the fault to recover.
