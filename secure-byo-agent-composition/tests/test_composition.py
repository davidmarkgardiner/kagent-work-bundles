import copy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'composition'
sys.path.insert(0, str(ROOT))
from compose import API, KIND, FINALIZER, Rejected, crd, generate, rgd
from controller import Controller, collection, managed_body, same_managed_body


def profile():
    return {'name': 'reviewed-v1', 'namespace': 'secure-byo-hosted', 'resources': [
        {'apiVersion': 'api.kagent.dev/v1alpha3', 'kind': 'AgentTemplate',
         'metadata': {'name': '{{NAME}}-template'}, 'spec': {'modelConfig': {'name': 'approved-model'},
         'systemPrompt': '{{INSTRUCTIONS}}', 'tools': [{'mcp': {'server': {'kind': 'RemoteMCPServer', 'name': 'approved-mcp'}, 'tools': ['get_demo_status']}}]}},
        {'apiVersion': 'api.kagent.dev/v1alpha3', 'kind': 'Agent', 'metadata': {'name': '{{NAME}}'},
         'spec': {'harnessRef': {'name': 'approved-harness'}, 'template': {'ref': {'name': '{{NAME}}-template'}}}}]}


def request():
    return {'apiVersion': API, 'kind': KIND, 'metadata': {'name': 'reader', 'namespace': 'secure-byo-hosted',
        'uid': 'request-1', 'generation': 1, 'resourceVersion': '1'},
        'spec': {'profileRef': 'reviewed-v1', 'instructions': 'Read bounded evidence.'}}


class Fake:
    def __init__(self):
        self.objects = {}
        self.calls = []

    def get(self, path):
        return copy.deepcopy(self.objects.get(path))

    def call(self, method, path, data=None):
        self.calls.append((method, path, copy.deepcopy(data)))
        if method == 'DELETE':
            self.objects.pop(path)
            return {}
        if method == 'POST':
            path += '/' + data['metadata']['name']
            data = copy.deepcopy(data)
            data['metadata'].update(uid='child-' + str(len(self.objects)), resourceVersion='1', generation=1)
            self.objects[path] = data
            return data
        if method == 'PUT':
            self.objects[path] = copy.deepcopy(data)
            return data
        return self.get(path)


