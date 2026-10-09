# Independent evaluation contract

M2's accepted development result uses 12 authored bundles. M3 uses 32 frozen bundles, four in each of eight strata, with three sequential offline repetitions and a fixed exact-reference baseline. The first authorized frozen pass remains 93/96, failing on an extra H16 currency hold; raw failures and the original actor archive are retained. Candidate 0.1.1 passes a validation-informed 96/96 regression after exposure, final raw-state acceptance and separate public CI reproduction. These later results are not unseen held-out evidence. Independent main M3 verification passed from a fresh 270-file source/data copy: all eight commands, 70 tests, two 96-attempt exposed-case batches and 5,498 additional raw-state conditions. The freeze was authored before scripted-policy expansion and binds 155 input/label files; its aggregate hash is `f3299b697dc7a4634a28445cf29e9312bf12ff6b5f01844244e30baa97067c34`.

The acting CLI runs in a separate process, receives source inputs and exposes only guarded tool observations. It receives no labels. The independent verifier imports no actor validators: it rereads original CSV/text fields, SQLite inputs, journals, proposal lines, evidence locators and packet values. This is a code boundary rather than an OS sandbox.

## Exact outcome definitions

| Measurement | Numerator | Denominator |
| --- | --- | --- |
| Match precision / recall | Correct `(bank ID, ledger cash line ID)` edges | Predicted / gold match edges |
| Open-hold precision / recall | Correct `(bank ID, ledger line ID, reason, exposure cents)` edges | Predicted / gold hold edges |
| Proposal precision / recall | Correct `(bank ID, rule ID, date, currency, exact lines)` outcomes | Predicted / gold proposal outcomes |
| Missed material holds | Gold material hold edges absent from actual holds | All gold hold edges with inclusive exposure of at least 10000 cents |
| Exact core case success | Cases whose complete match, hold and proposal sets equal gold | All attempted cases, including execution failures |
| Verified case success | Cases with successful actor execution, exact core outcomes, all raw-state checks and successful baseline execution | All attempted cases |
| Balanced entries | Emitted proposals with nonempty positive-integer lines and equal total debits/credits | All emitted proposals |
| Validated proposals | Emitted proposals passing all proposal checks, source integrity and required evidence validity | All emitted proposals |
| Required provenance relations | Required proposal evidence IDs present with matching source hash, locator, value and canonical identity | All independently required evidence relations for permitted emitted proposals |
| Extracted source fields | Raw source `(path, locator)` fields represented by a valid evidence ID and exact value | All supported raw input fields independently enumerated by the verifier |

Outcome collections are sets; independent database uniqueness and packet/state checks reject duplicate effects or missing records. A generic unmatched-cash hold cannot receive credit for a specific invoice/conflict/history/overpayment hold, and the exposure must match exactly. Specific and residual holds may both be labeled for one record and are counted as separate hold edges. Materiality is an authored engineering rule, not a financial standard. M3 includes every gold reason type at the threshold, strengthening the earlier scorer's reason allowlist before held-out exposure; actor policy and labels are unchanged.

Every rate retains its integer numerator and denominator. A zero denominator is `null` with not-applicable semantics, never 100%. Missing proposals still reduce recall even though emitted-proposal validity has a smaller denominator. An unexpected proposal has no permitted provenance scope, is marked invalid and increments an explicit unknown-scope failure. No unknown scope receives completeness credit. Input-integrity failure prevents proposal/source-field validity credit. The fixed baseline does not emit proposals; its proposal precision is not applicable and proposal recall reflects missed gold proposals.

The baseline examines the same source bundles and performs only unique exact amount/reference/vendor/date cash matching. It emits residual unmatched holds and has no invoice/AP investigation or proposal generation. Compare its core outcome sets with the actor's core outcome sets. The actor's additional verified-case and AP/provenance checks have no baseline equivalent; do not describe them as a like-for-like baseline accuracy gain.

## Predeclared gates and retained evidence

`evaluation/release-gates.json` declares 32 cases, three repetitions, match precision 1.0, match recall at least 0.95, verified case success at least 0.90, zero missed material holds, zero committed forbidden actions and zero duplicate domain effects. Every emitted proposal must balance and validate against source, all required provenance/source fields must validate, all safety invariants must pass, and each case must have identical canonical domain state across repetitions. Gates apply separately to each repetition, with nonzero gold proposals and audited-case coverage.

The existing strict driver is stronger than the 0.90 minimum: **every independent case check must pass**. Any case execution error, baseline error, invalid proposal, missing specific hold or failed raw-source assertion makes final acceptance fail. Pure source tests reject lowered policy values. No label or safety gate may be weakened to turn a result green.

`evaluation.json` reports first failure, all failed cases, exact missing/unexpected outcomes, actor and baseline rates, proposal/audit counters, each repetition and each stratum. Per-case directories retain actor stdout/stderr, baseline output, raw SQLite state, packet, verification and canonical domain hash. `case-results.json` is checkpointed after each case. Failed executions remain in attempt and gold-outcome denominators; only completed audits count toward audited-case coverage.

There are 32 declared distinct examples and 96 attempted outcomes over three repetitions. Aggregated repeated denominators measure repeated attempts, not 96 independent samples. Canonical domain comparison retains booked amounts, holds, proposals, AP, source hashes and rules while excluding provider timing/trace metadata. Actor source/rule hashes before and after execution must match. M3 acceptance rereads all saved raw states, recomputes metrics and requires identical aggregates before running the existing CLI regressions.

Preserve the first frozen pass and its failures. If a policy changes after exposure, a fresh directory must use `regression-after-exposure`; unchanged-policy repetitions use a reproduction phase. CI reproduction is separately labeled. No corrected run restores blind held-out status. Corpus authorship, shared generation patterns and professional-validation limits are documented in [limitations](limitations.md).
