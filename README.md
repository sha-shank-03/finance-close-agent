# Finance Close Agent

An inspectable bank-to-ledger reconciliation workflow on **authored fictional data**. A bounded scripted agent selects tools, matches cash records, preserves independent invoice holds, and prepares evidence-derived fee or missing-AP-payment entries for review. Every proposal and approval remains **unposted**.

Milestones 1 and 2 were independently accepted. **Candidate 0.1.1 passes all eight local M3 regression commands: 70 tests, demo verification, 96/96 exposed-case attempts, final raw-state/CLI acceptance and seven-step CI reproduction. Independent main M3 verification passed from a fresh 270-file source/data copy: all eight commands, 70 tests, two 96-attempt exposed-case batches and 5,498 additional raw-state conditions.** The original 0.1.0 candidate's first frozen score remains 93/96 (31/32 each repetition), failing on an extra H16 currency hold. The correction is validation-informed; the passing scores are regression after exposure. Live inference and hosted CI remain unexecuted. Exact evidence is in [EVIDENCE.md](EVIDENCE.md). Partial/AP history and reservations remain separate from immutable booked balances; every proposal remains unposted.

## Windows quickstart

Use an installed Python 3.11 runtime. No package installation, credentials, server, model download, Java build or Docker is needed. From this repository root:

```powershell
py -3.11 --version
py -3.11 -m finance_close doctor
py -3.11 -m finance_close demo --out artifacts/demo --provider scripted
py -3.11 -m evaluation.verify --run artifacts/demo --labels evaluation/labels/demo.json
```

Open `artifacts/demo/packet.html` in a browser. The JSON packet, SQLite state and tool trace are beside it. Select a fresh output directory when the input or policy version changes. On another OS, replace `py -3.11` with the selected Python 3.11 executable.

Independently accepted M1 outcomes under its recorded policy:

| Record | Cash outcome | Evidence/review outcome |
| --- | --- | --- |
| B001, $1,000 payment | Matches L001-CASH | Fictional invoice present |
| B003, $250 payment | Matches L003-CASH | Missing invoice remains an open hold |
| B005, $30 bank fee | Unmatched bank residual | Balanced $30 fee proposal, pending and unposted |

Bank closing was 872000 cents and immutable ledger closing 875000 cents. The -3000-cent booked difference equals unmatched bank minus unmatched ledger cash. The proposed -3000-cent cash effect is shown separately. M2 regression preserves these outcomes and passes 255 initial independent checks.

## Exact proposal review

Read the actual emitted proposal identity and content hash:

```powershell
$packet = Get-Content -LiteralPath artifacts/demo/packet.json -Raw | ConvertFrom-Json
$proposal = $packet.proposals | Select-Object -First 1
py -3.11 -m finance_close review --run artifacts/demo --proposal-id $proposal.id --expected-hash $proposal.hash --snapshot-version $packet.snapshot_version --decision approve --reviewer demo-accountant
py -3.11 -m finance_close report --run artifacts/demo
```

Approval checks exact content, source/rule hashes and snapshot version, and updates only the local review queue. Identical reviews are idempotent; conflicting or stale reviews fail. Reviewer names are local annotations, not authenticated identities. Rejection releases an active AP reservation while preserving its audit row. Approval keeps that reservation and never changes booked cash or AP.

## Component checks and integration commands

```powershell
py -3.11 -m unittest discover -s tests -p 'test_*.py' -v
py -3.11 -m evaluation.freeze
```

These are lightweight components and hash integrity checks. Tests use temporary source copies, SQLite components and in-memory transport doubles; they do not start HTTP services, launch subprocesses or execute complete demonstrations.

These integration commands passed locally and require fresh output directories:

```powershell
py -3.11 -m evaluation.acceptance --milestone 1 --out artifacts/m2-regression-m1
py -3.11 -m evaluation.run --split dev --provider scripted --baseline exact-reference --out artifacts/m2-evaluation
py -3.11 -m evaluation.acceptance --milestone 2 --out artifacts/acceptance-m2
```

Acceptance uses fresh output directories and records exact subprocess commands, expected/actual exit codes and assertions. M2 covers crash/resume after a proposal commit and before packet rename, repeated runs, both review decisions and review races, stale sources, corrupted-copy controls, no-network scripted execution and a real owned loopback HTTP protocol double. The latter validates wire behavior only: its decisions and token counts are synthetic, and no Ollama runtime/model is installed.

The independent verifier imports no actor validators, reads original fields and final SQLite state, and checks all cash residuals, explicit proposal presence or absence, exact provenance, immutable booked balances and independent holds. Outcome rates disclose numerators and denominators; a zero denominator is not applicable. The fixed baseline only matches unique exact cash references, amounts, vendors and dates; it has no invoice investigation or proposal capability. On the 12 authored development bundles, the workflow passes 12/12 exact labeled match/hold/proposal outcomes versus 3/12 for the baseline. Both match 19/19 labeled cash edges; the workflow identifies 15/15 labeled holds and 2/2 permitted proposals, with 0/12 missed material holds. The baseline identifies 7/15 holds and 0/2 proposals, missing 6/12 material holds. The actor additionally passes 3143 independent raw-source/state checks. These are the accepted M2 measurements; M3 reporting was subsequently integrated and independently verified; the M2 counts here remain historical development measurements. This small development comparison is not held-out or live-model evidence.

