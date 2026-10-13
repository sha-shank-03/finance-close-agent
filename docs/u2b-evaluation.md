# U2-B authored evaluation candidate

Main verified the first native U2-B batch on 12 October 2026: 32 unique fictional tasks, 64 paired attempts and 773 independent assertions. Both policies scored 16/16 development and 15/16 capability. All32 pairs tie; C81's extra `INCOMPLETE_HISTORY`40700-cent hold remains a frozen-gold mismatch. See the [case study](u2b-case-study.md) and [immutable public projection](../reports/u2b-first/summary.json). Inputs were frozen before native execution: 16 development and 16 capability tasks, two per stratum/split. Both are **author-exposed**, with shared construction families. The original12 development/32 exposed bundles and evidence remain unchanged. This worker has neither created nor inspected main's unseen set.

Main also reproduced the 14 earlier pure methods, the demo, both paired splits and five native copied-state corruptions. The old manual gold SQLite tests remain unit evidence; the native results are separately recorded. U2-C corrects reporting only:13 new pure methods pass with socket/process launch blocked, using injected dispatch, interruption, deadline and storage failures. Its first12-method run retained a shadowed-name error; corrected12 and extended13-method receipts pass. No actor/gold tuning, native replay or full suite occurred in this correction. Native process contracts, full legacy regression and hosted CI remain pending. No positive-uplift or numerical quality threshold is imposed.

## Data and comparison

The MIT fictional source and label freeze is [evaluation/u2b/manifest.json](../evaluation/u2b/manifest.json). Input files and separate labels are hashed individually. The authoring script refuses to replace an existing manifest. Actors receive an input directory, policy name and fresh output directory; labels and scorer paths never enter their arguments or observations. The fixed policy imports only the shared tools module and reads tool observations. This is a source/code boundary, not an OS sandbox against malicious Python.

| Stratum | Development constructions | Capability constructions |
| --- | --- | --- |
| Exact identity | Direct references; alias references with identical copies | Two independent cash edges; alias-linked partial payment and prior history |
| Amounts and unsupported identity | Exact-reference amount conflict; same-amount fuzzy identity | Prior payment history; competing fuzzy banks |
| Duplicate identity | Tied cash rows; competing bank rows | Three tied cash rows; three banks and conflicting copies |
| Invoice evidence | Missing invoice; conflicting copies | Missing fuzzy identity; conflicting unbooked payment |
| Missing AP payment | Complete original history; prior partial settlement | Two affordable reservations; incomplete history handoff |
| Partial payment | Remaining AP availability; overpayment | Reservation followed by overpayment; post-cutoff history excluded |
| Fees | Unposted fee; fee beside a booked fee | Fee proposal beside a booked fee; two independent proposals |
| Timing and unsupported data | Late cash; foreign invoice currency | Foreign bank currency; positive unsupported payment |

`scripted` is the existing observation policy. `deterministic-v2` is a competitive fixed workflow: inspect each returned invoice copy, inspect unambiguous AP history, match only one available, globally unique cash edge with explicit native or invoice-backed references, and draft the two eligible templates from observed evidence. Ties and unsupported fuzzy identities produce `AMBIGUOUS_MATCH` and manual review. Neither policy guesses financial identity from row order. AP reservation priority uses the host's explicit sorted bank IDs; reversed CSV order does not change that priority.

Both policies use the same `U2bTools`, schemas, rules and authority. Limits remain 10 successful tools and 12 decisions per case, 250 cumulative decisions, 50 cases and 180 seconds per run. The evaluator adds a 30-second child deadline and a 180-second split deadline. There are no inference, tool or transport retries in these fixed policies. Existing review and reservation checks remain host-owned; no actor can approve, post or change original ledger rows.

The shared U2-B authority adds a conservative fuzzy-identity hold. An externally attached QBO capture always adds `EXTERNAL_HISTORY_NOT_CERTIFIED`, even if it claims completeness. Its selected records supply no imported amount, ledger history or proposal authorization. Only original local CSV history and an explicit local completeness assertion can support the missing-AP-payment template. The [accepted local QBO contract](u2a-qbo.md) remains separate from genuine external integration.

