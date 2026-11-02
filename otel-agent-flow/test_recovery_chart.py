"""Deployment authority stays with the existing observer and agent services."""
from pathlib import Path
import subprocess
import unittest

import yaml


CHART = Path(__file__).resolve().parent / 'deploy/chart'


class RecoveryChartTests(unittest.TestCase):
    def render(self, *settings):
        return subprocess.run(['helm', 'template', 'recovery-test', str(CHART), *settings],
                              text=True, capture_output=True)

    def test_enabled_viewer_mounts_only_existing_read_only_evidence(self):
        result = self.render('--set', 'recovery.enabled=true', '--set', 'recovery.profileConfigMap=reviewed-profile',
                             '--set', 'recovery.snapshotClaim=observer-state')
        self.assertEqual(result.returncode, 0, result.stderr)
        resources = [d for d in yaml.safe_load_all(result.stdout) if d]
        dashboard = next(d for d in resources if d['kind'] == 'Deployment' and d['metadata']['name'] == 'flow-dashboard')
        pod = dashboard['spec']['template']['spec']
        container = pod['containers'][0]
        env = {e['name']: e.get('value') for e in container['env']}
        self.assertEqual(env['READ_ONLY_VIEWER'], 'true')
        self.assertEqual(env['RECOVERY_PROFILE'], '/recovery-profile/profile.json')
        self.assertEqual(env['RECOVERY_SNAPSHOT'], '/recovery-observer/recovery.json')
        self.assertFalse(pod['automountServiceAccountToken'])
        self.assertEqual(len(container['volumeMounts']), 2)
        self.assertTrue(all(m['readOnly'] for m in container['volumeMounts']))
        volumes = {v['name']: v for v in pod['volumes']}
        self.assertEqual(volumes['recovery-profile']['configMap']['name'], 'reviewed-profile')
        self.assertEqual(volumes['recovery-observer']['persistentVolumeClaim'], {'claimName': 'observer-state', 'readOnly': True})
        self.assertFalse(any(d['kind'] == 'PersistentVolumeClaim' for d in resources))
        self.assertFalse(any(e.get('valueFrom') for e in container['env']))

    def test_enabled_requires_both_existing_evidence_sources(self):
        for settings in ([], ['--set', 'recovery.profileConfigMap=profile'], ['--set', 'recovery.snapshotClaim=state']):
            with self.subTest(settings=settings):
                result = self.render('--set', 'recovery.enabled=true', *settings)
                self.assertNotEqual(result.returncode, 0)

    def test_disabled_preserves_original_dashboard(self):
        result = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        resources = [d for d in yaml.safe_load_all(result.stdout) if d]
        dashboard = next(d for d in resources if d['kind'] == 'Deployment' and d['metadata']['name'] == 'flow-dashboard')
        pod = dashboard['spec']['template']['spec']
        self.assertNotIn('volumes', pod)
        self.assertNotIn('volumeMounts', pod['containers'][0])
        self.assertFalse(any(e['name'].startswith('RECOVERY_') for e in pod['containers'][0]['env']))
