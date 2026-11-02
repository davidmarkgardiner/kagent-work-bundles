import json
import unittest
from unittest.mock import patch
from telemetry import ActivityStore
from test_telemetry import export, span


class OrdinaryTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.settings = patch.dict('os.environ', {'ORDINARY_AGENT_IDENTITIES': json.dumps([
            {'namespace': 'reviewed-demo', 'name': 'hosted-docs'}])})
        self.settings.start()
        self.addCleanup(self.settings.stop)

    def payload(self, spans, namespace='reviewed-demo'):
        value = export(spans, 'hosted-docs')
        value['resourceSpans'][0]['resource']['attributes'].append(
            {'key': 'service.namespace', 'value': {'stringValue': namespace}})
        return value

    def test_exact_opt_in_identity_and_typed_tools_preserve_call_and_task_ids(self):
        tools = []
        for n, (name, kind) in enumerate([('skills', 'SkillsTool'), ('read_file', 'ReadFileTool'), ('get_demo_status', 'McpTool')], 1):
            tool = span(n, values={'gen_ai.operation.name': 'execute_tool', 'gen_ai.tool.name': name,
                'gen_ai.tool.type': kind, 'gen_ai.tool.call.id': 'call-' + str(n), 'gen_ai.task.id': 'actual-task'})
            tool['kind'] = 1
            tools.append(tool)
        store = ActivityStore()
        store.ingest(self.payload(tools))
        trace = store.snapshot()['traces'][0]
        self.assertEqual(trace['executionMode'], 'ordinary')
        self.assertEqual(trace['nativeRuntimeIdentity']['source'], 'sdk-resource-and-reviewed-profile')
        self.assertEqual([s['toolCategory'] for s in trace['spans']], ['skill', 'skill', 'mcp'])
        self.assertEqual([s['toolExecution'] for s in trace['spans']], ['native-skill', 'native-skill', ''])
        self.assertEqual(trace['spans'][0]['attributes']['gen_ai.task.id'], 'actual-task')
        self.assertEqual(trace['spans'][0]['attributes']['gen_ai.tool.call.id'], 'call-1')

    def test_other_namespace_does_not_inherit_the_reviewed_runtime(self):
        store = ActivityStore()
        store.ingest(self.payload([span(values={'gen_ai.operation.name': 'execute_tool', 'gen_ai.tool.name': 'skills'})], 'other'))
        trace = store.snapshot()['traces'][0]
        self.assertIsNone(trace['nativeRuntimeIdentity'])
        self.assertNotIn('skills', trace['components'])
        self.assertNotIn('mcp', trace['components'])

    def test_model_operations_own_usage_without_counting_adk_bookkeeping(self):
        store = ActivityStore()
        usage = {'gen_ai.request.model': 'approved-model', 'gen_ai.usage.input_tokens': 12, 'gen_ai.usage.output_tokens': 3}
        store.ingest(self.payload([span(1, values={**usage, 'gen_ai.operation.name': 'chat'}), span(2, values=usage)]))
        trace = store.snapshot()['traces'][0]
        self.assertEqual(len(trace['modelCalls']), 1)
        self.assertEqual((trace['inputTokens'], trace['outputTokens']), (12, 3))
        self.assertEqual(trace['modelUsageSource'], 'native-runtime')

    def test_gateway_destination_comes_from_the_exact_url_without_exporting_it(self):
        with patch.dict('os.environ', {'MODEL_GATEWAY_URL': 'http://gateway.example.invalid:8081/approved/v1'}):
            store = ActivityStore()
            store.ingest(self.payload([span(values={'http.url': 'http://gateway.example.invalid:8081/approved/v1/chat/completions',
                                                   'gcp.vertex.agent.tool_response': 'hidden-data'})]))
            trace = store.snapshot()['traces'][0]
            self.assertIn('agentgateway', trace['components'])
            self.assertEqual(trace['spans'][0]['attributes']['flow.destination'], 'agentgateway')
            self.assertNotIn('gateway.example.invalid', json.dumps(trace))
            self.assertNotIn('hidden-data', json.dumps(trace))

    def test_reviewed_legacy_sdk_resource_mapping_is_explicit(self):
        from telemetry import native_runtime_identity
        values = {'service.name': 'hosted_docs', 'service.namespace': 'reviewed_demo'}
        self.assertIsNone(native_runtime_identity(values))
        with patch.dict('os.environ', {'ORDINARY_AGENT_IDENTITIES': json.dumps([{
                'namespace': 'reviewed-demo', 'name': 'hosted-docs',
                'serviceName': 'hosted_docs', 'serviceNamespace': 'reviewed_demo'}])}):
            self.assertEqual(native_runtime_identity(values)['agentId'], 'reviewed-demo/hosted-docs')
            self.assertIsNone(native_runtime_identity({**values, 'service.namespace': 'other'}))

    def test_legacy_openai_client_report_counts_once_with_adk_bookkeeping(self):
        usage = {'gen_ai.request.model': 'approved-model', 'gen_ai.usage.input_tokens': 12, 'gen_ai.usage.output_tokens': 3}
        client = span(1, values={**usage, 'gen_ai.system': 'openai'})
        client.update(name='openai.chat', kind=3)
        bookkeeping = span(2, values={**usage, 'gen_ai.system': 'gcp.vertex.agent'})
        bookkeeping.update(name='call_llm', kind=1)
        store = ActivityStore(); store.ingest(self.payload([client, bookkeeping]))
        trace = store.snapshot()['traces'][0]
        self.assertEqual(len(trace['modelCalls']), 1)
        self.assertEqual((trace['inputTokens'], trace['outputTokens']), (12, 3))


if __name__ == '__main__':
    unittest.main()
