"""Focused native gate regression tests; all external operations use loopback/fakes."""
import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load('native_gate_runtime', ROOT / 'runtime/server.py')
golden = load('native_golden', ROOT / 'runtime/golden.py')
# Run every existing runtime behavior test against the copied/extended server.
legacy = load('native_gate_legacy_tests', ROOT / 'tests/legacy_runtime.py')
legacy.runtime = runtime
LegacyRuntimeTests = legacy.RuntimeTests
NS = 'secure-byo-kro'
PREFIX = 'system:serviceaccount:' + NS + ':'
ENV = {'POD_NAME': 'demo-golden-test', 'POD_UID': 'pod-uid', 'JOB_NAME': 'demo-golden', 'ATTEMPT_ID': 'attempt-1'}
NAMES = {'agenttemplates': 'demo-template', 'harnesses': 'approved-harness',
         'modelconfigs': 'approved-model', 'remotemcpservers': 'approved-mcp'}
SKILLS = [
    {'name': 'aks-known-issues', 'source': {'oci': 'example.invalid/known@sha256:' + 'a' * 64, 'path': 'skill'},
     'proofTerms': ['aks-known-issues'], 'references': [{'path': 'references/error-code-map.md', 'proofTerms': ['OrasPullUnauthorizedVMExtensionError', '212']}]},
    {'name': 'kb-aks-bootstrap', 'source': {'oci': 'example.invalid/kb@sha256:' + 'b' * 64, 'path': 'skill'},
     'proofTerms': ['kb-aks-bootstrap'], 'references': [{'path': 'references/oras-pull-unauthorized.md', 'proofTerms': ['AKS-KB-ORAS-212-R1']}]}
]


def config():
    return {'namespace': NS, 'agentName': 'demo', 'approvalName': 'demo-approval',
            'request': {'apiVersion': 'kro.run/v1alpha1', 'plural': 'secureagents', 'name': 'demo'},
            'dependencyNames': NAMES.copy(), 'requireGoldenProof': True,
            'verifierSubject': PREFIX + 'approved-verifier'}


def native_result():
    parts = []
    ident = 0
    def pair(name, args, response):
        nonlocal ident
        ident += 1
        tag = 'call-' + str(ident)
        call = {'id': tag, 'name': 'native__' + name}
        if args is not None:
            call['args'] = args
        parts.extend([{'metadata': {'kagent.dev/a2a/part-type': 'function_call'}, 'data': call},
                      {'metadata': {'kagent.dev/a2a/part-type': 'function_response'},
                       'data': {'id': tag, 'name': 'native__' + name, 'response': response}}])
    for skill in SKILLS:
        pair('load_skill', {'name': skill['name']}, {'skill_name': skill['name'], 'instructions': 'reviewed'})
        ref = skill['references'][0]
        pair('load_skill_resource', {'skill_name': skill['name'], 'resource_path': ref['path']},
             {'content': ' '.join(ref['proofTerms']), 'path': ref['path'], 'skill_name': skill['name']})
    pair('get_demo_status', None, {'output': {'status': 'synthetic-ready'}})
    return {'task': {'id': 'native-task', 'contextId': 'native-context', 'status': {'state': 'TASK_STATE_COMPLETED'},
                     'history': [{'role': 'ROLE_USER', 'parts': [{'text': 'request'}]}], 'artifacts': [{'parts': parts}]}}