Twelve development bundles are authored. Thirty-two held-out input/label bundles across eight strata were frozen and hashed **before expanding the scripted policy**. The first authorized M3 evaluation completed all 96 attempts with no execution error. Each repetition has 31/32 exact cases, 49/49 correct cash edges, 40 correct holds out of 41 predicted and 40 gold, and four correct proposals out of four predicted/gold. H16 correctly matches USD cash and retains the conflict hold, but adds a 105500-cent `UNSUPPORTED_CURRENCY` hold for one EUR invoice copy; the frozen rubric requires only `CONFLICTING_EVIDENCE`. The fixed baseline has 9/32 exact core cases, 48/49 match recall, 20/40 hold recall and 0/4 proposal recall each repetition. These are authored scripted results, with no baseline-gap gate or live-model claim.

Three repeated runs add reproducibility evidence, not independent cases. Canonical domain states agree for all 32 cases; the repeated extra hold still fails the strict all-case gate. First failures, exact differences and all denominators are retained in `artifacts/final-evaluation/`. No actor, baseline, label, freeze or release-policy change occurred. [Evaluation definitions and gates](docs/evaluation.md) specify the stronger requirement that every independent case check pass.

The first-pass sequence is recorded below. Commands 1–5 passed; command 6 returned 1; commands 7–8 were **not executed** because the assignment requires stopping at an unexpected failure. Any correction/reproduction needs a new explicit bounded assignment, fresh directories and `regression-after-exposure` labeling. Preserve the first failed reports:

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

Prepared final acceptance would reread all 96 saved outcomes and run the M1/M2 CLI regressions. The CI wrapper would execute the same seven-step offline flow used by the authored GitHub Actions workflow, including another three repetitions labeled `public-ci-reproduction`. Both were left unexecuted after the first-score failure. A local result cannot establish hosted execution. See [CI scope and pins](docs/ci.md); remote CI remains unexecuted.

Candidate 0.1.1 changes only invoice-currency classification: copies for the same invoice identity must agree on one foreign currency to establish an unsupported invoice currency. Contradictory copies retain `CONFLICTING_EVIDENCE`; an actual foreign bank still triggers `UNSUPPORTED_CURRENCY`. Copy order and repetition do not choose a currency, and unresolved conflicts still prohibit AP drafts. The originally scored actor/freeze is archived and all first 96 attempt artifacts remain intact. This is validation-set-informed correction, with no new unseen evaluation claim.

Both the post-fix regression and separate public CI reproduction pass 32/32 cases in every repetition, with 49/49 cash matches, 40/40 exact holds, 4/4 exact proposals and zero missed material holds out of 30 each time. Each evaluation passes 24192 independent assertions and reproduces identical domain state. Each final acceptance rereads all 96 states, passes 215 driver checks and runs 15 M1 plus 40 M2 CLI calls. The fixed baseline remains 9/32 exact core cases each repetition. There is no baseline-gap gate or live-model claim.

The following corrected-candidate sequence **passed locally** under its fresh named integration lease. It preserved the first-score directories and explicitly labeled the new evaluation as regression after exposure. For reproduction, choose fresh output directories; the recorded directories already exist in the working checkout:

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

The dataset directory remains named `heldout` for byte-preserving compatibility; any subsequent result is exposed public-fixture regression/reproduction. The CI wrapper labels its second run `public-ci-reproduction`. Neither run can replace the original 31/32-per-repetition result.

## Provider and authority boundary

```text
validate/hash sources -> immutable SQLite inputs
provider -> scoped guarded tool -> observations -> next decision
           -> cash matches, independent holds, host-derived draft + reservation
committed state -> escaped static packet -> exact-content local review
original sources + separate labels + final database -> independent verifier
```

`ScriptedProvider` branches only on current-case observations. `OllamaProvider` implements native `/api/chat` tool messages with strict response validation, bounded local transport and persisted budgets. Tools own journal amounts/accounts and enforce reservations inside the same SQLite transaction as the proposal and audit event. Source notes cannot authorize actions; no tool posts or approves entries.

The optional live route requires an already installed, explicitly named local model and both `--provider ollama --model LOCAL_TAG --allow-local-model`. It performs no model download and accepts only a literal loopback HTTP endpoint. **Live inference is unexecuted and requires separate human authorization in this project.** Default quickstart stays scripted and offline.

The original contribution is source-field provenance connecting each draft to original source hashes, invoice/AP history, policy version and snapshot, together with reservations and independent final-state checks. Exact cash matching and double-entry balancing are established techniques. See [architecture](docs/architecture.md), [input contract](docs/input-contract.md), [limitations](docs/limitations.md), [contributing](CONTRIBUTING.md), and [primary sources](docs/sources.md). This is an independent implementation without employer endorsement.

Authored code and fictional fixtures use MIT. Attribution is in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
