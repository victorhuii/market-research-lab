"""Measure core and fsync-backed processing separately; run as a module."""
import json
import platform
import tempfile
import time
from marketlab.engine import DurableExchange, Engine


def benchmark(count=2000):
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, engine in [('core', Engine()), ('journal_fsync', DurableExchange(tmp))]:
            samples = []
            start = time.perf_counter()
            for i in range(count):
                c = dict(type='order', request_id=str(i), order_id=str(i), participant=f'p{i % 10}',
                         side='buy' if i % 2 == 0 else 'sell', price=10000, quantity=1, tif='IOC')
                t = time.perf_counter_ns()
                engine.execute(c)
                samples.append((time.perf_counter_ns() - t) / 1000)
            elapsed = time.perf_counter() - start
            samples.sort()
            results[name] = dict(commands=count, commands_per_second=round(count / elapsed, 2),
                                 latency_us={f'p{p}': round(samples[min(count - 1, int(count * p / 100))], 2) for p in (50, 95, 99)})
    return dict(machine=platform.platform(), processor=platform.machine(), python=platform.python_version(),
                workload='one caller; alternating unmatched IOC orders; empty resting book; no networking; service time only; durable wrapper copies cached history', results=results)


if __name__ == '__main__':
    print(json.dumps(benchmark(), indent=2))