class FakeKube:
    def __init__(self):
        self.calls, self.patches = [], []
        self.rv = 1
        self.record = {'state': 'Pending'}
        self.request = {'metadata': {'uid': 'request-uid'}}
        self.agent = {'metadata': {'uid': 'agent-uid', 'generation': 1},
                      'spec': {'template': {'ref': {'name': 'demo-template'}}, 'harnessRef': {'name': 'approved-harness'}},
                      'status': {'desiredRevision': 'rev1', 'latestSuccessfulRevision': 'rev1',
                                 'conditions': [{'type': k, 'status': 'True', 'observedGeneration': 1} for k in golden.CONDITIONS]}}
        self.objects = {}
        for plural, name in NAMES.items():
            spec = {'fixed': name}
            if plural == 'agenttemplates':
                spec = {'modelConfig': {'name': 'approved-model'},
                        'skills': [{k: s[k] for k in ('name', 'source')} for s in SKILLS],
                        'tools': [{'mcp': {'server': {'name': 'approved-mcp'}, 'tools': ['get_demo_status']}}]}
            self.objects[plural] = {'metadata': {'uid': plural + '-uid'}, 'spec': spec}
        self.sa_uids = {name: name + '-uid' for name in ('approved-caller', 'approved-worker', 'approved-verifier')}
        self.secret_rotated = False
        self.bootstrap_ready = False
        label = {'secure-byo.platform/request-uid': 'request-uid'}
        self.pod = {'metadata': {'uid': 'pod-uid', 'labels': label.copy(),
                                'ownerReferences': [{'kind': 'Job', 'name': 'demo-golden', 'uid': 'job-uid', 'controller': True}]},
                    'spec': {'serviceAccountName': 'approved-verifier', 'restartPolicy': 'Never'}}
        self.job = {'metadata': {'uid': 'job-uid', 'labels': label.copy()}, 'spec': {'backoffLimit': 0}}
        self.before_patch = None

    def call(self, path, value=None, method=None, headers=None):
        self.calls.append((path, method))  # No token, Secret data or HTTP headers in audit output.
        if path.endswith('/tokenreviews'):
            token = value['spec']['token']
            pieces = token.split('|')
            sa, audience = pieces if len(pieces) == 2 else ('unknown', 'wrong')
            return {'status': {'authenticated': sa in self.sa_uids, 'audiences': [audience],
                               'user': {'username': PREFIX + sa, 'uid': self.sa_uids.get(sa)}}}
        if path.endswith('/token'):
            sa = path.split('/')[-2]
            return {'status': {'token': sa + '|' + value['spec']['audiences'][0],
                               'expirationTimestamp': golden.iso(golden.now() + dt.timedelta(seconds=600))}}
        if '/serviceaccounts/' in path:
            return {'metadata': {'uid': self.sa_uids[path.split('/')[-1]]}}
        if '/pods/' in path:
            return copy.deepcopy(self.pod)
        if '/jobs/' in path:
            return copy.deepcopy(self.job)
        if '/configmaps/' in path:
            if method == 'PATCH':
                if self.before_patch:
                    hook, self.before_patch = self.before_patch, None
                    hook()
                self.assert_patch(value)
                self.record = json.loads(value[-1]['value'])
                self.patches.append(copy.deepcopy(self.record))
                self.rv += 1
            return {'metadata': {'resourceVersion': str(self.rv)}, 'data': {'approval.json': json.dumps(self.record)}}
        if '/secrets/' in path:
            if method == 'PATCH':
                if value[0] != {'op': 'test', 'path': '/metadata/resourceVersion', 'value': 'secret-rv'}:
                    raise golden.Failed('SecretCASFailed')
                self.secret_rotated = True
            return {'metadata': {'resourceVersion': 'secret-rv'}}
        if '/secureagents/' in path:
            return copy.deepcopy(self.request)
        if '/agents/' in path:
            agent = copy.deepcopy(self.agent)
            if self.bootstrap_ready and not self.secret_rotated:
                agent['status'] = {}
            return agent
        for plural, obj in self.objects.items():
            if '/' + plural + '/' in path:
                return copy.deepcopy(obj)
        raise AssertionError('Unexpected Kubernetes path ' + path)

    def assert_patch(self, value):
        if (value[0] != {'op': 'test', 'path': '/metadata/resourceVersion', 'value': str(self.rv)}
                or value[1] != {'op': 'test', 'path': '/data/approval.json', 'value': json.dumps(self.record)}):
            raise golden.Failed('KubernetesHTTP409')

    def verifying(self):
        pins = [{'apiVersion': golden.API, 'plural': plural, 'name': NAMES[plural],
                 'uid': obj['metadata']['uid'], 'specSha256': runtime.canonical(obj['spec'])}
                for plural, obj in sorted(self.objects.items())]
        self.record = {'state': 'Verifying', 'attemptID': 'attempt-1', 'jobUID': 'job-uid', 'podUID': 'pod-uid',
                       'requestUID': 'request-uid', 'agentUID': 'agent-uid', 'agentSpecSha256': runtime.canonical(self.agent['spec']),
                       'startedAt': golden.iso(golden.now()),
                       'expiresAt': golden.iso(golden.now() + dt.timedelta(seconds=600)), 'dependencies': pins,
                       'callers': {'invoke': [PREFIX + 'approved-caller'], 'mcp': [PREFIX + 'approved-worker']},
                       'callerUIDs': {PREFIX + sa: uid for sa, uid in self.sa_uids.items()}}
        return self.record


