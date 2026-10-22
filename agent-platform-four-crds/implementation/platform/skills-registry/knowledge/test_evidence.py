import json
from pathlib import Path
import unittest

from evidence_check import FILE_PATH, MARKER, PROMPT, Rejected, check_execution

HERE = Path(__file__).resolve().parent


class DocumentEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.release = json.loads((HERE / 'release.json').read_text())
        self.body = (HERE / 'payload/oras-pull-unauthorized.md').read_text()
        self.context = 'synthetic-unit-test-context'
        self.call = {'kind': 'data', 'metadata': {'kagent_type': 'function_call'},
                     'data': {'id': 'call-one', 'name': 'read_file', 'args': {'file_path': FILE_PATH}}}
        self.response = {'kind': 'data', 'metadata': {'kagent_type': 'function_response'},
                         'data': {'id': 'call-one', 'name': 'read_file', 'response': {
                             'result': '\n'.join(f'{i}|{line}' for i, line in enumerate(self.body.splitlines(), 1))}}}
        document = self.release['documents'][0]
        self.raw = {'result': {'id': 'synthetic-task', 'contextId': self.context, 'status': {'state': 'completed'},
            'metadata': {'kagent_app_name': 'skills_demo__NS__knowledge_demo_agent', 'kagent_author': 'knowledge_demo_agent', 'kagent_session_id': self.context},
            'history': [{'role': 'user', 'parts': [{'kind': 'text', 'text': PROMPT}]},
                        {'role': 'agent', 'parts': [self.call]}, {'role': 'agent', 'parts': [self.response]}],
            'artifacts': [{'parts': [{'kind': 'text', 'text': f'{document["title"]} {document["sourceURL"]} {MARKER} documentation only exit 212 kubelet'}]}]}}

    def check(self):
        return check_execution(self.raw, self.context, self.body, self.release)

    def test_synthetic_complete_evidence_passes(self):
        self.assertEqual(self.check()['phase'], 'Passed')

    def test_answer_without_read_is_rejected(self):
        self.raw['result']['history'] = self.raw['result']['history'][:1]
        with self.assertRaisesRegex(Rejected, 'RequiredToolEvidenceMissing'):
            self.check()

    def test_changed_document_is_rejected(self):
        self.response['data']['response']['result'] += '\n20|Injected'
        with self.assertRaises(Rejected):
            self.check()

    def test_truncated_document_is_rejected(self):
        self.response['data']['response']['result'] = '1|# AKS bootstrap registry authorization'
        with self.assertRaisesRegex(Rejected, 'DocumentResultContentMismatch'):
            self.check()

    def test_wrong_response_id_is_rejected(self):
        self.response['data']['id'] = 'another'
        with self.assertRaisesRegex(Rejected, 'ToolResultAttributionMismatch'):
            self.check()

    def test_extra_tool_is_rejected(self):
        self.call['data']['name'] = 'bash'
        with self.assertRaisesRegex(Rejected, 'UnexpectedTool'):
            self.check()

    def test_extra_argument_is_rejected(self):
        self.call['data']['args']['offset'] = 2
        with self.assertRaisesRegex(Rejected, 'UnexpectedToolArguments'):
            self.check()

    def test_wrong_path_is_rejected(self):
        self.call['data']['args']['file_path'] += '.another'
        with self.assertRaisesRegex(Rejected, 'UnexpectedToolArguments'):
            self.check()

    def test_duplicate_call_id_is_rejected(self):
        self.raw['result']['history'][1]['parts'].append(self.call)
        with self.assertRaisesRegex(Rejected, 'DuplicateToolIdentity'):
            self.check()

    def test_result_error_is_rejected(self):
        self.response['data']['isError'] = True
        with self.assertRaisesRegex(Rejected, 'ToolResultNotSuccessful'):
            self.check()

    def test_another_context_is_rejected(self):
        with self.assertRaisesRegex(Rejected, 'InvocationAttributionMismatch'):
            check_execution(self.raw, 'another-context', self.body, self.release)

    def test_another_agent_is_rejected(self):
        self.raw['result']['metadata']['kagent_author'] = 'skills_demo_agent'
        with self.assertRaisesRegex(Rejected, 'InvocationAttributionMismatch'):
            self.check()

    def test_user_tool_message_is_rejected(self):
        self.raw['result']['history'][2]['role'] = 'user'
        with self.assertRaises(Rejected):
            self.check()

    def test_another_prompt_is_rejected(self):
        self.raw['result']['history'][0]['parts'][0]['text'] = 'Something else'
        with self.assertRaisesRegex(Rejected, 'InvocationPromptMismatch'):
            self.check()

    def test_partial_number_does_not_pass(self):
        self.raw['result']['artifacts'][0]['parts'][0]['text'] = self.raw['result']['artifacts'][0]['parts'][0]['text'].replace(' 212 ', ' 2120 ')
        self.assertEqual(self.check()['phase'], 'Failed')

    def test_citation_with_added_path_is_not_exact(self):
        part = self.raw['result']['artifacts'][0]['parts'][0]
        document = self.release['documents'][0]
        part['text'] = part['text'].replace(document['sourceURL'], document['sourceURL'] + '/nonexistent-page')
        self.assertEqual(self.check()['phase'], 'Failed')

    def test_parentheses_suffix_is_not_the_citation(self):
        part = self.raw['result']['artifacts'][0]['parts'][0]
        url = self.release['documents'][0]['sourceURL']
        part['text'] = part['text'].replace(url, url + '(nonexistent-page)')
        self.assertEqual(self.check()['phase'], 'Failed')

    def test_brackets_suffix_is_not_the_citation(self):
        part = self.raw['result']['artifacts'][0]['parts'][0]
        url = self.release['documents'][0]['sourceURL']
        part['text'] = part['text'].replace(url, url + '[nonexistent-page]')
        self.assertEqual(self.check()['phase'], 'Failed')

    def test_markdown_link_has_exact_destination(self):
        part = self.raw['result']['artifacts'][0]['parts'][0]
        url = self.release['documents'][0]['sourceURL']
        part['text'] = part['text'].replace(url, '[Microsoft](' + url + ')')
        self.assertEqual(self.check()['phase'], 'Passed')
        part['text'] = part['text'].replace(url, url + '(nonexistent-page)')
        self.assertEqual(self.check()['phase'], 'Failed')

    def test_missing_citation_fails_answer(self):
        document = self.release['documents'][0]
        part = self.raw['result']['artifacts'][0]['parts'][0]
        part['text'] = part['text'].replace(document['sourceURL'], '')
        self.assertEqual(self.check()['phase'], 'Failed')


if __name__ == '__main__':
    unittest.main()
