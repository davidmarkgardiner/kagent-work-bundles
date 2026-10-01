import copy
import datetime as dt
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'guidance'))
from store import GuidanceStore

TARGET = dict(cluster='radar-lab', namespace='cert-manager', kind='Deployment', name='cert-manager')


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'guidance/catalog.lab.json').read_text())
        self.store = GuidanceStore(self.catalog, today=lambda: dt.date(2026, 10, 1))

    def test_exact_identity_and_missing_scope(self):
        self.assertEqual(self.store.find(**TARGET)['total'], 4)
        for field in ('cluster', 'namespace', 'name'):
            target = dict(TARGET, **{field: 'other'})
            self.assertEqual(self.store.find(**target)['status'], 'no_binding')
            self.assertEqual(self.store.read(**target, reference_id='cert-manager-http01')['status'], 'not_bound')

    def test_transient_pods_and_name_prefixes_are_not_workloads(self):
        for kind, name in [('Pod', 'cert-manager-abcd-12345'), ('ReplicaSet', 'cert-manager-abcd')]:
            with self.assertRaises(ValueError):
                self.store.find(**dict(TARGET, kind=kind, name=name))
        self.assertEqual(self.store.find(**dict(TARGET, name='cert-manager-webhook'))['status'], 'no_binding')

    def test_stale_guidance_is_not_returned_as_instructions(self):
        store = GuidanceStore(self.catalog, today=lambda: dt.date(2026, 11, 1))
        result = store.read(**TARGET, reference_id='cert-manager-http01')
        self.assertEqual(result['status'], 'review_required')
        self.assertNotIn('content', result)
        self.assertTrue(result['reference']['stale'])

    def test_future_review_is_not_current(self):
        store = GuidanceStore(self.catalog, today=lambda: dt.date(2026, 9, 30))
        self.assertEqual(store.read(**TARGET, reference_id='cert-manager-http01')['status'], 'review_required')

    def test_bounds_and_no_paging(self):
        result = self.store.find(**TARGET, limit=1)
        self.assertEqual(len(result['references']), 1)
        self.assertTrue(result['truncated'])
        for limit in (0, 6, True, 1.5):
            with self.assertRaises(ValueError):
                self.store.find(**TARGET, limit=limit)
        catalog = copy.deepcopy(self.catalog)
        catalog['documents'][0]['content'] = 'x' * 4097
        with self.assertRaises(ValueError):
            GuidanceStore(catalog)

    def test_unknown_ids_and_arbitrary_paths(self):
        for reference in ('../../etc/passwd', 'https://example.com', 'missing'):
            self.assertEqual(self.store.read(**TARGET, reference_id=reference)['status'], 'not_bound')

    def test_escaped_envelope_budget(self):
        catalog = copy.deepcopy(self.catalog)
        catalog['documents'][0]['content'] = '\\' * 4096
        store = GuidanceStore(catalog, today=lambda: dt.date(2026, 10, 1))
        result = store.read(**TARGET, reference_id='cert-manager-investigation')
        self.assertEqual(result['status'], 'budget_exceeded')
        self.assertNotIn('content', result)

    def test_missing_catalog_reference_fails_startup(self):
        self.catalog['bindings'][0]['references'].append('missing')
        with self.assertRaises(ValueError):
            GuidanceStore(self.catalog)

    def test_provenance_and_synthetic_history(self):
        result = self.store.read(**TARGET, reference_id='synthetic-incident-http01')
        self.assertEqual(result['status'], 'ok')
        self.assertIn('SYNTHETIC', result['content'])
        self.assertEqual(result['reference']['revision'], 'lab-snapshot-2026-10-01')


class GuidanceRenderTests(unittest.TestCase):
    def test_runtime_profiles_and_fixed_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            config = dict(radar_namespace='radar-trial', kagent_namespace='kagent',
                          model_config='existing-model', guidance_cluster='radar-lab',
                          guidance_image='example.com/guidance@sha256:' + '0' * 64)
            path = folder / 'config.json'
            path.write_text(json.dumps(config))
            for runtime in ('go', 'legacy'):
                subprocess.run([sys.executable, str(ROOT / 'guidance/render.py'),
                                '--config', str(path), '--catalog', str(ROOT / 'guidance/catalog.lab.json'),
                                '--out', str(folder / runtime), '--runtime', runtime], check=True,
                               capture_output=True)
                docs = list(yaml.safe_load_all((folder / runtime / 'guidance.yaml').read_text()))
                agent = next(d for d in docs if d['kind'] == 'Agent')
                self.assertEqual(agent['spec']['declarative'].get('runtime'), 'go' if runtime == 'go' else None)
                deployment = next(d for d in docs if d['kind'] == 'Deployment')
                self.assertFalse(deployment['spec']['template']['spec']['automountServiceAccountToken'])
                self.assertFalse(any(d['kind'] in {'Role', 'ClusterRole', 'RoleBinding', 'ClusterRoleBinding'} for d in docs))
            config['guidance_image'] = 'example.com/guidance:latest'
            path.write_text(json.dumps(config))
            rejected = subprocess.run([sys.executable, str(ROOT / 'guidance/render.py'),
                                       '--config', str(path), '--catalog', str(ROOT / 'guidance/catalog.lab.json'),
                                       '--out', str(folder / 'rejected')], capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)


if __name__ == '__main__':
    unittest.main()
