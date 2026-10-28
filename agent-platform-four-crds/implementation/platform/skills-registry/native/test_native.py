import copy
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'hosted'))
import test_onboarding as legacy
from artifacts import build
from controller import KNOWLEDGE_BASE, SKILL
from contract import canonical, parse_intent
from reconcile_native import CONDITIONS, NATIVE_API, NativeOnboarding, agent_ready
from golden_native import evaluate


class NativeTests(unittest.TestCase):
    def setUp(self):
        fixture = legacy.OnboardingTests(); fixture.setUp()
        self.kube, self.document, self.profile = fixture.kube, fixture.document, fixture.profile
        self.profile['runtimeProfile'] = 'lab-kagent-1x-v1'
        self.document['spec']['runtimeProfile'] = self.profile['runtimeProfile']
        self.profile['harness'] = {'name': 'native', 'specSha256': canonical({'native': True})}
        self.profile['packages'] = {}
        for plural, field in [('modelconfigs', 'modelConfig'), ('harnesses', 'harness')]:
            old = {'demo': 'pinned'} if plural == 'modelconfigs' else {'native': True}
            self.kube.data[f'/apis/{NATIVE_API}/namespaces/skills-demo/{plural}/' + self.profile[field]['name']] = {
                'metadata': {'generation': 1}, 'spec': old, 'status': {'conditions': [legacy.condition(c) for c in ['Accepted', 'ResolvedRefs']]}}
        self.controller = NativeOnboarding(self.kube, self.profile)
        intent = parse_intent(self.document, self.profile)
        self.packages = []
        for kind, pin in [(SKILL, intent.skill), (KNOWLEDGE_BASE, intent.knowledge)]:
            summary = self.controller.binding(kind, pin)
            release = self.kube.data[f'/apis/{legacy.API}/namespaces/skills-demo/{kind.plural}/' + pin.name]
            cm = self.kube.data['/api/v1/namespaces/skills-demo/configmaps/' + summary['configMapName']]
            texts = {p: cm['data'][f'file{i:02}'] for i, p in enumerate(sorted(release['spec']['files']))}
            package = build(kind, release['spec'], texts); self.packages.append(package)
            self.profile['packages'][kind.kind + '/' + pin.name] = {
                'packaging': 'reviewed-content-ustar-v3', 'sourceCommit': pin.source_commit, 'contentSha256': pin.content_sha256,
                'sourceSpecSha256': summary['sourceSpecSha256'], 'releaseSpecSha256': canonical(release['spec']),
                'image': 'registry.example.invalid/reviewed/' + package.name + '@' + package.digest}
        self.path = self.controller.hosted + '/' + self.document['metadata']['name']

    def reconcile(self):
        self.controller.reconcile(copy.deepcopy(self.kube.data[self.path]))
        return self.kube.data[self.path]['status']['conditions'][-1]['reason']

    def test_only_native_owned_children_and_idempotence(self):
        self.assertEqual(self.reconcile(), 'AgentNotReady')
        posts = [v for _, m, v in self.kube.writes if m == 'POST']
        self.assertEqual([v['kind'] for v in posts], ['AgentTemplate', 'Agent'])
        self.assertTrue(all(v['apiVersion'] == NATIVE_API for v in posts))
        self.assertTrue(all(v['metadata']['ownerReferences'][0]['uid'] == 'hosted-owner' for v in posts))
        self.kube.writes.clear(); self.reconcile()
        self.assertEqual(self.kube.writes, [])

    def test_wrong_oci_digest_rejected_before_children(self):
        next(iter(self.profile['packages'].values()))['image'] = 'registry.example.invalid/reviewed/test@sha256:' + '0' * 64
        self.assertEqual(self.reconcile(), 'PublishedPackageMismatch')
        self.assertFalse(any(m in ['POST', 'PUT'] for _, m, _ in self.kube.writes))

    def test_foreign_agent_collision_preflight(self):
        self.kube.data[self.controller.collection('Agent') + '/hosted-aks-team-v1'] = {
            'metadata': {'ownerReferences': []}, 'spec': {}}
        self.assertEqual(self.reconcile(), 'ManagedObjectCollision')
        self.assertFalse(any(m in ['POST', 'PUT'] for _, m, _ in self.kube.writes))

    def test_changed_source_catalog_rejected(self):
        next(iter(self.profile['packages'].values()))['sourceSpecSha256'] = '0' * 64
        self.assertEqual(self.reconcile(), 'PublishedPackageMismatch')

    def test_ready_requires_revision_and_every_native_condition(self):
        agent = {'metadata': {'generation': 2}, 'status': {'conditions': [legacy.condition(c, 2) for c in CONDITIONS],
                  'desiredRevision': 'a', 'latestSuccessfulRevision': 'a'}}
        self.assertTrue(agent_ready(agent))
        agent['status']['latestSuccessfulRevision'] = 'b'
        self.assertFalse(agent_ready(agent))
        agent['status']['latestSuccessfulRevision'] = 'a'
        agent['status']['conditions'][0]['observedGeneration'] = 1
        self.assertFalse(agent_ready(agent))

    def envelope(self):
        parts = []
        for package in self.packages:
            calls = [('load_skill', {'name': package.name}, {'skill_name': package.name,
                'frontmatter': {line.split(': ', 1)[0]: json.loads(line.split(': ', 1)[1]) if line.split(': ', 1)[1].startswith(chr(34)) else line.split(': ', 1)[1] for line in package.files['SKILL.md'].removeprefix('---\n').split('\n---\n', 1)[0].splitlines() if line.strip()}, 'instructions': package.files['SKILL.md'].split('\n---\n', 1)[1]})]
            paths = ['references/error-code-map.md'] if package == self.packages[0] else ['references/oras-pull-unauthorized.md']
            for path in paths + ['references/release-proof.txt']:
                calls.append(('load_skill_resource', {'skill_name': package.name, 'resource_path': path},
                    {'skill_name': package.name, 'path': path, 'content': package.files[path]}))
            for name, args, response in calls:
                call_id = str(len(parts))
                for kind, data in [('function_call', {'args': args}), ('function_response', {'response': response})]:
                    parts.append({'metadata': {'kagent.dev/a2a/part-type': kind}, 'data': {'id': call_id, 'name': name, **data}})
        answer = '\n'.join(p.files['references/release-proof.txt'] for p in self.packages) + '\nEvidence https://example.invalid/source'
        parts.append({'text': answer})
        return {'task': {'id': 'fresh-task', 'contextId': 'fresh-session', 'status': {'state': 'TASK_STATE_COMPLETED'}, 'artifacts': [{'parts': parts}]}}

    def test_golden_matches_full_bytes_and_rejects_tampering(self):
        scenario = {'spec': {'policy': 'aks-docs-kagent-1x-v1', 'inputOrigin': 'synthetic', 'prompt': 'Read both packages.',
            'referenceFile': 'references/error-code-map.md', 'knowledgeFile': 'references/oras-pull-unauthorized.md',
            'answerTerms': ['Evidence'], 'citations': ['https://example.invalid/source']}}
        envelope = self.envelope()
        envelope['task']['history'] = [{'role': 'ROLE_USER', 'contextId': 'fresh-session', 'taskId': 'fresh-task', 'parts': [{'text': scenario['spec']['prompt']}]}]
        self.assertEqual(evaluate(scenario, envelope, self.packages, 'fresh-session')['nativeToolCalls'], 6)
        for mutation in ['description', 'instructions', 'history']:
            changed = copy.deepcopy(envelope)
            if mutation == 'description':
                changed['task']['artifacts'][0]['parts'][1]['data']['response']['frontmatter']['description'] = 'unreviewed'
            elif mutation == 'instructions':
                changed['task']['artifacts'][0]['parts'][1]['data']['response']['instructions'] += ' '
            else:
                changed['task']['history'][0]['parts'][0]['text'] = 'different prompt'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                evaluate(scenario, changed, self.packages, 'fresh-session')
        envelope['task']['artifacts'][0]['parts'][3]['data']['response']['content'] += 'tampered'
        with self.assertRaises(ValueError):
            evaluate(scenario, envelope, self.packages, 'fresh-session')


if __name__ == '__main__':
    unittest.main()
