# M1 evidence record

Source checkpoint date: 2026-10-08. The accepted M1 scope is the authored three-transaction demo, exact cash matching, missing-invoice hold, `BANK_FEE_V1`, SQLite provenance, a bounded scripted tool loop, static packet and exact local review. The AP template, larger corpus and advanced partial-payment handling are deferred.

## Executed component checks

Command, from the repository root on Windows:

```powershell
py -3.11 -m unittest discover -s tests -p 'test_core*.py' -v
```

Observed runs:

| Run | Exit | Tests | Failures/errors | Unittest elapsed | Command wall time |
| --- | --- | --- | --- | --- | --- |
| Initial component suite | 0 | 21 | 0 | 3.160 s | about 3.699 s |
| Final suite after adding loop rejection/no-progress checks and tool budget | 0 | 23 | 0 | 3.554 s | about 4.302 s |

Tests use temporary authored copies and component-level SQLite state. They do not run the complete CLI demo or acceptance batch. Two loop tests intentionally stop at the first rejected/no-progress decision and verify bounded failure without domain mutation.

Assertions cover exact decimal equality and one-cent differences; malformed/excess-scale amounts; narrow reference normalization; exact import/provenance; duplicate bank IDs and invoice fields; unbalanced journal and statement mismatch; explicit M1 rejection of partial invoice amounts; unknown/extra/cross-case tool actions; unobserved evidence; wrong cash line; independent missing-invoice hold on matched cash; balanced 3000-cent fee/provenance/idempotency; forbidden vendor-to-fee coding; ledger update prohibition; exact repeated review; conflicting/stale review; changed source; HTML escaping; observation-dependent scripted decisions; forbidden provider action termination; and bounded repeated no-progress decisions.

No component-test attempts failed in this implementation turn. During the earlier planning read-only environment inspection, a nested-quote command raised a SyntaxError; the corrected check succeeded. No application or benchmark was executed by that planning attempt.

## Environment

The selected Windows launcher was inspected again as Python 3.11.9 with SQLite 3.45.1. The executed unit command explicitly selected `py -3.11`. An unqualified local `python` resolves to 3.12.7 and is not used for local acceptance. There are no pip/runtime downloads, Java builds, browser/HTTP services, model calls, API keys or external-account operations in this source checkpoint.

## Read-only source checkpoint

The exact PowerShell source-inspection command was:

```powershell
@'
import ast
import hashlib
import json
import pathlib
import sqlite3
import sys
import tomllib
root = pathlib.Path.cwd()
files = sorted(list(root.glob('finance_close/*.py')) + list(root.glob('evaluation/*.py')) + list(root.glob('tests/*.py')))
for source in files:
    ast.parse(source.read_text(encoding='utf-8'), filename=str(source.relative_to(root)))
tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))
for source in [root / 'rules/v1.json', root / 'fixtures/demo/manifest.json', root / 'evaluation/labels/demo.json']:
    json.loads(source.read_text(encoding='utf-8'))
print(json.dumps({'python': sys.version.split()[0], 'sqlite': sqlite3.sqlite_version, 'parsed_python_files': len(files), 'toml_json_valid': True, 'demo_artifacts_exist': (root / 'artifacts').exists(), 'fixture_hashes': {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root / 'fixtures/demo').rglob('*')) if p.is_file()}}))
'@ | py -3.11 -
```

Observed exit code **0**: 15 Python files parsed; TOML and the three named JSON files parsed; `demo_artifacts_exist:false`. This is syntax/source inspection, not application execution. Fixture hashes:

| Source | SHA-256 |
| --- | --- |
| bank.csv | 396ba8ef1df0aa9d241d0f17f23b3f93939a0b6b29098b54ef3f7cfa8787f305 |
| ledger.csv | 63d8bab616f04ff4cd2770bdba6e48935660bba9f5d5dcf7f15ee6f38a854666 |
| manifest.json | 70f8e347444a6ced6d9244297287f36357fa6786e84103b073366bebddc17c20 |
| invoices/inv-1001.txt | ee1ae838b207b16f03b49471c5343aa77e9e70a772fa169ff9963431869aa856 |

## Pre-lease integration checkpoint (historical)

At the source checkpoint the following commands were ready but had not run. Their later leased execution is recorded below:

```powershell
py -3.11 -m finance_close doctor
py -3.11 -m finance_close demo --out artifacts/m1 --provider scripted
py -3.11 -m evaluation.verify --run artifacts/m1 --labels evaluation/labels/demo.json
py -3.11 -m evaluation.acceptance --milestone 1 --out artifacts/acceptance-m1
```

Predeclared outcomes were: 872000-cent bank closing; immutable 875000-cent ledger closing; two exact cash matches; one open missing-invoice hold on B003; one pending balanced 3000-cent fee proposal on B005; complete residual bridge; source hashes and ledger unchanged; repeated run/review causing no duplicate effects. Acceptance must also detect a corrupted proposal in a copied database. All were subsequently observed below. Main independently reruns these checks before milestone acceptance.

Remote GitHub Actions, live inference, model adapter/protocol double, held-out evaluation/baseline, M2/M3, production integrations, ledger posting, publishing and deployment are unexecuted. The default decisions are explicitly scripted. Component success is not evidence of live-model quality or production accounting correctness.

## Resource boundary

The source checkpoint consumed no integration lease. Main subsequently granted `finance-close-m1-integration`: ten active minutes, zero downloads, one sequential CPU worker, maximum 256 MiB RAM and 25 MiB generated disk. Measured execution and disk use are recorded below; peak memory is not measured. Only main can release the shared grant.

## Leased M1 integration — executed 2026-10-08

The ignored local helper `work/run_leased_m1.py` read the **raw** shared JSON immediately before each command. It matched the exact lease name, project, worker owner, active status and M1 scope; parsed `granted_at` and `expires_at` with timezone-aware `datetime`; checked the current UTC time and cumulative active-minute budget; and stopped dependent commands if validation or a preceding command failed. All five grant checks passed. Grant interval: 09:26:44.251323 UTC to 10:56:44.251323 UTC on 2026-10-08.

| Exact command from repository root | Exit | Active wall time | Fresh grant check (UTC) |
| --- | --- | --- | --- |
| `py -3.11 -m finance_close doctor` | 0 | 0.282 s | 09:28:48.180788 |
| `py -3.11 -m finance_close demo --out artifacts/m1 --provider scripted` | 0 | 0.437 s | 09:28:48.469532 |
| `py -3.11 -m evaluation.verify --run artifacts/m1 --labels evaluation/labels/demo.json` | 0 | 0.266 s | 09:28:48.901671 |
| `py -3.11 -m evaluation.acceptance --milestone 1 --out artifacts/acceptance-m1` | 0 | 2.312 s | 09:28:49.167222 |
| `py -3.11 -m evaluation.acceptance --milestone 1 --out artifacts/acceptance-m1-review` | 0 | 2.969 s | 09:31:02.955627 |

The second acceptance run followed a bounded addition to the harness: exercise rejection of a still-pending proposal and repeat that rejection. The original passing report was preserved in its first output directory. No application behavior or assertion threshold was changed, and there were no unexpected failed integration attempts.

Observed demo: three authored bank transactions, four unchanged ledger lines, two exact cash matches, one missing-invoice hold, one fee proposal with two balanced 3000-cent lines and five field-level evidence relations, and 16 scripted decisions/tool calls. Model calls: **0**. Bank closing **872000**, ledger closing **875000**, difference **-3000**, unmatched bank **-3000**, unmatched ledger **0**, bridge residual **0**, separate proposed cash effect **-3000**, all in cents. Demo fee state is **PENDING** and `posted:false`. B003 is MATCHED with OPEN_HOLD invoice status.

The direct independent verifier passed **214/214 assertions**. The final acceptance report passed **14/14 driver assertions**, with **15 sequential CLI subprocess commands** returning their expected exits. Its verifier runs passed 214/214 before review, 216/216 after approval, and 216/216 after rejection. The deliberately corrupted copy returned expected exit **1**, with **3 detected assertion failures**; conflicting and stale-hash review attempts returned expected exit **2**. These expected negative checks are preserved, not hidden as successful commands.

