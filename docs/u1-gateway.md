# U1 Gateway local-double evidence

Main independently accepted U1 after source review and all eight documented commands: 92 tests, 41 expected nested command exits, 315 direct original-CSV/SQLite/receipt checks and four corrupt/false-completion controls. The worker's first 20-test and second 22-test pure receipts and earlier checkpoint/style failures remain preserved. Local HTTP, owned-process transport and independent end-to-end checks have run. There is no live inference, unseen evaluation, genuine QuickBooks sandbox result or deployment. Final upgrade acceptance remains pending.

The optional provider sends one non-streaming Chat Completions request per observed decision, with native function-call IDs linked to persisted tool observations. The host retains the original tool schemas, accounting templates, evidence checks, immutable source/booked tables and exact proposal review. The default scripted demo remains available. No extra packages are required.

`fixtures/u1/proposal` is one exposed, authored fictional USD journey. Its invoice uses explicit labels such as Invoice Number, Invoice Total, Bank Reference and Book Reference. Independent checks confirm that the original 100000-cent invoice and 20000-cent historical payment leave 80000 cents booked AP. The 60000-cent payment proposal debits AP and credits cash, reserves 60000 cents and leaves 20000 cents available. Exact human review marks it APPROVED with posted false. Booked cash and AP remain unchanged. These results do not establish general accounting accuracy or live model quality.

`--invoice-format aliases-v1` opts into an explicit label dictionary and retains original field labels in provenance. Duplicate canonical fields, unsupported labels and Amount Due are rejected. Multiple invoice targets require a hold. This does not implement OCR, fuzzy vendor identity or broad accounting import.

## Verification commands

The bounded pure check, without sockets or child processes inside its tests:

```powershell
py -3.11 tools/u1_pure.py --out artifacts/u1-pure-new
```

The following batch passed under the worker's named lease and main's independent reproduction. Managed worker reruns still require a named lease. Use fresh output directories and preserve unexpected failures before corrections.

```powershell
py -3.11 -m finance_close doctor
py -3.11 -m evaluation.freeze
py -3.11 -m unittest discover -s tests -p 'test_*.py' -v
py -3.11 -m finance_close demo --out artifacts/u1-offline --provider scripted
py -3.11 -m evaluation.verify --run artifacts/u1-offline --labels evaluation/labels/demo.json
py -3.11 -m evaluation.gateway_acceptance --out artifacts/u1-gateway
py -3.11 -m evaluation.gateway_transport --out artifacts/u1-transport
py -3.11 -m evaluation.gateway_verify --run artifacts/u1-gateway/journey --input fixtures/u1/proposal --review-state APPROVED --out artifacts/u1-raw-verify.json
```

All eight outer commands exited 0. The acceptance wrapper records negative actor exits 4, crash exits 85, recovery/review exits 0 and independent corruption/false-completion verifier exits 1. A false completion returned actor exit 0 and was rejected by the independent verifier. The wrapper uses an observation-driven scripted policy behind actual local HTTP function-call envelopes; its decisions and token usage are synthetic. It cannot pass a live model or external sandbox gate.

The raw verifier imports no actor, parser, tools or accounting helpers. It computes cents, partial AP history, source hashes and required field provenance directly from input bytes, then checks SQLite proposal lines, reservation, review state, native-call observations and packet content. Its scope is this one authored journey. Mutation controls change copied outputs, leaving the original result intact.

## Bounds and recovery

Requests are capped at 64 KiB, responses at 32 KiB, IPC at 48 KiB, output at 512 reported tokens, and history at 24 observations. Configured request deadlines are 0.05–15 seconds. Original cumulative limits remain: 12 decisions and 10 accepted tools per case, 250 decisions and 180 active seconds per run, at most 50 cases. Explicit config may reduce request/allocation bounds. The Gateway provider pins one configured provider and has no fallback.

One retained owned child performs HTTP. A monotonic parent deadline reserves cleanup time, polls bounded shared memory and terminates/reaps only that owned handle. Slow header/body, cancellation and partial IPC controls passed. DNS/TLS controls simulate a blocking phase inside the owned child; they do not verify external DNS or a genuine TLS handshake. Process creation itself is an OS call that cannot be forcibly preempted by Python while `start()` is blocked. Full-tree lifetime RAM remains unknown because sampling missed short-lived descendants and listener observations; those gaps remain disclosed in acceptance evidence.

Automatic transport/schema retries are zero, including 429, 5xx and timeouts. An unfinished, failed or uncertain journal entry blocks further inference on resume. Valid persisted observations can support a subsequent decision after a completed local commit. Completed runs regenerate their packet without further inference. Unknown actual cost stays null; live upper-cost reservations would remain retained after an uncertain request. Local doubles reserve zero and never load credentials.

`gateway-events.jsonl` and `gateway-summary.json` contain allowlisted versions, IDs, counts, usage and timings; rejected raw tool arguments, response text, headers and exception text are excluded. Usage in doubles is labelled synthetic. Actor summaries leave independent success and unsafe committed action counts null until a separate verification result exists. Latency percentiles report sample size and timeout censoring; zero/unknown actual cost is not treated as a measured cost per success.

Live mode is dormant. It requires explicit `--allow-gateway-live`, a fixed official endpoint, pinned catalog model/provider, a main-approved positive allocation, current per-request cost upper bound and runtime key loader. No live key is supplied to doubles. The worker allocation is currently zero. Main owns the aggregate budget, secure loader, unseen evaluation and any live assignment; the worker chat model is not the runtime model.

U2-A now has a separate source-only assignment for read-only vendor Bill/BillPayment sandbox evidence. Its adapter and in-memory contract checks do not establish genuine sandbox integration. See [the U2-A guide](u2a-qbo.md). No accounting write is supported. All fictional fixtures use the repository's existing MIT attribution; source code uses Python's standard library.