def receipt(record):
    result = {k: copy.deepcopy(record[k]) for k in ('attemptID', 'jobUID', 'podUID', 'requestUID', 'agentUID', 'agentSpecSha256', 'dependencies', 'expiresAt')}
    result.update(schemaVersion=golden.SCHEMA, proofScope=golden.SCOPE, passed=True, nativeRevision='rev1',
                  taskID='task-1', contextID='context-1', skills=[s['name'] for s in SKILLS],
                  witnessDeltas={'modelCalls': 3, 'mcpCalls': 1}, evidence={'toolCallCounts': {'load_skill': 2, 'load_skill_resource': 2, 'get_demo_status': 1}},
                  checks=[{'name': name, 'passed': True} for name in ('NativeInvocationHTTP', 'StructuredNativeEvidence', 'PositiveModelAndMcpWitnesses',
                          'NativeCurrentReadyAndPins', 'OrdinaryCallerDeniedWhileVerifying', 'MissingTokenDenied', 'WrongAudienceDenied',
                          'WorkerCannotInvoke', 'VerifierCannotUseWorkerLane', 'CallerCannotUseWorkerLane', 'ForbiddenMcpOperationDenied',
                          'NegativeControlsNoBackendDispatch')])
    return {'receipt': result, 'sha256': runtime.canonical(result)}


