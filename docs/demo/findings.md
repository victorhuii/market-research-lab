# Research findings

Source: synthetic. Dataset SHA-256: `9c49b5005a13012a7c7c5851810ba291195d302e8fb6fa33bb032f070d4217e0`.

2880 snapshots across 12 sessions. Train / validation / test: {'train': 1575, 'validation': 450, 'test': 675}.

Model C is selected on validation log loss from 0.1, 1 and 10; the model stays fitted to training sessions. The final test is evaluated once per run. Repeated manual runs on the same test set are exploratory, not fresh holdouts.

| Model | Macro F1 | Log loss | Brier | Calibration error |
| --- | ---: | ---: | ---: | ---: |
| majority | 0.1864 | 1.0541 | 0.6398 | 0.0282 |
| imbalance | 0.3830 | 1.3319 | 0.7926 | 0.2583 |
| logistic | 0.3282 | 1.0429 | 0.6302 | 0.0433 |

| Strategy | Fill assumption | Net P&L ($) | Drawdown ($) | Fills | Max inventory |
| --- | --- | ---: | ---: | ---: | ---: |
| fixed | touch | -2.3794 | 2.5410 | 477 | 10 |
| fixed | through | -3.5090 | 3.8013 | 253 | 10 |
| fixed | queue | -0.5089 | 1.4427 | 268 | 10 |
| inventory | touch | -2.1604 | 2.2637 | 498 | 9 |
| inventory | through | -3.1896 | 3.2905 | 264 | 7 |
| inventory | queue | -1.0597 | 1.6127 | 266 | 10 |
| signal | touch | -1.0797 | 1.6624 | 472 | 9 |
| signal | through | -3.1901 | 3.2607 | 237 | 7 |
| signal | queue | 0.1004 | 0.9441 | 243 | 9 |

## Interpretation

Prediction metrics and strategy outcomes answer separate questions. Compare every strategy under the same fill assumption. A strategy that loses after fees is a valid result. Synthetic price dynamics were designed with persistent order-book imbalance; any predictive relationship here is part of the generator, not a discovery about stocks or crypto.

Full per-class metrics, confusion matrices, calibration bins, per-session outcomes, model selection trials and replay traces are in `research.json`. No volatility-regime claims are made from this small demo.

## Assumptions and limitations

- Synthetic demo does not establish real market profitability.
- Top-of-book depth cannot identify exact queue position or own market impact.
- One unit per quote; each activation cancels/replaces the prior quote; latency is in events.
- Session P&L is marked at final midpoint; inventory resets between sessions without liquidation cost.
- Signals are zero during the 10-event warmup. Final unlabeled events receive forecasts but are excluded from prediction scoring. No annualization or independent-row significance claims.
- Post-fill markout clips to session end when the full horizon is unavailable.

Touch fills require a correctly sided observed trade at or beyond the quote. Through fills require a strictly better execution opportunity. The queue proxy additionally requires observed trade quantity to exceed all displayed same-side depth at decision time; it is a sensitivity case, not queue reconstruction.

Features use only the current and preceding events in the same session. Labels end within that session. Entire sessions are separated chronologically, with explicit label-boundary purging. Preprocessing is fitted only on training data.

Method references: [scikit-learn logistic regression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html), [log loss](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.log_loss.html).
