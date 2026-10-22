import copy
import json
from pathlib import Path
import unittest
import urllib.error

import yaml

from contract import API, GROUP, Rejected, canonical, load_profile, parse_intent
from reconcile import Onboarding, ready

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def condition(kind, generation=1):
    return {'type': kind, 'status': 'True', 'observedGeneration': generation}


class FakeKube:
    namespace = 'skills-demo'

    def __init__(self):
        self.data, self.writes, self.fail_kind = {}, [], None
        self.serial = 100

    def call(self, path, method='GET', value=None):
        if method == 'GET':
            if path not in self.data:
                raise urllib.error.HTTPError(path, 404, 'NotFound', {}, None)
            return copy.deepcopy(self.data[path])
        self.writes.append((path, method, copy.deepcopy(value)))
        if method == 'PATCH' and path.endswith('/status'):
            target = path.removesuffix('/status')
            if (value['metadata']['uid'] != self.data[target]['metadata']['uid']
                    or value['metadata']['resourceVersion'] != self.data[target]['metadata']['resourceVersion']):
                raise urllib.error.HTTPError(path, 409, 'Conflict', {}, None)
            self.data[target]['status'] = copy.deepcopy(value['status'])
            return copy.deepcopy(self.data[target])
        if method == 'PATCH':
            current = self.data[path]
            if value['metadata']['uid'] != current['metadata']['uid'] or value['metadata']['resourceVersion'] != current['metadata']['resourceVersion']:
                raise urllib.error.HTTPError(path, 409, 'Conflict', {}, None)
            current['automountServiceAccountToken'] = value['automountServiceAccountToken']
            current['metadata'].setdefault('labels', {}).update(value['metadata']['labels'])
            return copy.deepcopy(current)
        if self.fail_kind == value['kind']:
            self.fail_kind = None
            raise urllib.error.HTTPError(path, 500, 'InjectedCrash', {}, None)
        target = path + '/' + value['metadata']['name'] if method == 'POST' else path
        current = self.data.get(target)
        if current is not None and method == 'POST':
            raise urllib.error.HTTPError(path, 409, 'Conflict', {}, None)
        if method == 'PUT' and (value['metadata']['uid'] != current['metadata']['uid']
                               or value['metadata']['resourceVersion'] != current['metadata']['resourceVersion']):
            raise urllib.error.HTTPError(path, 409, 'Conflict', {}, None)
        self.serial += 1
        result = copy.deepcopy(value)
        result['metadata'].update(uid=current['metadata']['uid'] if current else 'uid-' + str(self.serial),
                                  resourceVersion=str(self.serial), generation=current['metadata']['generation'] if current else 1)
        if result['kind'] == 'Agent':
            result['status'] = {'conditions': [condition('Accepted'), condition('Ready')]}
        self.data[target] = result
        return copy.deepcopy(result)


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.kube = FakeKube()
        self.profile = load_profile()
        self.controller = Onboarding(self.kube, self.profile)
        skill = yaml.safe_load((ROOT / 'imports/aks-known-issues/skill.yaml').read_text())
        knowledge = yaml.safe_load((ROOT / 'knowledge/knowledgebase.yaml').read_text())
        for resource, payload, kind, label, prefix, plural in [
                (skill, ROOT / 'imports/aks-known-issues/payload', 'Skill', 'skill', '', 'skills'),
                (knowledge, ROOT / 'knowledge/payload', 'KnowledgeBase', 'knowledge-base', 'kb-', 'knowledgebases')]:
            resource['metadata'].update(uid=kind + '-uid', generation=1)
            spec = resource['spec']
            cm_name = prefix + resource['metadata']['name'] + '-' + spec['contentSha256'][:16]
            resource['status'] = {'conditions': [condition('Ready')], 'contentSha256': spec['contentSha256'],
                                  'observedSourceRevision': 'sha1:' + spec['sourceCommit'], 'configMapRef': {'name': cm_name}}
            self.kube.data[f'/apis/{API}/namespaces/skills-demo/{plural}/' + resource['metadata']['name']] = resource
            source = {'metadata': {'generation': 1, 'uid': spec['sourceRef']['name'] + '-uid'}, 'spec': {'ref': {'commit': spec['sourceCommit']}},
                      'status': {'conditions': [condition('Ready')], 'artifact': {'revision': 'sha1:' + spec['sourceCommit']}}}
            self.kube.data['/apis/source.toolkit.fluxcd.io/v1/namespaces/skills-demo/gitrepositories/' + spec['sourceRef']['name']] = source
            cm = {'metadata': {'uid': 'cm-' + kind, 'ownerReferences': [{'apiVersion': API, 'kind': kind,
                'name': resource['metadata']['name'], 'uid': resource['metadata']['uid'], 'controller': True}],
                'annotations': {GROUP + '/digest': spec['contentSha256']}, 'labels': {GROUP + '/' + label: resource['metadata']['name']}},
                'immutable': True, 'data': {f'file{i:02}': (payload / path).read_text() for i, path in enumerate(sorted(spec['files']))}}
            self.kube.data['/api/v1/namespaces/skills-demo/configmaps/' + cm_name] = cm
        self.skill = skill
        self.knowledge = knowledge
        self.pin = lambda resource: {'name': resource['metadata']['name'], 'sourceCommit': resource['spec']['sourceCommit'], 'contentSha256': resource['spec']['contentSha256']}
        self.document = {'apiVersion': API, 'kind': 'HostedAgent', 'metadata': {'name': 'aks-team-v1', 'namespace': 'skills-demo',
                          'uid': 'hosted-owner', 'generation': 1, 'resourceVersion': '1'}, 'spec': {'owner': {'team': 'platform-demo'},
                          'purpose': 'Synthetic AKS documentation', 'instructions': 'Use reviewed documents and cite sources.',
                          'runtimeProfile': self.profile['runtimeProfile'], 'modelProfile': self.profile['modelProfile'],
                          'skillRefs': [self.pin(skill)], 'knowledgeBaseRefs': [self.pin(knowledge)], 'toolGrantRefs': []}}
        self.hosted_path = self.controller.hosted + '/aks-team-v1'
        self.kube.data[self.hosted_path] = self.document
        self.model_path = '/apis/kagent.dev/v1alpha2/namespaces/skills-demo/modelconfigs/' + self.profile['modelConfig']['name']
        self.kube.data[self.model_path] = {'spec': {'demo': 'pinned'}}
        self.profile['modelConfig']['specSha256'] = canonical(self.kube.data[self.model_path]['spec'])

    def reconcile(self):
        self.controller.reconcile(copy.deepcopy(self.kube.data[self.hosted_path]))
        return self.kube.data[self.hosted_path]['status']

    def children(self):
        return [(p, v) for p, v in self.kube.data.items() if v.get('metadata', {}).get('name', '').startswith('hosted-aks-team-v1')]

    def reason(self):
        return next(c['reason'] for c in self.kube.data[self.hosted_path]['status']['conditions'] if c['type'] == 'Ready')

    def test_valid_request_creates_owned_account_policy_agent_in_order(self):
        self.reconcile()
        posts = [v for _, m, v in self.kube.writes if m == 'POST']
        self.assertEqual([v['kind'] for v in posts], ['ServiceAccount', 'NetworkPolicy', 'Agent'])
        self.assertFalse(posts[0]['automountServiceAccountToken'])
        self.assertEqual(posts[0]['metadata']['name'], posts[-1]['metadata']['name'])
        self.assertEqual(posts[-1]['spec']['declarative']['deployment']['serviceAccountName'], posts[0]['metadata']['name'])
        self.assertEqual(posts[-1]['spec']['declarative']['tools'], [])
        self.assertTrue(all(v['metadata']['ownerReferences'][0]['uid'] == 'hosted-owner' for v in posts))
        self.assertEqual(self.reason(), 'AgentReady')

    def test_second_reconciliation_writes_nothing(self):
        self.reconcile(); self.kube.writes.clear(); self.reconcile()
        self.assertEqual(self.kube.writes, [])

    def test_all_collisions_preflight_before_any_child_creation(self):
        for kind in ['ServiceAccount', 'NetworkPolicy', 'Agent']:
            with self.subTest(kind=kind):
                path = self.controller.collection(kind) + '/hosted-aks-team-v1'
                self.kube.data[path] = {'kind': kind, 'metadata': {'name': 'hosted-aks-team-v1', 'ownerReferences': [],
                                                                              'labels': {GROUP + '/hosted-agent': 'aks-team-v1'}}}
                self.reconcile()
                self.assertEqual(self.reason(), 'ManagedObjectCollision')
                self.assertFalse(any(method in {'POST', 'PUT'} for _, method, _ in self.kube.writes))
                del self.kube.data[path]
                self.kube.writes.clear()

    def test_crash_after_account_creation_converges_without_duplicate_account(self):
        self.kube.fail_kind = 'NetworkPolicy'
        self.reconcile()
        self.assertEqual(self.reason(), 'DependencyHTTP500')
        self.reconcile()
        self.assertEqual(self.reason(), 'AgentReady')
        self.assertEqual(sum(m == 'POST' and v['kind'] == 'ServiceAccount' for _, m, v in self.kube.writes), 1)

    def test_owned_agent_drift_is_replaced_completely(self):
        self.reconcile()
        path = self.controller.collection('Agent') + '/hosted-aks-team-v1'
        self.kube.data[path]['spec']['declarative']['deployment']['imageRegistry'] = 'unapproved.example.invalid'
        self.kube.data[path]['spec']['declarative']['tools'] = [{'type': 'McpServer'}]
        self.reconcile()
        actual = self.kube.data[path]['spec']['declarative']
        self.assertNotIn('imageRegistry', actual['deployment'])
        self.assertEqual(actual['tools'], [])

    def test_kagent_account_owner_lineage_is_accepted_without_rewriting(self):
        self.reconcile()
        agent = self.kube.data[self.controller.collection('Agent') + '/hosted-aks-team-v1']
        account = self.kube.data[self.controller.collection('ServiceAccount') + '/hosted-aks-team-v1']
        owner = {'apiVersion': agent['apiVersion'], 'kind': 'Agent', 'name': agent['metadata']['name'],
                 'uid': agent['metadata']['uid'], 'controller': True, 'blockOwnerDeletion': True}
        account['metadata']['ownerReferences'] = [owner]
        account['metadata']['labels']['app'] = 'kagent'
        self.kube.writes.clear(); self.reconcile()
        self.assertEqual(self.reason(), 'AgentReady')
        self.assertEqual(self.kube.writes, [])
        account['automountServiceAccountToken'] = True
        self.reconcile()
        self.assertFalse(account['automountServiceAccountToken'])
        self.assertEqual(account['metadata']['ownerReferences'], [owner])
        self.assertEqual(account['metadata']['labels']['app'], 'kagent')

    def test_wrong_agent_uid_cannot_authorize_account_adoption(self):
        self.reconcile()
        account = self.kube.data[self.controller.collection('ServiceAccount') + '/hosted-aks-team-v1']
        account['metadata']['ownerReferences'] = [{'apiVersion': 'kagent.dev/v1alpha2', 'kind': 'Agent', 'name': 'hosted-aks-team-v1',
                                                   'uid': 'foreign-agent', 'controller': True, 'blockOwnerDeletion': True}]
        self.reconcile()
        self.assertEqual(self.reason(), 'ManagedObjectCollision')

    def test_new_hosted_uid_does_not_adopt_old_children(self):
        self.reconcile(); self.kube.writes.clear()
        self.kube.data[self.hosted_path]['metadata']['uid'] = 'replacement-owner'
        self.reconcile()
        self.assertEqual(self.reason(), 'ManagedObjectCollision')
        self.assertFalse(any(m == 'PUT' for _, m, _ in self.kube.writes))

    def test_dependency_loss_marks_unready_and_preserves_children(self):
        self.reconcile(); before = copy.deepcopy(self.children())
        self.skill['status']['conditions'][0]['observedGeneration'] = 0
        self.reconcile()
        self.assertEqual(self.reason(), 'ReleaseNotCurrentAndPinned')
        self.assertEqual(before, self.children())

    def test_deleting_dependencies_cannot_gain_a_consumer(self):
        paths = [f'/apis/{API}/namespaces/skills-demo/skills/' + self.skill['metadata']['name'],
                 '/apis/source.toolkit.fluxcd.io/v1/namespaces/skills-demo/gitrepositories/' + self.skill['spec']['sourceRef']['name'],
                 '/api/v1/namespaces/skills-demo/configmaps/' + self.skill['status']['configMapRef']['name'], self.model_path]
        for path in paths:
            with self.subTest(path=path):
                self.kube.data[path].setdefault('metadata', {})['deletionTimestamp'] = '2026-10-21T00:00:00Z'
                self.reconcile()
                self.assertEqual(self.reason(), 'DependencyDeleting')
                self.assertEqual(self.children(), [])
                del self.kube.data[path]['metadata']['deletionTimestamp']

    def test_model_drift_blocks_creation(self):
        self.kube.data[self.model_path]['spec']['changed'] = True
        self.reconcile()
        self.assertEqual(self.reason(), 'ModelProfileMismatch')
        self.assertEqual(self.children(), [])

    def test_source_revision_drift_blocks_creation(self):
        path = '/apis/source.toolkit.fluxcd.io/v1/namespaces/skills-demo/gitrepositories/' + self.skill['spec']['sourceRef']['name']
        self.kube.data[path]['status']['artifact']['revision'] = 'sha1:' + '0' * 40
        self.reconcile()
        self.assertEqual(self.reason(), 'SourceNotCurrentAndPinned')
        self.assertEqual(self.children(), [])

    def test_configmap_tamper_blocks_creation(self):
        path = '/api/v1/namespaces/skills-demo/configmaps/' + self.knowledge['status']['configMapRef']['name']
        self.kube.data[path]['data']['file00'] += 'Tampered'
        self.reconcile()
        self.assertEqual(self.reason(), 'ContentHashMismatch')
        self.assertEqual(self.children(), [])

    def test_configmap_wrong_owner_blocks_creation(self):
        path = '/api/v1/namespaces/skills-demo/configmaps/' + self.knowledge['status']['configMapRef']['name']
        self.kube.data[path]['metadata']['ownerReferences'][0]['uid'] = 'foreign'
        self.reconcile()
        self.assertEqual(self.reason(), 'ContentOwnershipMismatch')

    def test_old_agent_generation_cannot_make_hosted_ready(self):
        self.reconcile()
        path = self.controller.collection('Agent') + '/hosted-aks-team-v1'
        self.kube.data[path]['metadata']['generation'] = 2
        self.reconcile()
        self.assertEqual(self.reason(), 'AgentNotReady')

    def test_old_request_cannot_write_replacement_status(self):
        old = copy.deepcopy(self.document)
        self.document['metadata'].update(uid='new-owner', resourceVersion='200')
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.controller.status(old, True, True, 'AgentReady')
        self.assertEqual(raised.exception.code, 409)
        self.assertNotIn('status', self.document)

    def test_operational_grants_are_rejected(self):
        self.document['spec']['toolGrantRefs'] = ['unapproved-tool']
        with self.assertRaisesRegex(Rejected, 'OperationalToolsNotSupported'):
            parse_intent(self.document, self.profile)

    def test_arbitrary_runtime_fields_are_rejected(self):
        self.document['spec']['image'] = 'unapproved.example.invalid/agent'
        with self.assertRaisesRegex(Rejected, 'InvalidContract'):
            parse_intent(self.document, self.profile)

    def test_cross_namespace_reference_is_rejected(self):
        self.document['spec']['skillRefs'][0]['namespace'] = 'another'
        with self.assertRaisesRegex(Rejected, 'InvalidReleasePin'):
            parse_intent(self.document, self.profile)


if __name__ == '__main__':
    unittest.main()