The final batch confirms both approval and rejection remain unposted; rejection contributes zero proposed cash effect while booked ledger cash remains 875000 cents; the missing-invoice hold survives both decisions; and repeated run/approval/rejection creates no duplicate effects. Original source hashes equal the source checkpoint hashes above. Exact resolved subprocess commands, outputs, errors and assertion details are in ignored local `artifacts/acceptance-m1-review/acceptance.json`. The SHA-256 proposal-content hash binds the fee's bank.csv row 4 identity/date/amount/currency/type evidence, rule hash and snapshot.

Static HTML source inspection found the $8,720.00 bank balance, $8,750.00 ledger balance, $30.00 fee, MISSING_INVOICE and UNPOSTED labels, five evidence anchors, restrictive content policy and no script tag. Packet HTML size: 19942 bytes. This is source inspection; a browser visual render was not performed. Component HTML escaping also passed.

Cumulative measured heavy-command wall time: **6.266 seconds** of the granted ten active minutes. Generated `artifacts/` size after both batches: **1890231 bytes** (about 1.80 MiB), within 25 MiB. Execution was sequential, with at most one acceptance child CLI at a time. All five top-level stderr logs are empty. Peak RAM was **not measured**; the prior <256 MiB figure remains an estimate. Downloads: **0 bytes**; no server/browser/model or owned background process was started.

M1 was ready for main's independent review at that historical checkpoint. Main subsequently accepted it, as recorded below. Remote CI, live inference, production accounts/ledger posting, publication and deployment remain unexecuted.

## Main independent M1 acceptance

Main accepted M1 on **2026-10-08T09:42:12.706574 UTC** after five fresh commands, 23 tests, 214 independent verifier assertions, 14 acceptance driver assertions across 15 expected-exit CLI calls and 12 additional domain checks. Its acceptance receipt records the original source hashes. The M1 worker lease is released. Historical M1 execution above applies to that original policy/source revision; M2 regression is not yet executed.

## M2 source and lightweight component checkpoint — 2026-10-08

The current assignment authorizes source work and lightweight components only. Source now includes booked AP history, partial settlements, semantic invoice copies/conflicts, `MISSING_AP_PAYMENT_V1`, pending/approved reservations, host-mandated holds, complete bank/current-period USD ledger residual coverage, provider-bound durable budgets, cancellation and resume state, strict schemas, an explicit local Ollama adapter, and separate exact-content review. Amounts/accounts remain host-derived. Approval cannot post, change booked cash/AP or infer a completed close.

The independent verifier was generalized to multiple or explicitly absent proposals, period/currency scope, original-field relations, exact match/proposal provenance, AP balances and reservations. A fixed exact-reference baseline, development evaluator, public-CLI recovery/review harness, six corrupted-copy controls plus a removed mandatory hold, no-network scripted integration check and owned HTTP protocol double are **authored but unexecuted**. Concurrent review checks launch at most two owned review children. The harness also tests cancellation after one committed tool and clearing provisional residual holds on resume.

### Corpus authorship before policy expansion

Only the standard-library authoring command was executed:

```powershell
py -3.11 -m evaluation.author_fixtures
```

Exit **0**, wall **2.399 s**: 12 development bundles and 32 held-out input/label bundles across eight strata. No actor, scorer or model ran during authorship. Freeze timestamp: **2026-10-08T09:49:51.685238 UTC**. Unchanged M1 scripted-policy SHA-256 captured before expansion: `e8321a39364bf60c7e58302cce5dc458347bb5fb5fd19ae5d27412281a7b5451`, matching main's M1 receipt. Frozen aggregate SHA-256: `f3299b697dc7a4634a28445cf29e9312bf12ff6b5f01844244e30baa97067c34`. The freeze file stores every input/label hash; it refuses regeneration. Development and held-out labels are never acting tool observations. Synthetic authoring and freezing do not certify labels or accounting authenticity.

### Executed lightweight checks

```powershell
py -3.11 -m unittest discover -s tests -p 'test_*.py' -v
py -3.11 -m evaluation.freeze
```

| Component run | Exit | Tests | Failures/errors | Unittest elapsed | Command wall |
| --- | --- | --- | --- | --- | --- |
| Initial M2 components | 0 | 40 | 0 | 4.908 s | 5.501 s |
| Expanded authority/cancellation/metric checks | 0 | 48 | 0 | 4.349 s | 4.937 s |
| Final provisional-residual cleanup check | 0 | **49** | **0** | **3.068 s** | **3.778 s** |

The final unit command's stdout/stderr are preserved in ignored `work/m2-source/units.*.txt`. Tests use temporary authored copies and SQLite components, plus injected in-memory wire transports. They do not run the complete demonstration, start HTTP servers or launch recovery/review subprocesses. Loop checks intentionally terminate on cancellation, malformed/forbidden action, retry exhaustion, no progress or a pre-spent budget. Protocol tests validate native request/observation messages, unknown usage, malformed/duplicate JSON, extra/multiple/free-text responses, body/context/deadline bounds and endpoint rejection. AP components prove settlement is counted once, duplicated sources do not multiply recognition, reservations prevent overcommit, rejected reservations retain audit, approved proposals remain unposted, changed rules/reservations block review, and another invoice's real evidence cannot authorize a proposal. Metric tests preserve zero denominators as not applicable and detect missing material holds/false matches.

`evaluation.freeze`: exit **0**, wall **0.432 s**, **155/155 declared frozen files** hash-matched, 32 cases/eight strata; no scoring. The source-inspection script parsed **25 Python files**, **92 JSON files**, and TOML, exit **0**, wall **0.655 s**; it found 12 development/32 held-out bundles and no M2 integration output directories. Authored corpus size was **87317 bytes**. Source hashes are retained in the checkpoint receipt; this is syntax/hash inspection, not application integration.

No unit-test attempts failed. Four source-patch attempts were rejected for duplicate targets or missing exact anchors and were corrected without running application work. Two read-only file lookups used the wrong root and were corrected. These tooling errors are distinct from the all-passing unit runs; they are not benchmark or application results.

Official Ollama chat/tool-calling documentation was rechecked for source implementation. Dependency/model download bytes: **0**. Live model calls: **0**. No M2 demo, development/held-out scoring, HTTP server, subprocess/recovery integration, remote CI, account operation, posting or publication ran. Peak RAM was not measured. Existing ignored M1 artifacts are historical and are not new M2 evidence.

### Ready commands and new resource request

Run from the repository root, only after main grants and explicitly resumes the **new** `finance-close-m2-integration` lease:

```powershell
py -3.11 -m finance_close doctor
py -3.11 -m evaluation.freeze
py -3.11 -m unittest discover -s tests -p 'test_*.py' -v
py -3.11 -m evaluation.acceptance --milestone 1 --out artifacts/m2-regression-m1
py -3.11 -m evaluation.run --split dev --provider scripted --baseline exact-reference --out artifacts/m2-evaluation
py -3.11 -m evaluation.acceptance --milestone 2 --out artifacts/acceptance-m2
```

Estimated execution: about two minutes; requested cap ten active minutes, **256 MiB RAM**, **25 MiB generated disk**, zero downloads/model calls, one sequential command worker. Maximum owned Python processes: three only during the two-review race; otherwise one child at a time. At most one loopback HTTP server, shut down/joined by the harness. No M3 held-out scoring is included. The old released M1 lease does not authorize this batch. Worker has stopped at `awaiting_integration_lease` and is consuming no heavy resource.


## Leased M2 integration — executed 2026-10-08

Main accepted the source checkpoint for measured integration at **2026-10-08T10:49:43.185690 UTC**, independently confirming all 32 held-out bundles/155 hashes without scoring. The new worker-owned `finance-close-m2-integration` grant expires at 12:19:43.185690 UTC, with a ten cumulative active-minute cap, 256 MiB RAM, 25 MiB generated disk, zero downloads, one sequential command worker, at most three owned Python processes and one loopback server. Only the authored review race uses two simultaneous owned review children.

