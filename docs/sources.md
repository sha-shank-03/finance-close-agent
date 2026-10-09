# Primary research references

Retrieved 8 October 2026. These are engineering context, not an employer specification or endorsement.

- [Ramp Q1 Accounting Agents](https://ramp.com/new-on-ramp-q1-2026) describes transaction coding, accruals and ERP reconciliation. Marketing performance claims are not adopted.
- [Ramp Applied AI Engineer](https://jobs.ashbyhq.com/ramp/d204e136-2749-42de-82b4-88a0dd352090) describes agents, structured extraction and backend infrastructure. [Financial Intelligence Fullstack](https://jobs.ashbyhq.com/ramp/6a7e382f-240a-4952-b9e5-7fe2b3856bc9) covers book-close experiences and explicitly leans toward frontend work. Both appeared on the public employer ATS board during research.
- [Beancount](https://github.com/beancount/beancount) is prior art for text-based double-entry accounting. Its implementation is not copied or used as a dependency.
- [Python decimal](https://docs.python.org/3.11/library/decimal.html), [sqlite3](https://docs.python.org/3.11/library/sqlite3.html) and [SQLite foreign keys](https://sqlite.org/foreignkeys.html) support the exact-money, transaction and referential-integrity choices.
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) documents free standard hosted runner use for public repositories; private usage depends on account quotas.

The provenance layout, synthetic case, entry policy, loop budget and acceptance assertions are authored project design. No proprietary pages, banking data or public financial dataset is redistributed.

For M2, the official [Ollama chat endpoint](https://docs.ollama.com/api/chat) and [tool-calling guide](https://docs.ollama.com/capabilities/tool-calling) were rechecked on 8 October 2026. They document native function schemas, assistant tool calls, tool observations, nonstreaming requests and returned usage fields. The local-only policy, strict bounds, single-call restriction and protocol double are project design. No model or Ollama runtime was downloaded or invoked.