class Composition(unittest.TestCase):
    def test_owner_and_native_wiring(self):
        objects = generate(profile(), request())
        self.assertEqual(objects[1]['spec']['template']['ref']['name'], objects[0]['metadata']['name'])
        self.assertEqual(objects[0]['metadata']['ownerReferences'][0]['uid'], 'request-1')
        self.assertEqual(objects[0]['spec']['tools'][0]['mcp']['tools'], ['get_demo_status'])

    def test_owner_cannot_add_authority_fields(self):
        for field in ['namespace', 'modelConfig', 'tools', 'serviceAccount', 'url', 'active', 'resources']:
            req = request()
            req['spec'][field] = 'untrusted'
            with self.assertRaises(Rejected):
                generate(profile(), req)

    def test_wrong_namespace_profile_and_missing_uid_rejected(self):
        for mutate in [lambda r: r['metadata'].update(namespace='another-team'),
                       lambda r: r['spec'].update(profileRef='admin'),
                       lambda r: r['metadata'].pop('uid')]:
            req = request()
            mutate(req)
            with self.assertRaises(Rejected):
                generate(profile(), req)

    def test_profile_cannot_create_cross_namespace_or_privilege_kinds(self):
        p = profile()
        p['resources'][0]['metadata']['namespace'] = 'kagent'
        with self.assertRaises(Rejected): generate(p, request())
        p = profile()
        p['resources'][0]['kind'] = 'ClusterRole'
        with self.assertRaises(Rejected): generate(p, request())

    def test_plain_json_preview_preserves_owner_instructions(self):
        req = request()
        req['spec']['instructions'] = 'Quote "x"; $value and ${schema.spec.nope} are content.'
        objects = generate(profile(), req, owner=False)
        self.assertEqual(objects[0]['spec']['systemPrompt'], req['spec']['instructions'])
        self.assertNotIn('ownerReferences', objects[0]['metadata'])

    def test_rgd_uses_same_fixed_objects(self):
        graph = rgd(profile())
        self.assertEqual(len(graph['spec']['resources']), 2)
        node = graph['spec']['resources'][0]['template']
        self.assertEqual(node['spec']['modelConfig']['name'], 'approved-model')
        self.assertEqual(node['spec']['systemPrompt'], '${schema.spec.instructions}')
        self.assertNotIn('ownerReferences', node['metadata'])
        agent_node = graph['spec']['resources'][1]
        self.assertEqual(len(agent_node['readyWhen']), 6)
        self.assertTrue(any('latestSuccessfulRevision' in e for e in agent_node['readyWhen']))
        self.assertTrue(all('observedGeneration' in e for e in agent_node['readyWhen'][:5]))

    def test_hosted_crd_immutable(self):
        spec = crd()['spec']['versions'][0]['schema']['openAPIV3Schema']['properties']['spec']
        self.assertNotIn('additionalProperties', spec)
        self.assertEqual(set(spec['properties']), {'profileRef', 'instructions'})
        self.assertEqual(spec['x-kubernetes-validations'][0]['rule'], 'self == oldSelf')

    def test_collision_preflight_writes_nothing(self):
        fake = Fake()
        req = request()
        req['metadata']['finalizers'] = [FINALIZER]
        child = generate(profile(), req)[1]
        child['metadata']['ownerReferences'][0]['uid'] = 'foreign-request'
        fake.objects[collection(child['apiVersion'], req['metadata']['namespace'], child['kind']) + '/' + child['metadata']['name']] = child
        with self.assertRaises(Rejected): Controller(fake, profile()).reconcile(req)
        self.assertFalse(fake.calls)

    def test_same_name_parent_replacement_cannot_adopt(self):
        fake = Fake()
        req = request()
        for child in generate(profile(), req):
            path = collection(child['apiVersion'], req['metadata']['namespace'], child['kind']) + '/' + child['metadata']['name']
            fake.objects[path] = child
        req['metadata']['uid'] = 'request-2'
        with self.assertRaises(Rejected): Controller(fake, profile()).reconcile(req)
        self.assertFalse(fake.calls)

    def test_finalizer_precedes_child_creation(self):
        fake = Fake()
        Controller(fake, profile()).reconcile(request())
        self.assertEqual([v[0] for v in fake.calls], ['PUT'])
        self.assertEqual(fake.calls[0][2]['metadata']['finalizers'], [FINALIZER])

    def test_profile_change_cannot_silently_replace_capabilities(self):
        fake = Fake()
        req = request()
        req['status'] = {'profileSha256': 'old-profile-hash'}
        with self.assertRaisesRegex(Rejected, 'ProfileChanged'):
            Controller(fake, profile()).reconcile(req)
        self.assertFalse(fake.calls)

    def test_service_allocation_survives_update_and_stable_reconcile(self):
        desired = {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'frontdoor'},
            'spec': {'selector': {'app': 'frontdoor'}, 'ports': [{'port': 8080}]}}
        live = copy.deepcopy(desired)
        live['metadata']['labels'] = {'controller-added': 'kept'}
        live['spec'].update(clusterIP='192.0.2.9', clusterIPs=['192.0.2.9'], ipFamilies=['IPv4'],
            ipFamilyPolicy='SingleStack', type='ClusterIP', sessionAffinity='None', internalTrafficPolicy='Cluster')
        live['spec']['ports'][0].update(protocol='TCP', targetPort=8080)
        body = managed_body(desired, live)
        self.assertTrue(same_managed_body(body, live))
        self.assertEqual(body['spec']['clusterIP'], '192.0.2.9')
        live['spec']['externalIPs'] = ['203.0.113.1']
        body = managed_body(desired, live)
        self.assertFalse(same_managed_body(body, live))
        self.assertNotIn('externalIPs', body['spec'])

    def test_deployment_defaults_stable_but_foreign_privilege_removed(self):
        desired = {'kind': 'Deployment', 'metadata': {'name': 'frontdoor'}, 'spec': {
            'replicas': 1, 'template': {'metadata': {'labels': {'app': 'frontdoor'}},
                'spec': {'containers': [{'name': 'frontdoor', 'image': 'reviewed@sha256:' + 'a' * 64}],
                    'serviceAccountName': 'approved'}}}}
        live = copy.deepcopy(desired)
        live['spec'].update(revisionHistoryLimit=10, progressDeadlineSeconds=600,
            strategy={'type': 'RollingUpdate', 'rollingUpdate': {'maxSurge': '25%', 'maxUnavailable': '25%'}})
        live['spec']['template']['metadata']['creationTimestamp'] = None
        pod = live['spec']['template']['spec']
        pod.update(restartPolicy='Always', dnsPolicy='ClusterFirst', schedulerName='default-scheduler', terminationGracePeriodSeconds=30)
        pod['containers'][0].update(imagePullPolicy='IfNotPresent', terminationMessagePath='/dev/termination-log', terminationMessagePolicy='File')
        self.assertTrue(same_managed_body(managed_body(desired, live), live))
        pod['containers'][0]['securityContext'] = {'privileged': True}
        body = managed_body(desired, live)
        self.assertFalse(same_managed_body(body, live))
        self.assertNotIn('securityContext', body['spec']['template']['spec']['containers'][0])

    def test_second_reconcile_is_write_free_and_old_revision_unready(self):
        fake = Fake()
        req = request()
        req['metadata']['finalizers'] = [FINALIZER]
        controller = Controller(fake, profile())
        controller.reconcile(req)
        status_path = controller.requests + '/reader/status'
        req['status'] = fake.objects[status_path]['status']
        fake.calls.clear()
        controller.reconcile(req)
        self.assertFalse(fake.calls)
        agent_path = collection('api.kagent.dev/v1alpha3', req['metadata']['namespace'], 'Agent') + '/reader'
        fake.objects[agent_path]['status'] = {'desiredRevision': 'new', 'latestSuccessfulRevision': 'old', 'conditions': [
            {'type': k, 'status': 'True', 'observedGeneration': 1} for k in
            ('Accepted', 'ResolvedRefs', 'Compatible', 'EgressPoliciesApplied', 'Ready')]}
        controller.reconcile(req)
        self.assertEqual(fake.objects[status_path]['status']['conditions'][0]['status'], 'False')

    def test_delete_pins_uids(self):
        fake = Fake()
        req = request()
        req['metadata'].update(deletionTimestamp='2026-11-03T00:00:00Z', finalizers=[FINALIZER])
        for child in generate(profile(), req):
            child['metadata']['uid'] = 'child-' + child['kind']
            fake.objects[collection(child['apiVersion'], req['metadata']['namespace'], child['kind']) + '/' + child['metadata']['name']] = child
        Controller(fake, profile()).reconcile(req)
        deletes = [v for v in fake.calls if v[0] == 'DELETE']
        self.assertEqual(len(deletes), 2)
        self.assertTrue(all(v[2]['preconditions']['uid'].startswith('child-') for v in deletes))
        self.assertEqual(fake.calls[-1][2]['metadata']['finalizers'], [])

    def test_delete_changed_profile_retires_old_inventory(self):
        fake = Fake()
        req = request()
        req['metadata'].update(deletionTimestamp='2026-11-03T00:00:00Z', finalizers=[FINALIZER])
        old = generate(profile(), req)[0]
        old['metadata'].update(name='previous-template', uid='old-template-uid')
        path = collection(old['apiVersion'], req['metadata']['namespace'], old['kind']) + '/previous-template'
        fake.objects[path] = old
        req['status'] = {'profileSha256': 'prior-profile', 'inventory': [{'apiVersion': old['apiVersion'],
            'kind': old['kind'], 'name': 'previous-template', 'uid': 'old-template-uid'}]}
        Controller(fake, profile()).reconcile(req)
        self.assertIsNone(fake.get(path))
        self.assertEqual(fake.calls[-1][2]['metadata']['finalizers'], [])


if __name__ == '__main__':
    unittest.main()