The ignored PowerShell helper `work/run_leased_m2.ps1` reads the **raw** shared grant JSON before each command, hashes it for the receipt, selects the exact lease/slug/owner/status/M2 scope, parses explicitly timezone-bearing grant/expiry with DateTimeOffset, checks current time and cumulative active seconds, and checks every agreed resource bound. All seven fresh checks passed. It starts the selected Windows `py` launcher with structured argument lists, captures stdout/stderr and exits, stops dependent work on an unexpected failure, and samples only descendants attributed by parent PID and creation time. No unrelated process was stopped. Commands and raw gate/output records are in ignored `work/m2-integration/`.

| Exact command from repository root | Exit | Measured active wall | Grant check UTC |
| --- | --- | --- | --- |
| `py -3.11 -m finance_close doctor` | 0 | 0.514 s | 10:53:09.623 |
| `py -3.11 -m evaluation.freeze` | 0 | 0.379 s | 10:53:10.320 |
| `py -3.11 -m unittest discover -s tests -p 'test_*.py' -v` | 0 | 4.398 s | 10:53:10.719 |
| `py -3.11 -m evaluation.acceptance --milestone 1 --out artifacts/m2-regression-m1` | 0 | 5.450 s | 10:53:15.133 |
| `py -3.11 -m evaluation.run --split dev --provider scripted --baseline exact-reference --out artifacts/m2-evaluation` | 0 | 6.203 s | 10:53:20.601 |
| `py -3.11 -m evaluation.acceptance --milestone 2 --out artifacts/acceptance-m2` | 0 | 13.084 s | 10:53:26.821 |
| `py -3.11 -m evaluation.acceptance --milestone 2 --out artifacts/acceptance-m2-measured` | 0 | 16.028 s | 10:55:12.420 |

Doctor confirms Python **3.11.9**, SQLite **3.45.1**, no runtime dependencies and default offline scripted mode. Units pass **49/49**, zero failures/errors, unittest time **3.979 s**. Freeze verifies **155/155** declared hashes, 32 cases/eight strata and the unchanged aggregate `f3299b697dc7a4634a28445cf29e9312bf12ff6b5f01844244e30baa97067c34`; no held-out scoring was performed. M1 regression passes **14/14** driver assertions and **15 expected-exit CLI calls**. Independent M1 raw-source/state verification passes 255 initial assertions and 257 after either review decision; its deliberately corrupted copy returns expected exit 1 with four detected failures. The original M1 cash outcomes and missing-invoice hold persist.

### Independent development outcomes and fixed baseline

All **12/12** development bundles complete, with zero execution errors, and pass **3143/3143** separate raw-source/state/provenance assertions. The acting policy receives no labels. This is a small authored development comparison; it is neither held-out scoring nor live-model-quality evidence.

| Labeled outcome | Scripted workflow | Fixed exact-reference baseline |
| --- | --- | --- |
| Exact match/hold/proposal case outcomes | 12/12 | 3/12 |
| Correct cash matches / predicted / gold | 19 / 19 / 19 | 19 / 19 / 19 |
| Correct open holds / predicted / gold | 15 / 15 / 15 | 7 / 9 / 15 |
| Correct proposals / predicted / gold | 2 / 2 / 2 | 0 / 0 / 2 |
| Missed material gold holds | 0/12 | 6/12 |

Both policies have 19/19 match precision and recall in these development cases; no match improvement is claimed. Workflow hold precision/recall is 15/15. Baseline hold precision is 7/9 and recall 7/15. Workflow proposal precision/recall is 2/2; baseline proposal precision has denominator zero and is **not applicable**, while recall is 0/2. Materiality is the authored inclusive 10000-cent policy, not an accounting standard; the denominator counts labeled holds, including specific and residual holds. Exact outcome comparison covers labeled matches, holds and proposals; the actor's independent verifier additionally checks AP, raw sources and provenance.

Observed domain examples, in cents:

- **D03 partial payment:** 103300 recognized, 80000 already booked settlements, 23300 booked AP remaining. Matching the current 60000 bank payment to its existing cash line does not subtract it a second time. Bank/ledger closing both 939300, no proposal.
- **D04 missing AP payment:** actual booked AP remains 100000; the unposted 100000 proposal reserves 100000 and leaves available AP zero. Bank closing 899300 and immutable ledger closing 999300 retain their -100000 booked difference; proposed cash effect is shown separately. Both balanced lines derive from source-backed policy, with full invoice/history/bank evidence.
- **D05/D06 duplicates/conflicts:** two semantic copies retain both source provenances without duplicate recognition. Conflicting invoice amount copies retain an independent open `CONFLICTING_EVIDENCE` hold and emit no proposal.
- **D09/D10:** booked AP -18900 produces an `OVERPAYMENT` hold; omitted complete-history assertion preserves `INCOMPLETE_HISTORY` on the matched 60000 cash payment.
- **D11 reservations:** actual AP is 103300, separate reservation 60000 and available AP 43300. A second 50000 payment is held with `OVERPAYMENT` and `UNMATCHED_CASH`; exactly one proposal exists. Actual ledger cash remains 999300 and every proposal is unposted.
- **D12 unsupported EUR:** record remains visible with `UNSUPPORTED_CURRENCY` and `UNMATCHED_CASH`. It is excluded from USD arithmetic, leaving bank/ledger closing both 999300 and bridge residual zero. No FX or automatic posting is inferred.

Every development bridge residual is zero. Every imported ledger and source field equals original bytes/values under independent checks. Actual booked balances exclude proposals throughout. Case DONE records investigation coverage and does not infer a financial close.

### Recovery, review, authority and verifier negative controls

Both M2 acceptance outputs pass **34/34** driver checks across **40 expected-exit CLI calls** each. The final measured run has 27 exits 0, seven expected verifier exits 1, three expected review exits 2, one expected cancellation exit 3 and two injected crash exits 85. No unexpected application/test command failure occurred; expected negative failures are retained in the reports.

Cancellation after one committed tool emits explicit CANCELLED state and both unmatched bank holds. Resume completes one proposal and removes resolved provisional residual holds. Crashes after proposal commit and before packet rename each recover to the same full proposal hash and one proposal/reservation, with unchanged imported ledger. Repeated completed runs do not repeat domain effects or calls.

Exact AP approval and rejection each remain unposted and preserve actual booked cash/AP. Approval keeps the active reservation; rejection releases its active effect while retaining one reservation audit row. Identical repeated reviews do not duplicate effects. Identical concurrent reviews return [0,0] with one committed review; conflicting concurrent reviews return [0,2] with one consistent decision. Stale hash and changed original source review attempts return expected exit 2 without committing a new review.

Six mutations of **fresh copied** final states plus one removed mandatory invoice hold all cause the independent verifier to return expected exit 1:

| Control | Detected failed assertions |
| --- | --- |
| Wrong proposal line amount | 4 |
| Deleted proposal, testing required presence/recall | 7 |
| Wrong bank-to-cash match | 14 |
| AP reservation overcommit | 4 |
| Deleted evidence relation | 2 |
| Real evidence from a different source row | 2 |
| Removed mandatory missing-invoice hold | 2 |

The source run, original input bytes and labels remain intact. The whole scripted no-network run also passes with socket construction forbidden. No actor API can approve/post, choose amounts/accounts or read labels; component authority tests remain passing.

### Real local protocol evidence and cleanup

Each M2 acceptance executes a real owned loopback `/api/chat` HTTP double for D04. **11 requests** carry native schemas, nonstreaming function calls and actual assistant/tool observations. The trace selects inspect/candidates/match/finish for the anchor, then inspect/candidates/search/read/AP balance/draft/finish for the missing payment, incorporating up to six prior observations. All **6/6** protocol checks and **237/237** independent domain assertions pass. Persisted adapter attempts match the 11 requests. Decisions and token counts are scripted/synthetic; live model calls are **0**, so this demonstrates wire behavior and guards, not model quality.