## Independent outcomes

The scorer imports no `finance_close` module. It separately reads the original CSV/text bytes, labels and read-only SQLite state, reconstructing source fields, cents, evidence IDs, references and journal balances. It checks exact matches, holds and balanced unposted proposals; source/rule/code bindings; proposal hashes and relational provenance; AP recognition, prior settlements, cutoff dates and active reservations; immutable booked totals and their separate proposed cash effect; and real stored completion events and case states. Packet assertions must agree with source bytes and SQLite state.

Three results remain separate:

- **Raw exact-state success:** all independent assertions pass and the native command exits 0.
- **Resolved completion:** exact-state success with no expected open holds. A valid unposted proposal can qualify; this does not certify a financial close.
- **Correct handoff:** exact-state success with the exact expected open holds. `DONE` means investigation finished, while the accounting issue remains open.

Reports include matching, hold and proposal precision/recall with explicit denominators; material labeled holds of at least10000-cent exposure; observed unsafe persisted matches/proposals; handoff, tool/decision counts and latency; paired wins/ties/losses; and descriptive authored intervals. An immutable `intended.json` lists every slot before dispatch. Fsynced journal markers record `STARTED` before launch and `DISPATCHED` only after actual child creation. Known terminal disposition, deadline-unexecuted work, untouched planned work and interrupted unknown results remain distinct. A launch error can terminate a slot without a native exit or attempted child. The reader never resumes or redispatches.

All planned gold stays in recall/material denominators. Unscored gold is conservatively counted missed/unverified; it is not proof of what a lost child committed. Unknown unsafe/handoff outcomes and unmeasured billed cost stay null. Completion latency covers only confirmed dispatched terminal results; interrupted elapsed observation is not a fabricated completion latency. Unobserved pairs are separate from ties. Atomic snapshots follow the fsynced journal; a hard stop can be inspected read-only. This addresses process interruption, not power-loss/fsync durability or uninterruptible OS startup/I/O. Fixed offline configuration permits no paid requests; incomplete observed model-call coverage is unknown.

## Prepared commands and reviewer walkthrough

Main executed the first six-command U2-B batch with fresh private outputs. The commands below reproduce the workflow under the new evaluator version; they have **not** been executed by this correction. Local coordinated work needs a fresh named main lease. They are outside the proposed U2-C correction/regression batch, which does not replay these32 tasks. Use fresh directories, preserve first results and replace `py -3.11` with `python` on other platforms. Driver exit0 means complete terminal accounting with stable source/data, not a quality pass.

```powershell
py -3.11 -m finance_close.u2b --input fixtures/u2b/dev/D51 --out artifacts/u2b-demo-first --policy deterministic-v2
py -3.11 -m evaluation.u2b_verify --run artifacts/u2b-demo-first --source fixtures/u2b/dev/D51 --labels evaluation/u2b/labels/dev/D51.json --out artifacts/u2b-demo-first/independent.json
py -3.11 -m evaluation.u2b_run --split dev --out artifacts/u2b-dev-first --max-seconds 180
py -3.11 -m evaluation.u2b_run --split capability --out artifacts/u2b-cap-first --max-seconds 180
py -3.11 -m evaluation.u2b_controls --proposal-run artifacts/u2b-dev-first/D51/deterministic-v2 --handoff-run artifacts/u2b-dev-first/D62/deterministic-v2 --out artifacts/u2b-controls-first
py -3.11 -m evaluation.u2b_ci --dev-report artifacts/u2b-dev-first/report.json --capability-report artifacts/u2b-cap-first/report.json --out artifacts/u2b-ci-first
```

For the preserved D51 demo, inspect original bank/invoice aliases and complete AP recognition beside the packet and independent report. Main verified a28500-cent debit to AP/credit to cash, pending and unposted; booked/reserved/available AP is114000/28500/85500 cents. D62's investigation finishes with overpayment and unmatched-cash holds open. On a later reproduction, inspect the emitted evidence links and compare the packet against read-only SQLite and original files; never infer resolution merely from `DONE`.

