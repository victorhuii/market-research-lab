"""Chronological research and explicit, independent execution assumptions."""
import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from marketlab.data import read_csv, synthetic, validate, write_csv

LABELS = [-1, 0, 1]
FEATURES = ['spread', 'imbalance', 'return_1', 'return_5', 'volatility_10', 'signed_trade_quantity']


@dataclass(frozen=True)
class Settings:
    seed: int = 42
    horizon: int = 5
    fee_bps: float = 1.0
    latency: int = 1
    position_limit: int = 10
    half_spread: int = 1
    tick_value: float = .01

    def check(self):
        for name, low, high in [('seed', 0, 1000000), ('horizon', 1, 20), ('latency', 1, 10), ('position_limit', 1, 100), ('half_spread', 1, 20)]:
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{name} must be an integer from {low} to {high}')
        for name, low, high in [('fee_bps', 0, 100), ('tick_value', .000001, 1000)]:
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f'{name} must be finite and between {low} and {high}')


def feature_rows(rows, horizon, include_unlabeled=False):
    result = []
    grouped = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[row['session']].append((index, row))
    for session, values in grouped.items():
        mids = np.array([(r['bid'] + r['ask']) / 2 for _, r in values])
        for i in range(10, len(values) if include_unlabeled else len(values) - horizon):
            index, r = values[i]
            features = [r['ask'] - r['bid'], (r['bid_size'] - r['ask_size']) / (r['bid_size'] + r['ask_size']),
                        mids[i] - mids[i-1], mids[i] - mids[i-5], float(np.std(np.diff(mids[i-10:i+1]))),
                        r['trade_quantity'] * (1 if r['trade_side'] == 'buy' else -1 if r['trade_side'] == 'sell' else 0)]
            has_label = i + horizon < len(values)
            result.append(dict(index=index, session=session, timestamp=r['timestamp'],
                               label_end=values[i+horizon][1]['timestamp'] if has_label else None,
                               x=features, y=int(np.sign(mids[i+horizon] - mids[i])) if has_label else None))
    return result


def chronological_split(examples):
    sessions = list(dict.fromkeys(e['session'] for e in examples))
    train_end = max(1, int(len(sessions) * .6))
    val_end = max(train_end + 1, int(len(sessions) * .8))
    groups = [sessions[:train_end], sessions[train_end:val_end], sessions[val_end:]]
    if not all(groups):
        raise ValueError('not enough sessions for train, validation and test')
    parts = [[e for e in examples if e['session'] in group] for group in groups]
    # Explicit horizon purging, including for future alternate splitting policies.
    for i in (0, 1):
        boundary = min(e['timestamp'] for e in parts[i+1])
        parts[i] = [e for e in parts[i] if e['label_end'] < boundary]
    return parts, dict(zip(['train', 'validation', 'test'], groups))


def probabilities(model, x):
    raw = model.predict_proba(x)
    p = np.full((len(x), 3), 1e-12)
    for j, label in enumerate(model.classes_):
        p[:, LABELS.index(int(label))] = raw[:, j]
    return p / p.sum(axis=1, keepdims=True)


def metrics(y, p):
    prediction = np.array(LABELS)[np.argmax(p, axis=1)]
    truth = np.array([[int(v == label) for label in LABELS] for v in y])
    confidence = np.max(p, axis=1)
    correct = prediction == y
    bins = []
    ece = 0.0
    for lo, hi in zip(np.linspace(0, 1, 6)[:-1], np.linspace(0, 1, 6)[1:]):
        mask = (confidence >= lo) & (confidence < hi if hi < 1 else confidence <= hi)
        if mask.any():
            accuracy, mean = float(correct[mask].mean()), float(confidence[mask].mean())
            bins.append(dict(confidence=mean, accuracy=accuracy, count=int(mask.sum())))
            ece += abs(accuracy - mean) * mask.mean()
    return dict(macro_f1=float(f1_score(y, prediction, labels=LABELS, average='macro', zero_division=0)),
                log_loss=float(log_loss(y, p, labels=LABELS)), brier=float(np.mean(np.sum((p-truth)**2, axis=1))),
                calibration_error=float(ece), calibration=bins,
                confusion=confusion_matrix(y, prediction, labels=LABELS).tolist(),
                classes=classification_report(y, prediction, labels=LABELS, target_names=['down', 'flat', 'up'], output_dict=True, zero_division=0))