class NativeGateTests(unittest.TestCase):
    def setUp(self):
        self.kube = FakeKube()
        self.authority = runtime.Authority(self.kube, config())
        self.kube.verifying()
        self.dispatch = []
        def upstream(prompt):
            self.dispatch.append(prompt)
            return native_result()
        self.server = runtime.Frontdoor(('127.0.0.1', 0), self.authority, upstream)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(self, path, value, token='approved-verifier|secure-byo'):
        headers = {'Content-Type': 'application/json'}
        if token is not None:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(self.url + path, json.dumps(value).encode(), headers)
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def activate(self):
        self.kube.record['state'] = 'Active'
        self.kube.record['goldenProof'] = receipt(self.kube.record)

    def test_only_exact_current_verifier_can_bootstrap_invoke(self):
        self.assertEqual(self.post('/invoke', {'prompt': 'scenario'})[0], 200)
        for sa in ('approved-caller', 'approved-worker'):
            self.assertEqual(self.post('/invoke', {'prompt': 'scenario'}, sa + '|secure-byo')[0], 403)
        self.kube.sa_uids['approved-verifier'] = 'replacement'
        self.assertEqual(self.post('/witness', {})[0], 403)
        self.assertEqual(len(self.dispatch), 1)

    def test_worker_lanes_bootstrap_before_ready_verifier_cannot(self):
        self.kube.agent['status'] = {}
        rpc = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}
        self.assertEqual(self.post('/mcp', rpc, 'approved-worker|secure-byo')[0], 200)
        self.assertEqual(self.post('/mcp', rpc)[0], 403)
        self.assertEqual(self.post('/witness', {})[0], 200)
        self.assertEqual(self.post('/invoke', {'prompt': 'scenario'})[0], 403)

    def test_missing_wrong_audience_and_subject_denied_without_dispatch(self):
        for token, expected in ((None, 401), ('approved-verifier|wrong-audience', 401), ('approved-caller|secure-byo', 403)):
            self.assertEqual(self.post('/invoke', {'prompt': 'scenario'}, token)[0], expected)
        self.assertEqual(self.dispatch, [])

    def test_plain_active_and_stale_or_mismatched_proofs_rejected(self):
        self.kube.record['state'] = 'Active'
        token = 'approved-caller|secure-byo'
        self.assertEqual(self.post('/invoke', {'prompt': 'scenario'}, token)[0], 403)
        self.kube.record['goldenProof'] = receipt(self.kube.record)
        good = copy.deepcopy(self.kube.record['goldenProof'])
        for key, value in [('attemptID', 'stale'), ('requestUID', 'old'), ('agentUID', 'old'), ('jobUID', 'old'),
                           ('dependencies', []), ('nativeRevision', 'old'), ('passed', False), ('skills', [])]:
            proof = copy.deepcopy(good)
            proof['receipt'][key] = value
            proof['sha256'] = runtime.canonical(proof['receipt'])
            self.kube.record['goldenProof'] = proof
            self.assertEqual(self.post('/invoke', {'prompt': 'scenario'}, token)[0], 403, key)
        self.assertEqual(self.dispatch, [])

    def test_valid_active_receipt_allows_caller_and_worker_never_verifier(self):
        self.activate()
        self.assertEqual(self.post('/invoke', {'prompt': 'scenario'}, 'approved-caller|secure-byo')[0], 200)
        self.assertEqual(self.post('/invoke', {'prompt': 'scenario'})[0], 403)
        rpc = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}
        self.assertEqual(self.post('/mcp', rpc, 'approved-worker|secure-byo')[0], 200)

    def test_expiry_revocation_dependency_and_revision_change_deny(self):
        self.activate()
        saved = copy.deepcopy(self.kube.record)
        for mutate in (lambda: self.kube.record.update(state='Revoked'),
                       lambda: self.kube.record.update(state='Failed'),
                       lambda: self.kube.record.update(expiresAt='2020-01-01T00:00:00Z')):
            mutate()
            self.assertEqual(self.post('/invoke', {'prompt': 'scenario'}, 'approved-caller|secure-byo')[0], 403)
            self.kube.record = copy.deepcopy(saved)
        self.kube.objects['modelconfigs']['spec']['changed'] = True
        self.assertEqual(self.post('/invoke', {'prompt': 'scenario'}, 'approved-caller|secure-byo')[0], 403)
        del self.kube.objects['modelconfigs']['spec']['changed']
        self.kube.agent['status']['latestSuccessfulRevision'] = 'old'
        self.assertEqual(self.post('/invoke', {'prompt': 'scenario'}, 'approved-caller|secure-byo')[0], 403)
        self.assertEqual(self.dispatch, [])

    def test_verification_mcp_and_invocation_budgets_fail_closed(self):
        self.authority.config['verificationBudgets'] = {'mcpCalls': 1, 'invocations': 1, 'modelCalls': 1}
        rpc = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'get_demo_status', 'arguments': {}}}
        self.assertEqual(self.post('/mcp', rpc, 'approved-worker|secure-byo')[0], 200)
        self.assertEqual(self.post('/mcp', rpc, 'approved-worker|secure-byo')[0], 429)
        self.assertEqual(self.post('/invoke', {'prompt': 'scenario'})[0], 200)
        self.assertEqual(self.post('/invoke', {'prompt': 'retry'})[0], 429)
        self.assertEqual(self.server.counters['authorizedMcpCalls'], 1)
        self.assertEqual(len(self.dispatch), 1)

    def test_runtime_rejects_unbounded_or_wrong_target_verification_config(self):
        for updates in ({'namespace': 'secure-byo-hosted'},
                        {'verifierSubject': PREFIX + 'approved-caller'},
                        {'verificationBudgets': {'modelCalls': 65}},
                        {'verificationBudgets': {'mcpCalls': 0}},
                        {'verificationBudgets': {'invocations': 2}}):
            cfg = config()
            cfg.update(updates)
            with self.assertRaises(ValueError):
                runtime.Authority(self.kube, cfg)

    def test_same_attempt_binding_changed_during_dispatch_withholds_result(self):
        def invoke(prompt):
            self.kube.record['attemptID'] = 'replaced-attempt'
            return native_result()
        self.server.upstream = invoke
        status, body = self.post('/invoke', {'prompt': 'scenario'})
        self.assertEqual(status, 403)
        self.assertNotIn('task', body)

    def test_verification_model_budget_checked_before_dispatch(self):
        self.authority.config['verificationBudgets'] = {'modelCalls': 1}
        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory) / 'key'
            key.write_text('private-provider-test-key')
            self.authority.config.update(upstreamModelURL='http://provider.invalid/v1/chat/completions', modelName='fixed-model',
                                         upstreamModelKeyFile=str(key))
            calls = []
            def post(url, value, headers, deadline, ca_file=None, before_dispatch=None):
                before_dispatch()
                calls.append(url)
                return {'choices': []}
            value = {'model': 'fixed-model', 'messages': [{'role': 'user', 'content': 'test'}]}
            with patch.object(runtime, 'post_json', post):
                self.assertEqual(self.post('/v1/chat/completions', value, 'approved-worker|secure-byo')[0], 200)
                self.assertEqual(self.post('/v1/chat/completions', value, 'approved-worker|secure-byo')[0], 429)
            self.assertEqual(len(calls), 1)

    def test_runtime_restart_cannot_reset_inflight_verification_budgets(self):
        self.server.reserve_verification(self.kube.record, 'modelCalls')
        restarted = runtime.Authority(self.kube, config())
        with self.assertRaises(runtime.Denied) as failure:
            restarted.authorize('Bearer approved-worker|secure-byo', 'mcp')
        self.assertEqual(failure.exception.reason, 'VerificationRuntimeRestarted')
        # A completed, persisted proof remains valid across process restarts.
        self.activate()
        self.assertEqual(restarted.authorize('Bearer approved-caller|secure-byo', 'invoke'), PREFIX + 'approved-caller')

    def test_single_concurrent_native_invocation(self):
        entered, release = threading.Event(), threading.Event()
        def invoke(prompt):
            entered.set()
            release.wait(3)
            return native_result()
        self.server.upstream = invoke
        result = []
        worker = threading.Thread(target=lambda: result.append(self.post('/invoke', {'prompt': 'first'})))
        worker.start()
        self.assertTrue(entered.wait(2))
        self.assertEqual(self.post('/invoke', {'prompt': 'concurrent'})[0], 429)
        release.set()
        worker.join(3)
        self.assertEqual(result[0][0], 200)

    def test_revocation_during_verifier_dispatch_withholds_native_response(self):
        def invoke(prompt):
            self.kube.record['state'] = 'Revoked'
            return native_result()
        self.server.upstream = invoke
        status, body = self.post('/invoke', {'prompt': 'scenario'})
        self.assertEqual(status, 403)
        self.assertNotIn('task', body)

    def golden(self):
        cfg = config()
        cfg.update(requestUID='request-uid', gatewayURL=self.url, skills=copy.deepcopy(SKILLS), maxTTLSeconds=600)
        return golden.Golden(self.kube, cfg, ENV, transport=self.post)

    def test_full_golden_publishes_bootstrap_then_passed_proof_and_real_caller_result(self):
        self.kube.record = {'state': 'Pending'}
        self.kube.bootstrap_ready = True
        def invoke(prompt):
            self.server.count('authorizedModelCalls')
            if prompt.startswith('Reply with exactly PONG'):
                return {'task': {'id': 'caller-task', 'contextId': 'caller-context', 'status': {'state': 'TASK_STATE_COMPLETED'},
                                 'artifacts': [{'parts': [{'text': 'PONG'}]}]}}
            self.server.count('authorizedMcpCalls')
            return native_result()
        self.server.upstream = invoke
        report = self.golden().run()
        self.assertTrue(report['passed'], report)
        self.assertEqual([r['state'] for r in self.kube.patches], ['Verifying', 'Active', 'Active'])
        self.assertTrue(self.kube.record['callerSmoke']['passed'])
        self.assertTrue(self.kube.secret_rotated)
        self.assertEqual(self.post('/invoke', {'prompt': 'scenario'})[0], 403)
        self.assertNotIn('approved-worker|secure-byo', json.dumps(report))

    def test_failed_native_proof_remains_terminal_and_caller_denied(self):
        self.kube.record = {'state': 'Pending'}
        self.server.upstream = lambda prompt: {'task': {'status': {'state': 'TASK_STATE_COMPLETED'}}}
        report = self.golden().run()
        self.assertFalse(report['passed'])
        self.assertEqual(self.kube.record['state'], 'Failed')
        self.assertEqual(self.post('/invoke', {'prompt': 'scenario'}, 'approved-caller|secure-byo')[0], 403)
        # The same Job cannot retry a terminal record.
        again = self.golden().run()
        self.assertFalse(again['passed'])
        self.assertEqual(self.kube.record['state'], 'Failed')

    def test_failed_post_promotion_caller_smoke_revokes_own_active(self):
        self.kube.record = {'state': 'Pending'}
        def invoke(prompt):
            self.server.count('authorizedModelCalls')
            if prompt.startswith('Reply with exactly PONG'):
                # A PONG echoed only in user history is not a passed caller answer.
                return {'task': {'id': 'caller-task', 'contextId': 'caller-context', 'status': {'state': 'TASK_STATE_COMPLETED'},
                                 'history': [{'role': 'ROLE_USER', 'parts': [{'text': 'Reply with exactly PONG'}]}],
                                 'artifacts': [{'parts': [{'text': 'NO'}]}]}}
            self.server.count('authorizedMcpCalls')
            return native_result()
        self.server.upstream = invoke
        report = self.golden().run()
        self.assertFalse(report['passed'])
        self.assertEqual([r['state'] for r in self.kube.patches], ['Verifying', 'Active', 'Failed'])
        self.assertEqual(self.kube.record['goldenFailure']['phase'], 'OrdinaryCallerSmoke')
        self.assertEqual(report['observations']['callerSmoke']['taskID'], 'caller-task')
        self.assertIn('responseSha256', report['observations']['callerSmoke'])
        self.assertEqual(self.post('/invoke', {'prompt': 'scenario'}, 'approved-caller|secure-byo')[0], 403)

    def test_ready_output_without_backend_witnesses_fails_closed(self):
        self.kube.record = {'state': 'Pending'}
        report = self.golden().run()
        self.assertFalse(report['passed'])
        self.assertEqual(self.kube.record['state'], 'Failed')
        self.assertEqual(report['reason'], 'PositiveModelAndMcpWitnesses')

    def test_rejected_existing_active_is_never_changed_by_failed_claim(self):
        self.activate()
        existing = copy.deepcopy(self.kube.record)
        report = self.golden().run()
        self.assertFalse(report['passed'])
        self.assertEqual(self.kube.record, existing)
        self.assertEqual(self.kube.patches, [])

    def test_selected_native_skills_are_derived_from_pinned_reviewed_catalog(self):
        self.kube.record = {'state': 'Pending'}
        self.kube.objects['agenttemplates']['spec']['skills'] = [copy.deepcopy(self.kube.objects['agenttemplates']['spec']['skills'][1])]
        job = self.golden()
        job.collect()
        self.assertEqual([skill['name'] for skill in job.skills], ['kb-aks-bootstrap'])
        self.kube.objects['agenttemplates']['spec']['skills'][0]['source']['oci'] = 'example.invalid/wrong@sha256:' + 'c' * 64
        with self.assertRaises(golden.Failed):
            job.collect()

    def test_golden_does_not_overwrite_external_revocation(self):
        self.kube.record = {'state': 'Pending'}
        def revoke(prompt):
            self.kube.record['state'] = 'Revoked'
            return native_result()
        self.server.upstream = revoke
        report = self.golden().run()
        self.assertFalse(report['passed'])
        self.assertEqual(self.kube.record['state'], 'Revoked')
        self.assertEqual(report['state'], 'UnchangedOrSuperseded')


