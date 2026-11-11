import copy
import hashlib
import json
from pathlib import Path
import unittest
import urllib.error

import yaml
from contract import (API, GROUP, ROOT, Rejected, code_digest, digest, profile, request_spec, verify_capture)
from eval_controller import Controller, executor_job, owner, run_name
from render import render

UID = 'b7d10585-4d09-4571-bbab-71c205fc497e'


def fixtures():
    scenario = yaml.safe_load((ROOT / 'fixtures/scenario.yaml').read_text())
    scenario['metadata'].update(uid='scenario-uid', generation=1)
    agent = {'metadata': {'uid': 'agent-uid', 'generation': 1}, 'spec': {'declarative': {'tools': []}},
             'status': {'conditions': [{'type': 'Ready', 'status': 'True', 'observedGeneration': 1}]}}
    scenario['spec']['agentSpecSha256'] = digest(agent['spec'])
    config = {'evaluationNamespace': 'skill-eval-poc', 'targetNamespace': 'skills-demo',
              'controllerURL': 'http://kagent-controller.kagent.svc.cluster.local:8083',
              'scenarioNames': [scenario['metadata']['name']], 'targetPodName': 'fixed-agent-pod',
              'targetPodUID': 'fixed-pod-uid', 'image': 'registry.example/eval@sha256:' + 'a' * 64,
              'labLocalImage': False}
    request = {'apiVersion': API, 'kind': 'SkillEvaluation',
               'metadata': {'name': 'unit-run', 'namespace': 'skill-eval-poc', 'uid': UID,
                            'resourceVersion': '1', 'generation': 1},
               'spec': {'scenarioRef': {'name': scenario['metadata']['name'], 'uid': 'scenario-uid',
                                        'specSha256': digest(scenario['spec'])}}}
    content = {'SKILL.md': (ROOT / 'fixtures/SKILL.md').read_text(),
               'references/error-code-map.md': (ROOT / 'fixtures/error-code-map.md').read_text()}
    hashes = {p: hashlib.sha256(s.encode()).hexdigest() for p, s in content.items()}
    identity = {'scenarioGeneration': 1, 'scenarioUID': 'scenario-uid', 'scenarioSpecSha256': digest(scenario['spec']),
                'podUID': config['targetPodUID'], 'podName': config['targetPodName'],
                'mountedFileHashes': hashes, 'skillUID': 'skill-uid', 'configMapUID': 'cm-uid',
                'sourceCommit': 'b' * 40, 'containerID': 'containerd://test', 'restartCount': 0,
                'imageID': 'test-image'}
    context = 'se-' + UID
    a2a = json.loads((ROOT / 'fixtures/a2a.json').read_text())
    # Historical native trace is replayed only in unit tests. Context is rebound to
    # the fixture run, never represented as fresh live execution.
    a2a['result']['contextId'] = context
    a2a['result']['metadata']['kagent_session_id'] = context
    for message in a2a['result']['history']:
        message['contextId'] = context
    capture = {'version': 1, 'requestUID': UID, 'contextID': context, 'codeSha256': code_digest(),
               'scenario': copy.deepcopy(scenario), 'before': {'identity': identity, 'content': content},
               'after': {'identity': copy.deepcopy(identity), 'content': content}, 'a2a': a2a}
    skill = {'apiVersion': 'skills.platform.kagent.dev/v1alpha1', 'kind': 'Skill',
             'metadata': {'name': scenario['spec']['skillRef']['name'], 'uid': 'skill-uid', 'generation': 1},
             'spec': {'contentSha256': scenario['spec']['skillContentSha256'], 'files': hashes,
                      'sourceCommit': 'b' * 40, 'skillName': 'aks-known-issues', 'sourceRef': {'name': 'skill-source'}},
             'status': {'conditions': [{'type': 'Ready', 'status': 'True', 'observedGeneration': 1}],
                        'contentSha256': scenario['spec']['skillContentSha256'], 'configMapRef': {'name': 'skill-content'}}}
    source = {'metadata': {'uid': 'source-uid', 'generation': 1}, 'spec': {'ref': {'commit': 'b' * 40}},
              'status': {'artifact': {'revision': 'sha1:' + 'b' * 40},
                         'conditions': [{'type': 'Ready', 'status': 'True', 'observedGeneration': 1}]}}
    extra = {'agentUID': 'agent-uid', 'agentGeneration': 1, 'agentSpecSha256': digest(agent['spec']),
             'skillGeneration': 1, 'skillContentSha256': skill['spec']['contentSha256'],
             'skillSpecSha256': digest(skill['spec']), 'sourceUID': 'source-uid', 'sourceGeneration': 1}
    capture['before']['identity'].update(extra)
    capture['after']['identity'].update(extra)
    cm = {'metadata': {'uid': 'cm-uid', 'ownerReferences': [{
        'apiVersion': skill['apiVersion'], 'kind': 'Skill', 'name': skill['metadata']['name'],
        'uid': 'skill-uid', 'controller': True}]}, 'immutable': True,
        'data': {f'file{i:02}': content[p] for i, p in enumerate(sorted(content))}}
    pod = {'metadata': {'name': config['targetPodName'], 'uid': config['targetPodUID']},
           'spec': {'containers': [{'name': 'agent'}]},
           'status': {'containerStatuses': [{'ready': True, 'containerID': 'containerd://test', 'restartCount': 0, 'imageID': 'test-image'}]}}
    return config, request, scenario, content, capture, skill, cm, pod, agent, source


