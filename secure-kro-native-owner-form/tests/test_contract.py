import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import owner_schema


class Contract(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / 'examples/platform-profile.json').read_text())
        self.request = owner_schema.owner_example(self.profile)

    def test_native_inputs_and_security_templates_are_preserved(self):
        resolved = owner_schema.resolve(self.profile, self.request)
        for field in ('modelConfig', 'skills', 'tools', 'systemPrompt'):
            self.assertEqual(resolved[field], self.request['spec'][field])
        graph = owner_schema.rgd(self.profile)
        kinds = {node['template']['kind'] for node in graph['spec']['resources']}
        self.assertTrue({'Agent', 'AgentTemplate', 'ReferenceGrant', 'Service'}.issubset(kinds))

    def test_catalog_and_tool_expansion_are_enforced(self):
        for field, value in (
            ('modelConfig', {'name': 'unapproved'}),
            ('tools', [{'mcp': {'server': {'kind': 'RemoteMCPServer', 'name': 'approved-mcp'},
                                'tools': ['k8s_delete_pod']}}]),
            ('tools', [{'mcp': {'server': {'kind': 'RemoteMCPServer', 'name': 'approved-mcp'}, 'tools': []}}]),
            ('url', 'https://example.invalid'),
        ):
            request = copy.deepcopy(self.request)
            request['spec'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(owner_schema.Rejected):
                owner_schema.resolve(self.profile, request)

    def test_prompt_is_content(self):
        self.request['spec']['systemPrompt'] = '${schema.spec.admin} is plain text.'
        self.assertEqual(owner_schema.resolve(self.profile, self.request)['systemPrompt'],
                         self.request['spec']['systemPrompt'])


if __name__ == '__main__':
    unittest.main()