def replay(rows, signals, settings, strategy, fill):
    """Quotes decided at t-latency; cancel/replace effective at t, one unit per side.

    Trade-at-touch is optimistic. Strict-through requires a price beyond the quote.
    Queue proxy additionally consumes displayed decision-time depth. No exact queue claim.
    """
    inventory, cash, peak, drawdown, exposure, turnover, fees = 0, 0., 0., 0., 0, 0., 0.
    fills, opportunities = 0, 0
    curve, executions = [], []
    for i, r in enumerate(rows):
        if i >= settings.latency:
            decision_index = i - settings.latency
            d = rows[decision_index]
            mid = (d['bid'] + d['ask']) / 2
            shift = 0
            if strategy != 'fixed':
                # Inventory observed at decision time, not at activation time.
                old_inventory = curve[decision_index]['inventory'] if decision_index < len(curve) else inventory
                shift -= round(old_inventory / settings.position_limit * settings.half_spread)
            if strategy == 'signal':
                shift += round(signals[decision_index] * 2)
            bid = min(d['ask'] - 1, math.floor(mid) - settings.half_spread + shift)
            ask = max(d['bid'] + 1, math.ceil(mid) + settings.half_spread + shift)
            for side, price in [('buy', bid), ('sell', ask)]:
                sign = 1 if side == 'buy' else -1
                if not -settings.position_limit <= inventory + sign <= settings.position_limit:
                    continue
                opportunities += 1
                opposite_trade = r['trade_side'] == ('sell' if side == 'buy' else 'buy')
                touches = r['trade_price'] <= price if side == 'buy' else r['trade_price'] >= price
                through = r['trade_price'] < price if side == 'buy' else r['trade_price'] > price
                # Conservative queue proxy assumes all displayed same-side depth is ahead.
                queue_depth = d['bid_size'] if side == 'buy' else d['ask_size']
                enough = fill != 'queue' or r['trade_quantity'] > queue_depth
                if opposite_trade and r['trade_quantity'] > 0 and (through if fill == 'through' else touches) and enough:
                    fee = price * settings.tick_value * settings.fee_bps / 10000
                    cash -= sign * price * settings.tick_value + fee
                    inventory += sign
                    turnover += price * settings.tick_value
                    fees += fee
                    fills += 1
                    future = rows[min(len(rows)-1, i + settings.horizon)]
                    markout = sign * ((future['bid'] + future['ask']) / 2 - price) * settings.tick_value
                    executions.append(dict(index=i, side=side, price=price, markout=markout))
        equity = cash + inventory * (r['bid'] + r['ask']) / 2 * settings.tick_value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
        exposure = max(exposure, abs(inventory))
        curve.append(dict(equity=round(equity, 6), inventory=inventory, cash=round(cash, 6)))
    return dict(pnl=curve[-1]['equity'], drawdown=round(drawdown, 6), max_inventory=exposure,
                fills=fills, opportunities=opportunities, fill_rate=fills / max(1, opportunities),
                turnover=round(turnover, 6), fees=round(fees, 6),
                mean_markout=float(np.mean([e['markout'] for e in executions])) if executions else None,
                curve=curve, executions=executions)


