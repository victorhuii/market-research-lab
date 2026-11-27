import unittest
from copy import deepcopy
from marketlab.data import read_csv, synthetic, validate, write_csv
from marketlab.research import Settings, chronological_split, feature_rows, replay, run


class ResearchTests(unittest.TestCase):
    def test_csv_audit(self):
        rows = synthetic(7, 5, 40)
        self.assertEqual(read_csv(write_csv(rows)), rows)
        self.assertEqual(validate(rows)['rows'], 200)
        for key, value in [('bid', rows[1]['ask']), ('timestamp', rows[0]['timestamp']), ('bid_size', 0)]:
            bad = deepcopy(rows)
            bad[1][key] = value
            with self.assertRaises(ValueError):
                validate(bad)

    def test_feature_causality_and_session_boundaries(self):
        rows = synthetic(7, 5, 50)
        original = feature_rows(rows, 5)
        changed = deepcopy(rows)
        for row in changed[25:]:
            row['bid'] += 100
            row['ask'] += 100
            row['bid_size'] += 10
        modified = feature_rows(changed, 5)
        self.assertEqual([e['x'] for e in original if e['index'] < 25], [e['x'] for e in modified if e['index'] < 25])
        parts, sessions = chronological_split(original)
        self.assertFalse(set(sessions['train']) & set(sessions['test']))
        for left, right in zip(parts, parts[1:]):
            self.assertLess(max(e['label_end'] for e in left), min(e['timestamp'] for e in right))
        # First 10 events of every session are unavailable, regardless of prior sessions.
        self.assertTrue(all(e['index'] % 50 >= 10 for e in original))

    def test_fill_fee_latency_and_inventory(self):
        rows = [dict(session='a', timestamp=i, symbol='X', bid=99, ask=101, bid_size=10, ask_size=10,
                     trade_price=99, trade_quantity=5, trade_side='sell') for i in range(8)]
        settings = Settings(latency=2, fee_bps=10, position_limit=2, tick_value=1)
        result = replay(rows, [0] * len(rows), settings, 'fixed', 'touch')
        self.assertEqual(result['fills'], 2)
        self.assertEqual(result['curve'][1]['inventory'], 0)
        self.assertEqual(result['max_inventory'], 2)
        self.assertAlmostEqual(result['pnl'], 2 - 198 * .001)
        for fill in ['through', 'queue']:
            self.assertEqual(replay(rows, [0]*len(rows), settings, 'fixed', fill)['fills'], 0)

    def test_deterministic_research(self):
        rows = synthetic(12, 5, 60)
        a = run(Settings(seed=12), rows)
        b = run(Settings(seed=12), rows)
        self.assertEqual(a, b)
        self.assertEqual(len(a['strategies']), 9)
        self.assertTrue(all(s['max_inventory'] <= 10 for s in a['strategies']))
        self.assertEqual(sum(a['audit']['sessions'].values()), 300)
        self.assertEqual(len(a['predictions']['logistic']['confusion']), 3)

    def test_settings_reject_nonfinite_and_types(self):
        for settings in [Settings(fee_bps=float('nan')), Settings(latency=0), Settings(horizon=True), Settings(tick_value=-1)]:
            with self.assertRaises(ValueError):
                settings.check()


if __name__ == '__main__':
    unittest.main()