The protocol harness shuts down/closes its server and joins its owned thread; the adapter cancels/joins its request timer and closes the connection. Review children are collected by their parent. Final parent-PID/creation-time inspection finds **zero remaining observed owned descendants** across all seven command runs. No unrelated process was interrupted.

### Instrument correction and resource accounting

The first six commands passed without changing application, verifier, label or policy code. Before reporting, every source-checkpoint hash still matched. The initial sampler correctly summed owned working sets, but its process-name regex missed Windows' `python3.11.exe`, so the initial zero Python count is **invalid and is not evidence of zero child processes**. The ignored helper's regex was corrected. Only M2 acceptance was repeated into a fresh output directory to verify this resource concern; its first passing raw report was preserved. No assertion or gate was weakened. The measured repeat records the permitted maximum **three concurrent owned Python processes** during the review race.

Cumulative measured heavy-command active wall time: **46.0566405 seconds** of 600 granted seconds. Sampled aggregate owned-process working set peaks at **97607680 bytes (93.09 MiB)**, below 256 MiB. This is sampled working set, **not an exact OS peak-memory measurement**. All artifact directories total **22407307 bytes (21.37 MiB)**, conservatively including historical M1 artifacts; current M2 integration logs add about 27 KiB. The M2 artifact increase is 19301233 bytes. Both the total artifacts and the new generated footprint are within the 25 MiB grant. Execution uses one sequential command worker except the authorized two-review race; no download, model runtime, credential or external-account operation occurred.

Worker marks the M2 lease **release-ready** and stops consuming it. Main must independently review before accepting M2. **M3 held-out scoring, live model inference, remote CI, real accounts/ledger posting, publishing and deployment remain unexecuted.**


## Main independent M2 acceptance — 8 October 2026

Main accepted M2 at **2026-10-08T11:05:04.116859+00:00**, after six fresh commands, **49/49** component tests, **3143/3143** development verifier assertions, **34/34** M2 driver checks across **40** nested CLI calls, M1 regression, and **106/106** additional direct reviewer checks. Main compared original bank/ledger CSV values and stored raw bytes across all **12/12** development cases. Exact core outcomes remained **12/12** for the actor versus **3/12** for the fixed baseline, with **0/12** missed material holds for the actor. Both actual owned abrupt child exits, review races, approval/rejection balances, seven corrupt-state controls and the owned protocol double passed. This supersedes the earlier worker report's pending-review status; its raw first reports and resource correction remain historical evidence. Main released the M2 lease. Held-out scoring remained unexecuted.

## M3 source and pure reporting checkpoint — 8 October 2026

**Source preparation only. No M3 lease has been granted or consumed. No full CLI, HTTP, integration, evaluator, held-out scoring, repetitions or CI-equivalent run was executed during this phase.** M2 actor modules and `rules/v1.json` are byte-identical to the accepted M2 source: all **14** hashes match the source baseline. No frozen input or label was changed or regenerated. The freeze manifest hash remains `789aa6862f42e8c130cefba74a6460704f700ca9bcd4c6b299abc09242a6faf5`; all **155** declared file hashes pass, covering **32** cases and **8** strata. Aggregate `f3299b697dc7a4634a28445cf29e9312bf12ff6b5f01844244e30baa97067c34` is unchanged.

Prepared source includes pure rate/aggregation/release helpers, first-failure and complete outcome differences, per-repetition/per-stratum and hold-reason/proposal-rule denominators, independent source/proposal/provenance audit rates, public-CLI actor subprocess evaluation, canonical domain comparison, final raw-state rechecks and a shared local/hosted CI command plan. Missing or failed executions retain gold and attempt denominators; only actually scored packets and completed audits count toward their corresponding coverage. Duplicate repetition identities and baseline failures are explicit failures. The first held-out report will be preserved; corrections after exposure must be labeled regression. The strict driver still requires **every independent case check**, in addition to the predeclared release minima. Nothing was weakened to pass.

M3 material reporting includes **all** gold hold reason types with inclusive exposure at least 10000 cents, replacing the earlier scorer's reason allowlist before held-out exposure. This strengthens the outcome denominator; it does not change actor behavior, materiality threshold, inputs or labels. New verifier counters also include invalid/unknown-scope proposals, duplicate exception identities, positive balanced lines, source/rule integrity and exact AP reservations. These verifier additions are source-prepared; their actual-domain integration remains pending.

Completed pure checks on Python **3.11.9**, SQLite **3.45.1**:

| Command/check | Actual result | Scope |
| --- | --- | --- |
| `py -3.11 -m unittest discover -s tests -p 'test_m3.py' -v` — first complete transcript | Exit 0; 11 tests; 0 failures/errors; 0.051 s unittest, 1.0788964 s command wall | In-memory reporting/gate examples only |
| Same pure subset after additional identity/baseline cases | Exit 0; 13 tests; 0 failures/errors; 0.071 s unittest, 0.5552613 s command wall | No actor, fixture scoring, database, subprocess or HTTP execution |
| Source AST and JSON/TOML parse | Exit 0; 31 Python files and 93 JSON files parse; TOML valid | Read-only syntax/config inspection; no outcome calculation |
| Read-only freeze hash check | Exit 0; 32 cases, 8 strata, 155 file hashes match | No regeneration or scoring |
| `evaluation.m3_acceptance.source_checks()` called directly | 10/10 checks; no broken local links | Documentation/config/path/license inspection only; not `accept()` |
| Actor/rule and freeze-manifest comparison | Exit 0; 14/14 actor/rule hashes and manifest hash unchanged | No actor policy tuning |

An initial parallel pure-unit reply was truncated, so the same 11-test invocation was repeated solely to obtain a complete visible transcript, with no source change between those invocations. The complete transcripts above have no unexpected test failure. They do not establish 62-test full-suite success: the accepted 49 M2 tests plus the 13 new tests must be run together under the final lease. Source-only documentation inspection initially found an uncreated CI document and a mistyped notice filename; the final required document names and links pass. No gate, label or safety control was reduced.

README, architecture, evaluation, CI, contribution instructions, MIT/data/runtime notices and limitations now describe standalone reproduction and the accepted M2 boundary. The actual recovery claim is two owned `os._exit(85)` CLI child exits after proposal commit or before packet rename, followed by normal resume. Power-loss, fsync, interrupted SQLite commit, host shutdown, disk/controller faults and production supervision remain untested. Packet JSON/HTML are individual replacements, not an atomic pair, and are not explicitly fsynced.

### Exact final commands prepared, not executed

All eight commands below require a **new named M3 integration lease** in this managed project. Outputs must be fresh. Expected top-level exits are 0; nested M1/M2 negative-control exits remain intentionally nonzero and recorded by their drivers.

```powershell
py -3.11 -m finance_close doctor
py -3.11 -m evaluation.freeze
py -3.11 -m unittest discover -s tests -p 'test_*.py' -v
py -3.11 -m finance_close demo --out artifacts/final-demo --provider scripted
py -3.11 -m evaluation.verify --run artifacts/final-demo --labels evaluation/labels/demo.json
py -3.11 -m evaluation.run --split heldout --provider scripted --baseline exact-reference --repeat 3 --allow-heldout --evidence-phase first-frozen-pass --out artifacts/final-evaluation
py -3.11 -m evaluation.acceptance --milestone 3 --evaluation artifacts/final-evaluation --out artifacts/acceptance-m3
py -3.11 -m evaluation.ci --out artifacts/ci-final --allow-heldout
```

The primary evaluation prepares **96** attempts on **32** distinct authored examples. Final acceptance rereads all saved states and runs the M1/M2 regressions (15 + 40 nested CLI calls when their ordinary paths complete). The CI-equivalent wrapper has seven sequential top-level steps, repeats the same frozen policy into a fresh directory, labels this `public-ci-reproduction`, and runs final acceptance again. Those are prepared counts, not observed M3 successes or independent additional samples. No automatic retry of a failing case is planned. Preserve first failed reports and stop for review if a top-level gate fails.