def run(settings=None, rows=None, source='synthetic'):
    settings = settings or Settings()
    settings.check()
    rows = synthetic(settings.seed) if rows is None else rows
    audit = validate(rows)
    examples = feature_rows(rows, settings.horizon)
    (train, val, test), splits = chronological_split(examples)
    xtrain, ytrain = np.array([e['x'] for e in train]), np.array([e['y'] for e in train])
    if len(set(ytrain)) < 2:
        raise ValueError('training sessions need at least two price-movement classes')
    xval, yval = np.array([e['x'] for e in val]), np.array([e['y'] for e in val])
    xtest, ytest = np.array([e['x'] for e in test]), np.array([e['y'] for e in test])
    trials, candidates = [], []
    for c in [.1, 1., 10.]:
        model = make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=500, random_state=settings.seed))
        model.fit(xtrain, ytrain)
        loss = float(log_loss(yval, probabilities(model, xval), labels=LABELS))
        trials.append(dict(C=c, validation_log_loss=loss))
        candidates.append(model)
    best_index = min(range(len(trials)), key=lambda i: trials[i]['validation_log_loss'])
    model = candidates[best_index]
    counts = np.array([sum(ytrain == label) for label in LABELS]) + 1
    majority = np.tile(counts / counts.sum(), (len(test), 1))
    imbalance = np.array([[.65, .25, .1] if e['x'][1] < -.2 else [.1, .25, .65] if e['x'][1] > .2 else [.15, .7, .15] for e in test])
    model_p = probabilities(model, xtest)
    predictions = {'majority': metrics(ytest, majority), 'imbalance': metrics(ytest, imbalance), 'logistic': metrics(ytest, model_p)}
    inference = [e for e in feature_rows(rows, settings.horizon, include_unlabeled=True) if e['session'] in splits['test']]
    inference_p = probabilities(model, np.array([e['x'] for e in inference]))
    signal_map = {e['index']: float(p[2]-p[0]) for e, p in zip(inference, inference_p)}
    test_rows = [r for r in rows if r['session'] in splits['test']]
    global_indices = [i for i, r in enumerate(rows) if r['session'] in splits['test']]
    grouped = defaultdict(list)
    for i, r in zip(global_indices, test_rows):
        grouped[r['session']].append((i, r))
    strategies = []
    for strategy in ['fixed', 'inventory', 'signal']:
        for fill in ['touch', 'through', 'queue']:
            sessions, curve, total = [], [], 0.
            for session, values in grouped.items():
                result = replay([r for _, r in values], [signal_map.get(i, 0.) for i, _ in values], settings, strategy, fill)
                curve.extend([{**p, 'equity': round(p['equity'] + total, 6)} for p in result.pop('curve')])
                result.pop('executions')
                total += result['pnl']
                sessions.append(dict(session=session, **result))
            equity = np.array([p['equity'] for p in curve])
            peak = np.maximum.accumulate(np.r_[0, equity])[1:]
            opportunities = sum(s['opportunities'] for s in sessions)
            fills = sum(s['fills'] for s in sessions)
            strategies.append(dict(strategy=strategy, fill=fill, pnl=round(total, 6),
                                   drawdown=float(np.max(peak - equity)), fills=fills, fill_rate=fills/max(1, opportunities),
                                   max_inventory=max(s['max_inventory'] for s in sessions),
                                   turnover=sum(s['turnover'] for s in sessions), fees=sum(s['fees'] for s in sessions),
                                   sessions=sessions, curve=curve))
    frames = []
    pmap = {e['index']: p.tolist() for e, p in zip(inference, inference_p)}
    for i, r in zip(global_indices, test_rows):
        frames.append({**r, 'mid': (r['bid']+r['ask']) / 2, 'probabilities': pmap.get(i), 'signal': signal_map.get(i, 0.)})
    return dict(source=source, synthetic=source == 'synthetic', settings=asdict(settings), audit=audit,
                dataset_sha256=hashlib.sha256(write_csv(rows).encode()).hexdigest(),
                splits=splits, sample_counts=dict(train=len(train), validation=len(val), test=len(test)),
                features=FEATURES, labels=['down', 'flat', 'up'], model_selection=trials,
                selected_C=trials[best_index]['C'], predictions=predictions,
                per_session_predictions=[dict(session=s, **metrics(ytest[[e['session'] == s for e in test]], model_p[[e['session'] == s for e in test]])) for s in splits['test']],
                strategies=strategies, frames=frames,
                limitations=['Synthetic demo does not establish real market profitability.' if source == 'synthetic' else 'Imported snapshots are not independently verified market data.',
                             'Top-of-book depth cannot identify exact queue position or own market impact.',
                             'One unit per quote; each activation cancels/replaces the prior quote; latency is in events.',
                             'Session P&L is marked at final midpoint; inventory resets between sessions without liquidation cost.',
                             'Signals are zero during the 10-event warmup. Final unlabeled events receive forecasts but are excluded from prediction scoring. No annualization or independent-row significance claims.',
                             'Post-fill markout clips to session end when the full horizon is unavailable.'])


