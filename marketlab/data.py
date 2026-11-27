"""Bounded top-of-book CSV inputs and reproducible synthetic sessions."""
import csv
import io
import math
import random
from collections import Counter

FIELDS = ['session', 'timestamp', 'symbol', 'bid', 'ask', 'bid_size', 'ask_size', 'trade_price', 'trade_quantity', 'trade_side']
INTEGER_FIELDS = ['timestamp', 'bid', 'ask', 'bid_size', 'ask_size', 'trade_price', 'trade_quantity']


def synthetic(seed=42, sessions=12, events=240):
    rng = random.Random(seed)
    rows = []
    for day in range(sessions):
        mid = 10000 + rng.randint(-100, 100)
        pressure = 0.0
        for i in range(events):
            pressure = .8 * pressure + rng.gauss(0, .6)
            move = rng.choices([-1, 0, 1], [max(.05, .3 - pressure * .12), .4, max(.05, .3 + pressure * .12)])[0]
            mid += move
            half = rng.choice([1, 1, 1, 2])
            bid_size = max(1, int(20 + pressure * 12 + rng.gauss(0, 4)))
            ask_size = max(1, int(20 - pressure * 12 + rng.gauss(0, 4)))
            side = rng.choices(['buy', 'sell', 'none'], [max(.1, .45 + pressure * .1), max(.1, .45 - pressure * .1), .1])[0]
            price = mid + half if side == 'buy' else mid - half if side == 'sell' else 0
            rows.append(dict(session=f'session-{day + 1:02}', timestamp=day * 86400000 + i * 1000,
                             symbol='DEMO', bid=mid - half, ask=mid + half, bid_size=bid_size, ask_size=ask_size,
                             trade_price=price, trade_quantity=rng.randint(1, 40) if side != 'none' else 0, trade_side=side))
    return rows


def validate(rows):
    if not 100 <= len(rows) <= 50000:
        raise ValueError('dataset must contain 100 to 50000 rows')
    symbols = set()
    completed, previous_session, previous_time = set(), None, None
    gaps = []
    counts = Counter()
    for n, row in enumerate(rows, 2):
        if not isinstance(row.get('session'), str) or not row['session'].strip() or len(row['session']) > 100:
            raise ValueError(f'row {n}: session must be a nonempty string up to 100 characters')
        if not isinstance(row.get('symbol'), str) or not row['symbol'].strip() or len(row['symbol']) > 30:
            raise ValueError(f'row {n}: invalid symbol')
        for key in INTEGER_FIELDS:
            if type(row.get(key)) is not int or not 0 <= row[key] <= 10**15:
                raise ValueError(f'row {n}: {key} must be a nonnegative integer <= 10^15')
        if row['bid'] <= 0 or row['ask'] <= row['bid'] or min(row['bid_size'], row['ask_size']) <= 0:
            raise ValueError(f'row {n}: need positive depth and 0 < bid < ask')
        if row.get('trade_side') not in ('buy', 'sell', 'none'):
            raise ValueError(f'row {n}: trade_side must be buy, sell or none (aggressor side)')
        if (row['trade_side'] == 'none' and (row['trade_quantity'] or row['trade_price'])) or (row['trade_side'] != 'none' and min(row['trade_quantity'], row['trade_price']) <= 0):
            raise ValueError(f'row {n}: inconsistent trade fields')
        session = row['session']
        if session != previous_session:
            if session in completed:
                raise ValueError(f'row {n}: sessions must be contiguous and chronological')
            if previous_session is not None:
                completed.add(previous_session)
        if previous_time is not None and row['timestamp'] <= previous_time:
            raise ValueError(f'row {n}: timestamps must strictly increase across the entire file')
        if session == previous_session:
            gaps.append(row['timestamp'] - previous_time)
        previous_session, previous_time = session, row['timestamp']
        symbols.add(row['symbol'])
        counts[session] += 1
    if len(symbols) != 1:
        raise ValueError('this release supports exactly one symbol')
    if len(counts) < 5 or min(counts.values()) < 30:
        raise ValueError('need at least five sessions, each with at least 30 events')
    typical_gap = sorted(gaps)[len(gaps) // 2]
    return dict(rows=len(rows), symbol=next(iter(symbols)), sessions=dict(counts),
                typical_interval_ms=typical_gap, large_gaps=sum(g > typical_gap * 5 for g in gaps),
                missingness=0, duplicate_timestamps=0, crossed_books=0,
                units='integer price ticks; integer quantity units; epoch or relative milliseconds',
                note='Gaps > 5× median are flagged. No imputation. Event horizons vary in wall-clock duration.')


def read_csv(text):
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != FIELDS:
        raise ValueError('CSV header must be: ' + ','.join(FIELDS))
    rows = []
    for n, row in enumerate(reader, 2):
        if len(rows) >= 50000:
            raise ValueError('CSV exceeds 50000 rows')
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'row {n}: column count does not match header')
        for key in INTEGER_FIELDS:
            try:
                row[key] = int(row[key])
            except (ValueError, TypeError):
                raise ValueError(f'row {n}: {key} must be an integer') from None
        rows.append(row)
    validate(rows)
    return rows


def write_csv(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
