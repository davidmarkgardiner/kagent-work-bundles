import copy
import unittest

from contract import (MCP_KINDS, MCP_ROLES, Rejected, canonical, crd, desired_children,
                      mcp_projection, parse_intent)
import test_onboarding as fixtures
from test_onboarding import condition


class FixedProfileTests(unittest.TestCase):
    def setUp(self):
        self.base = fixtures.OnboardingTests()
        self.base.setUp()
        variant = copy.deepcopy(self.base.profile)
        variant['runtimeProfile'] = 'lab-configmap-read-v1'
        self.pins, self.paths = [], {}
        for role, kind in MCP_ROLES.items():
            obj = {'apiVersion': MCP_KINDS[kind][0], 'kind': kind,
                'metadata': {'name': 'mcp-' + role, 'namespace': 'skills-demo', 'uid': 'uid-' + role, 'generation': 1}}
            if kind == 'RemoteMCPServer':
                obj.update(spec={'url': 'http://mcp-server.skills-demo.svc/mcp'},
                    status={'conditions': [condition('Accepted')], 'discoveredTools': [{'name': 'get_demo_status'}]})
            elif kind == 'Deployment':
                obj.update(spec={'replicas': 1, 'template': {'image': 'reviewed-image'}},
                    status={'observedGeneration': 1, 'availableReplicas': 1, 'updatedReplicas': 1})
            elif kind == 'Role':
                obj['rules'] = [{'apiGroups': [''], 'resources': ['configmaps'], 'resourceNames': ['mcp-data'], 'verbs': ['get']}]
            elif kind == 'RoleBinding':
                obj.update(roleRef={'kind': 'Role', 'name': 'mcp-role'}, subjects=[{'kind': 'ServiceAccount', 'name': 'mcp-account'}])
            elif kind == 'ServiceAccount':
                obj['automountServiceAccountToken'] = True
            elif kind == 'ConfigMap':
                obj.update(data={'reviewed': role}, immutable=True)
            else:
                obj['spec'] = {'reviewed': kind}
            api, plural = MCP_KINDS[kind]
            prefix = '/api/v1' if api == 'v1' else '/apis/' + api
            path = prefix + '/namespaces/skills-demo/' + plural + '/' + obj['metadata']['name']
            self.paths[role] = path
            self.base.kube.data[path] = obj
            self.pins.append({'role': role, 'kind': kind, 'name': obj['metadata']['name'], 'uid': obj['metadata']['uid'],
                              'sha256': canonical(mcp_projection(obj))})
        variant['approvedMcp'] = {'toolName': 'get_demo_status', 'pins': self.pins}
        self.base.profile['mcpProfile'] = variant
        self.base.document['spec']['runtimeProfile'] = variant['runtimeProfile']

    def test_fixed_profile_creates_only_the_approved_mcp_binding(self):
        self.base.reconcile()
        self.assertEqual(self.base.reason(), 'AgentReady')
        agent = next(x for _, x in self.base.children() if x['kind'] == 'Agent')
        self.assertEqual(agent['spec']['declarative']['tools'], [{'type': 'McpServer', 'mcpServer': {
            'apiGroup': 'kagent.dev', 'kind': 'RemoteMCPServer', 'name': 'mcp-server',
            'namespace': 'skills-demo', 'toolNames': ['get_demo_status']}}])
        self.assertIn('mcpDependencyPinsSha256', self.base.kube.data[self.base.hosted_path]['status'])
        self.base.kube.writes.clear()
        self.base.reconcile()
        self.assertEqual(self.base.kube.writes, [])

    def test_every_backend_dependency_uid_and_body_drift_blocks_before_child_creation(self):
        for role, path in self.paths.items():
            original = copy.deepcopy(self.base.kube.data[path])
            with self.subTest(role=role):
                self.base.kube.data[path]['metadata']['uid'] = 'foreign-uid'
                self.base.reconcile()
                self.assertEqual(self.base.reason(), 'MCPDependencyMismatch')
                self.assertFalse(any(method in {'POST', 'PUT'} for _, method, _ in self.base.kube.writes))
                self.base.kube.writes.clear()
                self.base.kube.data[path] = copy.deepcopy(original)
                kind = original['kind']
                if kind in {'RemoteMCPServer', 'Deployment', 'Service', 'NetworkPolicy'}:
                    self.base.kube.data[path]['spec']['unreviewed'] = True
                elif kind == 'Role':
                    self.base.kube.data[path]['rules'][0]['verbs'].append('list')
                elif kind == 'RoleBinding':
                    self.base.kube.data[path]['subjects'][0]['name'] = 'other'
                elif kind == 'ServiceAccount':
                    self.base.kube.data[path]['automountServiceAccountToken'] = False
                else:
                    self.base.kube.data[path]['data']['reviewed'] = 'changed'
                self.base.reconcile()
                self.assertEqual(self.base.reason(), 'MCPDependencyMismatch')
                self.assertFalse(any(method in {'POST', 'PUT'} for _, method, _ in self.base.kube.writes))
                self.base.kube.data[path] = original
                self.base.kube.writes.clear()

    def test_stale_discovery_or_unavailable_backend_blocks_wiring(self):
        server = self.base.kube.data[self.paths['server']]
        server['status']['discoveredTools'].append({'name': 'delete_resource'})
        self.base.reconcile()
        self.assertEqual(self.base.reason(), 'MCPDiscoveryNotCurrent')
        server['status']['discoveredTools'].pop()
        server['status']['conditions'][0]['observedGeneration'] = 0
        self.base.reconcile()
        self.assertEqual(self.base.reason(), 'MCPDiscoveryNotCurrent')
        server['status']['conditions'][0]['observedGeneration'] = 1
        self.base.kube.data[self.paths['backend']]['status']['observedGeneration'] = 0
        self.base.reconcile()
        self.assertEqual(self.base.reason(), 'MCPBackendNotCurrent')
        self.assertFalse(any(method in {'POST', 'PUT'} for _, method, _ in self.base.kube.writes))

    def test_legacy_children_remain_identical_when_the_second_profile_is_registered(self):
        document = copy.deepcopy(self.base.document)
        document['spec']['runtimeProfile'] = self.base.profile['runtimeProfile']
        legacy = {k: v for k, v in self.base.profile.items() if k != 'mcpProfile'}
        bindings = [{'projection': {'configMap': {'name': 'skill'}}, 'contentSha256': 'a' * 64},
                    {'projection': {'configMap': {'name': 'knowledge'}}, 'contentSha256': 'b' * 64}]
        intent = parse_intent(document, legacy)
        expected = desired_children(document, intent, bindings, legacy)
        self.assertEqual(expected, desired_children(document, intent, bindings, self.base.profile))

    def test_owner_cannot_select_an_unknown_profile_or_general_tool_grant(self):
        for field, value in [('runtimeProfile', 'unapproved'), ('toolGrantRefs', ['arbitrary-tools'])]:
            document = copy.deepcopy(self.base.document)
            document['spec'][field] = value
            with self.subTest(field=field), self.assertRaises(Rejected):
                parse_intent(document, self.base.profile)
        properties = crd(self.base.profile)['spec']['versions'][0]['schema']['openAPIV3Schema']['properties']['spec']['properties']
        self.assertEqual(properties['runtimeProfile']['enum'], ['lab-native-v1', 'lab-configmap-read-v1'])
        self.assertEqual(properties['toolGrantRefs']['maxItems'], 0)


    def test_portable_profile_compiler_requires_exact_hook_and_preserves_shared_enums(self):
        from pathlib import Path
        from ordinary_profile import compile_profile,preserve_crd_profiles
        base = {k: v for k, v in self.base.profile.items() if k != 'mcpProfile'}
        objects = {role: copy.deepcopy(self.base.kube.data[path]) for role,path in self.paths.items()}
        objects['telemetry']['data'] = {'sitecustomize.py': Path(__file__).with_name('sitecustomize.py').read_text()}
        objects['code']['data'] = {'fixed_mcp.py': Path(__file__).with_name('fixed_mcp.py').read_text()}
        objects['binding']['roleRef']['apiGroup'] = 'rbac.authorization.k8s.io'
        objects['binding']['subjects'][0]['namespace'] = 'skills-demo'
        result = compile_profile(base,objects,'skills-demo')
        self.assertEqual(result['runtimeProfile'],base['runtimeProfile'])
        self.assertEqual(result['mcpProfile']['runtimeProfile'],'work-configmap-read-v1')
        preserve_crd_profiles(crd(base),crd(result))
        with self.assertRaisesRegex(Rejected,'SharedCRDProfileEnumWouldShrink'):
            preserve_crd_profiles(crd(result),crd(base))
        objects['telemetry']['data']['sitecustomize.py'] = 'unreviewed'
        with self.assertRaisesRegex(Rejected,'UnreviewedTelemetryBootstrap'):
            compile_profile(base,objects,'skills-demo')


if __name__ == '__main__':
    unittest.main()
