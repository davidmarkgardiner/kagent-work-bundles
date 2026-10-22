import json
from pathlib import Path
import unittest

from acceptance import PROMPT, SKILL_URL, check

ROOT = Path(__file__).resolve().parents[1]


class HostedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.release = json.loads((ROOT / 'hosted/release.json').read_text())
        self.release['agentSpecSha256'] = 'a' * 64
        self.raw = json.loads((ROOT / 'imports/aks-known-issues/evidence/exact-signature-a2a.json').read_text())
        result = self.raw['result']
        self.context = result['contextId']
        result['metadata'].update(kagent_app_name='skills_demo__NS__hosted_aks_platform_demo_v1', kagent_author='hosted_aks_platform_demo_v1')
        for message in result['history']:
            if message['role'] == 'user':
                message['parts'] = [{'kind': 'text', 'text': PROMPT}]
        self.contents = {'skill': {path: (ROOT / 'imports/aks-known-issues/payload' / path).read_text() for path in self.release['skill']['files']},
                         'knowledge': {path: (ROOT / 'knowledge/payload' / path).read_text() for path in self.release['knowledge']['files']}}
        body = self.contents['knowledge']['oras-pull-unauthorized.md']
        self.call = {'kind': 'data', 'metadata': {'kagent_type': 'function_call'}, 'data': {
            'id': 'synthetic-kb-call', 'name': 'read_file', 'args': {'file_path': '/knowledge/aks-bootstrap/oras-pull-unauthorized.md'}}}
        self.response = {'kind': 'data', 'metadata': {'kagent_type': 'function_response'}, 'data': {
            'id': 'synthetic-kb-call', 'name': 'read_file', 'response': {'result': '\n'.join(f'{i}|{line}' for i, line in enumerate(body.splitlines(), 1))}}}
        result['history'].extend([{'role': 'agent', 'parts': [self.call]}, {'role': 'agent', 'parts': [self.response]}])
        url = self.release['knowledge']['documents'][0]['sourceURL']
        title = self.release['knowledge']['documents'][0]['title']
        result['artifacts'] = [{'parts': [{'kind': 'text', 'text': f'Synthetic unit fixture. {title}. OrasPullUnauthorizedVMExtensionError exit 212 kubelet bootstrap. documentation only. AKS-KB-ORAS-212-R1. {SKILL_URL} {url}'}]}]

    def check(self):
        return check(self.raw, self.context, self.contents, self.release)

    def test_complete_synthetic_combined_evidence_passes(self):
        self.assertEqual(self.check()['phase'], 'Passed')
        self.assertEqual(len(self.check()['toolCalls']), 3)

    def test_tool_evidence_before_user_input_is_rejected(self):
        history = self.raw['result']['history']
        self.raw['result']['history'] = [m for m in history if m['role'] != 'user'] + [m for m in history if m['role'] == 'user']
        with self.assertRaisesRegex(ValueError, 'ToolEvidenceBeforeInput'):
            self.check()

    def test_missing_knowledge_read_is_rejected(self):
        self.raw['result']['history'] = self.raw['result']['history'][:-2]
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_skill_load_is_rejected(self):
        for message in self.raw['result']['history']:
            message['parts'] = [p for p in message['parts'] if p.get('data', {}).get('name') != 'skills']
        with self.assertRaises(ValueError):
            self.check()

    def test_unknown_tool_is_rejected_before_partitioning(self):
        self.call['data']['name'] = 'bash'
        with self.assertRaisesRegex(ValueError, 'UnexpectedToolOrArguments'):
            self.check()

    def test_duplicate_ids_across_policies_are_rejected(self):
        native = [p for m in self.raw['result']['history'] for p in m['parts'] if p.get('metadata', {}).get('kagent_type') == 'function_call']
        self.call['data']['id'] = native[0]['data']['id']
        with self.assertRaisesRegex(ValueError, 'DuplicateToolIdentity'):
            self.check()

    def test_truncated_document_is_rejected(self):
        self.response['data']['response']['result'] = '1|# AKS bootstrap registry authorization'
        with self.assertRaisesRegex(ValueError, 'DocumentResultContentMismatch'):
            self.check()

    def test_wrong_input_is_rejected(self):
        for message in self.raw['result']['history']:
            if message['role'] == 'user':
                message['parts'][0]['text'] = 'Another prompt'
                break
        with self.assertRaises(ValueError):
            self.check()

    def test_old_context_is_rejected(self):
        with self.assertRaises(ValueError):
            check(self.raw, 'new-context', self.contents, self.release)

    def test_wrong_agent_is_rejected(self):
        self.raw['result']['metadata']['kagent_author'] = 'another_agent'
        with self.assertRaises(ValueError):
            self.check()

    def test_wrong_exact_skill_citation_fails(self):
        part = self.raw['result']['artifacts'][0]['parts'][0]
        part['text'] = part['text'].replace(SKILL_URL, SKILL_URL + '(different-page)')
        self.assertEqual(self.check()['phase'], 'Failed')


if __name__ == '__main__':
    unittest.main()
