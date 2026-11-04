import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import compose
import gateway_baseline
import preflight
from types import SimpleNamespace
spec = importlib.util.spec_from_file_location('classic_golden', ROOT / 'runtime/golden.py')
golden = importlib.util.module_from_spec(spec)
spec.loader.exec_module(golden)


class ClassicTests(unittest.TestCase):
    def profile(self):
        return json.loads((ROOT / 'examples/platform-profile.json').read_text())

    def test_native_runtime_is_a_classic_agent_without_substrate_objects(self):
        graph, owner = compose.compose(self.profile())
        kinds = [node['template']['kind'] for node in graph['spec']['resources']]
        self.assertNotIn('AgentTemplate', kinds)
        self.assertNotIn('Harness', kinds)
        agent = next(node['template'] for node in graph['spec']['resources'] if node['id'] == 'agent')
        self.assertEqual(agent['apiVersion'], 'kagent.dev/v1alpha2')
        self.assertEqual(agent['spec']['declarative']['modelConfig'], '${schema.spec.modelConfig}')
        self.assertEqual(agent['spec']['declarative']['systemMessage'], '${schema.spec.systemPrompt}')
        self.assertNotIn('skills', agent['spec'])
        caller = next(node for node in graph['spec']['resources'] if node['id'] == 'callerRoute')
        self.assertEqual(caller['template']['metadata']['annotations']['classic.kagent.dev/verified-job'], '${golden.metadata.name}')
        self.assertNotIn('includeWhen', caller)

    def test_empty_mcp_operation_list_is_not_accepted(self):
        profile = self.profile()
        profile['tools']['unsafe'] = {'type': 'McpServer', 'mcpServer': {'apiGroup': 'kagent.dev', 'kind': 'RemoteMCPServer', 'name': 'mcp', 'toolNames': []}}
        with self.assertRaises(ValueError):
            compose.compose(profile)

    def test_verifier_ingress_is_denied_without_an_empty_list_update_loop(self):
        graph, _ = compose.compose(self.profile())
        policy = next(n['template']['spec'] for n in graph['spec']['resources'] if n['id'] == 'verifierNetwork')
        self.assertIn('Ingress', policy['policyTypes'])
        self.assertNotIn('ingress', policy)
        self.assertEqual({port['port'] for port in policy['egress'][1]['ports']}, {8080, 8081})

    def test_gateway_listeners_have_distinct_exact_identities(self):
        items = gateway_baseline.resources(self.profile())['items']
        policies = [o for o in items if o['kind'] == 'AgentgatewayPolicy']
        self.assertEqual(len(policies), 2)
        subjects = [o['spec']['traffic']['authorization']['policy']['matchExpressions'][0] for o in policies]
        self.assertIn('demo-verifier', subjects[0])
        self.assertIn('demo-caller', subjects[1])
        self.assertNotEqual(policies[0]['spec']['targetRefs'][0]['sectionName'], policies[1]['spec']['targetRefs'][0]['sectionName'])

    def test_pong_must_be_native_completed_assistant_output(self):
        result = {'result': {'id': 'task', 'contextId': 'session', 'status': {'state': 'completed'},
                             'artifacts': [{'parts': [{'kind': 'text', 'text': 'PONG'}]}]}}
        self.assertEqual(golden.completed_task(result)['id'], 'task')
        echoed = copy.deepcopy(result)
        echoed['result']['artifacts'] = []
        echoed['result']['history'] = [{'role': 'user', 'parts': [{'kind': 'text', 'text': 'PONG'}]}]
        with self.assertRaisesRegex(ValueError, 'AssistantPongMissing'):
            golden.completed_task(echoed)
        result['result']['status']['state'] = 'failed'
        with self.assertRaisesRegex(ValueError, 'NativeTaskNotCompleted'):
            golden.completed_task(result)

    def test_oci_skills_remain_native_digest_references(self):
        profile = self.profile()
        profile['skills'] = {'kb': {'mode': 'oci', 'ref': 'registry.example.com/kb@sha256:' + 'a' * 64}}
        graph, owner = compose.compose(profile)
        agent = next(n['template'] for n in graph['spec']['resources'] if n['id'] == 'agent')
        self.assertIn('refs', agent['spec']['skills'])
        self.assertEqual(owner['spec']['skills'], ['kb'])
        self.assertIn('minItems=1', graph['spec']['schema']['spec']['skills'])