Requested lease: **finance-close-m3-integration**, ten active minutes, estimated four minutes; **256 MiB** sampled owned-process working-set budget; **200 MiB** generated artifact budget, conservatively including existing artifacts and two 96-attempt result trees plus two regression trees. The larger disk request replaces the earlier normal-acceptance estimate because raw first reports and CI reproduction are both retained; it is an estimate to measure, not an achieved footprint. One sequential command worker, at most **four** owned Python processes during CI-parent → acceptance-parent → two-review-child races, and one owned loopback HTTP server at a time. No downloads, dependency installs or model calls. Resource consumption is currently false; no finance lease is active.

**M3 held-out outcomes, baseline totals, repetition agreement, final CLI rechecks and local CI-equivalent results remain UNEXECUTED. Remote CI, Linux execution, live inference, professional accounting validation, production accounts/posting, power-loss/fsync durability, publication and deployment remain UNEXECUTED.** The worker stops at `awaiting_integration_lease`; source preparation is not M3 acceptance.


## M3 first frozen pass — stopped at an unexpected failure, 8 October 2026

Main accepted the M3 source and all 32 frozen rubrics after **13 pure tests** and **310 independent static conditions**. It then granted the worker-owned **finance-close-m3-integration** lease at **2026-10-08T12:59:44.346367+00:00**, expiring at **14:29:44.346367+00:00**. The exact lease and source preflight passed before execution; the ignored local guard reread the active named lease before each command. Scope was eight sequential commands, 600 cumulative active seconds, 256 MiB RAM, 200 MiB generated disk, zero installs/downloads/model calls, one CPU worker, at most four owned Python processes and one loopback double, with a 240-second top-level deadline.

**Command 6 returned 1 on the first frozen pass. Work stopped immediately after that top-level failure. Commands 7 and 8, final M3 acceptance and local CI-equivalent reproduction, were not run. M3 is not accepted; status is `correction_needed`, consuming false and lease release-ready.** No actor, baseline, evaluator, label, freeze, release policy or gate was changed. Only documentation was updated after the retained failure to describe actual results.

### Exact executed commands and measured time

| Index | Command | Actual exit | Active wall seconds |
| --- | --- | --- | --- |
| 1 | `py -3.11 -m finance_close doctor` | 0 | 0.4846819 |
| 2 | `py -3.11 -m evaluation.freeze` | 0 | 0.3714580 |
| 3 | `py -3.11 -m unittest discover -s tests -p 'test_*.py' -v` | 0 | 3.1392882 |
| 4 | `py -3.11 -m finance_close demo --out artifacts/final-demo --provider scripted` | 0 | 0.8353831 |
| 5 | `py -3.11 -m evaluation.verify --run artifacts/final-demo --labels evaluation/labels/demo.json` | 0 | 0.3843659 |
| 6 | `py -3.11 -m evaluation.run --split heldout --provider scripted --baseline exact-reference --repeat 3 --allow-heldout --evidence-phase first-frozen-pass --out artifacts/final-evaluation` | 1 | 57.8738735 |

The full suite passes **62/62** tests with zero failures/errors in **2.743 seconds** of unittest time. The scripted demo passes **257/257** independent assertions, preserving B001 and B003 exact cash matches, B003's missing-invoice hold, and the 3000-cent pending/unposted fee draft. Bank closing is 872000, immutable ledger closing 875000, booked difference -3000 and bridge residual zero. The draft's proposed cash effect is separate. Demo audit counts are 1/1 balanced and source-valid proposal, 5/5 required provenance relations and 74/74 extracted fields.

### First-score failure, preserved without correction

`artifacts/final-evaluation/evaluation.json` is the retained **first-frozen-pass** result. All **96/96** actor processes return 0, all packets are scored and independently audited, and actor/baseline execution errors are **0**. There are **32** declared distinct authored examples, not 96 independent samples. Three attempts fail the independent exact outcome check: **H16 in repetitions 1, 2 and 3**. The first failure is repetition 1, assertion **specific open exception outcomes**.

H16's bank and ledger cash rows are USD and match at **105500 cents**. Both bank and ledger closing are **893800**, bridge residual zero, actual AP zero, no reservation and no proposal. The USD/EUR invoice copies conflict. The frozen expected hold is exactly `CONFLICTING_EVIDENCE`, exposure **105500**. Actual output has that required hold plus an unexpected `UNSUPPORTED_CURRENCY`, also **105500**. No match or proposal is missing or extra. Read-only source inspection finds `Tools.required_flags` adds the currency flag for any non-USD invoice copy, even when the group is already conflicting. This diagnosis is not a code change or permission to tune after exposure.

Each repetition has **31/32** exact core and verified cases (96.875%). It clears the numerical 90% minimum but fails the preserved stronger **all independent case checks** gate. Exactly those three strict gates fail; the release decision remains false. All **32/32** canonical domain states agree across repetitions, including the repeated error. The independent verifier records **24189 passed / 24192 total assertions**, with exactly **3** failed assertions, one per H16 attempt. No failure was suppressed or rerun.

### Cash correctness, AP/holds and fixed baseline reported separately

| Outcome, each repetition | Scripted workflow | Fixed exact-reference baseline |
| --- | --- | --- |
| Exact core match/hold/proposal cases | 31/32 | 9/32 |
| Correct cash matches / predicted / gold | 49 / 49 / 49 | 48 / 48 / 49 |
| Correct open holds / predicted / gold | 40 / 41 / 40 | 20 / 26 / 40 |
| Correct proposals / predicted / gold | 4 / 4 / 4 | 0 / 0 / 4 |
| Missed material gold holds / gold material holds | 0/30 | 15/30 |

Workflow match precision and recall are **49/49** each repetition. Baseline precision is **48/48**, recall **48/49**. Workflow hold precision is **40/41**, recall **40/40**; baseline precision **20/26**, recall **20/40**. Workflow proposal precision/recall is **4/4**. Baseline proposal precision is **0/0, not applicable**, and recall **0/4**. The baseline has no invoice/AP investigation or proposal capability; compare its exact core sets, not the workflow's extra state/provenance checks. There is **no baseline-gap release gate**.

Across repeated attempts, workflow correct/predicted/gold match counts are **147/147/147**, holds **120/123/120**, proposals **12/12/12** and material misses **0/90**. Baseline counts are matches **144/144/147**, holds **60/78/120**, proposals **0/0/12**, material misses **45/90**. Exact cases are **93/96** versus **27/96**. Materiality counts all gold reasons with inclusive exposure at least 10000 cents. Aggregated repeated denominators measure attempts, not additional independent examples.

The existing saved verifier assertions for raw bank/ledger equality, literal bank/ledger closing, exact match edges and cash bridge all pass in **96/96** attempts. This cash result does not erase the extra invoice hold or certify a financial close. All **12/12** emitted proposals are balanced, validated and unposted; required provenance is **249/249** and extracted source fields **7818/7818**. Audited coverage is **96/96**; unknown scopes, committed forbidden actions and duplicate domain effects are **0**, and reported safety invariants pass. Actual booked balances exclude proposals throughout.

H27's actual AP is **104400**, separate pending reservation **60000** and available AP **44400**. Its second **50000** payment is held for overpayment and unmatched cash; one 60000 draft remains pending/unposted. Actual bank closing **889300**, ledger closing **999300** and booked difference **-110000** remain distinct from the **-60000** proposed cash effect. H28 has actual AP/reservation/available all **0**, emits no proposal and holds the new **30000** payment for overpayment and unmatched cash; bank closing **969300** versus ledger **999300**, bridge residual zero. These separate cash, AP and exception outcomes match the frozen rubric.

### Strata and exact reason/rule denominators

Each stratum has four distinct cases and twelve repeated attempts. The duplicate/conflict stratum contains the single failing distinct case H16.

| Stratum | Workflow exact attempts | Baseline exact attempts |
| --- | --- | --- |
| amounts | 12/12 | 0/12 |
| ap_missing | 12/12 | 0/12 |
| duplicates | 9/12 | 6/12 |
| exact | 12/12 | 9/12 |
| fees | 12/12 | 6/12 |
| missing_invoice | 12/12 | 0/12 |
| partial | 12/12 | 6/12 |
| timing_unsupported | 12/12 | 0/12 |

