# Architecture and tradeoffs

Python 3.11 standard library and SQLite implement the accepted local ledger alternative. A separate Java service would add process and serialization work without improving the no-posting boundary. There are no runtime packages or external accounts.

## Domain authority

`ingest.py` validates/hashes complete sources before opening workflow state. `store.py` separates immutable bank, ledger and source bytes from cases, matches, proposals, reservations, reviews and events. Foreign keys and explicit BEGIN IMMEDIATE transactions are enabled.

`tools.py` rejects unknown actions, other-case IDs and unobserved evidence. Exact cash matching uses signed integer cents, narrow normalized/source-aliased references, vendors, dates and reverse-bank uniqueness. `ap.py` calculates recognized credits minus booked settlement debits through period end. It never subtracts matched bank rows. Pending/approved proposal reservations affect available AP separately.

Both `BANK_FEE_V1` and `MISSING_AP_PAYMENT_V1` derive accounts, date and amounts on the host. The provider supplies only the rule and observed evidence IDs. Draft content, balanced lines, field relations, AP reservation and successful tool event commit atomically. Immediate SQLite write locking serializes competing reservations. Immutable imported balances never include a draft, even after approval.

The validation-informed 0.1.1 candidate classifies invoice currency by consensus within each same-identity group of source copies. One consistent non-USD currency produces an unsupported-currency hold; contradictory currencies produce the existing conflict hold without selecting the first or majority copy. Foreign bank currency remains independently unsupported. Other conflicts may coexist with an established foreign currency. Proposal restrictions and conflict handling are unchanged. The eight new pure tests, full 70-test suite, exposed-fixture regression, final acceptance and local CI reproduction pass; independent main M3 verification passed from a fresh source/data copy.

`providers.py` exposes one observation-dependent decision interface. Scripted policy has no labels, filesystem operations or expected outcomes in its tool context. `ollama.py` uses native function schemas and assistant/tool observation messages. A local protocol double exercises this boundary; it is not model-quality evidence.

## Budgets, cancellation and recovery

Run states are READY, INVESTIGATING, PACKET_READY, CANCELLED and BUDGET_EXHAUSTED. Cases move OPEN to DONE, which means investigation coverage, not resolved evidence or completed financial close. Host finish recomputes mandatory holds even if the provider declares completion. Incomplete runs preserve open coverage and emit an incomplete packet.

Limits are 12 persisted provider attempts and 10 successful tools per case, 250 attempts per run, 50 cases and 180 accumulated active seconds. Repeated identical successful decisions stop after two. One transient transport retry and one syntactic schema correction consume attempts. Forbidden actions are never automatically retried, including on resume. Provider mode/model/endpoint/evidence mode are bound to a persisted configuration hash.

Ollama is explicit opt-in, literal loopback HTTP only, with no proxy or redirect handling. Request context is capped at 64 KiB; response at 32 KiB; one call at 15 seconds or the remaining run budget. An owned socket deadline also bounds response headers/body. Inflight cancellation is applied before tool dispatch after the request returns. An arbitrary third-party Python provider is not preemptible; only the concrete transport has a bounded request.

Successful tool observations commit with their effects. Resume reconstructs observed evidence and policy history from those events. Unique bank/line/content keys prevent duplicate domain effects; completed runs only rerender. Elapsed time and attempt budgets survive process restarts. A crash may leave an attempt marked started, which still consumes its budget. Local idempotency does not claim exactly-once external execution.

Packet JSON and HTML each use a temporary file followed by `os.replace`; the two files are not one filesystem transaction. A crash between replacements can leave mixed generations until rerender. Independent verifier compares packet to committed state. M2 was independently accepted, including cancellation/resume and two actual owned CLI child exits through `os._exit(85)`: one after the proposal transaction commits, and one before packet rename. Each resumed child reproduced the uninterrupted proposal hash and one proposal/reservation. The harness did not simulate an OS crash, power loss, disk/controller failure or interrupted SQLite commit. Neither packet file/directory fsync behavior nor power-loss durability was tested. Exact measured outcomes and resource limits are recorded in EVIDENCE.md.

## Review and evidence

`review.py` separately checks exact content/hash, snapshot, current rules, original/stored source bytes, line/evidence relations, host-derived amounts/accounts and AP reservation sufficiency. Identical reviews return the existing decision; conflicting reviews are rejected. Review never posts or resolves invoice holds. Rejection preserves reservation audit but removes its active effect.

`render.py` presents actual cash/AP and reservations separately, escapes source text and emits no script. `evaluation/verify.py` imports no actor validators and recomputes raw money, period scope, evidence locators, cash bridge, per-invoice history, reservations and gold outcomes. Corrupted copied states must fail. Labels are outside actor tools; the Python process is not an OS sandbox.

The held-out input/label freeze precedes policy expansion and is integrity-checked independently. Development evaluation uses a fixed exact-reference baseline and reports undefined rates as not applicable. No held-out scoring occurred at the M2 or M3 source checkpoints.

M3's evaluator launches each acting run through the public CLI in a separate process; only the evaluator reads labels. It compares exact outcome sets, verifies raw state, records all failures and computes canonical domain hashes across three repetitions. Actor source/rule hashes before and after evaluation must agree. The first 96-attempt evaluation remains a failed original result because H16 emits an extra currency hold in each repetition. Candidate 0.1.1 passes a separately labeled post-fix 96-attempt regression and a separate public CI reproduction. Each final acceptance rereads all 96 saved states, recomputes aggregates and runs the existing CLI regressions. The original actor archive and first results remain intact. The separation prevents labels entering tool observations; it does not provide a hostile-code filesystem sandbox.

The standard-library design makes the offline workflow reproducible without dependency installation. It also trades away OCR breadth, authenticated review, external delivery and production storage guarantees. SQLite transactions cover local proposal/reservation/event consistency; source-derived proposals and independent verification expose those decisions for review. The scripted provider makes this inspectable but supplies no empirical live-model accuracy result.