class ParityTests(unittest.TestCase):
    def setup_case(self):
        lock = json.loads((ROOT / 'versions.lock.json').read_text())
        version = {'name': 'v1alpha2', 'served': True, 'schema': {'openAPIV3Schema': {'type': 'object'}}}
        lock['crdSchemas'] = {'agents.kagent.dev': preflight.schema_hash(version)}
        controller = {'metadata': {'generation': 2}, 'spec': {'replicas': 1, 'template': {'spec': {'containers': [{
            'name': 'controller', 'image': lock['images']['controller']['reference'],
            'env': [{'name': key, 'value': value} for key, value in {
                'IMAGE_TAG': '0.10.4', 'IMAGE_REGISTRY': 'ghcr.io', 'IMAGE_REPOSITORY': 'kagent-dev/kagent/app',
                'GO_IMAGE_TAG': '0.10.4', 'GO_IMAGE_REGISTRY': 'ghcr.io', 'GO_IMAGE_REPOSITORY': 'kagent-dev/kagent/golang-adk',
                'SKILLS_INIT_IMAGE_TAG': '0.10.4', 'SKILLS_INIT_IMAGE_REGISTRY': 'ghcr.io', 'SKILLS_INIT_IMAGE_REPOSITORY': 'kagent-dev/kagent/skills-init',
            }.items()]}]}}}, 'status': {'observedGeneration': 2, 'replicas': 1, 'updatedReplicas': 1, 'availableReplicas': 1}}
        args = SimpleNamespace(kagent_deployment='controller', kagent_namespace='kagent', kro_deployment='kro', kro_namespace='kro')
        def get(*command):
            if command[0] == 'crd':
                return {'spec': {'versions': [version]}}
            if command[1] == 'controller':
                return controller
            return {'spec': {'template': {'spec': {'containers': [{'image': lock['images']['kro']['tag']}]}}}}
        return lock, version, controller, args, get

    def test_matching_parity_is_accepted(self):
        lock, _, _, args, get = self.setup_case()
        self.assertEqual(preflight.check(get, args, lock)['result'], 'NonSubstrateParityEstablished')

    def test_old_controller_is_rejected_even_with_the_same_api(self):
        lock, _, controller, args, get = self.setup_case()
        controller['spec']['template']['spec']['containers'][0]['image'] = 'ghcr.io/kagent-dev/kagent/controller:0.8.0-beta4'
        with self.assertRaisesRegex(ValueError, 'pinned kagent 0.10.4'):
            preflight.check(get, args, lock)

    def test_incomplete_rollout_is_not_parity(self):
        lock, _, controller, args, get = self.setup_case()
        controller['status']['replicas'] = 2
        with self.assertRaisesRegex(ValueError, 'rollout is not complete'):
            preflight.check(get, args, lock)

    def test_matching_api_name_with_different_schema_is_rejected(self):
        lock, version, _, args, get = self.setup_case()
        version['schema']['openAPIV3Schema']['description'] = 'different schema'
        with self.assertRaisesRegex(ValueError, 'CRD schema differs'):
            preflight.check(get, args, lock)

    def test_mirror_requires_the_pinned_digest(self):
        expected = json.loads((ROOT / 'versions.lock.json').read_text())['images']['controller']
        self.assertTrue(preflight.image_matches('mirror.example.com/controller@' + expected['digest'], expected))
        self.assertFalse(preflight.image_matches('mirror.example.com/controller:0.10.4', expected))
