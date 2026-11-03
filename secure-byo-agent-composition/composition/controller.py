"""Namespaced controller for the small hosted composition experiment."""
import argparse
import copy
import json
import os
from pathlib import Path
import ssl
import time
import urllib.error
import urllib.request

from compose import API, KIND, FINALIZER, Rejected, digest, generate, resource_templates, substitute

PLURALS = {'HostedSecureAgent': 'hostedsecureagents', 'AgentTemplate': 'agenttemplates',
    'Agent': 'agents', 'ModelConfig': 'modelconfigs', 'RemoteMCPServer': 'remotemcpservers',
    'Harness': 'harnesses', 'EgressPolicy': 'egresspolicies', 'ServiceAccount': 'serviceaccounts', 'Service': 'services',
    'ConfigMap': 'configmaps', 'Deployment': 'deployments', 'NetworkPolicy': 'networkpolicies',
    'HTTPRoute': 'httproutes', 'ReferenceGrant': 'referencegrants',
    'AgentgatewayBackend': 'agentgatewaybackends', 'AgentgatewayPolicy': 'agentgatewaypolicies'}


def collection(api, namespace, kind):
    base = '/api/v1' if api == 'v1' else '/apis/' + api
    return base + '/namespaces/' + namespace + '/' + PLURALS[kind]


def owned(existing, parent):
    return any(r.get('uid') == parent['metadata']['uid'] and r.get('controller') is True
        and r.get('kind') == parent['kind'] and r.get('apiVersion') == parent['apiVersion']
        for r in existing.get('metadata', {}).get('ownerReferences', []))


def managed_body(desired, live):
    """Preserve allocation fields and explicit API defaults, never arbitrary spec additions."""
    body = copy.deepcopy(desired)
    meta = body['metadata']
    for field in ('labels', 'annotations'):
        merged = copy.deepcopy(live['metadata'].get(field, {}))
        merged.update(meta.get(field, {}))
        if merged:
            meta[field] = merged
    for field in ('uid', 'resourceVersion', 'finalizers', 'creationTimestamp'):
        if field in live['metadata']:
            meta[field] = copy.deepcopy(live['metadata'][field])
    spec = body.get('spec', {})
    observed = live.get('spec', {})
    def defaults(target, source, values):
        for key, value in values.items():
            if key not in target and key in source and source[key] == value:
                target[key] = copy.deepcopy(value)
    if body['kind'] == 'Service':
        for field in ('clusterIP', 'clusterIPs', 'ipFamilies', 'ipFamilyPolicy'):
            if field not in spec and field in observed:
                spec[field] = copy.deepcopy(observed[field])
        defaults(spec, observed, {'type': 'ClusterIP', 'sessionAffinity': 'None', 'internalTrafficPolicy': 'Cluster'})
        for port, current in zip(spec.get('ports', []), observed.get('ports', [])):
            defaults(port, current, {'protocol': 'TCP', 'targetPort': port.get('port')})
    if body['kind'] == 'Deployment':
        defaults(spec, observed, {'revisionHistoryLimit': 10, 'progressDeadlineSeconds': 600,
            'strategy': {'type': 'RollingUpdate', 'rollingUpdate': {'maxSurge': '25%', 'maxUnavailable': '25%'}}})
        template = spec.get('template', {})
        old_template = observed.get('template', {})
        defaults(template.setdefault('metadata', {}), old_template.get('metadata', {}), {'creationTimestamp': None})
        pod, old_pod = template.get('spec', {}), old_template.get('spec', {})
        defaults(pod, old_pod, {'restartPolicy': 'Always', 'dnsPolicy': 'ClusterFirst',
            'schedulerName': 'default-scheduler', 'terminationGracePeriodSeconds': 30,
            'enableServiceLinks': True, 'serviceAccount': pod.get('serviceAccountName')})
        for field in ('containers', 'initContainers'):
            old_containers = {c['name']: c for c in old_pod.get(field, [])}
            for container in pod.get(field, []):
                current = old_containers.get(container['name'], {})
                defaults(container, current, {'imagePullPolicy': 'IfNotPresent',
                    'terminationMessagePath': '/dev/termination-log', 'terminationMessagePolicy': 'File'})
                for port, old_port in zip(container.get('ports', []), current.get('ports', [])):
                    defaults(port, old_port, {'protocol': 'TCP'})
                for probe in ('readinessProbe', 'livenessProbe', 'startupProbe'):
                    if probe in container:
                        defaults(container[probe], current.get(probe, {}), {'failureThreshold': 3,
                            'periodSeconds': 10, 'successThreshold': 1, 'timeoutSeconds': 1})
                        if 'httpGet' in container[probe]:
                            defaults(container[probe]['httpGet'], current.get(probe, {}).get('httpGet', {}), {'scheme': 'HTTP'})
        old_volumes = {v['name']: v for v in old_pod.get('volumes', [])}
        for volume in pod.get('volumes', []):
            for kind in ('configMap', 'secret', 'projected'):
                if kind in volume:
                    defaults(volume[kind], old_volumes.get(volume['name'], {}).get(kind, {}), {'defaultMode': 420})
    return body