| Workflow hold reason, all repetitions | Correct | Predicted | Gold |
| --- | --- | --- | --- |
| AMBIGUOUS_MATCH | 9 | 9 | 9 |
| AMOUNT_CONFLICT | 6 | 6 | 6 |
| CONFLICTING_EVIDENCE | 6 | 6 | 6 |
| INCOMPLETE_HISTORY | 3 | 3 | 3 |
| MISSING_INVOICE | 15 | 15 | 15 |
| OVERPAYMENT | 9 | 9 | 9 |
| TIMING_DIFFERENCE | 6 | 6 | 6 |
| UNMATCHED_CASH | 39 | 39 | 39 |
| UNMATCHED_LEDGER | 21 | 21 | 21 |
| UNSUPPORTED_CURRENCY | 3 | 6 | 3 |
| UNSUPPORTED_TRANSACTION | 3 | 3 | 3 |

| Workflow proposal rule, all repetitions | Correct | Predicted | Gold |
| --- | --- | --- | --- |
| BANK_FEE_V1 | 3 | 3 | 3 |
| MISSING_AP_PAYMENT_V1 | 9 | 9 | 9 |

All first failures, missing/unexpected outcomes, baseline outputs, per-case source/SQLite state, packet, verification, canonical hashes and per-repetition/per-stratum counters remain in the first-score tree. **866** first-score files totaling **38152644 bytes** were read-only hash-sealed in the worker checkpoint after failure. No first report was overwritten. Any authorized future correction must use fresh output directories and **regression-after-exposure**; it cannot restore blind held-out status.

### Resources, cleanup, preserved hashes and unexecuted work

Cumulative measured heavy-command wall time is **63.0890506 seconds** of the 600-second grant. Sampled aggregate owned working set peaks at **83234816 bytes (79.38 MiB)**; at most **two** owned Python processes were observed. This is sampled working set, not an exact OS peak. Fast command samples can miss working-set values; zero samples are not evidence of zero memory use. No HTTP protocol server was started in this M3 sequence because the acceptance step was never reached.

All artifact directories total **73531555 bytes (70.13 MiB)**, conservatively including historical M1/M2 and main-review artifacts. Fresh demo plus first evaluation total **38414961 bytes (36.64 MiB)**. Current M3 integration logs/cleanup add **162351 bytes**. Counts were measured after the stopped run and are below the 200 MiB grant. No dependency installation, download, model call, paid call, account operation or publication occurred. Final PID/creation-time inspection finds **zero remaining observed owned descendants**, with no unrelated process interrupted.

All **49** source-checkpoint file hashes matched before documentation was updated; acting source/rule hashes before and after evaluation agree. The 32-case/155-file freeze is unchanged at aggregate `f3299b697dc7a4634a28445cf29e9312bf12ff6b5f01844244e30baa97067c34`. Release-policy hash remains `9f9ee61e6ade0fef90966adbca07e13c5d715b1e9e94d06dbdfd1c944c31a57a`. Frozen labels, baseline and all evaluation/actor logic remain unchanged.

**Final M3 raw-state acceptance, its M1/M2 regression reruns, local CI-equivalent/public-ci reproduction, remote CI/Linux, live inference, professional accounting validation, power-loss/fsync durability, production accounts/posting, deployment and publication remain UNEXECUTED.** Earlier accepted M2 evidence of actual owned `os._exit(85)` boundaries and a scripted local HTTP double does not establish power-loss durability or live-model quality. The worker has stopped and requests main's review of the preserved failure before any correction or additional integration.


## M3 bounded currency-consensus correction — source and pure units only

Main independently confirmed the retained H16 failure in all three original SQLite states and authorized only the generic classification correction plus pure source units. The old heavy lease is released. **No full suite, actor CLI, HTTP, integration, scoring, downloads or model calls ran during this correction phase.** The original first score remains **93/96 exact attempts, 31/32 each repetition**, with the three H16 failures retained.

Before modifying actor/version source, the originally scored **0.1.0** actor, evaluation logic, baseline, rules, release policy, freeze manifest and all 155 frozen input/label files were archived and read-back hash-verified. The archive has **187 files**, **127923 bytes**, SHA-256 `b178688ab125ba427ddb9f657ed8fe4f45fc5dcfbc1538fa875d850b8763a069`. All **866** first-score artifact hashes still match. The original result tree remains in place; it was not regenerated or overwritten.

Candidate **0.1.1** changes only the invoice-currency decision in `finance_close/tools.py`: derive the set of currencies within each same-identity invoice group; a group must agree on exactly one non-USD currency to establish unsupported invoice currency. Contradictory USD/EUR or EUR/GBP copies retain the existing conflicting-evidence hold without choosing a first or majority copy. A genuinely foreign bank independently remains unsupported. An unambiguous foreign invoice currency still produces its hold, even when other invoice fields conflict. Existing conflict and AP proposal restrictions are unchanged. Package/module versions advance from 0.1.0 to 0.1.1 to identify this corrected candidate; no rule, baseline, label, threshold or evaluation logic changes.

New `tests/test_currency_consensus.py` contains **8 pure test methods / 19 in-memory scenarios**: both copy orders, multiplicity without majority voting, contradictory foreign currencies, consistent USD and foreign copies, foreign-currency consensus with another field conflict, foreign bank plus contradictory invoice copies, and blocked AP drafts with no database call. Facts and read interfaces are mocked; no fixture parsing, SQL, actor CLI, HTTP or scoring occurs in this subset.

| Exact pure command | Candidate | Actual result |
| --- | --- | --- |
| `py -3.11 -m unittest discover -s tests -p 'test_currency_consensus.py' -v` | Before correction, archived 0.1.0 behavior | Exit **1**, 8 methods, **7 failing subtests**, 0 errors, **0.011 s** unittest, **0.234 s** command wall |
| Same command | Corrected 0.1.1 | Exit **0**, **8/8** methods, 0 failures/errors, **0.009 s** unittest, **0.234 s** command wall |

The initial failures deliberately demonstrate that the new tests catch the generic bug; both raw transcripts are retained in `work/m3-currency-source/`. No assertion was weakened between runs. Source inspection parses **32** Python files, finds **70** expected full-suite methods without executing them, validates version/dependency TOML, and passes **10/10** documentation/source checks. Baseline/evaluation logic, all 155 frozen hashes and the release-policy hash remain unchanged. The new ignored regression lease guard parses successfully and has not been invoked.

**This correction is validation-set-informed.** Future scores on this exposed authored corpus must be called post-fix regression or public-fixture reproduction. The directory stays named `heldout` for compatibility and byte preservation; that name does not restore unseen status. New primary evaluation must use `--evidence-phase regression-after-exposure`; the CI wrapper uses `public-ci-reproduction`. Never substitute a corrected score for the original 31/32 result.

### Fresh regression lease requested; commands unexecuted

Requested name **finance-close-m3-regression**: ten cumulative active minutes, estimated four minutes, 256 MiB RAM, 200 MiB generated disk including retained first-score/historical artifacts, one sequential CPU worker, at most four owned Python processes and one owned loopback double, 240-second top-level command timeout, zero downloads/installs/model calls. Estimates are not new measured integration evidence. No lease is active or consumed for this correction; the worker stops at `awaiting_integration_lease` for main's source review and fresh grant.

```powershell
py -3.11 -m finance_close doctor
py -3.11 -m evaluation.freeze
py -3.11 -m unittest discover -s tests -p 'test_*.py' -v
py -3.11 -m finance_close demo --out artifacts/currency-regression-demo --provider scripted
py -3.11 -m evaluation.verify --run artifacts/currency-regression-demo --labels evaluation/labels/demo.json
py -3.11 -m evaluation.run --split heldout --provider scripted --baseline exact-reference --repeat 3 --allow-heldout --evidence-phase regression-after-exposure --out artifacts/currency-regression-evaluation
py -3.11 -m evaluation.acceptance --milestone 3 --evaluation artifacts/currency-regression-evaluation --out artifacts/currency-regression-acceptance
py -3.11 -m evaluation.ci --out artifacts/currency-regression-ci --allow-heldout
```

