import contextlib
from concurrent.futures import ThreadPoolExecutor
import dataclasses
import hashlib
import http.client
import io
import json
from pathlib import Path
import socket
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

import budget_proxy as proxy


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.db = str(Path(self.temp.name) / 'budget.sqlite')
        self.config = proxy.Config('http://gateway.namespace.svc.cluster.local:8080',
                                   'approved-model', 'test-run', 32, 524288, 1200)
        self.calls = []
        self.lock = threading.Lock()
        self.reply = (200, b'{"id":"native-response","choices":[{"message":{"role":"assistant","content":"ok"}}],"usage":{"prompt_tokens":5,"completion_tokens":2,"total_tokens":7}}')
        self.server = None
        self.start()

    def start(self, transport=None):
        self.server = proxy.create_server(self.config, self.db, '127.0.0.1', 0, transport or self.transport)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join()
            self.server = None

    def tearDown(self):
        self.stop()
        self.temp.cleanup()

    def transport(self, config, body, headers):
        with self.lock:
            self.calls.append((config, body, headers))
        return self.reply

    def request(self, value=None, raw=None, headers=None, path='/v1/chat/completions', method='POST'):
        if raw is None:
            raw = json.dumps(value or {'messages': [{'role': 'user', 'content': 'hello'}]}).encode()
        client = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            client.request(method, path, raw if method == 'POST' else None,
                           headers or {'Content-Type': 'application/json'})
            response = client.getresponse()
            return response.status, response.read()
        finally:
            client.close()

    def summary(self):
        return json.loads(self.request(method='GET', path='/healthz')[1])

    def test_native_success_fixed_limits_and_headers(self):
        trace = '00-' + '1'*32 + '-' + '2'*16 + '-01'
        status, result = self.request(headers={'Content-Type': 'application/json', 'Authorization': 'Bearer secret-marker',
                                               'traceparent': trace, 'tracestate': 'sensitive', 'X-Secret': 'private'})
        self.assertEqual((status, result), self.reply)
        config, body, headers = self.calls[0]
        request = json.loads(body)
        self.assertEqual(request['model'], self.config.model)
        self.assertEqual(request['stream'], False)
        self.assertEqual(request['max_tokens'], 1200)
        self.assertNotIn('reasoning_effort', request)
        self.assertEqual(headers, {'Content-Type': 'application/json', 'Accept': 'application/json',
                                   'Authorization': 'Bearer secret-marker', 'traceparent': trace})
        self.assertEqual(self.summary()['statuses'], {'upstream_success': 1})
        with sqlite3.connect(self.db) as conn:
            row = conn.execute('SELECT status,http_status,digest,usage FROM attempts').fetchone()
        self.assertEqual(row[:2], ('upstream_success', 200))
        self.assertEqual(len(row[2]), 64)
        self.assertEqual(json.loads(row[3])['total_tokens'], 7)

    def test_optional_low_reasoning_effort_is_forwarded_unchanged(self):
        value = {'messages': [{'role': 'user', 'content': 'hello'}], 'reasoning_effort': 'low'}
        self.assertEqual(self.request(value=value)[0], 200)
        self.assertEqual(json.loads(self.calls[0][1])['reasoning_effort'], 'low')
        self.assertEqual(self.summary()['requests_reserved'], 1)

    def test_other_reasoning_efforts_are_rejected_and_reservations_remain_spent(self):
        modes = ('high', 'max', 'medium', 'none', 'off', '', None, True, {}, 1)
        for mode in modes:
            with self.subTest(mode=mode):
                value = {'messages': [{'role': 'user', 'content': 'hello'}], 'reasoning_effort': mode}
                self.assertEqual(self.request(value=value)[0], 400)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.summary()['requests_reserved'], len(modes))

    def test_malformed_inputs_reserve_attempts_without_call(self):
        values = [b'{"messages":[],"x":1}', b'{"messages":[{}],"stream":true}',
                  b'{"messages":[{}],"max_tokens":0}', b'{"messages":[{}],"max_tokens":1201}',
                  b'{"messages":[{}],"max_tokens":true}', b'{"messages":[{}],"model":"other"}',
                  b'{"messages":[{}],"temperature":NaN}', b'{"messages":[{}],"temperature":1e999}',
                  b'{"messages":[{}],"stream":false,"stream":false}', b'[]', b'not json']
        for raw in values:
            self.assertEqual(self.request(raw=raw)[0], 400)
        self.assertEqual(len(self.calls), 0)
        self.assertEqual(self.summary()['requests_reserved'], len(values))
        self.assertEqual(self.summary()['input_bytes'], sum(map(len, values)))

    def test_concurrent_shared_cap_and_restart(self):
        with ThreadPoolExecutor(max_workers=12) as workers:
            statuses = list(workers.map(lambda _: self.request()[0], range(45)))
        self.assertEqual(statuses.count(200), 32)
        self.assertEqual(statuses.count(429), 13)
        self.assertEqual(len(self.calls), 32)
        self.stop()
        self.start()
        self.assertEqual(self.request()[0], 429)
        self.assertEqual(self.summary()['requests_reserved'], 32)
        self.assertEqual(len(self.calls), 32)

    def test_cumulative_input_cap_reserves_rejections(self):
        self.stop()
        Path(self.db).unlink()
        raw = b'{"messages":[{"content":"' + b'x'*49000 + b'"}]}'
        self.config = dataclasses.replace(self.config, max_input_bytes=len(raw)*2)
        self.start()
        self.assertEqual(self.request(raw=raw)[0], 200)
        self.assertEqual(self.request(raw=raw)[0], 200)
        status, body = self.request(raw=raw)
        self.assertEqual(status, 429)
        self.assertIn(b'input_budget_exhausted', body)
        self.assertEqual(self.summary()['requests_reserved'], 3)
        self.assertEqual(self.summary()['input_bytes'], len(raw)*2)
        self.assertEqual(len(self.calls), 2)

    def test_existing_database_identity_cannot_change(self):
        self.request()
        for change in ({'run_id': 'fresh'}, {'max_requests': 31}, {'model': 'other'},
                       {'upstream_base_url': 'https://other.example'}):
            with self.assertRaisesRegex(ValueError, 'configuration mismatch'):
                proxy.BudgetStore(self.db, dataclasses.replace(self.config, **change))
        self.assertEqual(self.summary()['requests_reserved'], 1)

    def test_failed_and_rejected_upstream_preserve_reservations(self):
        cases = [(302, b'{"redirect":"https://no.example"}', 502),
                 (503, b'{"error":{"message":"busy"}}', 503),
                 (200, b'not json', 502), (200, b'[]', 502),
                 (200, b'x' * (proxy.RESPONSE_LIMIT+1), 502)]
        for status, body, expected in cases:
            self.reply = (status, body)
            actual_status, actual_body = self.request()
            self.assertEqual(actual_status, expected)
            if status == 503:
                self.assertEqual(actual_body, body)
        self.assertEqual(self.summary()['requests_reserved'], len(cases))
        self.assertEqual(len(self.calls), len(cases))

    def test_timeout_no_retry_and_durable_failure(self):
        self.stop()
        count = []
        def timeout(*args):
            count.append(1)
            raise socket.timeout('secret in exception')
        self.start(timeout)
        status, body = self.request()
        self.assertEqual(status, 504)
        self.assertEqual(count, [1])
        self.assertNotIn(b'secret', body)
        self.stop()
        self.start()
        self.assertEqual(self.summary()['statuses'], {'upstream_timeout': 1})

    def test_privacy_health_logs_and_database(self):
        marker = 'PRIVATE_REQUEST_CONTENT_MARKER'
        self.reply = (200, json.dumps({'choices': [{'message': {'content': 'PRIVATE_RESPONSE_MARKER'}}],
                                      'usage': {'prompt_tokens': 3, 'provider_secret': marker,
                                                'completion_tokens_details': {'reasoning_tokens': 2, 'private': marker}}}).encode())
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.request(value={'messages': [{'role': 'user', 'content': marker}]},
                         headers={'Content-Type': 'application/json', 'Authorization': 'Bearer PRIVATE_AUTH_MARKER',
                                  'traceparent': 'bad-secret-trace'})
            health = self.summary()
        self.assertEqual(output.getvalue() + errors.getvalue(), '')
        self.assertNotIn('traceparent', self.calls[0][2])
        stored = Path(self.db).read_bytes()
        for value in (marker, 'PRIVATE_RESPONSE_MARKER', 'PRIVATE_AUTH_MARKER', self.config.model,
                      self.config.run_id, self.config.upstream_base_url):
            self.assertNotIn(value.encode(), stored)
            self.assertNotIn(value, json.dumps(health))
        with sqlite3.connect(self.db) as conn:
            usage = json.loads(conn.execute('SELECT usage FROM attempts').fetchone()[0])
        self.assertEqual(usage, {'prompt_tokens': 3, 'completion_tokens_details': {'reasoning_tokens': 2}})

    def test_large_and_unsupported_bodies_and_routes(self):
        self.assertEqual(self.request(raw=b'x' * (proxy.REQUEST_LIMIT+1))[0], 413)
        self.assertEqual(self.request(headers={'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.request(path='/proxy?url=https://other.example')[0], 404)
        self.assertEqual(len(self.calls), 0)
        self.assertEqual(self.summary()['requests_reserved'], 2)

    def test_strict_config(self):
        path = Path(self.temp.name) / 'config.json'
        data = dataclasses.asdict(self.config)
        path.write_text(json.dumps(data))
        self.assertEqual(proxy.Config.read(path), self.config)
        for change in ({'max_requests': 33}, {'max_requests': True}, {'max_input_bytes': 524289},
                       {'max_output_tokens': 1201}, {'upstream_base_url': 'http://example.com'},
                       {'upstream_base_url': 'https://user:password@example.com'},
                       {'upstream_base_url': 'https://example.com/v1'}, {'unknown': 'x'}):
            path.write_text(json.dumps(dict(data, **change)))
            with self.assertRaises(ValueError):
                proxy.Config.read(path)

    def test_real_forwarding_uses_fixed_path_and_no_redirect_retry(self):
        seen = []
        class Response:
            status = 302
            def close(self):
                pass
            def read(self, limit):
                seen.append(('read', limit))
                return b'{"error":"redirect"}'
        class Connection:
            sock = None
            def __init__(self, host, port, timeout):
                seen.append(('connect', host, port, timeout))
            def request(self, method, path, body, headers):
                seen.append(('request', method, path, body, headers))
            def getresponse(self):
                return Response()
            def close(self):
                seen.append(('close',))
        with patch.object(proxy.http.client, 'HTTPConnection', Connection):
            self.assertEqual(proxy.forward(self.config, b'{}', {'Authorization': 'Bearer x'})[0], 302)
        self.assertEqual(seen[0], ('connect', 'gateway.namespace.svc.cluster.local', 8080, 100))
        self.assertEqual(seen[1][1:3], ('POST', '/v1/chat/completions'))
        self.assertEqual(sum(item[0] == 'request' for item in seen), 1)
        self.assertIn(('read', proxy.RESPONSE_LIMIT+1), seen)

    def test_transport_deadline_covers_connection_close_response(self):
        released = threading.Event()
        class Socket:
            def shutdown(self, how):
                released.set()
        class Response:
            status = 200
            def close(self):
                pass
            def read(self, limit):
                if not released.wait(1):
                    raise AssertionError('watchdog did not stop response')
                return b'{}'
        class Connection:
            def __init__(self, *args, **kwargs):
                self.sock = Socket()
            def request(self, *args, **kwargs):
                pass
            def getresponse(self):
                # http.client drops its socket on Connection: close responses.
                self.sock = None
                return Response()
            def close(self):
                pass
        with patch.object(proxy.http.client, 'HTTPConnection', Connection), patch.object(proxy, 'UPSTREAM_TIMEOUT', 0.02):
            with self.assertRaises(TimeoutError):
                proxy.forward(self.config, b'{}', {})
        self.assertTrue(released.is_set())

    def test_second_serving_process_cannot_share_database(self):
        with self.assertRaises(BlockingIOError):
            proxy.create_server(self.config, self.db, '127.0.0.1', 0, self.transport)

    def test_reservation_is_durable_before_upstream(self):
        self.stop()
        def inspect(config, payload, headers):
            with sqlite3.connect(self.db) as conn:
                row = conn.execute('SELECT status,input_bytes FROM attempts').fetchone()
            self.assertEqual(row[0], 'pending')
            self.assertGreater(row[1], 0)
            return self.reply
        self.start(inspect)
        self.assertEqual(self.request()[0], 200)

    def test_interrupted_reservation_stays_spent_and_finish_idempotent(self):
        attempt, reason = self.server.store.reserve(42)
        self.assertIsNone(reason)
        self.stop()
        self.start()
        self.assertEqual(self.summary()['statuses'], {'interrupted': 1})
        self.server.store.finish(attempt, 'upstream_success', 200)
        self.assertEqual(self.summary()['statuses'], {'interrupted': 1})
        self.assertEqual(self.summary()['input_bytes'], 42)


if __name__ == '__main__':
    unittest.main()