def same_managed_body(desired, live):
    return all(live.get(field) == desired.get(field) for field in ('spec', 'data', 'type')) and all(
        all(live['metadata'].get(field, {}).get(k) == v for k, v in desired['metadata'].get(field, {}).items())
        for field in ('labels', 'annotations')) and live['metadata'].get('ownerReferences') == desired['metadata'].get('ownerReferences')


class Kubernetes:
    def __init__(self):
        root = Path('/var/run/secrets/kubernetes.io/serviceaccount')
        self.token_file = root / 'token'
        self.base = 'https://' + os.environ['KUBERNETES_SERVICE_HOST'] + ':' + os.environ['KUBERNETES_SERVICE_PORT_HTTPS']
        self.context = ssl.create_default_context(cafile=str(root / 'ca.crt'))

    def call(self, method, path, data=None):
        headers = {'Authorization': 'Bearer ' + self.token_file.read_text().strip(), 'Content-Type': 'application/json'}
        req = urllib.request.Request(self.base + path, None if data is None else json.dumps(data).encode(), headers, method=method)
        with urllib.request.urlopen(req, context=self.context, timeout=15) as response:
            return json.load(response)

    def get(self, path):
        try:
            return self.call('GET', path)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise


class Controller:
    def __init__(self, kube, profile):
        self.kube, self.profile = kube, profile
        self.requests = collection(API, profile['namespace'], KIND)

    def parent_update(self, parent, finalizers):
        body = copy.deepcopy(parent)
        body.pop('status', None)
        body['metadata']['finalizers'] = finalizers
        return self.kube.call('PUT', self.requests + '/' + parent['metadata']['name'], body)

    def status(self, parent, ready, reason, objects):
        path = self.requests + '/' + parent['metadata']['name'] + '/status'
        metadata = parent['metadata']
        prior = parent.get('status', {})
        status = {'observedGeneration': metadata['generation'], 'profileSha256': prior.get('profileSha256', digest(self.profile)),
            'conditions': [{'type': 'Ready', 'status': 'True' if ready else 'False', 'reason': reason,
                'observedGeneration': metadata['generation'], 'lastTransitionTime': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}],
            'inventory': ([{'apiVersion': o['apiVersion'], 'kind': o['kind'], 'name': o['metadata']['name'],
                'uid': o['metadata'].get('uid', '')} for o in objects] if objects else prior.get('inventory', []))}
        old_condition = next((c for c in prior.get('conditions', []) if c.get('type') == 'Ready'), {})
        new_condition = status['conditions'][0]
        if all(old_condition.get(k) == new_condition.get(k) for k in ('type', 'status', 'reason', 'observedGeneration')):
            new_condition['lastTransitionTime'] = old_condition['lastTransitionTime']
        if status == prior:
            return
        self.kube.call('PUT', path, {'apiVersion': API, 'kind': KIND,
            'metadata': {'name': metadata['name'], 'namespace': metadata['namespace'],
                'uid': metadata['uid'], 'resourceVersion': metadata['resourceVersion']}, 'status': status})

    def reconcile(self, parent):
        meta = parent['metadata']
        prior_profile = parent.get('status', {}).get('profileSha256')
        deleting = bool(meta.get('deletionTimestamp'))
        if prior_profile and prior_profile != digest(self.profile) and not deleting:
            raise Rejected('ProfileChangedCreateNewRequest')
        if deleting:
            if meta['namespace'] != self.profile['namespace']:
                raise Rejected('NamespaceMismatch')
            desired = substitute(resource_templates(self.profile), meta['name'], meta['namespace'], parent['spec']['instructions'])
            known = {(o['apiVersion'], o['kind'], o['metadata']['name']) for o in desired}
            for item in parent.get('status', {}).get('inventory', []):
                key = (item['apiVersion'], item['kind'], item['name'])
                if item['kind'] not in PLURALS or item['kind'] == KIND or not item.get('uid'):
                    raise Rejected('InvalidRetirementInventory')
                if key not in known:
                    desired.append({'apiVersion': key[0], 'kind': key[1],
                        'metadata': {'name': key[2], 'namespace': meta['namespace'], 'uid': item['uid']}})
                    known.add(key)
        else:
            desired = generate(self.profile, parent)
        current = []
        for obj in desired:
            path = collection(obj['apiVersion'], meta['namespace'], obj['kind']) + '/' + obj['metadata']['name']
            live = self.kube.get(path)
            if live and not owned(live, parent):
                raise Rejected('ForeignChildCollision')
            if live and deleting and obj['metadata'].get('uid') and obj['metadata']['uid'] != live['metadata']['uid']:
                raise Rejected('RetirementInventoryUIDChanged')
            current.append((obj, live, path))
        if meta.get('deletionTimestamp'):
            if FINALIZER not in meta.get('finalizers', []):
                return
            order = {'HTTPRoute': 0, 'AgentgatewayPolicy': 1, 'Agent': 2}
            for obj, live, path in sorted(current, key=lambda row: order.get(row[0]['kind'], 3)):
                if live:
                    self.kube.call('DELETE', path, {'apiVersion': 'v1', 'kind': 'DeleteOptions',
                        'preconditions': {'uid': live['metadata']['uid']}})
            if all(self.kube.get(path) is None for _, _, path in current):
                self.parent_update(parent, [v for v in meta.get('finalizers', []) if v != FINALIZER])
            return
        if FINALIZER not in meta.get('finalizers', []):
            self.parent_update(parent, meta.get('finalizers', []) + [FINALIZER])
            return
        created = []
        for obj, live, path in current:
            if live is None:
                result = self.kube.call('POST', path.rsplit('/', 1)[0], obj)
            else:
                body = managed_body(obj, live)
                if same_managed_body(body, live):
                    result = live
                else:
                    result = self.kube.call('PUT', path, body)
            created.append(result)
        agent = next((o for o in created if o['kind'] == 'Agent'), {})
        state = agent.get('status', {})
        conditions = state.get('conditions', [])
        ready = all(any(c.get('type') == kind and c.get('status') == 'True'
            and c.get('observedGeneration') == agent.get('metadata', {}).get('generation') for c in conditions)
            for kind in ('Accepted', 'ResolvedRefs', 'Compatible', 'EgressPoliciesApplied', 'Ready'))
        ready = ready and bool(state.get('desiredRevision')) and state.get('desiredRevision') == state.get('latestSuccessfulRevision')
        self.status(parent, ready, 'RuntimeReady' if ready else 'WaitingForRuntime', created)

    def poll(self):
        for parent in self.kube.call('GET', self.requests).get('items', []):
            try:
                self.reconcile(parent)
            except (Rejected, urllib.error.HTTPError, OSError) as error:
                print(json.dumps({'request': parent['metadata']['name'], 'error': str(error)[:200]}), flush=True)
                try:
                    fresh = self.kube.get(self.requests + '/' + parent['metadata']['name'])
                    if fresh and fresh['metadata']['uid'] == parent['metadata']['uid']:
                        self.status(fresh, False, 'ReconciliationRejected', [])
                except (urllib.error.HTTPError, OSError):
                    pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    controller = Controller(Kubernetes(), json.loads(Path(args.profile).read_text()))
    while True:
        controller.poll()
        if args.once:
            break
        time.sleep(3)