All eight commands above are **unexecuted for candidate 0.1.1**. Fresh directories protect the first result. Final acceptance would independently reread all 96 new saved states and rerun M1/M2 CLI safety/recovery/protocol checks; CI would reproduce into another fresh tree. Stop at any unexpected top-level failure and report before changing code. Full candidate tests, corrected domain outcome counts, final M3 acceptance, local CI reproduction, hosted CI/Linux, live inference, production accounts/posting, power-loss/fsync durability and publication remain unexecuted. The original gates and first failure remain intact.


## M3 candidate 0.1.1 — passing post-fix regression and local CI reproduction

Main accepted the currency-consensus source after **8 pure tests and 947 independent hash conditions**. It granted the fresh worker-owned **finance-close-m3-regression** lease at **2026-10-08T13:30:59.704680+00:00**, expiring **2026-10-08T15:00:59.704680+00:00**. Exact owner, milestone, timestamps, command list and bounds passed preflight, and the ignored local guard reread the named active lease before every command. The same 600-active-second, 256 MiB RAM, 200 MiB disk, one-worker, four-owned-Python/one-loopback and 240-second top-level bounds applied. No source tuning was authorized or performed in this batch.

**All eight requested top-level commands return 0. Worker marks M3 `milestone_ready`, `release_ready=true`, `currently_consuming=false` and stops for independent main verification. This is worker evidence, not independent main M3 acceptance.** The first frozen result remains **93/96 exact attempts, 31/32 each repetition**, including all three original H16 failures. Candidate 0.1.1 was informed by that exposure; every subsequent score is explicitly regression/public-fixture reproduction, never a new blind or unseen held-out result.

### Exact commands and measured exits

| Index | Command | Actual exit | Active wall seconds |
| --- | --- | --- | --- |
| 1 | `py -3.11 -m finance_close doctor` | 0 | 0.4579114 |
| 2 | `py -3.11 -m evaluation.freeze` | 0 | 0.4204726 |
| 3 | `py -3.11 -m unittest discover -s tests -p 'test_*.py' -v` | 0 | 3.1828162 |
| 4 | `py -3.11 -m finance_close demo --out artifacts/currency-regression-demo --provider scripted` | 0 | 0.8496377 |
| 5 | `py -3.11 -m evaluation.verify --run artifacts/currency-regression-demo --labels evaluation/labels/demo.json` | 0 | 0.4022652 |
| 6 | `py -3.11 -m evaluation.run --split heldout --provider scripted --baseline exact-reference --repeat 3 --allow-heldout --evidence-phase regression-after-exposure --out artifacts/currency-regression-evaluation` | 0 | 66.6904535 |
| 7 | `py -3.11 -m evaluation.acceptance --milestone 3 --evaluation artifacts/currency-regression-evaluation --out artifacts/currency-regression-acceptance` | 0 | 19.2943669 |
| 8 | `py -3.11 -m evaluation.ci --out artifacts/currency-regression-ci --allow-heldout` | 0 | 90.7677349 |

Doctor records **Python 3.11.9**, **SQLite 3.45.1**, no runtime dependencies and no network/model inference for the scripted route. The full suite passes **70/70** tests with zero failures/errors in **2.661 seconds** of unittest time. The demo passes **257/257** independent assertions and preserves all earlier literal cash outcomes: B001 and B003 cash matches, B003 missing-invoice hold, 3000-cent pending/unposted fee, bank closing 872000, immutable ledger closing 875000, booked difference -3000 and bridge residual zero. The proposal never enters booked cash.

### Exposed-fixture regression, exact denominators and baseline

The primary report `artifacts/currency-regression-evaluation/evaluation.json` records **regression-after-exposure**. It completes **96/96** scored/audited attempts over **32** declared distinct authored cases, with zero actor/baseline execution errors, no first failure and no failed case. All **24192/24192** independent assertions pass. Each of three repetitions has the following same counts:

| Outcome, each repetition | Scripted workflow | Fixed exact-reference baseline |
| --- | --- | --- |
| Exact core match/hold/proposal cases | 32/32 | 9/32 |
| Correct cash matches / predicted / gold | 49 / 49 / 49 | 48 / 48 / 49 |
| Correct open holds / predicted / gold | 40 / 40 / 40 | 20 / 26 / 40 |
| Correct proposals / predicted / gold | 4 / 4 / 4 | 0 / 0 / 4 |
| Missed material gold holds / gold material holds | 0/30 | 15/30 |

Workflow match, hold and proposal precision/recall are exact **49/49**, **40/40**, **4/4** each repetition. Baseline match precision/recall are **48/48** and **48/49**; hold precision/recall **20/26** and **20/40**; proposal precision **0/0, not applicable**, recall **0/4**. Core outcome comparison is like-for-like; the actor's additional AP/provenance state audit has no baseline equivalent. There is **no baseline-gap gate**.

Across one 96-attempt tree, actor correct/predicted/gold counts are matches **147/147/147**, holds **120/120/120**, proposals **12/12/12**, with material misses **0/90**. The fixed baseline remains matches **144/144/147**, holds **60/78/120**, proposals **0/0/12**, material misses **45/90** and **27/96** exact cases. All gold reasons at inclusive 10000 cents count toward materiality. Repeated totals do not add independent examples. The only first-score behavior corrected is one false currency hold per repetition; cash matches and AP proposal counts were already correct in the original first result.

All **32/32** canonical domain states agree across three repetitions. All strict independent-case checks and all **53** predeclared release checks pass. Safety invariants pass, with zero committed forbidden actions, duplicate domain effects and unknown provenance scopes. Balanced and validated proposals are **12/12**; required provenance relations **249/249**; extracted fields **7818/7818**; audited coverage **96/96**. Missing/extra hold/proposal sets are empty. Actual booked balances exclude every pending or approved draft.

Literal cash checks are reported separately from invoice/AP behavior: saved raw-bank/ledger equality, gold cash closing, exact match-edge and bridge assertions all pass in **96/96** primary attempts. H16 now has only the required **CONFLICTING_EVIDENCE** hold at **105500 cents**. Its USD cash match, bank/ledger closing **893800**, actual AP/reservation **0**, no proposal and zero bridge residual are preserved. No invoice copy becomes posting authority. H27 retains actual AP **104400**, separate pending reservation **60000**, available **44400**, and second-payment **50000** overpayment/unmatched holds; H28 retains booked AP **0**, no proposal and **30000** overpayment/unmatched holds. Source-first evidence and booked/proposed cash separation remain intact.

### Strata, hold reasons and proposal rules

Each stratum contains four distinct authored cases and twelve repeated attempts. These are repeated outcome denominators, not independent samples.

| Stratum | Workflow exact attempts | Baseline exact attempts |
| --- | --- | --- |
| amounts | 12/12 | 0/12 |
| ap_missing | 12/12 | 0/12 |
| duplicates | 12/12 | 6/12 |
| exact | 12/12 | 9/12 |
| fees | 12/12 | 6/12 |
| missing_invoice | 12/12 | 0/12 |
| partial | 12/12 | 6/12 |
| timing_unsupported | 12/12 | 0/12 |

| Workflow hold reason, one 96-attempt tree | Correct | Predicted | Gold |
| --- | --- | --- | --- |
| AMBIGUOUS_MATCH | 9 | 9 | 9 |
| AMOUNT_CONFLICT | 6 | 6 | 6 |
| CONFLICTING_EVIDENCE | 6 | 6 | 6 |
| INCOMPLETE_HISTORY | 3 | 3 | 3 |
| MISSING_INVOICE | 15 | 15 | 15 |
| OVERPAYMENT | 9 | 9 | 9 |
| TIMING_DIFFERENCE | 6 | 6 | 6 |
| UNMATCHED_CASH | 39 | 39 | 39 |
| UNMATCHED_LEDGER | 21 | 21 | 21 |
| UNSUPPORTED_CURRENCY | 3 | 3 | 3 |
| UNSUPPORTED_TRANSACTION | 3 | 3 | 3 |

