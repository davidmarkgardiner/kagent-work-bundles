import json
import time
import unittest

import fixtures as f
from fixtures import agent, auth, common, facade


class VerificationTests(unittest.TestCase):
    def world(self, **kwargs):
        world = f.World(**kwargs)
        self.addCleanup(world.close)
        names = world.create()
        return world, names

    def test_golden_activates_with_one_mcp_call_and_independent_negative_identity(self):
        world, names = self.world()
        allowed = world.kube.tokens[world.verifier_token]
        wrong_audience = world.kube.tokens[world.verifier_negative_audience_token]
        self.assertEqual((wrong_audience['username'], wrong_audience['uid']),
                         (allowed['username'], allowed['uid']))
        self.assertEqual(wrong_audience['audiences'], [auth.NEGATIVE_AUDIENCE])
        code, receipt = world.verifier().run(names.agent)
        self.assertEqual((code, receipt['result'], receipt['state']), (0, 'Passed', 'Active'), receipt)
        self.assertEqual(receipt['golden']['mcpCalls'], 1)
        self.assertEqual(receipt['probes']['wrongAudience'], 401)
        self.assertEqual(receipt['probes']['wrongSubject'], 403)
        self.assertEqual(world.approval()['data']['state'], 'Active')
        requests = [path for method, path in world.kube.calls if method == 'POST' and path.endswith('/token')]
        self.assertEqual(requests, ['/api/v1/namespaces/%s/serviceaccounts/standalone-negative/token' % f.NS])
        negatives = [v for k, v in world.kube.tokens.items() if k.startswith('negative-token-')]
        self.assertEqual(len(negatives), 1)
        self.assertEqual(negatives[0]['audiences'], [auth.GATEWAY_AUDIENCE])

    def test_disabled_gateway_audience_enforcement_fails_even_when_facade_denies(self):
        world, names = self.world(enforce_audience=False)
        code, receipt = world.verifier().run(names.agent)
        self.assertEqual((code, receipt['result'], receipt['reason'], receipt['state']),
                         (1, 'Failed', 'ForbiddenFacadeActivity', 'Failed'), receipt)
        self.assertEqual(receipt['probes']['wrongAudience'], 401)
        self.assertEqual(world.approval()['data']['state'], 'Failed')
        self.assertEqual(world.model.requests, [])

    def test_missing_negative_projected_token_fails_without_activation(self):
        world, names = self.world()
        world.token_files['verifier-negative-audience'].unlink()
        code, receipt = world.verifier().run(names.agent)
        self.assertEqual((code, receipt['reason'], receipt['state']),
                         (1, 'VerifierCredentialUnavailable', 'Failed'), receipt)
        self.assertEqual(world.approval()['data']['state'], 'Failed')
        self.assertEqual(world.model.requests, [])

    def test_missing_or_duplicate_mcp_calls_fail_without_activation(self):
        for mode, reason in (('omit-mcp', 'McpCallRequired'), ('duplicate-mcp', 'McpCallLimitExceeded')):
            with self.subTest(mode=mode):
                world, names = self.world(model_mode=mode)
                code, receipt = world.verifier().run(names.agent)
                self.assertEqual((code, receipt['result'], receipt['reason'], receipt['state']),
                                 (1, 'Failed', 'GoldenInvokeRejected', 'Failed'), receipt)
                self.assertEqual(receipt['probes']['goldenRuntimeReason'], reason)
                self.assertEqual(world.approval()['data']['state'], 'Failed')
                self.assertLessEqual(len(world.model.requests), 2)

    def test_golden_rejects_two_matching_mcp_witnesses(self):
        world, names = self.world()
        verifier = world.verifier()

        def duplicate_witness(method, url, headers, body=None, **kwargs):
            status, raw = world.gateway(method, url, headers, body, **kwargs)
            if status != 200:
                return status, raw
            value = json.loads(raw)
            if url.endswith('/invoke') and 'receipt' in value:
                value['receipt']['mcpCalls'] = 2
                value['receipt']['mcpProofSha256'] *= 2
                value['facade']['mcpDispatches'] = 2
            if url.endswith('/witness') and 'run' in value:
                value['run']['mcpDispatches'] *= 2
                value['counters']['mcpDispatches'] += 1
                value['counters']['received'] += 1
            return status, common.encoded(value)

        verifier.transport = duplicate_witness
        code, receipt = verifier.run(names.agent)
        self.assertEqual((code, receipt['reason'], receipt['state']),
                         (1, 'McpProofNotWitnessed', 'Failed'), receipt)
        self.assertEqual(world.approval()['data']['state'], 'Failed')

    def test_facade_budget_prevents_second_mcp_dispatch(self):
        world, names = self.world()
        code, receipt = world.verifier().run(names.agent)
        self.assertEqual(code, 0, receipt)
        snap = world.authority.authorize(names.agent, 'invoke', 'Bearer ' + world.caller_token)
        handle, entry = world.facade.mint(snap, time.monotonic() + 30)
        self.addCleanup(world.facade.finish, handle, entry)
        body = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                'params': {'name': 'get_demo_status', 'arguments': {}}}
        headers = {facade.HANDLE_HEADER: handle}
        first = world.call(names.agent, 'mcp', body, world.worker_token, headers)
        second = world.call(names.agent, 'mcp', dict(body, id=2), world.worker_token, headers)
        self.assertEqual(first[0], 200, first)
        self.assertEqual(second, (429, {'error': 'ExecutionBudgetExceeded'}))
        status, witness = world.call(names.agent, 'witness', {'runId': entry['runId']}, world.verifier_token)
        self.assertEqual(status, 200, witness)
        self.assertEqual(len(witness['run']['mcpDispatches']), 1)


class UnicodeTransportTests(unittest.TestCase):
    def setUp(self):
        self.world = f.World()
        self.addCleanup(self.world.close)
        self.names = self.world.create()
        code, receipt = self.world.verifier().run(self.names.agent)
        self.assertEqual(code, 0, receipt)

    def test_valid_bmp_and_supplementary_prompts_cross_internal_envelope(self):
        for prompt in ('\u2615' * 3000, '\u0800' * 4000, '\U0001f642' * 4000):
            with self.subTest(character=prompt[0], count=len(prompt)):
                public = json.dumps({'prompt': prompt}, ensure_ascii=False).encode()
                internal = common.encoded({'prompt': prompt, 'runId': 'a' * 32})
                self.assertLessEqual(len(public), facade.BODY_LIMITS['invoke'])
                self.assertGreater(len(internal), facade.BODY_LIMITS['invoke'])
                self.assertLessEqual(len(internal), agent.INTERNAL_INVOKE_BYTES)
                status, payload = self.world.call(self.names.agent, 'invoke', {'prompt': prompt}, self.world.caller_token)
                self.assertEqual(status, 200, payload)
                self.assertEqual((payload['receipt']['result'], payload['receipt']['mcpCalls']), ('Passed', 1))

    def test_public_body_limit_remains_16_kib(self):
        public = json.dumps({'prompt': '\u2615' * 3000}).encode()
        self.assertGreater(len(public), 16 * 1024)
        calls_before = len(self.world.model.requests)
        with self.assertRaises(common.Denied) as caught:
            self.world.facade.handle('POST', '/agents/%s/invoke' % self.names.agent,
                                    [('Authorization', 'Bearer ' + self.world.caller_token)], public)
        self.assertEqual((caught.exception.status, caught.exception.reason), (413, 'BodyTooLarge'))
        self.assertEqual(len(self.world.model.requests), calls_before)


if __name__ == '__main__':
    unittest.main()
