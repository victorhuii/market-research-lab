# MarketLab · project scope

Build a local quantitative research workbench with a matching-engine sandbox. The source chat proposes separate research and systems projects; this release gives each a working, independently testable module in one repository.

## Release requirements

- Python price-time matching engine: integer ticks and quantities, limit and IOC orders, partial fills, cancellation, request deduplication, participant balances, durable command journal, snapshots and deterministic recovery.
- Reproducible seeded synthetic order-book sessions plus strict CSV import. Audit timestamps, session boundaries, positive prices/depth, missing intervals and crossed books.
- Causal features, session-based train/validation/test splits, horizon purging, majority and imbalance baselines, scaled regularized logistic regression, class metrics and calibration.
- Separate quote replay comparing fixed, inventory-aware and signal-aware strategies with fees, latency, position limits and three explicit fill assumptions. Report results by session and fill scenario.
- Simple browser dashboard: research results, replay controls, depth and equity charts, experiment settings, CSV import, JSON export, and interactive exchange order entry/cancellation/recovery.
- Automated correctness, leakage, replay, persistence and API checks; reproducible benchmark; local run instructions; generated findings report and CI.

## Boundaries and acceptance

Synthetic data is a labeled systems demonstration, not evidence of market profitability. Historical CSV input uses top-of-book snapshots and optional trade data; exact queue position and own market impact are unknown. No live trading, credentials, broker integration, paid datasets, external AI calls, accounts or hosted deployment. Python is chosen for inspectability and shared research code; this is not a production HFT engine.

Done means all release requirements work locally, checks pass, measured findings and limitations are documented, and each feature milestone is committed and pushed where GitHub access permits. Positive returns and external reviewer feedback are not completion requirements. Real multi-session validation remains a data collection task, not a result to fabricate.

## Milestones

1. Scope and compact project context.
2. Matching engine, recovery, reference checks and benchmark.
3. Data, research, replay and findings.
4. Dashboard, integration, CI and final verification.

## Efficient continuation

Read `AGENTS.md`, then `README.md` and `docs/STATUS.md`. Inspect only files relevant to the next change. Use deterministic small fixtures before broader runs. Avoid new dependencies unless needed. Keep commits small with simple lowercase messages; push each completed milestone. Do not include the raw chat export or unrelated personal documents in Git.
