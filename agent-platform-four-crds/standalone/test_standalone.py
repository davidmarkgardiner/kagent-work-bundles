"""Local deterministic HTTP tests, not a live Qwen or native-runtime proof."""
import copy
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

import prepare
from controller import API, GROUP, SKILL, KNOWLEDGE_BASE, content_digest, sha256
from contract import canonical, crd as hosted_crd
from golden_native import crd as golden_crd

HERE = Path(__file__).resolve().parent
SKILLS = ['test-skill', 'kb-test-knowledge']
CITATION = 'https://docs.example.invalid/reviewed'


def make_fixture(directory, endpoint, namespace='reference-lab'):
    """Write synthetic snapshots for local tests; fake UIDs/status are never live evidence."""
    directory = Path(directory); directory.mkdir(exist_ok=True)
    def meta(name):
        return {'name': name, 'namespace': namespace, 'uid': 'fixture-' + name, 'generation': 1, 'resourceVersion': '1'}
    condition = {'type': 'Ready', 'status': 'True', 'observedGeneration': 1}
    releases, sources, cms = [], [], []
    for kind, name, commit, texts in [(SKILL, 'test-skill', 'a' * 40, {
            'SKILL.md': '---\nname: test-skill\ndescription: Reviewed synthetic test instructions.\n---\n\nRead the reference.\n',
            'references/error-code-map.md': '# Test error map\n\nSource: ' + CITATION + '\nORAS-212 test fixture.\n'}),
            (KNOWLEDGE_BASE, 'test-knowledge', 'b' * 40, {'oras-pull-unauthorized.md':
                '# Synthetic reference\n\nSource: ' + CITATION + '\nReviewed: 2026-10-28\n\nORAS-212 documentation fixture.\n'})]:
        spec = {kind.name_field: name, 'sourceRef': {'name': name + '-source'}, 'sourceCommit': commit,
                'path': 'payload', 'files': {p: sha256(t.encode()) for p, t in texts.items()}}
        spec['contentSha256'] = content_digest(spec['files'])
        if kind == KNOWLEDGE_BASE:
            spec['documents'] = [{'path': 'oras-pull-unauthorized.md', 'title': 'Synthetic reference',
                                  'sourceURL': CITATION, 'reviewedAt': '2026-10-28'}]
        release = {'apiVersion': API, 'kind': kind.kind, 'metadata': meta(name + '-v1'), 'spec': spec}
        cm_name = kind.configmap_prefix + name + '-v1-' + spec['contentSha256'][:16]
        release['status'] = {'observedGeneration': 1, 'conditions': [copy.deepcopy(condition)],
            'contentSha256': spec['contentSha256'], 'observedSourceRevision': 'sha1:' + commit, 'configMapRef': {'name': cm_name}}
        source = {'apiVersion': 'source.toolkit.fluxcd.io/v1', 'kind': 'GitRepository', 'metadata': meta(name + '-source'),
            'spec': {'url': 'https://example.invalid/reviewed.git', 'ref': {'commit': commit}},
            'status': {'observedGeneration': 1, 'conditions': [copy.deepcopy(condition)], 'artifact': {'revision': 'sha1:' + commit}}}
        cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': meta(cm_name), 'immutable': True,
              'data': {f'file{i:02}': texts[p] for i, p in enumerate(sorted(texts))}}
        cm['metadata'].update(ownerReferences=[{'apiVersion': API, 'kind': kind.kind, 'name': name + '-v1',
            'uid': release['metadata']['uid'], 'controller': True}], labels={GROUP + '/' + kind.label: name + '-v1'},
            annotations={GROUP + '/digest': spec['contentSha256']})
        releases.append(release); sources.append(source); cms.append(cm)
    pin = lambda r: {'name': r['metadata']['name'], **{k: r['spec'][k] for k in ('sourceCommit', 'contentSha256')}}
    profile = {'runtimeProfile': 'native-fixture-v1', 'modelProfile': 'native-model-fixture-v1'}
    hosted = {'apiVersion': API, 'kind': 'HostedAgent', 'metadata': meta('reference-agent-v1'), 'spec': {
        'owner': {'team': 'reference-lab'}, 'purpose': 'Synthetic documentation test', 'instructions': 'Use reviewed references.',
        'runtimeProfile': prepare.RUNTIME, 'modelProfile': prepare.MODEL_PROFILE,
        'skillRefs': [pin(releases[0])], 'knowledgeBaseRefs': [pin(releases[1])], 'toolGrantRefs': []}}
    golden = {'apiVersion': API, 'kind': 'GoldenScenario', 'metadata': meta('reference-golden-v1'), 'spec': {
        'policy': prepare.POLICY, 'inputOrigin': 'synthetic', 'hostedAgentRef': {'name': hosted['metadata']['name']},
        'hostedAgentSpecSha256': canonical(hosted['spec']), 'prompt': 'Read both instructions, references and release proofs.',
        'referenceFile': 'references/error-code-map.md', 'knowledgeFile': 'references/oras-pull-unauthorized.md',
        'answerTerms': ['ORAS-212'], 'citations': [CITATION]}}
    module_spec = importlib.util.spec_from_file_location('fixture_resources', prepare.REGISTRY / 'resources.py')
    resources = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(resources)
    crds = [resources.crd(), resources.crd(KNOWLEDGE_BASE), hosted_crd(profile), golden_crd()]
    for crd in crds:
        crd['metadata']['resourceVersion'] = '7'
        crd['status'] = {'conditions': [{'type': 'Established', 'status': 'True'}]}
    cfg = {'namespace': namespace, 'helperImage': 'registry.example.invalid/helper@sha256:' + '1' * 64,
        'endpoint': endpoint, 'model': 'qwen-test-only', 'sourceControllerOrigin': 'http://source-controller.example.invalid:9090',
        'imagePullSecrets': [], 'limits': {'maxModelCalls': 3, 'maxToolCalls': 8, 'maxTokens': 1024,
            'requestTimeoutSeconds': 2, 'deadlineSeconds': 10, 'maxResponseBytes': 32768}}
    documents = {'skill.json': releases[0], 'knowledge.json': releases[1], 'hosted.json': hosted, 'golden.json': golden,
                 'sources.json': {'items': sources}, 'configmaps.json': {'items': cms}, 'crds.json': {'items': crds}, 'config.json': cfg,
                 'native-api-resources.json': {'groupVersion': 'api.kagent.dev/v1alpha3',
                    'resources': [{'name': 'agenttemplates', 'namespaced': True, 'verbs': ['get', 'list']}]}}
    for filename, document in documents.items():
        (directory / filename).write_text(json.dumps(document))
    return documents


