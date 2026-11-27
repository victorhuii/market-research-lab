"""Measure core and fsync-backed processing separately; run as a module."""
import json
import platform
import tempfile
import time
from marketlab.engine import DurableExchange, Engine
from marketlab.flow import commands


def benchmark(count=2000):
    results = {}
    stream = commands(count)
    with tempfile.TemporaryDirectory() as tmp:
        for name, engine in [('core', Engine()), ('journal_fsync', DurableExchange(tmp))]:
            samples = []
            start = time.perf_counter()
            max_depth = 0
            for c in stream:
                t = time.perf_counter_ns()
                engine.execute(c)
                samples.append((time.perf_counter_ns() - t) / 1000)
                core = engine.engine if isinstance(engine, DurableExchange) else engine
                max_depth = max(max_depth, len(core.orders))
            elapsed = time.perf_counter() - start
            samples.sort()
            results[name] = dict(commands=count, commands_per_second=round(count / elapsed, 2),
                                 trades=len(core.trades), max_resting_orders=max_depth,
                                 latency_us={f'p{p}': round(samples[min(count - 1, int(count * p / 100))], 2) for p in (50, 95, 99)})
    return dict(machine=platform.platform(), processor=platform.machine(), python=platform.python_version(),
                workload='seed 42; one caller; four participants; random buy/sell limit orders at 9995–10005 ticks, 1–8 units; 35% IOC probability, 15% cancel probability when resting orders exist; no networking; service time only; durable wrapper copies cached history',
                order_mix=dict(orders=sum(c['type'] == 'order' for c in stream), cancels=sum(c['type'] == 'cancel' for c in stream), ioc=sum(c.get('tif') == 'IOC' for c in stream)), results=results)


if __name__ == '__main__':
    print(json.dumps(benchmark(), indent=2))
