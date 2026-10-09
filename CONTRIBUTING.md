# Contributing

Use an installed Python 3.11 interpreter from the repository root. The source checkout requires no third-party packages, credentials, model weights or external accounts. Select `py -3.11` on Windows or the matching `python` executable on another OS. Do not commit generated `artifacts/`, SQLite states, local environment files or personal absolute paths.

For component changes, run:

```powershell
py -3.11 -m unittest discover -s tests -p 'test_*.py' -v
py -3.11 -m evaluation.freeze
```

The pure M3 reporting subset is `py -3.11 -m unittest discover -s tests -p 'test_m3.py' -v`. It uses in-memory synthetic results and does not read frozen cases, execute the actor, open HTTP services or score held-out data. Tests should assert independent domain behavior and authority limits. Do not duplicate implementation expressions merely to inflate a test count.

The currency-consensus subset is `py -3.11 -m unittest discover -s tests -p 'test_currency_consensus.py' -v`. It exercises host classification and the unresolved-conflict proposal guard against in-memory facts and mocked read interfaces, without SQL, fixtures, actor CLI, HTTP or scoring. The original scored 0.1.0 source/freeze was archived before the 0.1.1 validation-informed correction; the first failed result is retained.

Use development bundles for policy work. Never change frozen inputs, labels, materiality, required holds or release gates to make a result pass. The actor must receive observations through scoped tools and must not import evaluation labels or derive decisions from case identifiers. All proposals remain unposted. Changes to AP logic must preserve original booked values, explicit completeness, source provenance and atomic reservation checks.

Full CLI, HTTP, integration, evaluation and CI-equivalent work in this managed project requires the current named resource lease and explicit milestone assignment. [README.md](README.md) contains the recorded original first-pass and passing post-fix regression commands. A public checkout can reproduce the explicit offline CI wrapper after choosing a fresh output directory. The authored corpus is already exposed, and all subsequent scores are regression/reproduction.

Preserve the first evaluation directory and first failed assertion/command. Once outcomes are exposed, use a fresh directory and `--evidence-phase regression-after-exposure` after any policy correction. An unchanged-policy repetition can be labeled `frozen-policy-reproduction`; the CI wrapper labels its evidence `public-ci-reproduction`. Do not overwrite a failed report, silently retry only failed cases or describe a corrected run as a fresh blind evaluation. Record source hashes, exact commands, exit codes, denominators and remaining unexecuted checks in [EVIDENCE.md](EVIDENCE.md).

Before review, inspect the emitted proposal, original source evidence and booked-versus-proposed balances. Approval requires the exact emitted proposal hash and snapshot version. A reviewer annotation is not authentication, and approval does not post to any ledger. Live inference, remote services, publishing and actual financial accounts are outside the authorized offline contribution flow.

Authored contributions and fictional data use the MIT license. Keep runtime and CI attribution in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and data attribution in [DATA_LICENSE.md](DATA_LICENSE.md).
