import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from marketlab.server import Application, handler_for
from marketlab.data import synthetic, write_csv


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = Application(cls.tmp.name)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(cls.app))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.app.close()
        cls.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        connection.request(method, path, json.dumps(body) if body is not None else None,
                           headers or {'Content-Type': 'application/json'})
        response = connection.getresponse()
        status, data = response.status, response.read()
        connection.close()
        return status, data

    def test_routes_and_validation(self):
        status, data = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'MarketLab', data)
        self.assertEqual(self.request('GET', '/../../etc/passwd')[0], 404)
        self.assertEqual(self.request('POST', '/api/run', {'latency': 0})[0], 400)
        self.assertEqual(self.request('POST', '/api/run', {'horizon': 2, 'unknown': 1})[0], 400)
        self.assertEqual(self.request('POST', '/api/import', {'csv': 'invalid'})[0], 400)
        for path in ['/api/research', '/api/export', '/api/report', '/api/csv', '/api/history']:
            self.assertEqual(self.request('GET', path)[0], 200)

    def test_same_origin_and_content_type(self):
        self.assertEqual(self.request('POST', '/api/snapshot', {}, {'Content-Type':'text/plain'})[0], 415)
        self.assertEqual(self.request('POST', '/api/snapshot', {}, {'Content-Type':'application/json', 'Origin':'https://example.com'})[0], 403)
        self.assertEqual(self.request('GET', '/', headers={'Host':'example.com'})[0], 403)

    def test_exchange_http_recovery(self):
        command = dict(request_id='r', type='order', order_id='a', participant='alice', side='sell', price=100, quantity=3)
        status, data = self.request('POST', '/api/command', command)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)['result']['resting'], 3)
        self.assertEqual(self.request('POST', '/api/snapshot', {})[0], 200)
        self.assertTrue(json.loads(self.request('POST', '/api/recover', {})[1])['identical'])
        self.assertEqual(json.loads(self.request('POST', '/api/command', command)[1])['result']['sequence'], 1)
        status, data = self.request('POST', '/api/simulate', {})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)['state']['sequence'], 101)
        self.assertTrue(json.loads(self.request('POST', '/api/recover', {})[1])['identical'])

    def test_csv_import_and_settings(self):
        status, data = self.request('POST', '/api/import', {'csv': write_csv(synthetic(9, 5, 40))})
        self.assertEqual(status, 200)
        result = json.loads(data)
        self.assertEqual(result['source'], 'imported CSV')
        self.assertEqual(result['audit']['rows'], 200)
        self.assertEqual(self.request('POST', '/api/run', {'fee_bps': 2, 'latency': 2})[0], 200)
        status, data = self.request('POST', '/api/demo', {})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(data)['synthetic'])

    def test_single_server_writer(self):
        with self.assertRaises(RuntimeError):
            Application(self.tmp.name)


if __name__ == '__main__':
    unittest.main()
