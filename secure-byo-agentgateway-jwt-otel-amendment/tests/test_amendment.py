import base64
import contextlib
import copy
import http.server
import importlib.util
import json
import io
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from render_telemetry import render
from probe_trace import canonical_id, credential, exchange, main as probe_main, origin, project_trace


def settings():
    return {'gatewayNamespace': 'demo-gateway', 'gatewayName': 'demo', 'policyName': 'demo-observability',
        'collectorNamespace': 'telemetry', 'collectorService': 'collector', 'collectorPort': 4317, 'collectorPodPort': 14317,
        'protocol': 'GRPC', 'sampleRatio': '1.0', 'serviceName': 'agentgateway-secure-onboarding',
        'gatewayPodLabels': {'gateway.networking.k8s.io/gateway-name': 'demo'},
        'collectorPodLabels': {'app': 'collector'}, 'approvedGatewayScope': True,
        'privacyReviewReference': 'platform-review-123'}


def crd():
    endpoint = {'backendRef': {}, 'protocol': {'enum': ['GRPC', 'HTTP']}}
    frontend = {'tracing': {'properties': dict(endpoint, randomSampling={}, clientSampling={}, resources={}, attributes={})},
        'accessLog': {'properties': {'otlp': {'properties': endpoint}}}}
    return {'metadata': {'name': 'agentgatewaypolicies.agentgateway.dev'}, 'spec': {'versions': [
        {'name': 'v1alpha1', 'served': True, 'schema': {'openAPIV3Schema': {'properties': {
            'spec': {'properties': {'frontend': {'properties': frontend}}}}}}}]}}


class Renderer(unittest.TestCase):
    def test_additive_output_preserves_input_and_does_not_apply_network_isolation(self):
        s, schema, policies = settings(), crd(), {'kind': 'List', 'items': []}
        before = copy.deepcopy((s, schema, policies))
        result = render(s, schema, policies)
        self.assertEqual((s, schema, policies), before)
        objects = result['resources']['items']
        self.assertEqual([x['kind'] for x in objects], ['AgentgatewayPolicy', 'ReferenceGrant'])
        self.assertEqual(objects[1]['spec']['from'][0]['kind'], 'AgentgatewayPolicy')
        self.assertEqual(objects[1]['spec']['to'][0]['name'], 'collector')
        self.assertEqual(objects[0]['spec']['targetRefs'][0]['kind'], 'Gateway')
        self.assertFalse(result['review']['applied'])
        self.assertFalse(result['review']['tempoEvidenceVerified'])
        self.assertNotIn('apiVersion', result['networkFragments'])
        self.assertEqual(objects[0]['spec']['frontend']['tracing']['backendRef']['port'], 4317)
        self.assertEqual(result['networkFragments']['gatewayEgressRule']['ports'][0]['port'], 14317)

    def test_same_namespace_needs_no_cross_namespace_grant(self):
        s = settings(); s['collectorNamespace'] = s['gatewayNamespace']
        self.assertEqual(len(render(s, crd(), {'kind': 'List', 'items': []})['resources']['items']), 1)

    def test_existing_frontend_policy_requires_owner_merge(self):
        policy = {'metadata': {'name': 'existing', 'namespace': 'demo-gateway'}, 'spec': {
            'targetRefs': [{'group': 'gateway.networking.k8s.io', 'kind': 'Gateway', 'name': 'demo'}],
            'frontend': {'tracing': {}}}}
        with self.assertRaisesRegex(ValueError, 'merge'):
            render(settings(), crd(), {'kind': 'List', 'items': [policy]})

    def test_jwt_route_policies_are_preserved_and_not_replaced(self):
        policy = {'metadata': {'name': 'jwt', 'namespace': 'demo-gateway'}, 'spec': {
            'targetRefs': [{'group': 'gateway.networking.k8s.io', 'kind': 'HTTPRoute', 'name': 'agent'}],
            'traffic': {'jwtAuthentication': {'mode': 'Strict'}}}}
        result = render(settings(), crd(), {'kind': 'List', 'items': [policy]})
        self.assertNotIn('traffic', result['resources']['items'][0]['spec'])
        self.assertEqual(policy['spec']['traffic']['jwtAuthentication']['mode'], 'Strict')

    def test_missing_capability_unapproved_scope_and_cel_injection_rejected(self):
        for field, value in [('approvedGatewayScope', False), ('sampleRatio', 'request.headers["x"]'),
            ('collectorPort', True), ('privacyReviewReference', '{{UNRESOLVED}}')]:
            s = settings(); s[field] = value
            with self.assertRaises(ValueError):
                render(s, crd(), {'kind': 'List', 'items': []})
        schema = crd()
        schema['spec']['versions'][0]['schema']['openAPIV3Schema']['properties']['spec']['properties'].pop('frontend')
        with self.assertRaises(ValueError):
            render(settings(), schema, {'kind': 'List', 'items': []})


