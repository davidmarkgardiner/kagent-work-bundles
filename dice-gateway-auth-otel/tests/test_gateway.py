import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from render import Settings, gateway_config, render
from trace_report import report
from dashboard import dashboard


class Routing(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(namespace='demo', agent_name='dice-lifecycle-recording', model_name='approved',
            issuer='https://issuer.example', jwks_file='/private/jwks.json', api_server_cidr='192.0.2.1/32',
            python_image='python@sha256:' + 'a' * 64)
        self.agent = {'metadata': {'name': 'dice-lifecycle-recording'}, 'spec': {'type': 'Declarative',
            'declarative': {'systemMessage': 'Reviewed demonstration.', 'deployment': {}, 'modelConfig': 'old'}}}
        self.jwks = {'keys': [{'kty': 'RSA', 'n': 'public', 'e': 'AQAB'}]}

    def test_distinct_strict_subjects_and_audiences(self):
        routes = gateway_config(self.settings, self.jwks)['binds']
        policies = [b['listeners'][0]['routes'][0]['policies'] for b in routes]
        self.assertEqual([p['jwtAuth']['audiences'] for p in policies], [['dice-a2a'], ['dice-mcp']])
        self.assertTrue(all(p['jwtAuth']['mode'] == 'strict' for p in policies))
        self.assertIn('demo:dice-caller', policies[0]['authorization']['rules'][0]['require'])
        self.assertIn('demo:dice-lifecycle-recording', policies[1]['authorization']['rules'][0]['require'])
        self.assertTrue(all(not p['jwtAuth']['preserveToken'] for p in policies))

    def test_clone_uses_gateway_and_preserves_source(self):
        before = copy.deepcopy(self.agent)
        result = render(self.settings, self.agent, self.jwks, {'status': 'available'})
        self.assertEqual(self.agent, before)
        remote = next(i for i in result['items'] if i['kind'] == 'RemoteMCPServer')
        self.assertEqual(remote['spec']['url'], 'http://dice-agentgateway.demo.svc.cluster.local:8081/mcp')
        self.assertEqual(remote['spec']['headersFrom'][0]['valueFrom']['type'], 'Secret')
        self.assertFalse(any(i['kind'] == 'Secret' for i in result['items']))
        agent = next(i for i in result['items'] if i['kind'] == 'Agent')
        self.assertEqual(agent['spec']['declarative']['tools'][0]['mcpServer']['name'], 'dice-gateway-mcp')
        self.assertNotIn('KAGENT_PROPAGATE_TOKEN', json.dumps(agent))

    def test_direct_backend_and_telemetry_paths_are_not_allowed(self):
        items = render(self.settings, self.agent, self.jwks, {})['items']
        policies = {i['metadata']['name']: i['spec'] for i in items if i['kind'] == 'NetworkPolicy'}
        self.assertEqual(policies['default-deny']['ingress'], [])
        self.assertEqual(policies['default-deny']['egress'], [])
        for name in ('agent', 'mcp'):
            self.assertEqual(policies[name]['ingress'][0]['from'],
                [{'podSelector': {'matchLabels': {'app': 'dice-agentgateway'}}}])
        self.assertNotIn('8084', json.dumps(policies['agent']['egress']))
        self.assertNotIn('namespaceSelector', json.dumps(policies['collector']['ingress'][0]))

    def test_private_signing_keys_rejected(self):
        for key in ({'kty': 'RSA', 'd': 'private'}, {'kty': 'oct', 'k': 'secret'}):
            with self.assertRaises(ValueError):
                render(self.settings, self.agent, {'keys': [key]}, {})

    def test_config_change_restarts_the_affected_helper(self):
        before = render(self.settings, self.agent, self.jwks, {})['items']
        after = render(replace(self.settings, issuer='https://other.example'), self.agent, self.jwks, {})['items']
        def template(items):
            return next(i for i in items if i['kind'] == 'Deployment' and i['metadata']['name'] == 'dice-agentgateway')['spec']['template']
        self.assertNotEqual(template(before), template(after))

    def test_dashboard_queries_observed_metric_family(self):
        value = dashboard('demo')
        self.assertEqual(value['refresh'], '5s')
        self.assertIn('dice_calls_total', json.dumps(value))
        self.assertIn('dice_duration_milliseconds_bucket', json.dumps(value))
        self.assertIn('service_namespace', json.dumps(value))


class TraceEvidence(unittest.TestCase):
    def setUp(self):
        self.trace_id = '1' * 32
        services = ['agentgateway', 'dice_lifecycle_recording', 'agentgateway', 'dice-status-mcp']
        batches = []
        parent = '0' * 16
        for i, service in enumerate(services):
            span = {'traceId': self.trace_id, 'spanId': str(i + 1) * 16, 'parentSpanId': parent,
                    'attributes': [], 'status': {'code': 1}, 'kind': 2}
            if service == 'dice_lifecycle_recording':
                span['attributes'].append({'key': 'gen_ai.task.id', 'value': {'stringValue': 'task'}})
            if service == 'dice-status-mcp':
                span['attributes'].append({'key': 'flow.execution.id', 'value': {'stringValue': 'execution'}})
            batches.append({'resource': {'attributes': [{'key': 'service.name', 'value': {'stringValue': service}}]},
                            'scopeSpans': [{'spans': [span]}]})
            parent = span['spanId']
        self.trace = {'resourceSpans': batches}
        self.native = {'result': {'id': 'task', 'contextId': 'context', 'status': {'state': 'completed'},
                                 'history': [{'role': 'agent', 'parts': [
                                     {'kind': 'data', 'metadata': {'kagent_type': 'function_call'},
                                      'data': {'id': 'call', 'name': 'get_demo_status', 'args': {}}},
                                     {'kind': 'data', 'metadata': {'kagent_type': 'function_response'},
                                      'data': {'id': 'call', 'name': 'get_demo_status',
                                               'response': {'isError': False, 'executionId': 'execution'}}}]}]}}

    def test_both_gateway_hops_and_execution_match(self):
        self.assertTrue(report(self.trace, self.native)['verified'])

    def test_direct_agent_to_mcp_is_not_gateway_proof(self):
        self.trace['resourceSpans'][-1]['scopeSpans'][0]['spans'][0]['parentSpanId'] = '2' * 16
        with self.assertRaises(ValueError):
            report(self.trace, self.native)

    def test_other_task_trace_is_rejected(self):
        self.native['result']['id'] = 'different-task'
        with self.assertRaises(ValueError):
            report(self.trace, self.native)

    def test_other_execution_is_rejected(self):
        self.native['result']['history'][0]['parts'][1]['data']['response']['executionId'] = 'different-execution'
        with self.assertRaises(ValueError):
            report(self.trace, self.native)

    def test_user_text_cannot_supply_tool_evidence(self):
        self.native['result']['history'] = [{'role': 'user', 'parts': [{'kind': 'text', 'text': '{"executionId":"execution"}'}]}]
        with self.assertRaises(ValueError):
            report(self.trace, self.native)

    def test_unset_or_client_mcp_spans_are_not_completion(self):
        span = self.trace['resourceSpans'][-1]['scopeSpans'][0]['spans'][0]
        span['status'] = {}
        with self.assertRaises(ValueError):
            report(self.trace, self.native)
        span.update(status={'code': 1}, kind=3)
        with self.assertRaises(ValueError):
            report(self.trace, self.native)


if __name__ == '__main__':
    unittest.main()
