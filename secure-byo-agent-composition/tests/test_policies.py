import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('secure_byo_policies', ROOT / 'policies' / 'generate.py')
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class PolicyContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'policies' / 'config.example.json').read_text())

    def test_rejects_wildcard_or_existing_platform_scope(self):
        for names in (['*'], ['secure-byo-*'], ['kagent'], ['kube-system'], [], ['secure-byo-a', 'secure-byo-a']):
            config = copy.deepcopy(self.config)
            config['namespaces'] = names
            with self.subTest(names=names), self.assertRaises(ValueError):
                generator.build(config)

    def test_rejects_wildcard_writer_identity(self):
        for field in ('composerUsers', 'nativeControllerUsers', 'platformUsers'):
            config = copy.deepcopy(self.config)
            config[field] = ['system:serviceaccount:*:*']
            with self.subTest(field=field), self.assertRaises(ValueError):
                generator.build(config)

    def test_rejects_mutable_approved_images(self):
        for field in ('contentImages', 'workloadImages'):
            config = copy.deepcopy(self.config)
            config[field] = ['registry.example.invalid/runtime:latest']
            with self.subTest(field=field), self.assertRaises(ValueError):
                generator.build(config)

    def test_native_remote_mcp_and_all_security_objects_are_owned(self):
        policies = generator.build(self.config)
        owner = next(p for p in policies if p['metadata']['name'] == 'secure-byo-protected-ownership')
        resources = next(r for r in owner['spec']['rules'] if r['name'] == 'platform-owned-scaffolding')['match']['any'][0]['resources']
        self.assertIn('api.kagent.dev/v1alpha3/RemoteMCPServer', resources['kinds'])
        self.assertIn('DELETE', resources['operations'])
        self.assertIn('UPDATE', resources['operations'])
        self.assertIn('CREATE', resources['operations'])
        for policy in policies:
            self.assertEqual(policy['apiVersion'], 'kyverno.io/v1')
            self.assertEqual(policy['spec']['failurePolicy'], 'Fail')
            for rule in policy['spec']['rules']:
                self.assertEqual(rule['validate']['failureAction'], 'Enforce')
                self.assertFalse(rule['validate']['allowExistingViolations'])
                if rule['name'].startswith('request-namespace-'):
                    self.assertNotIn('namespaces', rule['match']['any'][0]['resources'])
                else:
                    self.assertEqual(rule['match']['any'][0]['resources']['namespaces'], self.config['namespaces'])
                self.assertNotIn('exclude', rule)

    def test_controller_identity_does_not_exempt_binding_checks(self):
        policies = generator.build(self.config)
        binding = policies[0]
        for rule in binding['spec']['rules']:
            self.assertNotIn('exclude', rule)
            for condition in rule['validate']['cel']['expressions']:
                self.assertNotIn('request.userInfo', condition['expression'])

    def worker_config(self):
        config = copy.deepcopy(self.config)
        config['workerException'] = {
            'serviceAccount': 'approved-worker',
            'images': ['registry.example.invalid/worker@sha256:' + 'c' * 64],
            'deploymentName': 'approved-worker',
            'controllerUsers': ['system:serviceaccount:ate-system:ate-controller', 'system:kube-controller-manager'],
            'namespaces': ['secure-byo-hosted', 'secure-byo-kro']}
        return config

    def test_worker_exception_rejects_broad_or_unpinned_inputs(self):
        for field, value in [('namespaces', ['kagent']), ('images', ['worker:latest']),
                             ('controllerUsers', ['*']), ('deploymentName', '*'), ('serviceAccount', '*')]:
            config = self.worker_config()
            config['workerException'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                generator.build(config)

    def test_worker_exception_is_identity_image_lineage_and_namespace_bound(self):
        config = self.worker_config()
        policies = generator.build(config)
        workload = policies[2]
        expressions = workload['spec']['rules'][0]['validate']['cel']['expressions']
        host_check = expressions[0]['expression']
        for required in ('request.userInfo.username', 'serviceAccountName', 'ownerReferences',
                         'object.metadata.namespace', 'object.metadata.name.startsWith',
                         config['workerException']['images'][0], 'size(object.spec.ephemeralContainers) == 0'):
            self.assertIn(required, host_check)
        self.assertNotIn('workerException', json.dumps(policies[0]))
        self.assertNotIn('approved-worker', json.dumps(policies[1]))
        cron = workload['spec']['rules'][2]
        self.assertNotIn('approved-worker', json.dumps(cron))
        self.assertTrue(all('exclude' not in r for r in workload['spec']['rules']))

    def test_covers_ephemeral_containers_and_controller_templates(self):
        workload = generator.build(self.config)[2]
        encoded = json.dumps(workload)
        self.assertIn('v1/Pod/ephemeralcontainers', encoded)
        self.assertIn('batch/v1/CronJob', encoded)
        self.assertIn('apps/v1/Deployment', encoded)


if __name__ == '__main__':
    unittest.main()