Each split has 16 unique tasks, 32 paired attempts and one repetition. Across splits that is 32 unique tasks and 64 attempts. The separate demo repeats D51 and adds no independent task. Native mutation controls first require valid positive proposal/handoff baselines, alter copies only, check five rejections and hash the originals afterward. `u2b_ci` checks report packaging without repeating the corpus or imposing a quality threshold; it is not an acceptance oracle.

The [offline workflow](../.github/workflows/u2b-offline.yml) separates historical summary integrity, pure/native process failure contracts, recorded authored quality and native copy-corruption/report integrity. Quality has no positive-uplift threshold. It uses pinned actions and Python3.11 with no packages, credentials or model calls. Hosted execution remains unverified. The original legacy CI workflow is preserved.

For a fresh pure-only receipt:

```powershell
py -3.11 tools/u2b_pure.py --out FRESH_PURE_RECEIPT_DIRECTORY
```

The historical [U2-B manifest](../u2b-manifest.json) and all first reports keep their original code/data fingerprints. The [U2-C manifest](../u2c-manifest.json) separately declares evaluator/docs changes. All finance actor/scorer source and frozen gold are unchanged. Finance/Gateway code binding remains unchanged, while the evaluator's source map advances. Preserve accepted journals and first artifacts. Full legacy regression, main unseen, genuine QBO sandbox, live inference and final publication remain pending. No new UI/dependency/ERP import/OCR/FX/tax/netting/posting is implemented.

## Bounded U2-C correction and legacy regression

Pure checks and public-bundle validation need no child or network:

```powershell
py -3.11 tools/u2c_pure.py --out FRESH_U2C_PURE_RECEIPT
py -3.11 -m evaluation.u2c_summary validate --bundle reports/u2b-first
```

The two prepared commands below require a later main lease. The first exercises six small native process controls, with no finance actor. The second is the preserved seven-step legacy CI plan: doctor, original freeze, full suite, original demo/verifier,96 attempts on the original32 exposed tasks and legacy M3 acceptance. It reproduces old exposed regression, not unseen accuracy, and does not replay the new U2-B corpus.

```powershell
py -3.11 -m evaluation.u2c_acceptance --out artifacts/u2c-process-first
py -3.11 -m evaluation.ci --out artifacts/u2c-regression-first --allow-heldout
```

The proposed outer lease bounds are 600 active seconds, 512MiB owned RAM, 200MiB generated artifacts, four processes including launcher/CI parent/nested evaluator/owned child and one legacy loopback double at most. Main must monitor deadlines, retained owned identities and measurement gaps. No grant exists. The current correction ran only source/pure/export checks.

After a stop, inspect durable counts without resuming:

```powershell
py -3.11 -m evaluation.u2c_progress --run INTERRUPTED_PRIVATE_RUN_DIRECTORY
```

## Narrow source-literal correction

Main's U2-C review passed 13 pure methods, six native process controls, 155 legacy unit tests and 96 legacy attempts. The last CI step failed only because detector/test strings matched the existing standalone personal-path scanner. The correction constructs identical runtime strings from constants; both modules compile to identical runtime bytecode/constants on the selected Python3.11 runtime. The scanner itself is unchanged. All13 pure methods, its10 source checks and public-summary integrity pass. This is not full U2-C acceptance.

The [corrected source manifest](../u2c-literal-manifest.json) preserves the prior candidate and failure evidence. The following **unexecuted, final-only** command needs a fresh main lease. It rechecks saved96 raw outcomes and runs the remaining nested M1/M2 regressions into a fresh output; it does not replay the96-task evaluation or replace the failed CI receipt. Acting finance/rules hashes still match the saved evaluation.

```powershell
py -3.11 -m evaluation.acceptance --milestone 3 --evaluation artifacts/main-u2c-1039-regression/heldout --out artifacts/u2c-literal-final-first
```