class FakeAPI:
    def __init__(self, config, request, scenario, content, capture, skill, cm, pod, agent, source):
        self.docs = {}
        self.calls = []
        self.config = config
        self.request_path = f'/apis/{API}/namespaces/skill-eval-poc/skillevaluations/' + request['metadata']['name']
        self.docs[self.request_path] = copy.deepcopy(request)
        prefix = '/apis/skills.platform.kagent.dev/v1alpha1/namespaces/skills-demo/'
        self.docs[prefix + 'goldenscenarios/' + scenario['metadata']['name']] = scenario
        self.docs[prefix + 'skills/' + skill['metadata']['name']] = skill
        self.docs['/apis/kagent.dev/v1alpha2/namespaces/skills-demo/agents/' + scenario['spec']['agentRef']['name']] = agent
        self.docs['/apis/source.toolkit.fluxcd.io/v1/namespaces/skills-demo/gitrepositories/skill-source'] = source
        self.docs['/api/v1/namespaces/skills-demo/configmaps/skill-content'] = cm
        self.docs['/api/v1/namespaces/skills-demo/pods/' + pod['metadata']['name']] = pod
        self.capture = capture
        self.create_uncertain = False
        self.conflict = False
        self.executor_pods = []

    def call(self, path, method='GET', value=None, raw=False):
        self.calls.append((path, method, copy.deepcopy(value)))
        if method == 'PATCH':
            current = self.docs[self.request_path]
            if self.conflict or value['metadata']['resourceVersion'] != current['metadata']['resourceVersion']:
                raise urllib.error.HTTPError(path, 409, 'conflict', {}, None)
            current['status'] = copy.deepcopy(value['status'])
            current['metadata']['resourceVersion'] = str(int(current['metadata']['resourceVersion']) + 1)
            return copy.deepcopy(current)
        if method == 'POST':
            target = path + '/' + value['metadata']['name']
            if target in self.docs:
                raise urllib.error.HTTPError(path, 409, 'exists', {}, None)
            document = copy.deepcopy(value)
            document['metadata']['uid'] = 'job-uid' if value['kind'] == 'Job' else 'result-uid'
            self.docs[target] = document
            if value['kind'] == 'Job' and self.create_uncertain:
                raise OSError('accepted but response lost')
            return copy.deepcopy(document)
        if '/log?' in path:
            return json.dumps(self.capture)
        if '?labelSelector=' in path:
            return {'items': copy.deepcopy(self.executor_pods)}
        if path not in self.docs:
            raise urllib.error.HTTPError(path, 404, 'not found', {}, None)
        return copy.deepcopy(self.docs[path])

    def current(self):
        return copy.deepcopy(self.docs[self.request_path])

    def job_posts(self):
        return sum(method == 'POST' and path.endswith('/jobs') for path, method, _ in self.calls)

    def finish(self, controller):
        request = self.current()
        path = controller.jobs + '/' + run_name(request)
        job = self.docs[path]
        job['status'] = {'conditions': [{'type': 'Complete', 'status': 'True'}]}
        self.executor_pods = [{'metadata': {'name': 'executor-one', 'uid': 'executor-uid', 'ownerReferences': [
            {'kind': 'Job', 'uid': job['metadata']['uid'], 'controller': True}]},
            'spec': copy.deepcopy(job['spec']['template']['spec']),
            'status': {'phase': 'Succeeded', 'containerStatuses': [{'name': 'worker', 'restartCount': 0,
                       'imageID': 'sha256:executor-image', 'state': {'terminated': {'exitCode': 0}}}]}}]


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixtures()
        self.config, self.request, self.scenario, self.content, self.capture, self.skill, self.cm, self.pod, self.agent, self.source = self.fx
        self.api = FakeAPI(*copy.deepcopy(self.fx))
        self.controller = Controller(self.api, self.config)

    def result(self, capture=None, **kwargs):
        return verify_capture(capture or self.capture, self.request, self.config, self.scenario,
                              self.content, self.pod, code_digest())

    def test_real_native_trace_checks_pass_offline(self):
        receipt = self.result()
        self.assertEqual(receipt['phase'], 'Passed')
        self.assertEqual(receipt['semanticScore'], 'not_scored')
        self.assertEqual(len(receipt['toolCalls']), 2)

    def test_completed_answer_missing_terms_fails_not_errors(self):
        self.capture['a2a']['result']['artifacts'][0]['parts'][0]['text'] = 'No required answer'
        self.assertEqual(self.result()['phase'], 'Failed')

    def test_missing_tools_rejected_even_with_good_answer(self):
        history = self.capture['a2a']['result']['history']
        self.capture['a2a']['result']['history'] = [m for m in history if m['role'] == 'user']
        with self.assertRaisesRegex(Rejected, 'RequiredToolEvidenceMissing'):
            self.result()

    def test_wrong_pin_context_code_and_forged_pass_rejected(self):
        for field, value in [('requestUID', 'wrong'), ('contextID', 'stale'), ('codeSha256', '0' * 64), ('phase', 'Passed')]:
            with self.subTest(field=field):
                altered = copy.deepcopy(self.capture)
                altered[field] = value
                with self.assertRaises(Rejected):
                    self.result(altered)
        altered = copy.deepcopy(self.capture)
        altered['scenario']['spec']['prompt'] = 'changed'
        with self.assertRaisesRegex(Rejected, 'ScenarioPinMismatch'):
            self.result(altered)

    def test_content_from_worker_cannot_override_controller_bytes(self):
        self.capture['before']['content'] = {'SKILL.md': 'forged'}
        with self.assertRaisesRegex(Rejected, 'SnapshotPinMismatch'):
            self.result()

    def test_changed_after_snapshot_rejected(self):
        self.capture['after']['identity']['restartCount'] = 1
        with self.assertRaisesRegex(Rejected, 'DeploymentChanged'):
            self.result()

    def test_unknown_request_and_profile_fields_rejected(self):
        with self.assertRaises(Rejected):
            request_spec({'scenarioRef': self.request['spec']['scenarioRef'], 'command': 'anything'})
        with self.assertRaises(Rejected):
            profile({**self.config, 'env': {'TOKEN': 'unallowed'}})
        with self.assertRaisesRegex(Rejected, 'ImageDigestRequired'):
            profile({**self.config, 'image': 'mutable:latest'})

    def test_profile_accepts_registry_port_and_rejects_invalid_namespace(self):
        image = 'registry.example.invalid:5000/eval@sha256:' + 'a' * 64
        self.assertEqual(profile({**self.config, 'image': image})['image'], image)
        with self.assertRaisesRegex(Rejected, 'InvalidNamespace'):
            profile({**self.config, 'targetNamespace': 'invalid-'})

    def test_one_post_then_terminal_capture_and_receipt(self):
        self.controller.reconcile(self.api.current())
        self.assertEqual(self.api.current()['status']['phase'], 'Running')
        self.api.finish(self.controller)
        self.controller.reconcile(self.api.current())
        status = self.api.current()['status']
        self.assertEqual(status['phase'], 'Passed')
        self.assertNotIn('a2a', status)
        for suffix in ['capture', 'receipt']:
            stored = self.api.docs[self.controller.cms + '/' + run_name(self.request) + '-' + suffix]
            self.assertTrue(stored['immutable'])
        self.controller.reconcile(self.api.current())
        self.assertEqual(self.api.job_posts(), 1)

    def test_restart_after_fence_without_job_is_error_no_post(self):
        self.controller.status(self.request, 'LaunchRecorded', frozenSpecSha256=digest(self.request['spec']),
            profileSha256=digest(self.config), codeSha256=code_digest(), contextID='se-' + UID)
        Controller(self.api, self.config).reconcile(self.api.current())
        self.assertEqual(self.api.current()['status']['phase'], 'Error')
        self.assertEqual(self.api.job_posts(), 0)

    def test_restart_after_post_recovers_existing_job_without_post(self):
        self.controller.reconcile(self.api.current())
        self.api.docs[self.api.request_path]['status']['phase'] = 'LaunchRecorded'
        self.api.docs[self.api.request_path]['status'].pop('jobUID')
        Controller(self.api, self.config).reconcile(self.api.current())
        self.assertEqual(self.api.current()['status']['phase'], 'Running')
        self.assertEqual(self.api.job_posts(), 1)

    def test_create_uncertain_never_retries(self):
        self.api.create_uncertain = True
        self.controller.reconcile(self.api.current())
        self.assertEqual(self.api.current()['status']['phase'], 'Error')
        self.controller.reconcile(self.api.current())
        self.assertEqual(self.api.job_posts(), 1)

    def test_cas_loser_does_not_post(self):
        self.api.conflict = True
        self.controller.reconcile(self.api.current())
        self.assertEqual(self.api.job_posts(), 0)

    def test_missing_or_replaced_job_errors_without_relaunch(self):
        for replacement in [None, 'replacement-uid']:
            with self.subTest(replacement=replacement):
                self.setUp()
                self.controller.reconcile(self.api.current())
                path = self.controller.jobs + '/' + run_name(self.request)
                if replacement:
                    self.api.docs[path]['metadata']['uid'] = replacement
                else:
                    del self.api.docs[path]
                self.controller.reconcile(self.api.current())
                self.assertEqual(self.api.current()['status']['phase'], 'Error')
                self.assertEqual(self.api.job_posts(), 1)

    def test_multiple_executor_pods_and_wrong_owner_rejected(self):
        for mode in ['multiple', 'wrong-owner', 'wrong-template']:
            with self.subTest(mode=mode):
                self.setUp()
                self.controller.reconcile(self.api.current())
                self.api.finish(self.controller)
                if mode == 'multiple':
                    self.api.executor_pods *= 2
                elif mode == 'wrong-owner':
                    self.api.executor_pods[0]['metadata']['ownerReferences'][0]['uid'] = 'foreign'
                else:
                    path = self.controller.jobs + '/' + run_name(self.request)
                    self.api.docs[path]['spec']['template']['spec']['containers'][0]['image'] = 'forged'
                self.controller.reconcile(self.api.current())
                self.assertEqual(self.api.current()['status']['phase'], 'Error')

    def test_missing_tools_controller_error_good_trace_incomplete_answer_failed(self):
        for malformed in [True, False]:
            with self.subTest(malformed=malformed):
                self.setUp()
                self.controller.reconcile(self.api.current())
                self.api.finish(self.controller)
                if malformed:
                    self.api.capture['a2a']['result']['history'] = []
                else:
                    self.api.capture['a2a']['result']['artifacts'][0]['parts'][0]['text'] = 'incomplete'
                self.controller.reconcile(self.api.current())
                self.assertEqual(self.api.current()['status']['phase'], 'Error' if malformed else 'Failed')

    def test_renderer_has_exact_exec_target_and_no_secrets_or_portforward(self):
        docs = render(self.config)
        roles = [d for d in docs if d['kind'] == 'Role']
        rules = [r for d in roles for r in d['rules']]
        self.assertFalse(any('secrets' in r['resources'] or 'pods/portforward' in r['resources'] for r in rules))
        exec_rules = [r for r in rules if 'pods/exec' in r['resources']]
        self.assertEqual(exec_rules, [{'apiGroups': [''], 'resources': ['pods/exec'], 'verbs': ['create'],
                                      'resourceNames': [self.config['targetPodName']]}])
        worker = executor_job(self.request, self.config)
        self.assertEqual(worker['spec']['backoffLimit'], 0)
        self.assertEqual(worker['spec']['template']['spec']['restartPolicy'], 'Never')

    def test_optional_scheduling_and_lab_image_are_explicit(self):
        config = {**self.config, 'labLocalImage': True, 'image': 'skill-eval:lab',
                  'nodeSelector': {'kubernetes.io/hostname': 'lab-cp'},
                  'tolerations': [{'key': 'node-role.kubernetes.io/control-plane', 'operator': 'Exists', 'effect': 'NoSchedule'}]}
        job = executor_job(self.request, profile(config))
        self.assertEqual(job['spec']['template']['spec']['containers'][0]['imagePullPolicy'], 'Never')
        self.assertEqual(job['spec']['template']['spec']['nodeSelector'], config['nodeSelector'])


