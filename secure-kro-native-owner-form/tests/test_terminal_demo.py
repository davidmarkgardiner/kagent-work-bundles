import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('terminal_demo', Path(__file__).resolve().parents[1] / 'demo/terminal_demo.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class TerminalDemoTests(unittest.TestCase):
    def test_user_echo_does_not_prove_pong(self):
        result = {'task': {'id': 'task', 'contextId': 'session', 'status': {'state': 'TASK_STATE_COMPLETED'},
                           'history': [{'role': 'ROLE_USER', 'parts': [{'text': 'PONG'}]}]}}
        with self.assertRaisesRegex(ValueError, 'no assistant output'):
            demo.task_output(result)

    def test_existing_instance_is_not_reapplied_as_a_fresh_demo(self):
        with patch.object(demo, 'current', return_value={'metadata': {'uid': 'existing'}}), patch.object(demo, 'kubectl') as kubectl:
            with self.assertRaisesRegex(ValueError, 'already exists'):
                demo.deployment(SimpleNamespace(command='deploy'))
            kubectl.assert_not_called()

    def test_query_evidence_cannot_overwrite_an_earlier_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            demo.write_json(root, 'result.json', {'passed': True})
            self.assertEqual((root / 'result.json').stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                demo.write_json(root, 'result.json', {'passed': False})

    def task(self, response=True, error=False):
        parts = [{'metadata': {'kagent.dev/a2a/part-type': 'function_call'}, 'data': {'name': 'approved_get_namespace_count', 'id': 'call'}}]
        if response:
            parts.append({'metadata': {'kagent.dev/a2a/part-type': 'function_response'}, 'data': {'name': 'approved_get_namespace_count', 'id': 'call',
                'response': {'isError': True} if error else {'output': {'namespace_count': 3}}}})
        return {'history': [{'role': 'ROLE_AGENT', 'parts': parts}]}

    def test_requested_tool_requires_a_paired_returned_result(self):
        self.assertEqual(demo.tool_evidence(self.task(), ['get_namespace_count']), ['get_namespace_count'])
        with self.assertRaisesRegex(ValueError, 'Missing paired'):
            demo.tool_evidence(self.task(response=False), ['get_namespace_count'])
        with self.assertRaisesRegex(ValueError, 'returned an error'):
            demo.tool_evidence(self.task(error=True), ['get_namespace_count'])

    def test_user_supplied_tool_data_does_not_prove_a_tool_call(self):
        task = self.task()
        task['history'][0]['role'] = 'ROLE_USER'
        with self.assertRaisesRegex(ValueError, 'Missing paired'):
            demo.tool_evidence(task, ['get_namespace_count'])
