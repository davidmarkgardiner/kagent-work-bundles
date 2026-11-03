"""Admission specimens; callers must submit them to the real Kyverno webhook."""

from copy import deepcopy


def cases(config):
    namespace = config['namespaces'][0]
    composer = config['composerUsers'][0]
    metadata = {'name': 'secure-byo-admission-fixture', 'namespace': namespace}
    template = {'apiVersion': 'api.kagent.dev/v1alpha3', 'kind': 'AgentTemplate',
                'metadata': metadata, 'spec': {'modelConfig': {'name': config['modelConfig']},
                'skills': [{'name': 'reviewed', 'source': {'oci': config['contentImages'][0], 'path': 'skill'}}]}}
    if config.get('templateTools'):
        template['spec']['tools'] = deepcopy(config['templateTools'])
    results = []

    def add(identifier, resource, allowed, rule=None, username=composer, operation='CREATE'):
        results.append({'id': identifier, 'object': deepcopy(resource), 'allowed': allowed,
                        'rule': rule, 'username': username, 'operation': operation})

    add('approved-template', template, True)
    changed = deepcopy(template)
    changed['spec']['modelConfig']['name'] = 'unapproved-provider'
    add('reject-model', changed, False, 'template-model-and-content')
    changed = deepcopy(template)
    changed['spec']['skills'][0]['source']['oci'] = 'registry.example.invalid/unreviewed:latest'
    add('reject-mutable-skill', changed, False, 'template-model-and-content')
    changed = deepcopy(template)
    changed['spec']['tools'] = [{'mcp': {'server': {'kind': 'RemoteMCPServer', 'name': 'arbitrary'}, 'tools': ['execute']}}]
    add('reject-tool-widening', changed, False, 'template-model-and-content')
    add('reject-tenant-template', template, False, 'composer-owned-native-agent', username='untrusted-owner')
    agent = {'apiVersion': 'api.kagent.dev/v1alpha3', 'kind': 'Agent', 'metadata': metadata,
             'spec': {'harnessRef': {'name': config['harness']}, 'template': {'ref': {'name': 'reviewed'}}}}
    add('approved-agent', agent, True)
    changed = deepcopy(agent)
    changed['spec']['harnessRef']['name'] = 'unapproved-runtime'
    add('reject-harness', changed, False, 'agent-harness-and-template')
    changed = deepcopy(agent)
    changed['spec']['template'] = {'inline': template['spec']}
    add('reject-inline-template', changed, False, 'agent-harness-and-template')
    for kind, api in [('HTTPRoute', 'gateway.networking.k8s.io/v1'),
                      ('ReferenceGrant', 'gateway.networking.k8s.io/v1beta1'),
                      ('NetworkPolicy', 'networking.k8s.io/v1')]:
        obj = {'apiVersion': api, 'kind': kind, 'metadata': metadata, 'spec': {}}
        add('reject-owner-' + kind.lower(), obj, False, 'platform-owned-scaffolding', username='untrusted-owner')
        add('reject-owner-delete-' + kind.lower(), obj, False, 'platform-owned-scaffolding', username='untrusted-owner', operation='DELETE')
    pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': metadata, 'spec': {
        'serviceAccountName': config.get('workloadServiceAccounts', ['default'])[0],
        'containers': [{'name': 'fixture', 'image': config.get('workloadImages', ['registry.example.invalid/runtime:fixture'])[0],
                        'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}}}]}}
    add('approved-pod', pod, True)
    changed = deepcopy(pod)
    changed['spec']['containers'][0]['securityContext']['privileged'] = True
    add('reject-privileged', changed, False, 'workload-safety-0')
    changed = deepcopy(pod)
    changed['spec']['hostNetwork'] = True
    add('reject-host-network', changed, False, 'workload-safety-0')
    changed = deepcopy(pod)
    changed['spec']['serviceAccountName'] = 'privileged-account'
    add('reject-account-spoof', changed, False, 'workload-safety-0')
    changed = deepcopy(pod)
    changed['metadata'] = deepcopy(metadata)
    changed['metadata']['labels'] = {config.get('reservedLabelPrefixes', ['secure-byo.platform/'])[0] + 'role': 'runtime'}
    add('reject-runtime-label-spoof', changed, False, 'workload-safety-0', username='untrusted-owner')
    if config.get('requestKinds'):
        api, version, kind = config['requestKinds'][0].split('/')
        request = {'apiVersion': api + '/' + version, 'kind': kind, 'metadata': metadata,
                   'spec': {**deepcopy(config['requestEquals']), 'instructions': 'Use the reviewed content.'}}
        add('approved-request', request, True, username='untrusted-owner')
        changed = deepcopy(request)
        field = next(iter(config['requestEquals']))
        changed['spec'][field] = 'unapproved'
        add('reject-request-profile', changed, False, 'approved-owner-request', username='untrusted-owner')
    worker = config.get('workerException')
    if worker:
        worker_pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {
            'name': worker['deploymentName'] + '-fixture-pod', 'namespace': worker['namespaces'][0],
            'ownerReferences': [{'apiVersion': 'apps/v1', 'kind': 'ReplicaSet',
                                 'name': worker['deploymentName'] + '-fixture', 'uid': 'fixture-worker-owner', 'controller': True}]},
            'spec': {'serviceAccountName': worker['serviceAccount'], 'hostPID': True,
                     'volumes': [{'name': 'worker-host', 'hostPath': {'path': '/var/lib/reviewed-worker'}}],
                     'containers': [{'name': 'worker', 'image': worker['images'][0],
                                     'securityContext': {'privileged': True}}]}}
        add('approved-worker-exception', worker_pod, True, username=worker['controllerUsers'][-1])
        add('reject-worker-identity-copy', worker_pod, False, 'workload-safety-0', username='untrusted-owner')
        changed = deepcopy(worker_pod)
        changed['spec']['containers'][0]['image'] = 'registry.example.invalid/worker:unreviewed'
        add('reject-worker-image-copy', changed, False, 'workload-safety-0', username=worker['controllerUsers'][-1])
        changed = deepcopy(worker_pod)
        changed['metadata']['ownerReferences'][0]['name'] = 'unapproved-worker'
        add('reject-worker-lineage-copy', changed, False, 'workload-safety-0', username=worker['controllerUsers'][-1])
        changed = deepcopy(worker_pod)
        changed['spec']['ephemeralContainers'] = [{'name': 'debugger', 'image': worker['images'][0]}]
        add('reject-worker-ephemeral-container', changed, False, 'workload-safety-0', username=worker['controllerUsers'][-1])
    return results
