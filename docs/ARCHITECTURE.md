# Architecture and protocol

## Modules

| Module | Responsibility |
| --- | --- |
| `engine.py` | Matching, command validation, request deduplication, balances, journal and snapshot recovery. |
| `flow.py` | Seeded commands from four simulated participants, used in the UI and benchmark. |
| `data.py` | Synthetic sessions, strict normalized CSV import/export and audit. |
| `research.py` | Causal features, session splits, model selection/scoring, strategy replay and reports. |
| `server.py` | Loopback HTTP interface, single-writer locking and local experiment log. |
| `web/` | Dependency-free HTML, CSS, JavaScript and accessible SVG charts. |

No bundler, database service, frontend framework or external runtime requests are needed. Every displayed research result comes from Python. The engine and historical replay are separate systems: synthetic participant interactions do not establish historical execution quality.

## Engine commands

```json
{"type":"order","request_id":"request-1","order_id":"order-1","participant":"alice","side":"buy","price":10000,"quantity":5,"tif":"GTC"}
```

```json
{"type":"cancel","request_id":"request-2","order_id":"order-1","participant":"alice"}
```

Names are nonempty strings up to 100 characters. Price/quantity are positive integers up to 10^9; booleans and floats are rejected. `tif` defaults to `GTC`; `IOC` cancels unfilled remainder. A unique order ID cannot be reused even after fill/cancel. Cancel requires the original participant name; this is a simulator identity, not authentication. Self-trading is permitted and nets balances; there are no margin/funding constraints. Simultaneous cancel/fill requests serialize under the app lock; the first accepted command determines the outcome.

Responses contain command `sequence`, `order_id`, generated `trades`, `resting` units and `cancelled` units. Better prices execute first; equal prices use arrival sequence. Trades execute at the resting order price. Filled/cancelled orders leave the book. Repeating the identical request ID and body returns the original response without another journal record; conflicting reuse is rejected.

## Durability

One application process owns the data directory with an OS file lock. Within that process, one lock serializes state mutations. `DurableExchange` itself assumes a single caller; standalone callers must provide that guarantee.

Each command is validated and applied to a copy, appended as one JSON journal line, flushed and fsynced before the in-memory state is replaced and acknowledgment returned. Creating the journal also syncs its directory. A failed write poisons the instance; it must be reopened. An unacknowledged command may recover if it reached disk, so callers must reuse its request ID when retrying.

Snapshots are written to a temporary file, flushed, fsynced and atomically replaced, then the directory is synced. Recovery reads the snapshot, validates journal sequencing from record one and replays subsequent commands. The journal is retained in full; there is no compaction. An incomplete trailing line is truncated. Complete invalid JSON, gaps, duplicate sequences and an ahead-of-journal snapshot fail closed. There is no checksum for detecting arbitrary valid-JSON disk corruption. These guarantees assume the filesystem honors fsync/atomic replacement.

The browser retains an unacknowledged order command in page memory for retry. Reloading the page loses that pending command; callers integrating directly should retain IDs themselves. The sandbox caps at 5,000 commands to bound retained history and state-copy overhead. It does not model network transport or exchange queueing latency.

## HTTP interface

| Method | Route | Result |
| --- | --- | --- |
| GET | `/api/research` | Current experiment including replay frames. |
| POST | `/api/run` | Run with Settings fields; unspecified fields use defaults. |
| POST | `/api/import` | `{ "csv": "..." }`; validate, study and retain local CSV. |
| POST | `/api/demo` | Return to seeded synthetic data using current settings. |
| GET | `/api/export`, `/api/report`, `/api/csv` | Download JSON, Markdown findings or dataset. |
| GET | `/api/history` | Last 30 runs, newest first. |
| GET | `/api/exchange` | Book, orders, trades and balances. |
| POST | `/api/command` | Submit one order/cancel command. |
| POST | `/api/simulate` | Process 100 seeded participant commands. Not one atomic batch. |
| POST | `/api/snapshot` | Save snapshot; return sequence. |
| POST | `/api/recover` | Reopen journal and compare persisted state against memory. |

POST requires JSON and same-origin access when an Origin header is supplied. Unknown routes/invalid inputs return an error. File paths are not accepted through the API. This local server is not designed for internet exposure.

## Research limits

The majority predictor uses smoothed training class frequencies. The imbalance rule uses a fixed ±0.2 threshold and fixed class probabilities; it is not tuned on test data. Logistic regression compares three regularization choices on validation loss. The training fit is retained after selection. Missing training classes receive a tiny probability for aligned three-class scoring; a one-class training set is rejected.

Inference uses causal features even at the end of each session, where future labels do not exist. Those final events are excluded from forecast metrics. Warmup signals are zero. Quotes are chosen at event t and activated at t + latency; inventory skew uses inventory known at the decision event. Each activation cancels/replaces both quotes. Positions are checked at execution. The synthetic trader is assumed too small to affect market events.

The queue proxy assumes displayed same-side depth is ahead and requires an observed qualifying trade to exceed it. It does not accumulate depletion across quote replacements or reconstruct queue position. Strict-through and queue cases need not order P&L monotonically: fewer fills can avoid adverse selection. Drawdown uses a zero starting peak and the cumulative held-out equity path. Session inventory is marked and reset without liquidation fees, so reported P&L is not executable cash liquidation value.
