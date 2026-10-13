# First authored offline comparison

The first native U2-B batch finished 64 paired attempts on 32 unique fictional tasks: 16 development and 16 capability, one repetition, two fixed policies. Both sets are author-exposed and share construction families. Main independently executed the six commands and checked 773 assertions against original CSVs, read-only SQLite, unposted proposals, balances, hashes, counts and cost labeling. This is evidence about an offline workflow on this authored set.

| Split and policy | Investigations finished | Exact-state success | Resolved completion | Correct handoff | Latency coverage | Median / p95 seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Development, scripted | 16/16 | 16/16 | 7/16 | 9/16 | 16/16 | 1.117 / 1.438 |
| Development, deterministic-v2 | 16/16 | 16/16 | 7/16 | 9/16 | 16/16 | 1.133 / 1.437 |
| Capability, scripted | 16/16 | 15/16 | 6/16 | 9/16 | 16/16 | 1.149 / 1.391 |
| Capability, deterministic-v2 | 16/16 | 15/16 | 6/16 | 9/16 | 16/16 | 1.156 / 1.516 |

All 32 pairs tie: 31 pairs pass for both policies and C81 fails for both. Both used identical host tools/authority and cumulative budgets. No positive uplift was required. Latency covers dispatch through independent verification for all 64 completed attempts. The sequential order, one repetition and shared machine do not support a general speed comparison. Measured billed cost is **null**, with zero model and external calls; it is not a measured zero-dollar provider result.

C81 contains a EUR bank payment against the USD account and an empty AP-history completeness assertion. Both policies retain `UNSUPPORTED_CURRENCY` and `UNMATCHED_CASH`, plus an extra `INCOMPLETE_HISTORY` hold with 40700-cent exposure. Frozen gold expects only the first two. The extra hold is conservative, but **remains an exact-state failure**. Neither actor nor gold was tuned to turn the score green. Investigation `DONE` means the workflow finished examining the case; it does not mean the accounting issue was resolved or handed off exactly as labeled.

Development hold precision/recall is 23/23 for both policies. Capability holds are 38 correct of 39 predicted against 38 gold: precision 38/39 and recall 38/38. No expected material holds were missed in these completed reports. Material units are labeled holds with exposure at least 10000 cents, not independent cash losses or summed financial impact. Independently inspected proposals remain pending, balanced and unposted; booked ledger values stay immutable. Five copied-state controls reject a cent change, deleted hold, forged match, provenance corruption and false completion.

The [public summary](../reports/u2b-first/summary.json) contains only an allowlisted projection: case outcomes, aggregate metrics, coverage, source-file hashes and first-report/code fingerprints. Its [manifest](../reports/u2b-first/manifest.json) pins the summary bytes. It excludes SQLite, raw source contents, native argv/PIDs, personal paths and private coordination evidence. The private original reports and all first attempts remain unchanged. First evaluator/actor code fingerprint is `17e084d3080809e81aac3fdaf86fe9167df634ffd3d6f83cd538ef8a18f6d414`; the later [U2-C manifest](../u2c-manifest.json) versions reporting changes separately.

```powershell
py -3.11 -m evaluation.u2c_summary validate --bundle reports/u2b-first
```

The exporter accepts completed source reports, validates their counts/projections, and creates a fresh directory once. To independently reconstruct this summary from the preserved first reports, supply their paths privately:

```powershell
py -3.11 -m evaluation.u2c_summary export --dev-report PRESERVED_DEV_REPORT --capability-report PRESERVED_CAPABILITY_REPORT --out FRESH_PUBLIC_SUMMARY_DIRECTORY
```

Validation checks the allowlist, derived metrics, coverage, fingerprints and manifest hash. These are integrity checks, not a cryptographic authenticity service; provenance comes from the preserved first reports and independent review. The evaluator correction does not retroactively change them. New progress records plan every slot before launch, fsync a `STARTED` intent and separate actual launch confirmation, terminal disposition, deadline-unexecuted work and interrupted unknown results. Gold stays in planned denominators. Lost results have no invented latency, cost, success or safe-action outcome and are never automatically redispatched.

Main-owned unseen evaluation, genuine QBO sandbox compatibility, live inference, full legacy regression, hosted CI and final upgrade acceptance/publication remain pending. Small correlated fictional inputs do not establish population accuracy, enterprise readiness or a completed financial close. See the [reproduction and reporting guide](u2b-evaluation.md).
