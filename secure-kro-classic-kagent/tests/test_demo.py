import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import demo


class DemoProofTests(unittest.TestCase):
    def receipt(self):
        return {'schemaVersion': 'classic-golden/v1', 'requestUID': 'current-owner',
                'passed': True, 'taskID': 'task', 'contextID': 'context'}

    def test_stale_success_is_not_current_instance_proof(self):
        owner = {'metadata': {'uid': 'current-owner'}}
        job = {'metadata': {'labels': {'kro.run/instance-id': 'current-owner'}}, 'status': {'succeeded': 1}}
        demo.validate_receipt(owner, job, self.receipt())
        stale = self.receipt()
        stale['requestUID'] = 'previous-owner'
        with self.assertRaisesRegex(ValueError, 'does not prove this instance'):
            demo.validate_receipt(owner, job, stale)
        job['metadata']['labels']['kro.run/instance-id'] = 'previous-owner'
        with self.assertRaises(ValueError):
            demo.validate_receipt(owner, job, self.receipt())

    def test_existing_instance_is_never_reapplied_as_a_fresh_demo(self):
        args = SimpleNamespace(kubectl='kubectl', context='test', file=demo.ROOT / 'examples/agent-demo.yaml')
        runner = demo.Demo(args)
        runner.run = Mock(return_value=SimpleNamespace(stdout=json.dumps({
            'apiVersion': 'demo.kagent.dev/v1alpha1', 'kind': 'ClassicSecureAgent',
            'metadata': {'name': 'demo', 'namespace': 'classic-agents'}})))
        runner.get = Mock(return_value={'metadata': {'uid': 'already-exists'}})
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'already exists'):
            runner.apply()
        self.assertEqual(runner.run.call_count, 1)
        self.assertIn('--dry-run=server', runner.run.call_args.args)

    def test_applied_bytes_equal_displayed_snapshot_even_if_the_file_changes(self):
        original = (demo.ROOT / 'examples/agent-demo.yaml').read_text()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'owner.yaml'
            path.write_text(original)
            runner = demo.Demo(SimpleNamespace(kubectl='kubectl', context='test', file=path))
            calls = []
            def run(*command, **options):
                calls.append((command, options))
                path.write_text('changed-after-read')
                return SimpleNamespace(stdout=json.dumps({'apiVersion': 'demo.kagent.dev/v1alpha1',
                    'kind': 'ClassicSecureAgent', 'metadata': {'name': 'demo', 'namespace': 'classic-agents'}}))
            runner.run = run
            runner.get = Mock(return_value=None)
            with contextlib.redirect_stdout(io.StringIO()):
                runner.apply()
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][1]['input_text'], original)
            self.assertEqual(calls[1][1]['input_text'], original)
            self.assertNotIn('--dry-run=server', calls[1][0])

    def test_unfilled_customer_template_never_reaches_kubectl(self):
        runner = demo.Demo(SimpleNamespace(kubectl='kubectl', context='test',
                                        file=demo.ROOT / 'examples/agent-template.yaml'))
        runner.run = Mock()
        with self.assertRaisesRegex(ValueError, 'Fill the customer template'):
            runner.apply()
        runner.run.assert_not_called()
