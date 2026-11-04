import copy
import http.server
import http.client
import socket
import importlib.util
import json
from pathlib import Path
import threading
import sys
import tempfile
import time
from unittest.mock import patch
import unittest
import urllib.error
import urllib.request

MODULE = Path(__file__).resolve().parents[1] / 'runtime' / 'server.py'
spec = importlib.util.spec_from_file_location('secure_byo_runtime', MODULE)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
USER = 'system:serviceaccount:secure-byo-callers:alice'


class FakeKube:
    def __init__(self):
        self.agent = {'metadata': {'uid': 'agent-uid', 'generation': 1}, 'status': {'desiredRevision':'revision1', 'latestSuccessfulRevision':'revision1', 'conditions': [{'type':k, 'status':'True', 'observedGeneration':1} for k in ('Accepted','ResolvedRefs','Compatible','EgressPoliciesApplied','Ready')]}, 'spec': {'template': {'ref': {'name': 'reviewed'}}}}
        self.request = {'metadata': {'uid': 'request-uid'}}
        self.record = {'state': 'Active', 'expiresAt': '2030-01-01T00:00:00Z', 'requestUID': 'request-uid',
                       'agentUID': 'agent-uid', 'agentSpecSha256': runtime.canonical(self.agent['spec']),
                       'callers': {'invoke': [USER], 'mcp': [USER]}, 'callerUIDs': {USER: 'sa-uid'}}
        self.audiences = ['secure-byo']
        self.uid = 'sa-uid'
        self.username = USER
        self.down = False
        self.calls = []
        self.dependencies = {}

    def call(self, path, value=None):
        self.calls.append((path, value))
        if self.down:
            raise OSError('offline')
        if path.endswith('/tokenreviews'):
            return {'status': {'authenticated': value['spec']['token'] == 'valid',
                               'audiences': self.audiences, 'user': {'username': self.username, 'uid': self.uid}}}
        if '/configmaps/' in path:
            return {'metadata': {}, 'data': {'approval.json': json.dumps(self.record)}}
        if '/agents/' in path:
            return copy.deepcopy(self.agent)
        if path in self.dependencies:
            return copy.deepcopy(self.dependencies[path])
        return copy.deepcopy(self.request)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.kube = FakeKube()
        config = {'namespace': 'secure-byo-hosted', 'agentName': 'demo', 'approvalName': 'demo-approval',
                  'request': {'apiVersion': 'secure.platform.example/v1alpha1', 'plural': 'hostedsecureagents', 'name': 'demo'}}
        self.authority = runtime.Authority(self.kube, config, clock=lambda: 1800000000)
        self.dispatch = []
        def upstream(prompt):
            self.dispatch.append(prompt)
            return {'result': {'message': 'fresh native placeholder test'}}
        self.server = runtime.Frontdoor(('127.0.0.1', 0), self.authority, upstream)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def post(self, path='/mcp', value=None, token='valid'):
        if value is None:
            value = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'get_demo_status', 'arguments': {}}}
        headers = {'Content-Type': 'application/json'}
        if token is not None:
            headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(self.url + path, json.dumps(value).encode(), headers)
        try:
            response = urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def test_allowed_tool_has_bounded_fixed_result(self):
        status, body = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body['result']['content'][0]['text'])['agent'], 'demo')
        self.assertEqual(self.server.counters['authorizedMcpCalls'], 1)
        self.assertEqual(self.kube.calls[0][1]['spec']['audiences'], ['secure-byo'])

    def test_anonymous_and_invalid_tokens_denied(self):
        self.assertEqual(self.post(token=None)[0], 401)
        self.assertEqual(self.post(token='bad')[0], 401)
        self.assertEqual(self.server.counters['authorizedMcpCalls'], 0)

    def test_wrong_audience_is_denied(self):
        self.kube.audiences = ['some-other-audience']
        self.assertEqual(self.post()[0], 401)

    def test_wrong_caller_and_same_name_replacement_denied(self):
        self.kube.username = USER + '-other'
        self.assertEqual(self.post()[0], 403)
        self.kube.username = USER
        self.kube.uid = 'replacement'
        self.assertEqual(self.post()[0], 403)

    def test_revocation_is_fresh_on_existing_http_endpoint(self):
        self.assertEqual(self.post()[0], 200)
        self.kube.record['state'] = 'Revoked'
        self.assertEqual(self.post()[0], 403)
        self.assertEqual(self.server.counters['authorizedMcpCalls'], 1)

    def test_expiry_and_missing_record_fail_closed(self):
        self.kube.record['expiresAt'] = '2020-01-01T00:00:00Z'
        self.assertEqual(self.post()[0], 403)
        del self.kube.record['expiresAt']
        self.assertEqual(self.post()[0], 503)

    def test_deleted_replaced_or_drifted_agent_request_denied(self):
        for target, key, value in [(self.kube.agent['metadata'], 'uid', 'replacement'),
                                   (self.kube.request['metadata'], 'uid', 'replacement'),
                                   (self.kube.request['metadata'], 'deletionTimestamp', 'now'),
                                   (self.kube.agent['metadata'], 'deletionTimestamp', 'now')]:
            old = target.get(key)
            target[key] = value
            self.assertEqual(self.post()[0], 403)
            if old is None:
                del target[key]
            else:
                target[key] = old
        self.kube.agent['spec']['extra'] = 'unsafe'
        self.assertEqual(self.post()[0], 403)

    def test_authority_outage_denies_new_calls(self):
        self.assertEqual(self.post()[0], 200)
        self.kube.down = True
        self.assertEqual(self.post()[0], 503)
        self.assertEqual(self.server.counters['authorizedMcpCalls'], 1)

    def test_forbidden_tool_and_arguments_never_count(self):
        for params in ({'name': 'delete_pod'}, {'name': 'get_demo_status', 'arguments': {'namespace': 'other'}}):
            status, body = self.post(value={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': params})
            self.assertEqual(status, 200)
            self.assertIn('error', body)
        self.assertEqual(self.server.counters['authorizedMcpCalls'], 0)

    def test_invoke_accepts_prompt_only_and_no_session_history(self):
        self.assertEqual(self.post('/invoke', {'prompt': 'explain'})[0], 200)
        self.assertEqual(self.dispatch, ['explain'])
        self.assertEqual(self.post('/invoke', {'prompt': 'x', 'sessionId': 'stolen'})[0], 400)
        for path in ('/sessions', '/tasks/other', '/invoke?agent=other', '/invoke/stream'):
            self.assertEqual(self.post(path, {})[0], 404)
        self.assertEqual(self.dispatch, ['explain'])

    def test_witness_is_authenticated(self):
        self.assertEqual(self.post('/witness', {}, None)[0], 401)
        self.assertEqual(self.post('/witness', {})[0], 200)

    def test_oversize_body_is_rejected_before_dispatch(self):
        self.assertEqual(self.post('/invoke', {'prompt': 'x' * 20000})[0], 413)
        self.assertEqual(self.dispatch, [])


    def test_revocation_during_invocation_withholds_result(self):
        def revoke(prompt):
            self.kube.record['state'] = 'Revoked'
            return {'private': 'result'}
        self.server.upstream = revoke
        status, body = self.post('/invoke', {'prompt': 'explain'})
        self.assertEqual(status, 403)
        self.assertNotIn('private', body)

    def test_fixed_cli_transport_creates_bound_session_then_invokes(self):
        self.authority.config.update(kagentBinary='/approved/kagent', apiURL='http://native:8083',
                                     gatewayURL='http://native:8083', nativeUserID='fixed-owner')
        outputs = [{'session': {'id': 'new-session', 'agent': {'namespace': 'secure-byo-hosted', 'name': 'demo'}}},
                   {'task': {'contextId': 'new-session', 'id': 'task'}}]
        commands = []
        def execute(argv, deadline):
            commands.append(argv)
            if '--file' in argv:
                self.assertEqual(Path(argv[-1]).read_text(), '--api-url http://attacker')
            return outputs.pop(0)
        with patch.object(runtime, 'run_cli', execute):
            result = self.server.invoke_cli('--api-url http://attacker')
        self.assertEqual(result['task']['id'], 'task')
        self.assertEqual(commands[0][:11], ['/approved/kagent', '--api-url', 'http://native:8083',
            '--gateway-url', 'http://native:8083', '--namespace', 'secure-byo-hosted', '--user-id', 'fixed-owner', '--timeout', '90s'])
        self.assertEqual(commands[0][-5:], ['agent', 'session', 'create', '--agent', 'demo'])
        self.assertEqual(commands[1][-6:-2], ['agent', 'invoke', '--session', 'new-session'])
        self.assertNotIn('--api-url http://attacker', commands[1])

    def test_cli_rejects_session_for_other_agent_before_invocation(self):
        self.authority.config.update(kagentBinary='/approved/kagent', apiURL='http://native:8083',
                                     gatewayURL='http://native:8083', nativeUserID='fixed-owner')
        with patch.object(runtime, 'run_cli', return_value={'session': {'id': 'stolen', 'agent': {'namespace': 'other', 'name': 'demo'}}}) as call:
            with self.assertRaises(runtime.Denied) as error:
                self.server.invoke_cli('x')
        self.assertEqual(error.exception.reason, 'NativeSessionBindingMismatch')
        self.assertEqual(call.call_count, 1)

    def test_cli_process_deadline_and_output_limit(self):
        self.assertEqual(runtime.run_cli([sys.executable, '-c', 'import json; print(json.dumps(dict(ok=True)))'], time.monotonic() + 3), {'ok': True})
        with self.assertRaises(runtime.Denied) as error:
            runtime.run_cli([sys.executable, '-c', 'import time; time.sleep(5)'], time.monotonic() + 0.05)
        self.assertEqual(error.exception.status, 504)
        with self.assertRaises(runtime.Denied) as error:
            runtime.run_cli([sys.executable, '-c', 'print("x" * 1100000)'], time.monotonic() + 3)
        self.assertEqual(error.exception.reason, 'NativeResponseTooLarge')


    def start_model(self, hook=None):
        self.model_calls = []
        owner = self
        class Provider(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.model_calls.append({'path': self.path, 'authorization': self.headers.get('Authorization'), 'body': body})
                if hook:
                    hook()
                data = json.dumps({'choices': [{'message': {'role': 'assistant', 'content': 'bounded answer'}}]}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        provider = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Provider)
        worker = threading.Thread(target=provider.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(provider.server_close)
        self.addCleanup(provider.shutdown)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        key = Path(directory.name) / 'provider-key'
        key.write_text('provider-private-key')
        self.authority.config.update(upstreamModelURL='http://127.0.0.1:' + str(provider.server_port) + '/v1/chat/completions',
                                     upstreamModelKeyFile=str(key), modelName='approved-model', modelMaxTokens=1200)
        return {'model': 'approved-model', 'messages': [{'role': 'user', 'content': 'hello'}], 'stream': False}

    def test_model_proxy_uses_only_fixed_upstream_credential_and_caps_default(self):
        value = self.start_model()
        status, result = self.post('/v1/chat/completions', value)
        self.assertEqual(status, 200)
        self.assertEqual(self.model_calls[0]['authorization'], 'Bearer provider-private-key')
        self.assertEqual(self.model_calls[0]['path'], '/v1/chat/completions')
        self.assertEqual(self.model_calls[0]['body']['max_tokens'], 1200)
        self.assertEqual(self.model_calls[0]['body']['stream'], False)
        self.assertNotIn('provider-private-key', json.dumps(result))
        self.assertEqual(self.server.counters['authorizedModelCalls'], 1)

    def test_model_mismatch_stream_and_token_overflow_never_dispatch(self):
        value = self.start_model()
        for changes in ({'model': 'unapproved'}, {'stream': True}, {'max_tokens': 1201},
                        {'max_completion_tokens': 5000}, {'max_tokens': 1, 'max_completion_tokens': 1},
                        {'base_url': 'http://attacker'}, {'n': 2}):
            self.assertEqual(self.post('/v1/chat/completions', dict(value, **changes))[0], 400)
        self.assertEqual(self.model_calls, [])
        self.assertEqual(self.server.counters['authorizedModelCalls'], 0)

    def test_model_wrong_principal_and_revocation_never_dispatch(self):
        value = self.start_model()
        self.kube.record['callers']['mcp'] = []
        self.assertEqual(self.post('/v1/chat/completions', value)[0], 403)
        self.kube.record['callers']['mcp'] = [USER]
        self.kube.record['state'] = 'Revoked'
        self.assertEqual(self.post('/v1/chat/completions', value)[0], 403)
        self.assertEqual(self.model_calls, [])

    def test_model_revocation_before_response_withholds_output(self):
        def revoke():
            self.kube.record['state'] = 'Revoked'
        value = self.start_model(revoke)
        status, result = self.post('/v1/chat/completions', value)
        self.assertEqual(status, 403)
        self.assertEqual(len(self.model_calls), 1)
        self.assertNotIn('choices', result)

    def test_model_completion_token_limit_preserved(self):
        value = self.start_model()
        value['max_completion_tokens'] = 500
        self.assertEqual(self.post('/v1/chat/completions', value)[0], 200)
        self.assertEqual(self.model_calls[0]['body']['max_completion_tokens'], 500)
        self.assertNotIn('max_tokens', self.model_calls[0]['body'])


    def test_slow_body_crossing_revocation_never_dispatches(self):
        sock = socket.create_connection(('127.0.0.1', self.server.server_port), timeout=3)
        body = json.dumps({'prompt': 'explain'}).encode()
        request = ('POST /invoke HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer valid\r\nContent-Length: '
                   + str(len(body)) + '\r\n\r\n').encode()
        with sock:
            sock.sendall(request + body[:1])
            deadline = time.monotonic() + 2
            while not self.kube.calls and time.monotonic() < deadline:
                time.sleep(0.005)
            self.kube.record['state'] = 'Revoked'
            sock.sendall(body[1:])
            response = http.client.HTTPResponse(sock)
            response.begin()
            self.assertEqual(response.status, 403)
            response.read()
        self.assertEqual(self.dispatch, [])
        self.assertEqual(self.server.counters['authorizedInvocations'], 0)

    def test_body_has_absolute_deadline(self):
        with patch.object(runtime, 'BODY_TIMEOUT', 0.1):
            sock = socket.create_connection(('127.0.0.1', self.server.server_port), timeout=3)
            with sock:
                sock.sendall(b'POST /invoke HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer valid\r\nContent-Length: 100\r\n\r\n{')
                response = http.client.HTTPResponse(sock)
                response.begin()
                self.assertEqual(response.status, 408)
                response.read()
        self.assertEqual(self.dispatch, [])

    def test_invoke_requires_current_native_ready_revision(self):
        self.kube.agent['status']['latestSuccessfulRevision'] = 'old'
        self.assertEqual(self.post('/invoke', {'prompt': 'x'})[0], 403)
        self.assertEqual(self.post()[0], 200)
        self.kube.agent['status']['latestSuccessfulRevision'] = 'revision1'
        self.kube.agent['status']['conditions'][0]['observedGeneration'] = 0
        self.assertEqual(self.post('/invoke', {'prompt': 'x'})[0], 403)
        self.assertEqual(self.dispatch, [])

    def test_native_dependency_pins_and_reference_edges_checked_fresh(self):
        names = {'agenttemplates':'reviewed', 'harnesses':'harness', 'modelconfigs':'model', 'remotemcpservers':'mcp'}
        self.authority.config['dependencyNames'] = names
        self.kube.agent['spec']['harnessRef'] = {'name':'harness'}
        self.kube.record['agentSpecSha256'] = runtime.canonical(self.kube.agent['spec'])
        self.kube.record['dependencies'] = []
        for plural, name in names.items():
            spec = {'modelConfig':{'name':'model'}, 'tools':[{'mcp':{'server':{'name':'mcp'}}}]} if plural == 'agenttemplates' else {'fixed':name}
            obj = {'metadata':{'uid':plural + '-uid'}, 'spec':spec}
            path = '/apis/api.kagent.dev/v1alpha3/namespaces/secure-byo-hosted/' + plural + '/' + name
            self.kube.dependencies[path] = obj
            self.kube.record['dependencies'].append({'apiVersion':'api.kagent.dev/v1alpha3', 'plural':plural,
                'name':name, 'uid':plural+'-uid', 'specSha256':runtime.canonical(spec)})
        self.assertEqual(self.post()[0], 200)
        path = '/apis/api.kagent.dev/v1alpha3/namespaces/secure-byo-hosted/modelconfigs/model'
        self.kube.dependencies[path]['spec']['unsafe'] = True
        self.assertEqual(self.post()[0], 403)
        del self.kube.dependencies[path]['spec']['unsafe']
        self.kube.dependencies[path]['metadata']['uid'] = 'replacement'
        self.assertEqual(self.post()[0], 403)
        self.assertEqual(self.server.counters['authorizedMcpCalls'], 1)

    def test_cli_reauthorizes_between_session_and_native_dispatch(self):
        self.authority.config.update(kagentBinary='/approved/kagent', apiURL='http://native:8083',
                                     gatewayURL='http://native:8083', nativeUserID='fixed-owner')
        def create(argv, deadline):
            self.kube.record['state'] = 'Revoked'
            return {'session': {'id':'fresh', 'agent':{'namespace':'secure-byo-hosted','name':'demo'}}}
        with patch.object(runtime, 'run_cli', create) as call:
            with self.assertRaises(runtime.Denied) as result:
                self.server.invoke_cli('x', reauthorize=lambda: self.authority.authorize('Bearer valid','invoke'))
        self.assertEqual(result.exception.status, 403)


    def test_absolute_upstream_deadline_prevents_dispatch_after_slow_connect(self):
        requests = []
        finished = threading.Event()
        class Connection:
            sock = None
            def __init__(self, *args, **kwargs):
                pass
            def connect(self):
                time.sleep(0.15)
            def request(self, *args):
                requests.append(args)
            def close(self):
                finished.set()
        with patch.object(runtime.http.client, 'HTTPConnection', Connection):
            start = time.monotonic()
            with self.assertRaises(runtime.Denied) as error:
                runtime.post_json('http://provider/v1/chat/completions', {}, {}, start + 0.05)
            self.assertEqual(error.exception.status, 504)
            self.assertLess(time.monotonic() - start, 0.12)
            self.assertTrue(finished.wait(1))
        self.assertEqual(requests, [])


if __name__ == '__main__':
    unittest.main()