def findings(result):
    text = ['# Research findings', '', f"Source: {result['source']}. Dataset SHA-256: `{result['dataset_sha256']}`.", '',
            f"{result['audit']['rows']} snapshots across {len(result['audit']['sessions'])} sessions. Train / validation / test: {result['sample_counts']}.", '',
            'Model C is selected on validation log loss from 0.1, 1 and 10; the model stays fitted to training sessions. The final test is evaluated once per run. Repeated manual runs on the same test set are exploratory, not fresh holdouts.', '',
            '| Model | Macro F1 | Log loss | Brier | Calibration error |', '| --- | ---: | ---: | ---: | ---: |']
    for name, m in result['predictions'].items():
        text.append(f"| {name} | {m['macro_f1']:.4f} | {m['log_loss']:.4f} | {m['brier']:.4f} | {m['calibration_error']:.4f} |")
    text += ['', '| Strategy | Fill assumption | Net P&L ($) | Drawdown ($) | Fills | Max inventory |', '| --- | --- | ---: | ---: | ---: | ---: |']
    for s in result['strategies']:
        text.append(f"| {s['strategy']} | {s['fill']} | {s['pnl']:.4f} | {s['drawdown']:.4f} | {s['fills']} | {s['max_inventory']} |")
    text += ['', '## Interpretation', '', 'Prediction metrics and strategy outcomes answer separate questions. Compare every strategy under the same fill assumption. A strategy that loses after fees is a valid result. Synthetic price dynamics were designed with persistent order-book imbalance; any predictive relationship here is part of the generator, not a discovery about stocks or crypto.', '',
             'Full per-class metrics, confusion matrices, calibration bins, per-session outcomes, model selection trials and replay traces are in `research.json`. No volatility-regime claims are made from this small demo.', '',
             '## Assumptions and limitations', '']
    text.extend('- ' + line for line in result['limitations'])
    text += ['', 'Touch fills require a correctly sided observed trade at or beyond the quote. Through fills require a strictly better execution opportunity. The queue proxy additionally requires observed trade quantity to exceed all displayed same-side depth at decision time; it is a sensitivity case, not queue reconstruction.', '',
             'Features use only the current and preceding events in the same session. Labels end within that session. Entire sessions are separated chronologically, with explicit label-boundary purging. Preprocessing is fitted only on training data.', '',
             'Method references: [scikit-learn logistic regression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html), [log loss](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.log_loss.html).', '']
    return '\n'.join(text)


def main():
    parser = argparse.ArgumentParser(description='Run reproducible MarketLab research')
    parser.add_argument('--csv', type=Path)
    parser.add_argument('--output', type=Path, default=Path('runtime/research'))
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    result = run(Settings(seed=args.seed), read_csv(args.csv.read_text()) if args.csv else None, 'imported CSV' if args.csv else 'synthetic')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'research.json').write_text(json.dumps(result, indent=2, allow_nan=False))
    (args.output / 'findings.md').write_text(findings(result))
    print(args.output / 'findings.md')


if __name__ == '__main__':
    main()
