from contextlib import redirect_stdout
import io
import json
import unittest
from unittest.mock import Mock, patch

import test_live_demo
import terminal_demo


class TerminalTests(unittest.TestCase):
    def run_command(self, backend, line):
        with redirect_stdout(io.StringIO()) as out:
            terminal_demo.execute(backend, line)
        return out.getvalue()

    def test_ask_preserves_apostrophe_and_uses_the_shared_contextual_chat(self):
        b=Mock();b.chat.return_value=dict(text='answer',taskID='t',contextID='c',responseSha256='digest')
        out=self.run_command(b,"ask What's your security boundary?")
        b.chat.assert_called_once_with(dict(prompt="What's your security boundary?",namespaceCounts=False))
        self.assertIn('answer',out)
        self.assertIn('taskID',out)

    def test_delete_passes_connected_uid_and_typed_name_to_shared_guard(self):
        b=Mock();b.uid='current-uid';b.args.in_cluster=True
        b.inspect.return_value=dict(deletion=dict(complete=True,remaining=[],capturedCount=20))
        out=self.run_command(b,'delete demo')
        b.delete.assert_called_once_with(dict(uid='current-uid',confirmName='demo'))
        self.assertIn('Secret cleanup',out)

    def test_unguarded_delete_cannot_start_cleanup(self):
        b=test_live_demo.backend()
        with patch.object(b,'cleanup_orphans_once') as cleanup:
            with self.assertRaises(terminal_demo.DemoError):self.run_command(b,'delete demo')
            cleanup.assert_not_called()

    def test_default_deploy_uses_small_frontend_contract(self):
        b=Mock();b.create.return_value=dict(uid='new')
        self.run_command(b,'deploy')
        payload=b.create.call_args.args[0]
        self.assertEqual(set(payload),{'modelConfig','systemPrompt','tools','skills'})
        self.assertEqual(payload['tools'],[])

    def test_counts_uses_platform_observation_and_challenge_never_calls_chat(self):
        b=Mock();b.chat.return_value=dict(text='counts',taskID='t',contextID='c',responseSha256='d')
        self.run_command(b,'counts')
        self.assertTrue(b.chat.call_args.args[0]['namespaceCounts'])
        b.reset_mock();b.challenge.return_value=dict(passed=True,http=401)
        self.run_command(b,'challenge missing-jwt')
        b.challenge.assert_called_once_with({'case':'missing-jwt'})
        b.chat.assert_not_called()