Fee proposal counts are **3/3/3** correct/predicted/gold across repetitions; missing-AP-payment proposals **9/9/9**. Each emitted proposal balances, validates against original evidence and remains unposted. Raw per-repetition, per-stratum, reason/rule and baseline denominators remain in both separate reports.

### Final raw-state acceptance and local CI reproduction

Primary M3 acceptance passes **215/215** driver checks, rereads all **96** saved states and passes another **24192/24192** raw-state assertions. It recomputes metrics from original sources/SQLite/evidence and requires equality with the report. It also executes the M1 driver (**14/14** checks, **15** public CLI calls) and M2 driver (**34/34** checks, **40** public CLI calls). Approval/rejection, races, stale review guards, immutable source/booked balances, no-network scripted integration, cancellation/resume, actual owned child exits and seven verifier corruption controls all pass.

The local CI wrapper completes **7/7** sequential steps with zero unexpected failure:

| CI step | Actual exit | Nested wall seconds |
| --- | --- | --- |
| doctor | 0 | 0.188 |
| freeze integrity | 0 | 0.171 |
| 70-test suite | 0 | 2.672 |
| scripted demo | 0 | 0.672 |
| independent demo verification | 0 | 0.203 |
| public-ci-reproduction, 96 attempts | 0 | 67.516 |
| M3 raw-state/CLI acceptance | 0 | 18.844 |

CI component tests pass **70/70** in **2.445 seconds** of unittest time. Its separate evaluation is labeled **public-ci-reproduction**, passes **96/96** attempts and **24192/24192** assertions, and has the same exact aggregate/per-repetition/per-stratum/domain results as the primary regression. Its separate M3 acceptance also passes **215/215** checks, rereads **96** states with **24192/24192** assertions, and reruns the **15 + 40** public CLI regressions. These two trees still represent the same **32** exposed authored examples; they are not 192 independent samples or hosted execution.

Each M2 nested driver retains 27 expected exits 0, seven expected verifier exits 1, three expected review exits 2, one expected cancellation exit 3 and two deliberate owned crash exits **85**. Thus this batch exercises four actual owned `os._exit(85)` child exits across two runs, at the previously defined after-proposal-commit/before-packet-rename boundaries. Recovery, proposal hashes and immutable booked values pass. These controlled process exits do not test power-loss, interrupted commit, disk/controller faults or fsync durability.

Each owned native-chat loopback protocol double receives **11** actual HTTP requests, passes **6/6** wire/domain checks and **241/241** independent assertions. Actual assistant/tool observations, schemas and attempt counts agree; proposal remains unposted. Decisions and token counts are scripted/synthetic, and live model calls are **0**. The double tests transport/authority behavior, not model reasoning. Server/connection/timer cleanup is bounded by the harness. Existing milestone-local M2 report notes describe that driver's scope; the enclosing M3 reports supply actual exposed-regression evidence.

### Resource measurements and final integrity

Cumulative heavy-command active wall time is **182.0656584 seconds** of the fresh 600-second grant. Sampled aggregate owned working set peaks at **123277312 bytes (117.57 MiB)**, below 256 MiB. At most **three** concurrent owned Python processes were observed; four were allowed for the CI/review path. Sampling may miss brief children or short-lived working sets and is not an exact OS peak measurement. No additional acceptance repeat was run to inflate that observation. One sequential command worker and at most one owned loopback double execute; no downloads, installs, live models, paid calls or external accounts.

All artifact directories total **167278177 bytes (159.53 MiB)**, below 200 MiB and conservatively including the preserved original first-score, historical M1/M2 and main-review artifacts. New regression demo/evaluation/acceptance/CI trees total **93746622 bytes (89.40 MiB)**. Their individual footprints are **262317**, **38140566**, **8393385** and **46950354** bytes. Current regression logs/cleanup total **186226** bytes. Final PID/creation-time inspection finds **zero remaining observed owned descendants** and no unrelated process was interrupted.

Before documentation updates, all **50** candidate source-checkpoint file hashes matched; actor source/rule hashes stayed fixed through both evaluation trees. All **866** original first-score files and the archived original actor still match their recorded hashes. All **155** frozen input/label hashes remain unchanged at aggregate `f3299b697dc7a4634a28445cf29e9312bf12ff6b5f01844244e30baa97067c34`; release-policy hash remains `9f9ee61e6ade0fef90966adbca07e13c5d715b1e9e94d06dbdfd1c944c31a57a`. No baseline/evaluator/rule/label/safety change occurred. Only standalone documentation now records actual results.

**Independent main M3 verification is pending. Hosted GitHub Actions, Linux execution, live-model quality, professional accounting validation, power-loss/fsync durability, production account/ledger posting, deployment and publication remain UNEXECUTED.** Approved drafts remain unposted. No financial close certification, representative accuracy, employer endorsement or production success is claimed. The worker has completed the authorized local regression batch, is release-ready and stops for main verification.


## Independent final local acceptance — 8 October 2026

Main independently accepted candidate 0.1.1 after copying 270 shipping source/data files (463051 bytes) to a fresh directory, without installation. All eight documented corrected-candidate commands exited 0, including 70 tests, the demo and verifier, 96 exposed-case regression attempts, final CLI acceptance and the seven-step local CI reproduction. The CI wrapper separately repeated 70 tests and 96 attempts. Main command wall times were 0.235, 0.203, 4.609, 1.063, 0.235, 82.250, 20.359 and 108.828 seconds. These are separate from worker observations.

A separate main stdlib checker imported neither actor nor evaluator and passed 5,498 conditions across 192 read-only SQLite states, corresponding raw CSVs, saved packets, baselines and command receipts. It recomputed imported amounts, booked cash bridges, exact matches/holds, balanced unposted proposals and content hashes, booked AP versus reservations, fixed-baseline matches/holds and aggregate denominators. All 32 groups agree across six repetitions from the two batches. All 270 source/data copies remained unchanged. Every original first-score artifact (866 files) retained its sealed hash, and the original failed 93/96 score remains intact.

Each current batch has 96/96 exact workflow attempts, 147/147 match edges, 120/120 holds and 12/12 proposals across repetitions. The unchanged baseline has 27/96 exact attempts, 144/147 matching edges, 60/120 hold recall and no proposals. Both M3 acceptance runs passed 215 checks and 96 raw-state rechecks, including separate 15-call M1 and 40-call M2 regressions, expected negative CLI exits and conflicting concurrent review outcomes of one success and one rejection. Local provider doubles, deliberate crashes and corruption tests are engineering evidence only.

Main corrected its own read-only audit helper: a label's zero booked AP does not require an invoice packet row when no matching invoice exists, and conflicting review-race receipts declare the pair of expected exits rather than one integer per command. Original failed helper output is retained separately; no application source, test expectation, rubric or application result was changed or rerun to correct the helper.

Final local acceptance is passed. The correction remains informed by exposed authored fixtures; it does not establish fresh unseen accuracy or live model quality. Main peak RAM was not sampled; worker sampling is separate. Hosted CI, Linux execution, live inference, accounting certification, power-loss/fsync durability, production posting, publication and deployment remain unexecuted. Final status documentation changed afterward; freeze and Git whitespace checks passed.

## Public source release — 9 October 2026

All three local MVP milestones passed independent acceptance on 8 October 2026, including final documentation review. The review was executed separately from the implementation worker and included documented quickstarts, meaningful success/failure tests and direct domain-state checks. The results and limitations above remain unchanged.

This source release includes application code, authored fixtures, evaluator/tests, quickstart, architecture, license/attribution and the prepared CI workflow. Private orchestration records, machine-specific paths, runtime caches and generated local runs are excluded. Offline scripted/rule/replay outcomes and local provider doubles do not establish live model quality, employer adoption or production impact. Hosted CI results are available in this repository's Actions tab after publication; historical local reports retain their original execution dates.