if __name__ == '__main__':
    unittest.main()


class WorkerPinTests(unittest.TestCase):
    def test_worker_wrong_pod_uid_rejected_before_exec_or_snapshot(self):
        from unittest.mock import patch
        from worker import PinnedCluster
        config, request, scenario, content, capture, skill, cm, pod, agent, source = fixtures()
        cluster = PinnedCluster(config)
        pod['metadata']['uid'] = 'replacement'
        with patch.object(cluster, 'get', return_value=pod), patch('run.Cluster.snapshot') as inherited:
            with self.assertRaisesRegex(Rejected, 'AgentPodPinMismatch'):
                cluster.snapshot(scenario)
            inherited.assert_not_called()

    def test_worker_rechecks_pod_uid_immediately_before_exec(self):
        from unittest.mock import patch
        from worker import PinnedCluster
        config, request, scenario, content, capture, skill, cm, pod, agent, source = fixtures()
        cluster = PinnedCluster(config)
        pod['metadata']['uid'] = 'replacement'
        with patch.object(cluster, 'get', return_value=pod), patch('run.Cluster.json') as execute:
            with self.assertRaisesRegex(Rejected, 'AgentPodPinMismatch'):
                cluster.json(['exec', '-n', 'skills-demo', config['targetPodName'], '--', 'python'])
            execute.assert_not_called()


class IndependentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixtures()
        self.config, self.request, self.scenario, self.content, self.capture, self.skill, self.cm, self.pod, self.agent, self.source = self.fx
        self.api = FakeAPI(*copy.deepcopy(self.fx))
        self.controller = Controller(self.api, self.config)
        self.controller.reconcile(self.api.current())
        self.api.finish(self.controller)

    def test_executor_container_exit_restart_and_injection_rejected(self):
        for mode in ['restart', 'exit', 'image-missing', 'env', 'envFrom', 'init', 'mount', 'security']:
            with self.subTest(mode=mode):
                self.setUp()
                pod = self.api.executor_pods[0]
                status = pod['status']['containerStatuses'][0]
                if mode == 'restart': status['restartCount'] = 1
                elif mode == 'exit': status['state']['terminated']['exitCode'] = 7
                elif mode == 'image-missing': status.pop('imageID')
                elif mode == 'env': pod['spec']['containers'][0]['env'] = [{'name': 'URL', 'value': 'forged'}]
                elif mode == 'envFrom': pod['spec']['containers'][0]['envFrom'] = [{'configMapRef': {'name': 'forged'}}]
                elif mode == 'init': pod['spec']['initContainers'] = [{'name': 'forged'}]
                elif mode == 'mount': pod['spec']['containers'][0]['volumeMounts'].append({'name': 'profile', 'mountPath': '/forged'})
                elif mode == 'security': pod['spec']['securityContext']['runAsUser'] = 0
                self.controller.reconcile(self.api.current())
                self.assertEqual(self.api.current()['status']['phase'], 'Error')

    def test_executor_uid_recorded_then_replacement_is_rejected(self):
        path = self.controller.jobs + '/' + run_name(self.request)
        self.api.docs[path].pop('status')
        self.controller.reconcile(self.api.current())
        self.assertEqual(self.api.current()['status']['executorPodUID'], 'executor-uid')
        self.api.executor_pods[0]['metadata']['uid'] = 'replacement-uid'
        self.controller.reconcile(self.api.current())
        self.assertEqual(self.api.current()['status']['phase'], 'Error')

    def test_agent_skill_and_source_live_drift_independently_rejected(self):
        for mode in ['agent-spec', 'agent-generation', 'agent-uid', 'skill-not-ready', 'skill-generation', 'source-revision', 'source-uid', 'cm-mutable']:
            with self.subTest(mode=mode):
                self.setUp()
                prefix = '/apis/skills.platform.kagent.dev/v1alpha1/namespaces/skills-demo/'
                agent = self.api.docs['/apis/kagent.dev/v1alpha2/namespaces/skills-demo/agents/' + self.scenario['spec']['agentRef']['name']]
                skill = self.api.docs[prefix + 'skills/' + self.skill['metadata']['name']]
                source = self.api.docs['/apis/source.toolkit.fluxcd.io/v1/namespaces/skills-demo/gitrepositories/skill-source']
                if mode == 'agent-spec': agent['spec']['injected'] = True
                elif mode == 'agent-generation': agent['metadata']['generation'] = 2
                elif mode == 'agent-uid': agent['metadata']['uid'] = 'replacement'
                elif mode == 'skill-not-ready': skill['status']['conditions'] = []
                elif mode == 'skill-generation': skill['metadata']['generation'] = 2
                elif mode == 'source-revision': source['status']['artifact']['revision'] = 'changed'
                elif mode == 'source-uid': source['metadata']['uid'] = 'changed'
                elif mode == 'cm-mutable': self.api.docs['/api/v1/namespaces/skills-demo/configmaps/skill-content']['immutable'] = False
                self.controller.reconcile(self.api.current())
                self.assertEqual(self.api.current()['status']['phase'], 'Error')

    def test_receipt_records_executor_provenance(self):
        self.controller.reconcile(self.api.current())
        receipt = json.loads(self.api.docs[self.controller.cms + '/' + run_name(self.request) + '-receipt']['data']['result.json'])
        self.assertEqual(receipt['jobUID'], 'job-uid')
        self.assertEqual(receipt['executorPodUID'], 'executor-uid')
        self.assertEqual(receipt['executorImageID'], 'sha256:executor-image')
