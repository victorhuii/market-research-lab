# Design choices

MarketLab — implementation rationale and tradeoffs.

| Choice | Why it fits this project | Cost or boundary |
| --- | --- | --- |
| Research and matching sandbox are separate | Avoid treating synthetic participant matching as evidence of historical fill quality. | Replay assumptions remain approximations. |
| Integer matching and single-writer persistence | Keep trades, balances, deduplication and recovery inspectable. | Local simulator, not an authenticated multi-user venue. |
| Python calculations with a buildless UI | Keep analysis authoritative in one backend and remove bundler/runtime services. | Standard-library server is scoped to loopback use. |

## Evidence and scope

Causal research/execution separation with synthetic demonstration evidence. Synthetic demos and simulated fills are labeled; no real profitability claim.

Ownership: **Original implementation**. Attribution and source notices remain in the [README](../README.md).

See [architecture](ARCHITECTURE.md) and [portfolio notes](PORTFOLIO.md) for implementation details and existing evidence. This documentation update does not add a new benchmark or training run.
