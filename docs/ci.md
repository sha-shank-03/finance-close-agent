# Offline CI scope

The authored workflow uses the same seven-step command plan as `evaluation.ci`: runtime doctor, freeze integrity, all component tests, scripted demo, independent demo verification, three frozen repetitions with the fixed baseline, and final M3 acceptance. Final acceptance rereads all 96 saved states and executes the M1/M2 CLI regression drivers. Every nested command, exit, stdout and stderr is retained; the wrapper stops at the first unexpected failure and requires a fresh output directory.

```powershell
py -3.11 -m evaluation.ci --out artifacts/ci-final --allow-heldout
```

The wrapper passed all seven steps locally for candidate 0.1.1 under the named M3 regression lease, using `artifacts/currency-regression-ci`. Its evaluation passes 96/96 exposed-fixture attempts and its acceptance rereads all saved states. This demonstrates local CI-equivalent execution; hosted GitHub Actions execution needs its own actual job evidence and remains unexecuted. The wrapper labels evaluations `public-ci-reproduction`, preserving the separately recorded original 93/96 first frozen pass. Choose a fresh output directory for reproduction. Full integration in this managed project needs a current named lease.

The workflow selects Python 3.11.9, read-only repository contents permission, a ten-minute job deadline and one matrix worker at a time across Ubuntu and Windows. It makes no model calls and needs no secrets, dependency installation or paid hosting. Standard public-repository hosted runner use is documented in the [GitHub Actions billing reference](https://docs.github.com/en/billing/concepts/product-billing/github-actions); private repository usage depends on account quotas.

CI actions use the reviewed immutable commits in [the workflow](../.github/workflows/ci.yml): checkout v7.0.1 at `3d3c42e5aac5ba805825da76410c181273ba90b1`, and setup-python v7.0.0 at `5fda3b95a4ea91299a34e894583c3862153e4b97`. Action licenses are linked in [runtime attribution](../THIRD_PARTY_NOTICES.md). The hosted `ubuntu-latest` and `windows-latest` images still move, and the selected interpreter bundles its own SQLite version; the job doctor records that environment. These pins are not a reproducible OS image or a supply-chain audit.

Remote CI, Linux execution and publication remain unexecuted. The measured M1/M2 and post-fix M3 local evidence, exact commands and resources are recorded in [EVIDENCE.md](../EVIDENCE.md).