def provider_response(request, mode='success'):
    """OpenAI-shaped test provider: proofs come only from returned tool bytes."""
    results = [json.loads(m['content']) for m in request['messages'] if m['role'] == 'tool']
    if mode == 'model-loop':
        return {'choices': [{'message': {'role': 'assistant', 'content': None, 'tool_calls': [{
            'id': 'loop_' + str(len(results)), 'type': 'function',
            'function': {'name': 'load_skill', 'arguments': json.dumps({'name': SKILLS[0]})}}]}, 'finish_reason': 'tool_calls'}]}
    if not results or mode == 'loop':
        calls = [('load_skill', {'name': SKILLS[0]}), ('load_skill', {'name': SKILLS[1]}),
                 ('load_skill_resource', {'skill_name': SKILLS[0], 'resource_path': 'references/error-code-map.md'}),
                 ('load_skill_resource', {'skill_name': SKILLS[1], 'resource_path': 'references/oras-pull-unauthorized.md'})]
        calls += [('load_skill_resource', {'skill_name': n, 'resource_path': 'references/release-proof.txt'}) for n in SKILLS]
        if mode == 'unknown':
            calls[0] = ('shell', {'command': 'echo forbidden'})
        if mode == 'arguments':
            calls[0][1]['extra'] = 'denied'
        message = {'role': 'assistant', 'content': None, 'tool_calls': [
            {'id': 'call_' + str(i), 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}
            for i, (name, args) in enumerate(calls)]}
        finish = 'tool_calls'
    else:
        answer = 'ORAS-212 documentation only. ' + CITATION + '\n' + '\n'.join(
            r['content'] for r in results if r.get('path') == 'references/release-proof.txt')
        if mode == 'missing-proof':
            answer = 'ORAS-212 ' + CITATION
        message, finish = {'role': 'assistant', 'content': answer}, 'stop'
    return {'choices': [{'message': message, 'finish_reason': finish}]}


class StandaloneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=HERE); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.snapshot = self.root / 'snapshot'
        self.docs = make_fixture(self.snapshot, 'http://127.0.0.1:1/v1/chat/completions')

    def cli(self, mode=()):
        return subprocess.run([sys.executable, '-B', str(HERE / 'prepare.py'), '--config', str(self.snapshot / 'config.json'),
            '--snapshot', str(self.snapshot), '--output', str(self.root / 'output'), *mode], capture_output=True, text=True)

    def test_real_cli_render_and_guarded_additive_schema_patches(self):
        result = self.cli(); self.assertEqual(result.returncode, 0, result.stderr)
        job = json.loads((self.root / 'output/job.json').read_text())
        rendered = json.dumps(job)
        for forbidden in ('Substrate', 'Harness', 'WorkerPool', 'api.kagent.dev', 'v1alpha2', 'serviceaccount/token'):
            self.assertNotIn(forbidden, rendered.replace('not native kagent runtime or Harness proof', ''))
        self.assertEqual([o['kind'] for o in job['items']], ['ServiceAccount', 'ConfigMap', 'ConfigMap', 'Job'])
        pod = job['items'][-1]['spec']['template']['spec']
        self.assertFalse(pod['automountServiceAccountToken']); self.assertEqual(pod['restartPolicy'], 'Never')
        self.assertEqual(job['items'][-1]['spec']['backoffLimit'], 0)
        patch = json.loads(next((self.root / 'output').glob('hostedagents*.patch.json')).read_text())
        self.assertEqual(patch[0]['path'], '/metadata/resourceVersion')
        self.assertEqual([p['op'] for p in patch], ['test', 'test', 'add', 'test', 'add'])
        self.assertEqual((self.root / 'output').stat().st_mode & 0o777, 0o700)

    def test_snapshot_tampering_denied(self):
        for mutation in ('hash', 'owner', 'generation', 'native-profile', 'golden-pin'):
            docs = copy.deepcopy(self.docs)
            if mutation == 'hash': docs['configmaps.json']['items'][0]['data']['file00'] += 'tampered'
            if mutation == 'owner': docs['configmaps.json']['items'][0]['metadata']['ownerReferences'][0]['uid'] = 'foreign'
            if mutation == 'generation': docs['skill.json']['metadata']['generation'] = 2
            if mutation == 'native-profile': docs['hosted.json']['spec']['runtimeProfile'] = 'native-fixture-v1'
            if mutation == 'golden-pin': docs['golden.json']['spec']['hostedAgentSpecSha256'] = '0' * 64
            for name, doc in docs.items(): (self.snapshot / name).write_text(json.dumps(doc))
            with self.subTest(mutation=mutation): self.assertNotEqual(self.cli().returncode, 0)

    def test_invalid_private_config_denied(self):
        for change in ({'helperImage': 'python:latest'}, {'endpoint': 'https://user:secret@example.invalid/v1/chat/completions'},
                       {'endpoint': 'https://example.invalid/v1/chat/completions?key=secret'}, {'extra': 'denied'}):
            with self.subTest(change=change), self.assertRaises(ValueError): prepare.config({**self.docs['config.json'], **change})

    def test_optional_content_adapter_requires_verified_api_and_has_no_lab_scheduling(self):
        cfg = self.docs['config.json']; adapter = prepare.adapter(cfg, self.snapshot)
        deployment = next(o for o in adapter['items'] if o['kind'] == 'Deployment')
        pod = deployment['spec']['template']['spec']; container = pod['containers'][0]
        self.assertNotIn('nodeSelector', pod); self.assertNotIn('tolerations', pod)
        self.assertEqual(container['image'], cfg['helperImage'])
        self.assertIn({'name': 'NATIVE_KAGENT', 'value': '1'}, container['env'])
        (self.snapshot / 'native-api-resources.json').write_text('{}')
        with self.assertRaises(ValueError): prepare.adapter(cfg, self.snapshot)

    def worker(self, mode='success', tamper=False):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(handler):
                request = json.loads(handler.rfile.read(int(handler.headers['Content-Length']))); requests.append(request)
                if mode == 'http-error': handler.send_error(503, 'TEST ONLY'); return
                if mode == 'redirect':
                    handler.send_response(302); handler.send_header('Location', 'http://127.0.0.1:1/denied'); handler.end_headers(); return
                raw = b'x' * 32769 if mode == 'oversize' else json.dumps(provider_response(request, mode)).encode()
                handler.send_response(200); handler.send_header('Content-Type', 'application/json'); handler.end_headers(); handler.wfile.write(raw)
            def log_message(self, *args): pass
        server = HTTPServer(('127.0.0.1', 0), Handler); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            cfg = self.docs['config.json']; cfg['endpoint'] = f'http://127.0.0.1:{server.server_port}/v1/chat/completions'
            manifest, _ = prepare.render(cfg, self.snapshot)
            input_raw = manifest['items'][2]['data']['input.json']; (self.root / 'input.json').write_text(input_raw)
            content = self.root / 'content'; content.mkdir(exist_ok=True)
            for i, cm in enumerate(self.docs['configmaps.json']['items']):
                (content / str(i)).mkdir(exist_ok=True)
                for key, text in cm['data'].items(): (content / str(i) / key).write_text(text + ('bad' if tamper else ''))
            result = subprocess.run([sys.executable, '-B', str(HERE / 'worker.py'), '--input', str(self.root / 'input.json'),
                '--sha256', sha256(input_raw.encode()), '--receipt', str(self.root / 'receipt.json'),
                '--content-root', str(content)], capture_output=True, text=True, timeout=15)
            return result, json.loads(result.stdout), requests
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_actual_local_http_tool_exchange_passes_and_receipt_is_sanitized(self):
        result, receipt, requests = self.worker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr); self.assertEqual(receipt['result'], 'Passed')
        self.assertEqual(receipt['modelCalls'], 2); self.assertEqual(receipt['toolCalls'], 6)
        self.assertEqual({c['name'] for c in receipt['toolEvidence']}, {'load_skill', 'load_skill_resource'})
        self.assertEqual(len(requests), 2)
        for private in (CITATION, 'qwen-test-only', 'http://127.0.0.1', 'Read the reference'):
            self.assertNotIn(private, result.stdout)

    def test_failures_do_not_retry_or_fall_back(self):
        for mode, reason, count in [('unknown', 'UnknownTool', 1), ('arguments', 'InvalidToolArguments', 1),
                ('http-error', 'ProviderHTTP503', 1), ('redirect', 'ProviderRedirectDenied', 1),
                ('oversize', 'ProviderResponseTooLarge', 1), ('missing-proof', 'AnswerMissingEvidenceOrCitation', 2),
                ('loop', 'ToolCallLimitOrFinish', 2), ('model-loop', 'ModelCallLimitExceeded', 3)]:
            result, receipt, requests = self.worker(mode)
            with self.subTest(mode=mode):
                self.assertEqual(result.returncode, 1); self.assertEqual(receipt['reason'], reason)
                self.assertEqual(len(requests), count); self.assertEqual(receipt['result'], 'Failed')
        result, receipt, requests = self.worker(tamper=True)
        self.assertEqual(receipt['reason'], 'MountedContentHashMismatch'); self.assertEqual(requests, [])


if __name__ == '__main__':
    unittest.main()
