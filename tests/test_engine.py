import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from marketlab.engine import DurableExchange, Engine
from marketlab.flow import commands


def order(n, side='buy', price=100, quantity=5, **kw):
    return dict(request_id=f'r{n}', type='order', order_id=f'o{n}', participant=f'p{n}',
                side=side, price=price, quantity=quantity, **kw)


class EngineTests(unittest.TestCase):
    def test_participant_flow(self):
        stream = commands(200)
        self.assertEqual(stream, commands(200))
        e = Engine()
        for command in stream:
            e.execute(command)
        self.assertTrue(e.trades)
        self.assertTrue(any(c['type'] == 'cancel' for c in stream))
        self.assertEqual(sum(b['inventory'] for b in e.balances.values()), 0)

    def test_price_time_partial_ioc(self):
        e = Engine()
        e.execute(order(1, 'sell', 102, 3))
        e.execute(order(2, 'sell', 101, 2))
        e.execute(order(3, 'sell', 101, 4))
        r = e.execute(order(4, 'buy', 101, 5))
        self.assertEqual([(t['maker'], t['price'], t['quantity']) for t in r['trades']], [('o2', 101, 2), ('o3', 101, 3)])
        self.assertEqual(e.orders['o3'].quantity, 1)
        r = e.execute(order(5, 'buy', 103, 10, tif='IOC'))
        self.assertEqual(r['cancelled'], 6)
        self.assertEqual(e.state()['orders'], [])
        self.assertEqual(sum(b['cash'] for b in e.balances.values()), 0)
        self.assertEqual(sum(b['inventory'] for b in e.balances.values()), 0)

    def test_dedup_cancel_invalid(self):
        e = Engine()
        c = order(1)
        first = e.execute(c)
        self.assertEqual(e.execute(c), first)
        self.assertEqual(e.sequence, 1)
        with self.assertRaises(ValueError):
            e.execute({**c, 'quantity': 10})
        for value in (0, -1, True, 1.5, '5'):
            with self.assertRaises(ValueError):
                e.execute(order(2, quantity=value))
        cancel = dict(request_id='cancel', type='cancel', order_id='o1', participant='other')
        with self.assertRaises(ValueError):
            e.execute(cancel)
        result = e.execute({**cancel, 'participant': 'p1'})
        self.assertEqual((result['resting'], result['cancelled']), (0, 5))
        self.assertEqual(e.orders, {})
        with self.assertRaises(ValueError):
            e.execute({**c, 'request_id': 'new'})

    def test_random_stream_against_reference(self):
        # Deliberately simple list-based reference; no engine matching helpers.
        rng = random.Random(21)
        e, resting = Engine(), []
        expected_trades = []
        for i in range(500):
            c = order(i, rng.choice(['buy', 'sell']), rng.randrange(95, 106), rng.randrange(1, 15), tif=rng.choice(['GTC', 'IOC']))
            left = c['quantity']
            while left:
                candidates = [o for o in resting if o['side'] != c['side'] and (o['price'] <= c['price'] if c['side'] == 'buy' else o['price'] >= c['price'])]
                if not candidates:
                    break
                best_price = (min if c['side'] == 'buy' else max)(o['price'] for o in candidates)
                maker = next(o for o in resting if o in candidates and o['price'] == best_price)
                size = min(left, maker['quantity'])
                expected_trades.append((maker['order_id'], c['order_id'], best_price, size))
                left -= size
                maker['quantity'] -= size
                if not maker['quantity']:
                    resting.remove(maker)
            if left and c['tif'] == 'GTC':
                resting.append({**c, 'quantity': left})
            e.execute(c)
            state = e.state()
            self.assertEqual({o['order_id']: o['quantity'] for o in resting}, {o['order_id']: o['quantity'] for o in state['orders']})
            if state['bids'] and state['asks']:
                self.assertLess(state['bids'][0]['price'], state['asks'][0]['price'])
        self.assertEqual([(t['maker'], t['taker'], t['price'], t['quantity']) for t in e.trades], expected_trades)

    def test_recovery_snapshot_and_torn_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            x = DurableExchange(tmp)
            x.execute(order(1, 'sell'))
            x.save_snapshot()
            x.execute(order(2))
            before = x.engine.state()
            with x.journal.open('ab') as f:
                f.write(b'{"sequence":3')
            y = DurableExchange(tmp)
            self.assertEqual(y.engine.state(), before)
            self.assertEqual(y.execute(order(2))['sequence'], 2)
            y.execute(order(3))
            self.assertEqual(DurableExchange(tmp).engine.state(), y.engine.state())

    def test_write_failure_requires_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            x = DurableExchange(tmp)
            real = x._append
            def persisted_then_failure(record):
                real(record)
                raise OSError('simulated failure before acknowledgment')
            with patch.object(x, '_append', persisted_then_failure):
                with self.assertRaises(OSError):
                    x.execute(order(1))
            with self.assertRaises(RuntimeError):
                x.execute(order(2))
            y = DurableExchange(tmp)
            self.assertEqual(y.execute(order(1))['sequence'], 1)
            self.assertEqual(len(y.engine.orders), 1)

    def test_corrupt_journal_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'commands.jsonl').write_text(json.dumps({'sequence': 2, 'command': order(1)}) + '\n')
            with self.assertRaises(ValueError):
                DurableExchange(tmp)


if __name__ == '__main__':
    unittest.main()
