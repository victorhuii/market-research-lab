# Data contract

UTF-8 CSV with this exact ordered header:

```csv
session,timestamp,symbol,bid,ask,bid_size,ask_size,trade_price,trade_quantity,trade_side
```

| Field | Meaning |
| --- | --- |
| session | Contiguous session identifier, 1–100 characters. Use real session boundaries; do not invent independent sessions from adjacent rows. |
| timestamp | Strictly increasing integer milliseconds across the entire file. Epoch or consistent relative time. |
| symbol | One instrument per file, 1–30 characters. |
| bid / ask | Positive integer price ticks; bid must be less than ask. Locked/crossed books are rejected. |
| bid_size / ask_size | Positive integer displayed quantity at the best price. Empty sides are rejected. |
| trade_price | Integer ticks of an observed trade for this event. Zero when no trade exists. |
| trade_quantity | Integer quantity of that trade. Zero when no trade exists. |
| trade_side | Aggressor side: `buy`, `sell`, or `none`. A sell aggressor may fill a resting bid. |

All numeric columns must be nonnegative integers no greater than 10^15. Price/size fields have additional positive constraints. No nulls or implicit floating-point conversion. Choose a quantity unit small enough for fractional exchange quantities to become integers, then interpret tick value as USD per price tick per chosen quantity unit. The app quotes one quantity unit per side.

At least 100 and at most 50,000 snapshots, with at least 5 sessions of 30 or more events. The browser accepts files under 7 MB; the JSON endpoint caps encoded requests at 8 MB. Gaps over five times the median within-session interval are flagged, not filled. Horizon and latency are event counts, so elapsed time can vary.

Each row describes the observable book and optionally one trade known by that timestamp. Do not aggregate different trade prices into a fake last-price volume: replay assumes the entire trade quantity belongs to `trade_price`. If the source only has snapshots, set all trade fields to zero/none. Research features still work, but there will be no simulated fills.

To obtain an exact sample file, start the app and use Download data, or run:

```sh
python -c "from pathlib import Path; from marketlab.data import synthetic, write_csv; Path('runtime').mkdir(exist_ok=True); Path('runtime/demo.csv').write_text(write_csv(synthetic()))"
```

The generator uses twelve 240-event sessions, seed 42 by default, a single fictional `DEMO` instrument and a nominal $0.01 tick value. These are not downloaded or historical prices.

LOBSTER, ITCH and Coinbase raw feeds require source-specific normalization into this schema; native feed parsing is outside this release. Verify access and redistribution terms for any real dataset before publishing it. Real data is kept under ignored `runtime/` by default.
