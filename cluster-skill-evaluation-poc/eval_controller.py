#!/usr/bin/env python3
"""Single replica bounded poller. LaunchRecorded is a durable no-relaunch fence."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from contract import (API, GROUP, MAX_CAPTURE, TERMINAL, TRANSITIONS, SCENARIO_GROUP,
                      Rejected, code_digest, digest, pin_scenario, pod_pin, profile,
                      request_spec, verify_capture)


class KubeAPI:
    def __init__(self):
        self.base = 'https://' + os.environ['KUBERNETES_SERVICE_HOST'] + ':' + os.environ['KUBERNETES_SERVICE_PORT']
        self.sa = Path('/var/run/secrets/kubernetes.io/serviceaccount')
        self.ssl = ssl.create_default_context(cafile=str(self.sa / 'ca.crt'))

    def call(self, path, method='GET', value=None, raw=False):
        headers = {'Authorization': 'Bearer ' + (self.sa / 'token').read_text().strip()}
        if value is not None:
            headers['Content-Type'] = 'application/merge-patch+json' if method == 'PATCH' else 'application/json'
        req = urllib.request.Request(self.base + path, method=method, headers=headers,
                                     data=json.dumps(value).encode() if value is not None else None)
        with urllib.request.urlopen(req, context=self.ssl, timeout=20) as response:
            data = response.read(MAX_CAPTURE + 1)
        if len(data) > MAX_CAPTURE:
            raise Rejected('APIResponseTooLarge')
        return data.decode() if raw else json.loads(data)


def optional(api, path):
    try:
        return api.call(path)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def owner(request):
    return {'apiVersion': API, 'kind': 'SkillEvaluation', 'name': request['metadata']['name'],
            'uid': request['metadata']['uid'], 'controller': True, 'blockOwnerDeletion': False}


def run_name(request):
    uid = request['metadata']['uid']
    import uuid
    if str(uuid.UUID(uid)) != uid:
        raise Rejected('InvalidRequestUID')
    return 'se-' + uid


def executor_job(request, config):
    name = run_name(request)
    return {'apiVersion': 'batch/v1', 'kind': 'Job',
            'metadata': {'name': name, 'namespace': config['evaluationNamespace'], 'ownerReferences': [owner(request)]},
            'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 300,
                     'template': {'metadata': {'labels': {GROUP + '/run': request['metadata']['uid']}},
                     'spec': {'restartPolicy': 'Never', 'terminationGracePeriodSeconds': 1, 'serviceAccountName': 'skill-eval-worker',
                              'nodeSelector': config.get('nodeSelector', {}), 'tolerations': config.get('tolerations', []),
                              'automountServiceAccountToken': True,
                              'securityContext': {'runAsNonRoot': True, 'runAsUser': 10001, 'fsGroup': 10001,
                                                  'seccompProfile': {'type': 'RuntimeDefault'}},
                              'containers': [{'name': 'worker', 'image': config['image'],
                                  'imagePullPolicy': 'Never' if config['labLocalImage'] else 'IfNotPresent',
                                  'command': ['python', '/app/worker.py'],
                                  'args': ['--request', json.dumps({'metadata': {'uid': request['metadata']['uid']},
                                                               'spec': request['spec']}, separators=(',', ':'))],
                                  'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                                      'capabilities': {'drop': ['ALL']}},
                                  'resources': {'requests': {'cpu': '50m', 'memory': '96Mi'},
                                                'limits': {'cpu': '500m', 'memory': '256Mi'}},
                                  'volumeMounts': [{'name': 'profile', 'mountPath': '/profile', 'readOnly': True},
                                                   {'name': 'work', 'mountPath': '/work'}, {'name': 'tmp', 'mountPath': '/tmp'}]}],
                              'volumes': [{'name': 'profile', 'configMap': {'name': 'skill-eval-profile-' + digest(config)[:16]}},
                                          {'name': 'work', 'emptyDir': {'sizeLimit': '8Mi'}},
                                          {'name': 'tmp', 'emptyDir': {'sizeLimit': '8Mi'}}]}}}}


class Controller:
    def __init__(self, api, config):
        self.api, self.config = api, profile(config)
        ns = config['evaluationNamespace']
        self.requests = f'/apis/{API}/namespaces/{ns}/skillevaluations'
        self.jobs = f'/apis/batch/v1/namespaces/{ns}/jobs'
        self.pods = f'/api/v1/namespaces/{ns}/pods'
        self.cms = f'/api/v1/namespaces/{ns}/configmaps'
        self.code = code_digest()

    def status(self, request, phase, **fields):
        old = request.get('status', {})
        previous = old.get('phase', 'Pending')
        if phase != previous and phase not in TRANSITIONS.get(previous, set()):
            raise Rejected('InvalidRunTransition')
        value = {**old, **fields, 'phase': phase}
        result = self.api.call(self.requests + '/' + request['metadata']['name'] + '/status', 'PATCH',
                              {'metadata': {'uid': request['metadata']['uid'],
                                            'resourceVersion': request['metadata']['resourceVersion']}, 'status': value})
        request.update(result)

    def inputs(self, request):
        ref = request_spec(request['spec'])
        if ref['name'] not in self.config['scenarioNames']:
            raise Rejected('ScenarioNotAllowed')
        target = self.config['targetNamespace']
        scenario = self.api.call(f'/apis/{SCENARIO_GROUP}/v1alpha1/namespaces/{target}/goldenscenarios/{ref["name"]}')
        pin_scenario(scenario, ref, self.config)
        agent = self.api.call(f'/apis/kagent.dev/v1alpha2/namespaces/{target}/agents/{scenario["spec"]["agentRef"]["name"]}')
        skill = self.api.call(f'/apis/{SCENARIO_GROUP}/v1alpha1/namespaces/{target}/skills/{scenario["spec"]["skillRef"]["name"]}')
        for resource in [agent, skill]:
            if not any(c.get('type') == 'Ready' and c.get('status') == 'True'
                       and c.get('observedGeneration') == resource['metadata']['generation']
                       for c in resource.get('status', {}).get('conditions', [])):
                raise Rejected('ReferencedResourceNotCurrentlyReady')
        if digest(agent['spec']) != scenario['spec']['agentSpecSha256'] or agent['spec'].get('declarative', {}).get('tools'):
            raise Rejected('AgentConfigurationMismatch')
        if (skill['spec']['contentSha256'] != scenario['spec']['skillContentSha256']
                or skill['status'].get('contentSha256') != skill['spec']['contentSha256']
                or skill['spec']['skillName'] != 'aks-known-issues'):
            raise Rejected('SkillContentPinMismatch')
        source = self.api.call(f'/apis/source.toolkit.fluxcd.io/v1/namespaces/{target}/gitrepositories/{skill["spec"]["sourceRef"]["name"]}')
        if (source['spec'].get('ref', {}).get('commit') != skill['spec']['sourceCommit']
                or source.get('status', {}).get('artifact', {}).get('revision') != 'sha1:' + skill['spec']['sourceCommit']
                or not any(c.get('type') == 'Ready' and c.get('status') == 'True'
                           and c.get('observedGeneration') == source['metadata']['generation']
                           for c in source.get('status', {}).get('conditions', []))):
            raise Rejected('SkillSourceNotCurrent')
        cm = self.api.call(f'/api/v1/namespaces/{target}/configmaps/{skill["status"]["configMapRef"]["name"]}')
        expected_owner = {'apiVersion': skill['apiVersion'], 'kind': 'Skill', 'name': skill['metadata']['name'],
                          'uid': skill['metadata']['uid'], 'controller': True}
        if not cm.get('immutable') or expected_owner not in cm['metadata'].get('ownerReferences', []):
            raise Rejected('SkillConfigMapNotOwnedAndImmutable')
        content = {p: cm['data'][f'file{i:02}'] for i, p in enumerate(sorted(skill['spec']['files']))}
        if any(hashlib.sha256(content[p].encode()).hexdigest() != h for p, h in skill['spec']['files'].items()):
            raise Rejected('SkillFileHashMismatch')
        pod = self.api.call(f'/api/v1/namespaces/{target}/pods/{self.config["targetPodName"]}')
        pod_pin(pod, self.config)
        if (len(pod.get('spec', {}).get('containers', [])) != 1
                or len(pod.get('status', {}).get('containerStatuses', [])) != 1
                or not pod['status']['containerStatuses'][0].get('ready')):
            raise Rejected('AgentPodNotCurrentlyReady')
        return scenario, content, pod, skill, cm, agent, source

    def check_job(self, job, request):
        expected = executor_job(request, self.config)
        if owner(request) not in job['metadata'].get('ownerReferences', []):
            raise Rejected('JobOwnershipMismatch')
        # Kubernetes defaults augment Job spec; compare every fixed security-relevant field.
        def subset(want, got):
            if isinstance(want, dict):
                return isinstance(got, dict) and all(k in got and subset(v, got[k]) for k, v in want.items())
            if isinstance(want, list):
                return isinstance(got, list) and len(want) == len(got) and all(subset(a, b) for a, b in zip(want, got))
            return want == got
        if not subset(expected['spec'], job['spec']):
            raise Rejected('JobTemplateMismatch')
        recorded_uid = request.get('status', {}).get('jobUID')
        if recorded_uid and recorded_uid != job['metadata']['uid']:
            raise Rejected('JobReplaced')

    def save(self, request, suffix, data):
        name = run_name(request) + '-' + suffix
        document = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
                    'metadata': {'name': name, 'namespace': self.config['evaluationNamespace'],
                                 'ownerReferences': [owner(request)]},
                    'data': {'result.json': json.dumps(data, separators=(',', ':'))}}
        existing = optional(self.api, self.cms + '/' + name)
        if existing is None:
            self.api.call(self.cms, 'POST', document)
        elif (not existing.get('immutable') or existing.get('data') != document['data']
              or owner(request) not in existing['metadata'].get('ownerReferences', [])):
            raise Rejected('EvidenceConfigMapMismatch')
        return name

    def reconcile(self, request):
        state = request.get('status', {}).get('phase', 'Pending')
        if state in TERMINAL or request['metadata'].get('deletionTimestamp'):
            return
        try:
            request_spec(request['spec'])
            if state == 'Pending':
                self.inputs(request)
                self.status(request, 'LaunchRecorded', frozenSpecSha256=digest(request['spec']),
                            profileSha256=digest(self.config), codeSha256=self.code,
                            contextID='se-' + request['metadata']['uid'], jobName=run_name(request))
                job = self.api.call(self.jobs, 'POST', executor_job(request, self.config))
                self.status(request, 'Running', jobUID=job['metadata']['uid'])
                return
            status = request['status']
            if (status.get('frozenSpecSha256') != digest(request['spec'])
                    or status.get('profileSha256') != digest(self.config) or status.get('codeSha256') != self.code
                    or status.get('contextID') != 'se-' + request['metadata']['uid']):
                raise Rejected('FrozenRunMismatch')
            job = optional(self.api, self.jobs + '/' + run_name(request))
            if job is None:
                raise Rejected('LaunchUncertainOrJobMissing')
            self.check_job(job, request)
            if state == 'LaunchRecorded':
                self.status(request, 'Running', jobUID=job['metadata']['uid'])
                return
            pods = self.api.call(self.pods + '?labelSelector=' + urllib.parse.quote(GROUP + '/run=' + request['metadata']['uid']))['items']
            if len(pods) > 1:
                raise Rejected('MultipleExecutorPods')
            for pod in pods:
                if not any(o.get('uid') == job['metadata']['uid'] and o.get('kind') == 'Job'
                           and o.get('controller') is True for o in pod['metadata'].get('ownerReferences', [])):
                    raise Rejected('ExecutorPodOwnershipMismatch')
                recorded = request['status'].get('executorPodUID')
                if recorded and recorded != pod['metadata']['uid']:
                    raise Rejected('ExecutorPodReplaced')
                if not recorded:
                    self.status(request, 'Running', executorPodUID=pod['metadata']['uid'])
                spec = pod['spec']
                expected = executor_job(request, self.config)['spec']['template']['spec']
                containers = spec.get('containers', [])
                if (spec.get('serviceAccountName') != 'skill-eval-worker' or spec.get('restartPolicy') != 'Never'
                        or spec.get('automountServiceAccountToken') is not True
                        or spec.get('securityContext') != expected['securityContext']
                        or len(containers) != 1 or spec.get('initContainers') or spec.get('ephemeralContainers')
                        or containers[0].get('env') or containers[0].get('envFrom')
                        or any(containers[0].get(k) != expected['containers'][0][k]
                               for k in ['name', 'image', 'imagePullPolicy', 'command', 'args', 'securityContext', 'resources'])):
                    raise Rejected('ExecutorPodTemplateMismatch')
                # API admission appends one projected service-account volume/mount.
                volumes = spec.get('volumes', [])
                extra = [v for v in volumes if v.get('name') not in {'profile', 'work', 'tmp'}]
                if len(extra) > 1 or any(not v.get('name', '').startswith('kube-api-access-')
                    or set(v) != {'name', 'projected'} for v in extra):
                    raise Rejected('ExecutorUnexpectedVolume')
                for wanted in expected['volumes']:
                    actual = next((v for v in volumes if v['name'] == wanted['name']), None)
                    if wanted['name'] == 'profile':
                        if not actual or actual.get('configMap', {}).get('name') != wanted['configMap']['name']:
                            raise Rejected('ExecutorProfileVolumeMismatch')
                    elif actual != wanted:
                        raise Rejected('ExecutorWorkVolumeMismatch')
                mounts = containers[0].get('volumeMounts', [])
                for wanted in expected['containers'][0]['volumeMounts']:
                    if wanted not in mounts:
                        raise Rejected('ExecutorMountMismatch')
                extras = [m for m in mounts if m not in expected['containers'][0]['volumeMounts']]
                if len(extras) != len(extra) or any(m.get('name') not in {v['name'] for v in extra}
                    or m.get('mountPath') != '/var/run/secrets/kubernetes.io/serviceaccount'
                    or m.get('readOnly') is not True or set(m) != {'name', 'mountPath', 'readOnly'} for m in extras):
                    raise Rejected('ExecutorUnexpectedMount')
                statuses = pod.get('status', {}).get('containerStatuses', [])
                if statuses and (len(statuses) != 1 or statuses[0].get('name') != 'worker'
                                 or statuses[0].get('restartCount') != 0):
                    raise Rejected('ExecutorContainerRestartedOrAmbiguous')
            conditions = job.get('status', {}).get('conditions', [])
            terminal = any(c.get('status') == 'True' and c.get('type') in {'Complete', 'Failed'} for c in conditions)
            if not terminal:
                return
            if len(pods) != 1:
                raise Rejected('ExecutorPodMissing')
            statuses = pods[0].get('status', {}).get('containerStatuses', [])
            if (pods[0].get('status', {}).get('phase') != 'Succeeded' or len(statuses) != 1
                    or statuses[0].get('name') != 'worker' or statuses[0].get('restartCount') != 0
                    or statuses[0].get('state', {}).get('terminated', {}).get('exitCode') != 0
                    or not statuses[0].get('imageID')):
                raise Rejected('ExecutorDidNotExitSuccessfully')
            raw = self.api.call(self.pods + '/' + pods[0]['metadata']['name'] + '/log?container=worker', raw=True)
            if len(raw.encode()) > MAX_CAPTURE or len(raw.strip().splitlines()) != 1:
                raise Rejected('InvalidEvidenceEnvelope')
            capture = json.loads(raw)
            if capture.get('workerError'):
                raise Rejected('WorkerTransportOrSnapshotError')
            if any(c.get('type') == 'Failed' and c.get('status') == 'True' for c in conditions):
                raise Rejected('ExecutorJobFailed')
            scenario, content, pod, skill, cm, agent, source = self.inputs(request)
            receipt = verify_capture(capture, request, self.config, scenario, content, pod, self.code)
            for name in ['before', 'after']:
                identity = capture[name]['identity']
                expected_identity = {'scenarioGeneration': scenario['metadata']['generation'], 'skillUID': skill['metadata']['uid'], 'skillGeneration': skill['metadata']['generation'],
                    'skillContentSha256': skill['spec']['contentSha256'], 'skillSpecSha256': digest(skill['spec']),
                    'configMapUID': cm['metadata']['uid'], 'sourceCommit': skill['spec']['sourceCommit'],
                    'sourceUID': source['metadata']['uid'], 'sourceGeneration': source['metadata']['generation'],
                    'agentUID': agent['metadata']['uid'], 'agentGeneration': agent['metadata']['generation'],
                    'agentSpecSha256': digest(agent['spec'])}
                if any(identity.get(k) != v for k, v in expected_identity.items()):
                    raise Rejected('ControllerSnapshotIdentityMismatch')
                runtime = pod['status']['containerStatuses'][0]
                if any(identity.get(k) != runtime.get(k) for k in ['containerID', 'restartCount', 'imageID']):
                    raise Rejected('ControllerPodRuntimeMismatch')
            evidence_ref = self.save(request, 'capture', capture)
            receipt.update(evidenceRef=evidence_ref, jobUID=job['metadata']['uid'],
                           executorPodUID=pods[0]['metadata']['uid'], executorImageID=statuses[0]['imageID'])
            receipt_ref = self.save(request, 'receipt', receipt)
            self.status(request, receipt['phase'], reason='ChecksCompleted', evidenceRef=evidence_ref,
                        receiptRef=receipt_ref, evidenceSha256=receipt['evidenceSha256'],
                        semanticScore='not_scored', deepEval='not_used')
        except urllib.error.HTTPError as error:
            if error.code == 409:
                return
            self.status(request, 'Error', reason='APIError', detail='HTTP' + str(error.code))
        except (Rejected, ValueError, KeyError, TypeError, OSError, IndexError) as error:
            self.status(request, 'Error', reason='EvidenceRejected' if state == 'Running' else 'RunRejected',
                        detail=str(error) if isinstance(error, Rejected) else type(error).__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', default='/profile/profile.json')
    args = parser.parse_args()
    controller = Controller(KubeAPI(), json.loads(Path(args.profile).read_text()))
    while True:
        try:
            requests = controller.api.call(controller.requests + '?limit=100')['items']
            for request in requests:
                try:
                    controller.reconcile(request)
                except (OSError, ValueError, KeyError, urllib.error.HTTPError) as error:
                    print(json.dumps({'controllerError': type(error).__name__}), flush=True)
        except (OSError, ValueError) as error:
            print(json.dumps({'pollError': type(error).__name__}), flush=True)
        time.sleep(3)


if __name__ == '__main__':
    main()
