"""Loopback-only local application. No external services or credentials."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit

from marketlab.data import read_csv, synthetic, write_csv
from marketlab.engine import DurableExchange
from marketlab.flow import commands
from marketlab.research import Settings, findings, run

WEB = Path(__file__).resolve().parent.parent / 'web'


class Application:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lockfile = (self.directory / 'server.lock').open('a')
        try:
            fcntl.flock(self._lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lockfile.close()
            raise RuntimeError('another MarketLab server is using this data directory') from None
        self.exchange = DurableExchange(self.directory / 'exchange')
        self.rows = None
        self.source = 'synthetic'
        self.lock = threading.RLock()
        self.result = run()
        self.log_run()

    def close(self):
        self._lockfile.close()

    def log_run(self):
        record = dict(timestamp=datetime.now(timezone.utc).isoformat(), source=self.result['source'],
                      settings=self.result['settings'], dataset_sha256=self.result['dataset_sha256'],
                      selected_C=self.result['selected_C'], predictions=self.result['predictions'],
                      strategies=[{k: v for k, v in s.items() if k != 'curve'} for s in self.result['strategies']])
        with (self.directory / 'experiments.jsonl').open('a') as f:
            f.write(json.dumps(record, allow_nan=False) + '\n')

    def action(self, path, body):
        with self.lock:
            if path == '/api/run':
                if not isinstance(body, dict) or set(body) - set(asdict(Settings())):
                    raise ValueError('unknown experiment setting')
                settings = Settings(**body)
                result = run(settings, self.rows, self.source)
                self.result = result
                self.log_run()
                return result
            if path == '/api/import':
                text = body.get('csv')
                if not isinstance(text, str):
                    raise ValueError('csv must be text')
                rows = read_csv(text)
                result = run(Settings(**self.result['settings']), rows, 'imported CSV')
                (self.directory / 'import.csv').write_text(text)
                self.rows, self.source, self.result = rows, 'imported CSV', result
                self.log_run()
                return result
            if path == '/api/demo':
                self.result = run(Settings(**self.result['settings']))
                self.rows, self.source = None, 'synthetic'
                self.log_run()
                return self.result
            if path == '/api/command':
                if self.exchange.engine.sequence >= 5000:
                    raise ValueError('sandbox command limit reached (5000); start with a new --data directory')
                result = self.exchange.execute(body)
                return dict(result=result, state=self.exchange.engine.state())
            if path == '/api/simulate':
                if self.exchange.engine.sequence + 100 > 5000:
                    raise ValueError('not enough sandbox capacity for 100 simulated commands')
                stream = commands(100, initial=self.exchange.engine)
                for command in stream:
                    self.exchange.execute(command)
                return dict(commands=len(stream), state=self.exchange.engine.state())
            if path == '/api/snapshot':
                return dict(sequence=self.exchange.save_snapshot())
            if path == '/api/recover':
                before = self.exchange.engine.state()
                self.exchange = DurableExchange(self.directory / 'exchange')
                after = self.exchange.engine.state()
                return dict(identical=before == after, state=after)
            raise ValueError('unknown API route')


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, data, content_type='application/json; charset=utf-8', disposition=None):
            payload = json.dumps(data, allow_nan=False).encode() if content_type.startswith('application/json') else data.encode() if isinstance(data, str) else data
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            if disposition:
                self.send_header('Content-Disposition', f'attachment; filename="{disposition}"')
            self.end_headers()
            self.wfile.write(payload)

        def valid_host(self):
            return self.headers.get('Host', '') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {'error': 'loopback host required'})
            path = urlsplit(self.path).path
            with app.lock:
                if path == '/api/research':
                    return self.send(200, app.result)
                if path == '/api/exchange':
                    return self.send(200, app.exchange.engine.state())
                if path == '/api/export':
                    return self.send(200, app.result, disposition='marketlab-research.json')
                if path == '/api/report':
                    return self.send(200, findings(app.result), 'text/markdown; charset=utf-8', 'marketlab-findings.md')
                if path == '/api/csv':
                    rows = app.rows if app.rows is not None else synthetic(app.result['settings']['seed'])
                    return self.send(200, write_csv(rows), 'text/csv; charset=utf-8', 'marketlab-data.csv')
                if path == '/api/history':
                    records = (app.directory / 'experiments.jsonl').read_text().splitlines()[-30:]
                    return self.send(200, [json.loads(r) for r in reversed(records)])
            assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path in assets:
                name, content_type = assets[path]
                return self.send(200, (WEB / name).read_bytes(), content_type)
            return self.send(404, {'error': 'not found'})

        def do_POST(self):
            # JSON-only, same-origin writes; no CORS. Host check also blocks DNS rebinding.
            if not self.valid_host():
                return self.send(403, {'error': 'loopback host required'})
            origin = self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
                return self.send(403, {'error': 'same-origin requests only'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, {'error': 'application/json required'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 8_000_000:
                    return self.send(413, {'error': 'request must be between 1 byte and 8 MB'})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('request must be a JSON object')
                return self.send(200, app.action(urlsplit(self.path).path, body))
            except (ValueError, TypeError, UnicodeError) as exc:
                return self.send(400, {'error': str(exc)})
            except (OSError, RuntimeError):
                return self.send(503, {'error': 'local storage failed; restart the server and retry with the same request ID'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description='Start the MarketLab local dashboard')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data', type=Path, default=Path('runtime'))
    args = parser.parse_args()
    app = Application(args.data)
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(app))
    except OSError:
        app.close()
        raise
    print(f'MarketLab: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.close()


if __name__ == '__main__':
    main()