class GoldenCASTests(unittest.TestCase):
    def setUp(self):
        self.kube = FakeKube()
        self.record = self.kube.verifying()
        self.store = golden.Approval(self.kube, NS, 'demo-approval', 'request-uid', 'attempt-1', 'job-uid', 'pod-uid')

    def test_stale_attempt_cannot_promote_or_undo_revoke(self):
        self.kube.record['attemptID'] = 'another-attempt'
        with self.assertRaises(golden.Superseded):
            self.store.transition('Verifying', 'Active')
        self.kube.record['attemptID'] = 'attempt-1'
        self.kube.record['state'] = 'Revoked'
        with self.assertRaises(golden.Superseded):
            self.store.transition('Verifying', 'Active')
        with self.assertRaises(golden.Superseded):
            self.store.fail_owned('NativeScenario', {})
        self.assertEqual(self.kube.patches, [])

    def test_resource_version_race_prevents_promotion(self):
        def raced():
            self.kube.rv += 1
            self.kube.record['state'] = 'Revoked'
        self.kube.before_patch = raced
        with self.assertRaises(golden.Failed):
            self.store.transition('Verifying', 'Active')
        self.assertEqual(self.kube.record['state'], 'Revoked')
        self.assertEqual(self.kube.patches, [])

    def test_existing_active_failed_or_verifying_not_reclaimed(self):
        for state in ('Active', 'Failed', 'Revoked', 'Verifying'):
            self.kube.record['state'] = state
            with self.assertRaises(golden.Superseded):
                self.store.claim(self.record)
        self.assertEqual(self.kube.patches, [])

    def test_structured_proof_requires_correlated_calls_reference_args_and_response_terms(self):
        result = native_result()
        good = golden.native_evidence(result, SKILLS)
        self.assertEqual(good['toolCallCounts']['load_skill_resource'], 2)
        for mutate in (
            lambda r: r['task']['artifacts'][0]['parts'][1]['data'].update(id='wrong-id'),
            lambda r: r['task']['artifacts'][0]['parts'][0]['data'].update(name='delete_pod'),
            lambda r: r['task']['artifacts'][0]['parts'][2]['data']['args'].update(resource_path='references/foreign.md'),
            lambda r: r['task']['artifacts'][0]['parts'][3]['data'].update(response={'content': 'missing-evidence'}),
            lambda r: r['task']['artifacts'][0]['parts'].pop()):
            altered = copy.deepcopy(result)
            mutate(altered)
            with self.assertRaises(golden.Failed):
                golden.native_evidence(altered, SKILLS)

    def test_job_pod_serviceaccount_and_request_binding_required(self):
        cfg = config()
        cfg.update(requestUID='request-uid', gatewayURL='http://127.0.0.1', skills=SKILLS)
        for mutate in (lambda: self.kube.pod['spec'].update(serviceAccountName='approved-caller'),
                       lambda: self.kube.job['metadata']['labels'].update({'secure-byo.platform/request-uid': 'old-request'})):
            kube = self.kube
            mutate()
            with self.assertRaises(golden.Failed):
                golden.Golden(kube, cfg, ENV)
            self.kube = FakeKube()


if __name__ == '__main__':
    unittest.main()
