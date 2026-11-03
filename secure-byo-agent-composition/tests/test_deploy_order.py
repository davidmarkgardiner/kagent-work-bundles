import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('deployment_driver', ROOT / 'scripts/deploy.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class SubmissionOrdering(unittest.TestCase):
    def test_owner_requests_wait_for_composer_rollout(self):
        empty = {'apiVersion': 'v1', 'kind': 'List', 'items': []}
        resources = {key: empty for key in ('baseline', 'routes', 'hosted-crd', 'kro-rgd', 'policies')}
        resources.update({'hosted-platform': {'kind': 'List', 'items': [{'kind': 'Deployment'}]},
            'profiles': {namespace: {} for namespace in driver.NAMESPACES},
            'requests': {namespace: {} for namespace in driver.NAMESPACES}})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'input.json').write_text(json.dumps({}))
            argv = ['deploy.py', '--kubeconfig', 'explicit', '--context', 'bounded',
                '--snapshot', str(path / 'input.json'), '--settings', str(path / 'input.json'),
                '--output', str(path / 'output')]
            with patch.object(sys, 'argv', argv), patch.object(driver, 'render', return_value=resources), \
                    patch.object(driver.subprocess, 'run') as calls, contextlib.redirect_stdout(io.StringIO()):
                driver.main()
            commands = [call.args[0] for call in calls.call_args_list]
            rollout = next(i for i, command in enumerate(commands) if 'rollout' in command)
            owners = [i for i, command in enumerate(commands) if '--as' in command]
            self.assertEqual(len(owners), 2)
            self.assertTrue(all(index > rollout for index in owners))