class Probe(unittest.TestCase):
    def fixture(self):
        trace, span = 'a' * 32, 'b' * 16
        return trace, {'batches': [{'resource': {'attributes': [{'key': 'service.name', 'value': {'stringValue': 'gateway'}}]},
            'scopeSpans': [{'spans': [{'traceId': trace, 'spanId': span,
                'name': 'sensitive prompt', 'events': [{'name': 'sensitive event'}], 'attributes': [
                    {'key': 'http.status', 'value': {'intValue': 200}},
                    {'key': 'authorization', 'value': {'stringValue': 'private credential'}},
                    {'key': 'gen_ai.input.messages', 'value': {'stringValue': 'private prompt'}}]}]}]}]}

    def test_projection_retains_actual_ids_and_removes_content_headers_and_events(self):
        trace, body = self.fixture()
        result = project_trace(body, trace, 'gateway')
        self.assertEqual(result['spans'][0]['spanId'], 'b' * 16)
        self.assertEqual(result['spans'][0]['attributes'], {'http.status': 200})
        for sensitive in ('private credential', 'private prompt', 'sensitive prompt', 'sensitive event'):
            self.assertNotIn(sensitive, json.dumps(result))

    def test_base64_protobuf_ids_and_v2_wrapper_supported(self):
        trace, body = self.fixture()
        body['batches'][0]['scopeSpans'][0]['spans'][0]['traceId'] = base64.b64encode(bytes.fromhex(trace)).decode()
        self.assertEqual(project_trace({'trace': body}, trace, 'gateway')['traceId'], trace)

    def test_duration_uses_observed_timestamps_and_absent_is_unknown(self):
        trace, body = self.fixture()
        self.assertIsNone(project_trace(body, trace, 'gateway')['spans'][0]['durationNanoseconds'])
        span = body['batches'][0]['scopeSpans'][0]['spans'][0]
        span.update(startTimeUnixNano='100', endTimeUnixNano='110')
        self.assertEqual(project_trace(body, trace, 'gateway')['spans'][0]['durationNanoseconds'], 10)
        span['endTimeUnixNano'] = '90'
        with self.assertRaises(ValueError): project_trace(body, trace, 'gateway')

    def test_wrong_trace_service_and_unknown_envelope_never_pass(self):
        trace, body = self.fixture()
        for value, requested, service in [(body, 'c' * 32, 'gateway'), (body, trace, 'missing'), ({}, trace, 'gateway')]:
            with self.assertRaises(ValueError):
                project_trace(value, requested, service)
        with self.assertRaises(ValueError):
            canonical_id('0' * 32, 16)

    def test_private_credentials_and_explicit_transport_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'credential'; path.write_text('synthetic-test-value'); path.chmod(0o644)
            with self.assertRaises(ValueError): credential(path)
            path.chmod(0o600); self.assertEqual(credential(path), 'synthetic-test-value')
        for url in ['http://example.invalid', 'https://user:secret@example.invalid', 'https://example.invalid?secret=x']:
            with self.assertRaises(ValueError): origin(url)
        self.assertEqual(origin('http://localhost:1234', True), 'http://localhost:1234')

    def test_real_http_denial_retained_and_redirect_not_followed(self):
        observed = []
        class Backend(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append(self.path)
                self.send_response(302 if self.path == '/redirect' else 403)
                if self.path == '/redirect': self.send_header('Location', '/forbidden')
                self.end_headers(); self.wfile.write(b'bounded response')
            def log_message(self, *args): pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Backend)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            base = 'http://127.0.0.1:' + str(server.server_port)
            self.assertEqual(exchange(base + '/deny', 'GET', {})[0], 403)
            self.assertEqual(exchange(base + '/redirect', 'GET', {})[0], 302)
            self.assertEqual(observed, ['/deny', '/redirect'])
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_cli_local_fixture_export_does_not_store_credentials_or_response_body(self):
        observed = {}
        trace, body = self.fixture()
        class Backend(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                observed['trace'] = self.headers['traceparent'].split('-')[1]
                observed['auth'] = self.headers['Authorization']
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"private":"body omitted from receipt"}')
            def do_GET(self):
                observed['queryAuth'] = self.headers.get('Authorization')
                body['batches'][0]['scopeSpans'][0]['spans'][0]['traceId'] = observed['trace']
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(body).encode())
            def log_message(self, *args): pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Backend)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/'token').write_text('synthetic-credential'); (root/'token').chmod(0o600)
                (root/'payload.json').write_text('{"prompt":"fixture only"}')
                base = 'http://127.0.0.1:' + str(server.server_port)
                arguments = ['probe_trace.py','request','--url',base+'/invoke','--payload',str(root/'payload.json'),
                    '--token-file',str(root/'token'),'--expected-status','200','--allow-http','--output',str(root/'request.json')]
                with patch.object(sys,'argv',arguments),contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(probe_main(),0)
                request = json.loads((root/'request.json').read_text())
                self.assertEqual(request['targetOutcome'],'unverified')
                self.assertEqual(observed['auth'],'Bearer synthetic-credential')
                self.assertNotIn('synthetic-credential',(root/'request.json').read_text())
                self.assertNotIn('body omitted',(root/'request.json').read_text())
                self.assertEqual((root/'request.json').stat().st_mode & 0o777,0o600)
                arguments = ['probe_trace.py','trace','--tempo-url',base,'--trace-id',observed['trace'],
                    '--expected-service','gateway','--allow-http','--output',str(root/'trace.json')]
                with patch.object(sys,'argv',arguments),contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(probe_main(),0)
                self.assertIsNone(observed['queryAuth'])
                self.assertTrue(json.loads((root/'trace.json').read_text())['expectedServiceObserved'])
        finally:
            server.shutdown(); server.server_close(); thread.join()
