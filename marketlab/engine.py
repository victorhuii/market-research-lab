"""Single-instrument price-time matching with integer ticks and quantities."""
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path


def positive_int(value, name):
    if type(value) is not int or not 0 < value <= 1_000_000_000:
        raise ValueError(f'{name} must be an integer from 1 to 1000000000')
    return value


def identifier(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        raise ValueError(f'{name} must be a nonempty string of at most 100 characters')
    return value


@dataclass
class Order:
    order_id: str
    participant: str
    side: str
    price: int
    quantity: int
    sequence: int


class Engine:
    def __init__(self):
        self.sequence = 0
        self.orders = {}
        self.used_ids = set()
        self.requests = {}
        self.trades = []
        self.balances = defaultdict(lambda: {'cash': 0, 'inventory': 0})

    def execute(self, command):
        if not isinstance(command, dict):
            raise ValueError('command must be an object')
        c = deepcopy(command)
        request_id = identifier(c.get('request_id'), 'request_id')
        if request_id in self.requests:
            previous, response = self.requests[request_id]
            if previous != c:
                raise ValueError('request_id was already used for a different command')
            return deepcopy(response)
        participant = identifier(c.get('participant'), 'participant')
        kind = c.get('type')
        order_id = identifier(c.get('order_id'), 'order_id')
        if kind == 'cancel':
            if order_id not in self.orders:
                raise ValueError('order is not resting; it may have filled or been cancelled')
            if self.orders[order_id].participant != participant:
                raise ValueError('only the order owner can cancel it')
        elif kind == 'order':
            if order_id in self.used_ids:
                raise ValueError('order_id has already been used')
            if c.get('side') not in ('buy', 'sell'):
                raise ValueError('side must be buy or sell')
            if c.get('tif', 'GTC') not in ('GTC', 'IOC'):
                raise ValueError('tif must be GTC or IOC')
            positive_int(c.get('price'), 'price')
            positive_int(c.get('quantity'), 'quantity')
        else:
            raise ValueError('type must be order or cancel')
        self.sequence += 1
        trades = []
        if kind == 'cancel':
            cancelled = self.orders.pop(order_id).quantity
            remaining = cancelled
        else:
            self.used_ids.add(order_id)
            incoming = Order(order_id, participant, c['side'], c['price'], c['quantity'], self.sequence)
            opposite = sorted((o for o in self.orders.values() if o.side != incoming.side),
                              key=lambda o: (o.price if incoming.side == 'buy' else -o.price, o.sequence))
            for maker in opposite:
                if incoming.quantity == 0:
                    break
                if (incoming.side == 'buy' and maker.price > incoming.price) or (incoming.side == 'sell' and maker.price < incoming.price):
                    break
                size = min(incoming.quantity, maker.quantity)
                buyer = participant if incoming.side == 'buy' else maker.participant
                seller = maker.participant if incoming.side == 'buy' else participant
                trade = dict(trade_id=len(self.trades) + 1, sequence=self.sequence, price=maker.price,
                             quantity=size, buyer=buyer, seller=seller, maker=maker.order_id, taker=order_id)
                self.trades.append(trade)
                trades.append(trade)
                for owner, sign in ((buyer, 1), (seller, -1)):
                    self.balances[owner]['inventory'] += sign * size
                    self.balances[owner]['cash'] -= sign * size * maker.price
                incoming.quantity -= size
                maker.quantity -= size
                if maker.quantity == 0:
                    del self.orders[maker.order_id]
            remaining = incoming.quantity
            cancelled = remaining if c.get('tif') == 'IOC' else 0
            if remaining and not cancelled:
                self.orders[order_id] = incoming
        response = dict(sequence=self.sequence, order_id=order_id, trades=trades,
                        resting=remaining - cancelled, cancelled=cancelled)
        self.requests[request_id] = (c, deepcopy(response))
        return response

    def state(self):
        levels = {'buy': defaultdict(int), 'sell': defaultdict(int)}
        for o in self.orders.values():
            levels[o.side][o.price] += o.quantity
        return dict(sequence=self.sequence,
                    bids=[dict(price=p, quantity=q) for p, q in sorted(levels['buy'].items(), reverse=True)],
                    asks=[dict(price=p, quantity=q) for p, q in sorted(levels['sell'].items())],
                    orders=[asdict(o) for o in sorted(self.orders.values(), key=lambda o: o.sequence)],
                    trades=deepcopy(self.trades), balances=deepcopy(dict(self.balances)))

    def dump(self):
        return dict(sequence=self.sequence, orders=[asdict(o) for o in self.orders.values()],
                    used_ids=sorted(self.used_ids), requests=self.requests,
                    trades=self.trades, balances=dict(self.balances))

    @classmethod
    def restore(cls, data):
        e = cls()
        e.sequence = data['sequence']
        e.orders = {o['order_id']: Order(**o) for o in data['orders']}
        e.used_ids = set(data['used_ids'])
        e.requests = data['requests']
        e.trades = data['trades']
        e.balances.update(data['balances'])
        return e


class DurableExchange:
    """One writer. Ack follows journal flush+fsync; an unacked command may recover."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.journal = self.directory / 'commands.jsonl'
        self.snapshot = self.directory / 'snapshot.json'
        self.poisoned = False
        self.engine = Engine.restore(json.loads(self.snapshot.read_text())) if self.snapshot.exists() else Engine()
        data = self.journal.read_bytes() if self.journal.exists() else b''
        # A torn final record was never acknowledged. Remove it before appending.
        end = data.rfind(b'\n') + 1
        if end != len(data):
            with self.journal.open('r+b') as f:
                f.truncate(end)
                f.flush()
                os.fsync(f.fileno())
        count = 0
        for line in data[:end].splitlines():
            record = json.loads(line)
            count += 1
            if record['sequence'] != count:
                raise ValueError('journal sequence gap or duplicate')
            if count > self.engine.sequence:
                response = self.engine.execute(record['command'])
                if response['sequence'] != count:
                    raise ValueError('journal replay sequence mismatch')
        if self.engine.sequence > count:
            raise ValueError('snapshot is ahead of journal')

    def _append(self, record):
        existed = self.journal.exists()
        with self.journal.open('ab') as f:
            f.write((json.dumps(record, separators=(',', ':')) + '\n').encode())
            f.flush()
            os.fsync(f.fileno())
        if not existed:
            self._sync_directory()

    def _sync_directory(self):
        fd = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def execute(self, command):
        if self.poisoned:
            raise RuntimeError('journal write failed; reopen exchange before submitting more commands')
        trial = deepcopy(self.engine)
        result = trial.execute(command)
        if trial.sequence == self.engine.sequence:
            return result
        try:
            self._append(dict(sequence=trial.sequence, command=command))
        except OSError:
            self.poisoned = True
            raise
        self.engine = trial
        return result

    def save_snapshot(self):
        if self.poisoned:
            raise RuntimeError('reopen exchange before taking a snapshot')
        temp = self.snapshot.with_suffix('.tmp')
        with temp.open('w') as f:
            json.dump(self.engine.dump(), f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, self.snapshot)
        self._sync_directory()
        return self.engine.sequence
