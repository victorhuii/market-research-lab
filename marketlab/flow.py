"""Seeded simulated participants; generation is excluded from benchmark timings."""
from copy import deepcopy
import random
from marketlab.engine import Engine


def commands(count=100, seed=42, initial=None):
    rng = random.Random(seed)
    reference = deepcopy(initial) if initial else Engine()
    result = []
    participants = ['maker-a', 'maker-b', 'taker-a', 'taker-b']
    for _ in range(count):
        key = f'flow-{reference.sequence + 1}'
        resting = [o for o in reference.orders.values() if o.participant in participants]
        if resting and rng.random() < .15:
            order = rng.choice(resting)
            command = dict(type='cancel', request_id=key, order_id=order.order_id, participant=order.participant)
        else:
            command = dict(type='order', request_id=key, order_id=key,
                           participant=rng.choice(participants), side=rng.choice(['buy', 'sell']),
                           price=rng.randint(9995, 10005), quantity=rng.randint(1, 8),
                           tif='IOC' if rng.random() < .35 else 'GTC')
        reference.execute(command)
        result.append(command)
    return result
