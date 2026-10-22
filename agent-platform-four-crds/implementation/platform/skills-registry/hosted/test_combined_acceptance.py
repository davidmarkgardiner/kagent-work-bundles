import copy
import json
import unittest
from combined_acceptance import COMBINED_PROMPT, check_combined
from contract import canonical
import test_acceptance as fixtures


class CombinedAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.base = fixtures.HostedEvidenceTests(); self.base.setUp()
        for message in self.base.raw['result']['history']:
            if message['role'] == 'user':
                message['parts'] = [{'kind': 'text', 'text': COMBINED_PROMPT}]
        self.source = {'metadata': {'uid': 'source-uid', 'resourceVersion': '123'},
            'data': {'status': 'available', 'caseCode': 'bootstrap-registry', 'evidenceCode': 'e' * 32}}
        value = {**self.source['data'], 'sourceUID': 'source-uid', 'resourceVersion': '123', 'executionId': 'f' * 32}
        self.call = {'kind': 'data', 'metadata': {'kagent_type': 'function_call'},
            'data': {'id': 'fixed-mcp-call', 'name': 'get_demo_status', 'args': {}}}
        self.response = {'kind': 'data', 'metadata': {'kagent_type': 'function_response'}, 'data': {
            'id': 'fixed-mcp-call', 'name': 'get_demo_status', 'response': {
                'content': [{'type': 'text', 'text': json.dumps(value)}], 'isError': False}}}
        self.base.raw['result']['history'].extend([{'role': 'agent', 'parts': [self.call]}, {'role': 'agent', 'parts': [self.response]}])
        self.base.raw['result']['artifacts'][0]['parts'][0]['text'] += ' Synthetic demo data ' + 'e' * 32 + ' ' + 'f' * 32
        self.audit = {'events': [{'executionId': 'f' * 32, 'result': 'passed', 'resultSha256': canonical(value),
            'sourceUID': 'source-uid', 'resourceVersion': '123', 'traceId': 'a' * 32, 'spanId': 'b' * 16}]}

    def check(self):
        return check_combined(self.base.raw, self.base.context, self.base.contents, self.base.release, self.source, self.audit)

    def test_complete_fixture_composes_both_document_policies_and_mcp(self):
        result = self.check()
        self.assertEqual(result['phase'], 'Passed')
        self.assertEqual(len(result['toolCalls']), 4)

    def test_wrong_arguments_never_pass_as_a_fixed_capability(self):
        self.call['data']['args'] = {'name': 'another-resource'}
        with self.assertRaisesRegex(ValueError, 'UnexpectedMCPArguments'): self.check()

    def test_malformed_response_shapes_are_bounded_rejections(self):
        for raw in ([], {}, {'result': []}, {'result': {'history': [None]}}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                check_combined(raw, self.base.context, self.base.contents, self.base.release, self.source, self.audit)

    def test_duplicate_id_across_mcp_and_document_calls_is_rejected(self):
        self.call['data']['id'] = self.base.call['data']['id']
        with self.assertRaisesRegex(ValueError, 'DuplicateOrExcessiveToolCalls'): self.check()

    def test_other_source_result_or_unmatched_execution_cannot_pass(self):
        self.source['metadata']['uid'] = 'different-uid'
        with self.assertRaisesRegex(ValueError, 'MCPResultSourceMismatch'): self.check()
        self.source['metadata']['uid'] = 'source-uid'
        self.audit['events'][0]['executionId'] = '0' * 32
        with self.assertRaisesRegex(ValueError, 'MCPBackendAuditMismatch'): self.check()

    def test_answer_without_the_fresh_backend_code_fails(self):
        text = self.base.raw['result']['artifacts'][0]['parts'][0]
        text['text'] = text['text'].replace('e' * 32, 'omitted')
        self.assertEqual(self.check()['phase'], 'Failed')
