import copy
import hashlib
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from fixed_mcp import Capability, Handler, TOOL, encoded


class FixedCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.calls = 0
        self.document = {'data': {'status': 'available', 'caseCode': 'bootstrap-registry', 'evidenceCode': 'a' * 32,
                                  'unrelated': 'must-not-leak'},
                         'metadata': {'uid': 'fixture-uid', 'resourceVersion': '12'}}
        def source():
            self.calls += 1
            return copy.deepcopy(self.document)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.capability = Capability(source)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port) + '/mcp'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def post(self, method, params=None, headers=None):
        request = urllib.request.Request(self.url, encoded({'jsonrpc': '2.0', 'id': 7, 'method': method, 'params': params or {}}),
                                         {'Content-Type': 'application/json', **(headers or {})})
        with urllib.request.urlopen(request) as response:
            raw = response.read()
        self.assertLessEqual(len(raw), 4096)
        return json.loads(raw)

    def test_single_read_is_bounded_fresh_and_audited_by_exact_result_digest(self):
        trace = 'b' * 32
        results = [self.post('tools/call', {'name': TOOL, 'arguments': {}},
                            {'traceparent': '00-' + trace + '-' + 'c' * 16 + '-01'})['result'] for _ in range(2)]
        self.assertEqual(self.calls, 2)
        values = [json.loads(result['content'][0]['text']) for result in results]
        self.assertNotEqual(values[0]['executionId'], values[1]['executionId'])
        self.assertNotIn('unrelated', values[0])
        for result, value, event in zip(results, values, self.server.capability.events()):
            self.assertFalse(result['isError'])
            self.assertNotEqual(event['traceId'], trace)
            self.assertEqual(event['executionId'], value['executionId'])
            self.assertEqual(event['resultSha256'], hashlib.sha256(encoded(value)).hexdigest())
        self.assertNotEqual(self.server.capability.events()[0]['traceId'], self.server.capability.events()[1]['traceId'])

    def test_telemetry_failure_does_not_replace_the_backend_result(self):
        def fail_export(*args):
            raise ValueError('Invalid collector endpoint')
        self.server.capability.export = fail_export
        result = self.post('tools/call', {'name': TOOL})['result']
        self.assertFalse(result['isError'])
        event = self.server.capability.events()[0]
        self.assertEqual(event['result'], 'passed')
        self.assertEqual(event['telemetryOutcome'], 'unavailable')

    def test_unknown_tools_and_extra_arguments_never_dispatch_a_backend_read(self):
        for params in [{'name': 'delete_configmap'}, {'name': TOOL, 'arguments': {'namespace': 'kube-system'}},
                       {'name': TOOL, 'arguments': {'command': 'kubectl get secrets'}}, {'name': TOOL, 'arguments': None}]:
            with self.subTest(params=params):
                self.assertTrue(self.post('tools/call', params)['result']['isError'])
        self.assertEqual(self.calls, 0)
        self.assertEqual(self.server.capability.events(), [])

    def test_discovery_and_unknown_protocol_methods_do_not_read_the_backend(self):
        tools = self.post('tools/list')['result']['tools']
        self.assertEqual([x['name'] for x in tools], [TOOL])
        self.assertFalse(tools[0]['inputSchema']['additionalProperties'])
        self.assertEqual(self.post('initialize', {'protocolVersion': '2025-06-18'})['result']['protocolVersion'], '2025-06-18')
        self.assertEqual(self.post('initialize', {'protocolVersion': []})['error']['code'], -32602)
        self.assertEqual(self.post('resources/read', {'uri': 'file:///etc/passwd'})['error']['code'], -32601)
        self.assertEqual(self.calls, 0)

    def test_oversized_request_is_rejected_before_dispatch(self):
        request = urllib.request.Request(self.url, b'x' * 4097)
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.calls, 0)

    def test_malformed_backend_data_is_an_error_with_no_unbounded_content(self):
        for data in [[], {'status': 'available', 'caseCode': 'x' * 10000, 'evidenceCode': 'a' * 32}]:
            self.document['data'] = data
            result = self.post('tools/call', {'name': TOOL})['result']
            self.assertTrue(result['isError'])
            self.assertLess(len(encoded(result)), 256)
        self.assertEqual([e['result'] for e in self.server.capability.events()], ['failed', 'failed'])


if __name__ == '__main__':
    unittest.main()
