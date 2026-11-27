# MarketLab

A local workbench for market-making research and exchange mechanics. Compare short-horizon forecasts, test quoting strategies under different fill assumptions, and inspect a deterministic matching engine.

**The included data is synthetic. This project measures simulated behavior, not live trading profitability.** No paid APIs, AI calls, brokerage accounts or credentials are required.

## Run

Python 3.14 and Node 24 were used for verification. The server and research pipeline need Python; Node is only used to check frontend syntax. macOS and Linux are supported (the server uses a POSIX file lock).

```sh
cd /Users/vhui/Desktop/market-research-lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m marketlab.server
```

Open **http://127.0.0.1:8765**. Stop with Ctrl+C. A different port or data directory can be selected with `--port 8766 --data runtime/another-session`.

The UI has three views:

- **Research:** model comparisons, equity replay, displayed depth, next-price probabilities, fee/latency/inventory controls, execution sensitivity, CSV import and downloadable results/findings.
- **Exchange:** submit/cancel limit or IOC orders, generate 100 commands from simulated participants, inspect trades and balances, save a snapshot, and verify recovery.
- **Experiments:** the last 30 research runs with settings, data fingerprint and outcomes. Full records remain in `runtime/experiments.jsonl`.

The server binds only to loopback. It rejects cross-origin writes and unexpected hosts. No uploaded data leaves the computer. Exchange commands survive restarts; research opens on the synthetic demo each time. The last imported CSV remains at `runtime/import.csv` and can be imported again. Keep one server per data directory; a file lock enforces this.

## Reproduce the evidence

```sh
python -m unittest discover -s tests -v
node --check web/app.js
node --test tests/frontend.test.cjs
python -m marketlab.research --output runtime/research
python -m marketlab.benchmark
```

Use your own normalized data:

```sh
python -m marketlab.research --csv /path/to/snapshots.csv --output runtime/import-study
```

See the [CSV contract](docs/DATA.md), [architecture and protocol](docs/ARCHITECTURE.md), [project scope](PROJECT_SCOPE.md), [generated findings](docs/demo/findings.md), and [measured benchmark](docs/benchmark.json). The full default-run results are in [research.json](docs/demo/research.json).

## What the evidence establishes

The research compares a majority baseline, a fixed imbalance rule and regularized multinomial logistic regression. Entire sessions are split 60% / 20% / remainder, chronologically. Labels stay within sessions; overlapping label horizons are purged at boundaries. Scaling fits only training rows. C is selected on validation loss; the final test is scored afterward. Rerunning and tuning on that same test set makes subsequent work exploratory.

Fixed, inventory-aware and signal-aware quotes are evaluated under touch, strict trade-through and displayed-depth queue-proxy assumptions. Fees, event latency and position limits apply consistently. Prediction and strategy results remain separate. P&L is marked to midpoint, with per-session inventory reset and no liquidation cost; exact queue position and own market impact are unobserved.

Synthetic order-book pressure was deliberately made persistent. Predictive performance here demonstrates the pipeline, not a financial discovery. Real market conclusions require independently obtained sessions and a fresh holdout. No annualized returns, production HFT claims or recruiter endorsements are made.

The engine uses integer arithmetic, price-time priority and execution at the resting price. Tests include an independent list-based reference, conservation checks, journal corruption, torn writes, unacknowledged persisted commands and snapshot replay. Python favors inspectability; the durable wrapper copies command history before committing and is deliberately slower than the matching core. Benchmark results state the workload and separate both paths.

## Two-minute demo

1. In Research, inspect the synthetic source label, test metrics and default strict-through results.
2. Switch fill assumptions and compare the sensitivity table. Move the replay slider or press Play to inspect book depth, forecasts and inventory over time.
3. Change fees or latency, run again, and inspect the new entry in Experiments. Export findings or JSON.
4. In Exchange, run the simulated flow, inspect partial fills and balances, then save a snapshot and recover. The confirmation compares book, trades and balances.
5. Download the demo CSV to inspect the exact input format. Import your own chronological sessions to repeat the study.

## Repository context

`AGENTS.md` and `docs/STATUS.md` are the compact continuation context. The raw conversation export and personal source documents are intentionally excluded. Feature commits use simple lowercase messages and are pushed to the configured GitHub origin.
