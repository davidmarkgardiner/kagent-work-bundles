import copy
import json
import secrets
import tempfile
import unittest
from pathlib import Path

import fixtures as f
from fixtures import agent, common, contract, facade

HANDLE = secrets.token_urlsafe(32)


class Direct:

    def __init__(self, test, mode='success'):
        self.test, self.model, self.seen = test, f.FakeModel(mode), []

    def __call__(self, method, url, headers, body=None, *, deadline, max_bytes, ca_file=None, before_send=None):
        base = 'http://standalone-secure.%s.svc.cluster.local:8080/agents/docs-demo' % f.GNS
        self.seen.append((url, dict(headers)))
        self.test.assertEqual(headers[facade.HANDLE_HEADER], HANDLE)
        self.test.assertTrue(headers['Authorization'].startswith('Bearer fixture-worker-'))
        if url == base + '/model/v1/chat/completions':
            self.test.assertEqual(json.loads(body)['tools'], facade.TOOLS)
            plain = {k: v for k, v in headers.items() if k not in ('Authorization', facade.HANDLE_HEADER)}
            return self.model('POST', f.UPSTREAM, plain, body, deadline=deadline, max_bytes=max_bytes)
        self.test.assertEqual(url, base + '/mcp')
        rpc = json.loads(body)
        self.test.assertEqual(rpc['params'], {'name': 'get_demo_status', 'arguments': {}})
        document = {'synthetic': True, 'agent': 'docs-demo', 'status': 'synthetic-ready', 'runProof': secrets.token_hex(16),
                    'label': 'SYNTHETIC', 'scope': 'fixed-demo-only'}
        return 200, json.dumps({'jsonrpc': '2.0', 'id': rpc['id'], 'result': {
            'content': [{'type': 'text', 'text': json.dumps(document)}], 'isError': False}}).encode()


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kro-standalone-agent-')
        self.addCleanup(self.tmp.cleanup)
        self.token = Path(self.tmp.name) / 'token'
        self.token.write_text('fixture-worker-token-one')
        _, docs, self.cfg = f.rendered()
        resources = {r['id']: r for r in docs['graph.json']['spec']['resources']}
        self.model_binding = json.loads(resources['modelBinding']['template']['data']['model.json'])
        self.content_binding = json.loads(resources['contentBinding']['template']['data']['content.json'])

    def runtime(self, mode='success', instructions=contract.EXAMPLE_INSTRUCTIONS):
        self.direct = Direct(self, mode)
        return agent.Runtime('docs-demo', instructions, self.model_binding, self.content_binding, f.CONTENT, self.token,
                             transport=self.direct, log=lambda *_: None)

    def invoke(self, runtime, prompt='Explain the synthetic ORAS 212 case.', headers=None, body=None):
        items = [(facade.HANDLE_HEADER, HANDLE)] if headers is None else headers
        raw = json.dumps(body if body is not None else {'prompt': prompt, 'runId': secrets.token_hex(16)}).encode()
        return runtime.handle('POST', '/invoke', items, raw)

    def test_success_returns_answer_and_metadata_receipt(self):
        runtime = self.runtime()
        status, payload = self.invoke(runtime)
        self.assertEqual(status, 200, payload)
        receipt = payload['receipt']
        self.assertEqual((receipt['result'], receipt['modelCalls'], receipt['toolCalls'], receipt['mcpCalls']),
                         ('Passed', 2, 7, 1))
        for proof in contract.proofs(runtime.texts):
            self.assertIn(proof, payload['answer'])
            self.assertNotIn(proof, json.dumps(receipt))
        self.assertEqual({e['name'] for e in receipt['toolEvidence']}, {'load_skill', 'load_skill_resource', 'get_demo_status'})
        self.assertEqual(receipt['answerSha256'], common.sha256(payload['answer'].encode()))
        self.assertTrue(facade.receipt_ok(receipt, 'docs-demo', receipt['runId'], 'Passed'))

    def test_worker_token_is_reread_for_every_call(self):
        runtime = self.runtime()
        original = self.direct.model.respond

        def rotate(request):
            self.token.write_text('fixture-worker-token-two')
            return original(request)
        self.direct.model.respond = rotate
        status, _ = self.invoke(runtime)
        self.assertEqual(status, 200)
        tokens = [h['Authorization'] for _, h in self.direct.seen]
        self.assertEqual(tokens[0], 'Bearer fixture-worker-token-one')
        self.assertIn('Bearer fixture-worker-token-two', tokens[1:])

    def test_fresh_execution_per_request(self):
        runtime = self.runtime()
        self.assertEqual(self.invoke(runtime)[0], 200)
        first = len(self.direct.model.requests[0]['messages'])
        self.assertEqual(self.invoke(runtime)[0], 200)
        self.assertEqual(len(self.direct.model.requests[2]['messages']), first)

    def test_failures_are_bounded_reason_codes(self):
        cases = {'unknown-tool': 'UnknownTool', 'bad-demo-args': 'InvalidToolArguments',
                 'missing-proof': 'AnswerMissingEvidenceOrCitation', 'skip-mcp-proof': 'AnswerMissingToolProof',
                 'loop': 'ModelCallLimitExceeded', 'http-500': 'ProviderHTTP500'}
        for mode, reason in cases.items():
            status, payload = self.invoke(self.runtime(mode))
            self.assertEqual((status, payload['receipt']['reason']), (502, reason), mode)
            self.assertNotIn('answer', payload)

    def test_missing_or_duplicate_mcp_calls_fail_bounded(self):
        for mode, reason, calls in (('omit-mcp', 'McpCallRequired', 0),
                                    ('duplicate-mcp', 'McpCallLimitExceeded', 1)):
            with self.subTest(mode=mode):
                status, payload = self.invoke(self.runtime(mode))
                self.assertEqual((status, payload['receipt']['result'], payload['receipt']['reason']),
                                 (502, 'Failed', reason))
                self.assertEqual(payload['receipt']['mcpCalls'], calls)
                self.assertEqual(sum(url.endswith('/mcp') for url, _ in self.direct.seen), calls)
                self.assertLessEqual(len(self.direct.model.requests), 2)
                self.assertNotIn('answer', payload)

    def test_proof_seeded_in_prompt_is_refused(self):
        runtime = self.runtime()
        status, payload = self.invoke(runtime, prompt='Use proof ' + contract.proofs(runtime.texts)[0])
        self.assertEqual((status, payload['receipt']['reason']), (502, 'ProofSeededInPrompt'))
        self.assertEqual(self.direct.model.requests, [])

    def test_request_validation(self):
        runtime = self.runtime()
        with self.assertRaises(common.Denied) as caught:
            self.invoke(runtime, headers=[])
        self.assertEqual(caught.exception.reason, 'ExecutionHandleRequired')
        with self.assertRaises(common.Denied) as caught:
            self.invoke(runtime, headers=[(facade.HANDLE_HEADER, HANDLE), ('Authorization', 'Bearer x' * 4)])
        self.assertEqual(caught.exception.reason, 'UnexpectedCredential')
        with self.assertRaises(common.Denied) as caught:
            self.invoke(runtime, headers=[(facade.HANDLE_HEADER, HANDLE), (facade.HANDLE_HEADER, HANDLE)])
        self.assertEqual(caught.exception.reason, 'DuplicateHeader')
        for body in ({'prompt': 'x', 'runId': 'a' * 32, 'extra': 1}, {'prompt': 'bad\x00', 'runId': 'a' * 32},
                     {'prompt': 'x', 'runId': 'not-hex'}):
            with self.assertRaises(common.Denied) as caught:
                self.invoke(runtime, body=body)
            self.assertEqual(caught.exception.reason, 'InvalidInvocation')
        with self.assertRaises(common.Denied) as caught:
            runtime.handle('POST', '/invoke', [(facade.HANDLE_HEADER, HANDLE)], b'{"prompt":"x","prompt":"y","runId":"a"}')
        self.assertEqual(caught.exception.reason, 'InvalidJSON')
        with self.assertRaises(common.Denied) as caught:
            runtime.handle('POST', '/invoke', [(facade.HANDLE_HEADER, HANDLE)],
                           b' ' * (agent.INTERNAL_INVOKE_BYTES + 1))
        self.assertEqual((caught.exception.status, caught.exception.reason), (413, 'BodyTooLarge'))

    def test_concurrency_one(self):
        runtime = self.runtime()
        runtime.busy.acquire()
        try:
            with self.assertRaises(common.Denied) as caught:
                self.invoke(runtime)
            self.assertEqual((caught.exception.status, caught.exception.reason), (429, 'RuntimeBusy'))
        finally:
            runtime.busy.release()

    def test_start_refuses_mismatched_bindings(self):
        tampered = copy.deepcopy(self.content_binding)
        tampered['packages'][0]['files']['SKILL.md'] = '0' * 64
        with self.assertRaises(ValueError):
            agent.Runtime('docs-demo', 'x', self.model_binding, tampered, f.CONTENT, self.token)
        proof = (f.CONTENT / 'aks-known-issues/references/release-proof.txt').read_text().split()[-1]
        with self.assertRaises(ValueError):
            agent.Runtime('docs-demo', 'Use ' + proof, self.model_binding, self.content_binding, f.CONTENT, self.token)
        with self.assertRaises(ValueError):
            agent.Runtime('docs-demo', 'line\nbreak', self.model_binding, self.content_binding, f.CONTENT, self.token)
        bad_model = dict(self.model_binding, gatewayBaseURL='http://gw.example:8080/path')
        with self.assertRaises(ValueError):
            agent.Runtime('docs-demo', 'x', bad_model, self.content_binding, f.CONTENT, self.token)
        with self.assertRaises(ValueError):
            agent.Runtime('Docs_Demo', 'x', self.model_binding, self.content_binding, f.CONTENT, self.token)

    def test_vendored_cli_contract_is_unchanged_without_hooks(self):
        from vendor import worker_base
        self.assertEqual(worker_base.TOOLS[0]['function']['name'], 'load_skill')
        data = {'runtime': 'standalone-reference-v1', 'limits': {'deadlineSeconds': 10}, 'packages': [],
                'endpoint': 'http://x/chat/completions'}
        with self.assertRaises(worker_base.Denied):
            worker_base.Agent(data, {'toolEvidence': [], 'toolCalls': 0})


if __name__ == '__main__':
    unittest.main()
