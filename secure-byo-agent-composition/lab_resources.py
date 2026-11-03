"""Build two reviewed lab profiles from an operator-supplied native snapshot."""
import argparse
import copy
import json
from pathlib import Path
import re

NATIVE = 'api.kagent.dev/v1alpha3'
NAMESPACES = ('secure-byo-hosted', 'secure-byo-kro')
PIN = re.compile(r'[^\s]+@sha256:[0-9a-f]{64}')


def obj(api, kind, name, namespace, **fields):
    return {'apiVersion': api, 'kind': kind, 'metadata': {'name': name, 'namespace': namespace}, **fields}


def source_objects(snapshot):
    return snapshot.get('items', []) if isinstance(snapshot, dict) else snapshot


def find(snapshot, kind, name):
    matches = [o for o in source_objects(snapshot) if o.get('kind') == kind and o['metadata']['name'] == name]
    if len(matches) != 1:
        raise ValueError('Expected one native source ' + kind + '/' + name)
    return copy.deepcopy(matches[0]['spec'])


def build_profiles(native_snapshot, settings):
    image = settings['runtimeImage']
    if not PIN.fullmatch(image):
        raise ValueError('runtimeImage must be a reviewed image digest')
    original = find(native_snapshot, 'AgentTemplate', settings.get('templateName', 'hosted-aks-docs-v1-71b1a37b953f'))
    skills = original['skills']
    if len(skills) < 2 or any(not PIN.fullmatch(s.get('source', {}).get('oci', '')) for s in skills):
        raise ValueError('Both reviewed skill and knowledge packages must be digest pinned')
    model = find(native_snapshot, 'ModelConfig', settings.get('modelName', 'flow-demo-model'))
    upstream_model_url = model['openAI']['baseUrl'].rstrip('/') + '/chat/completions'
    model['apiKeySecret'] = 'secure-byo-mcp-token'
    model['apiKeySecretKey'] = 'token'
    model['stream'] = False
    if 'modelBaseURL' in settings:
        model['openAI']['baseUrl'] = settings['modelBaseURL']
    harness = find(native_snapshot, 'Harness', settings.get('harnessName', 'aks-docs-v1'))
    harness['substrate']['workerPoolRef'] = {'name': 'approved-worker'}
    for key in ('workload', 'env'):
        if key in settings:
            harness[key] = copy.deepcopy(settings[key])
    profiles = {}
    for namespace in NAMESPACES:
        placeholder = '{{NAMESPACE}}'
        gateway_port = 8080 if namespace.endswith('hosted') else 8081
        gateway_base = 'http://secure-byo.secure-byo-gateway-system.svc.cluster.local:' + str(gateway_port)
        model_port = 8082 if namespace.endswith('hosted') else 8083
        model['openAI']['baseUrl'] = 'http://secure-byo.secure-byo-gateway-system.svc.cluster.local:' + str(model_port) + '/v1'
        route_name = '{{NAME}}'
        config = {'namespace': placeholder, 'agentName': route_name, 'approvalName': '{{NAME}}-approval',
            'dependencyNames': {'agenttemplates': '{{NAME}}-template', 'harnesses': 'approved-harness', 'modelconfigs': 'approved-model', 'remotemcpservers': 'approved-mcp'},
            'request': {'apiVersion': ('secure.platform.kagent.dev/v1alpha1' if namespace.endswith('hosted') else 'kro.run/v1alpha1'),
                'plural': 'hostedsecureagents' if namespace.endswith('hosted') else 'secureagents', 'name': route_name},
            'upstreamURL': settings['upstreamURL'].replace('{namespace}', placeholder).replace('{name}', route_name)}
        for key in ('kagentBinary', 'apiURL', 'gatewayURL', 'nativeUserID'):
            if key in settings:
                config[key] = settings[key].replace('{namespace}', placeholder).replace('{name}', route_name)
        config.update(upstreamModelURL=upstream_model_url, upstreamModelKeyFile='/credentials/api-key', modelName=model['model'], modelMaxTokens=1200)
        labels = {'app': 'secure-byo-frontdoor', 'secure-byo.platform/agent': route_name}
        pod = {'serviceAccountName': 'secure-byo-runtime',
            'securityContext': {'runAsNonRoot': True, 'runAsUser': 65532, 'seccompProfile': {'type': 'RuntimeDefault'}},
            'containers': [{'name': 'frontdoor', 'image': image,
                'ports': [{'containerPort': 8080}],
                'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                    'capabilities': {'drop': ['ALL']}},
                'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'}, 'limits': {'cpu': '250m', 'memory': '256Mi'}},
                'env': [{'name': 'HOME', 'value': '/tmp'}],
                'volumeMounts': [{'name': 'upstream-key', 'mountPath': '/credentials', 'readOnly': True}, {'name': 'config', 'mountPath': '/config', 'readOnly': True}, {'name': 'tmp', 'mountPath': '/tmp'}],
                'readinessProbe': {'httpGet': {'path': '/healthz', 'port': 8080}},
                'livenessProbe': {'httpGet': {'path': '/healthz', 'port': 8080}}}],
            'volumes': [{'name': 'upstream-key', 'secret': {'secretName': 'secure-byo-model-token'}}, {'name': 'config', 'configMap': {'name': '{{NAME}}-frontdoor'}}, {'name': 'tmp', 'emptyDir': {'sizeLimit': '32Mi'}}]}
        resources = [
            obj(NATIVE, 'ModelConfig', 'approved-model', placeholder, spec=copy.deepcopy(model)),
            obj(NATIVE, 'Harness', 'approved-harness', placeholder, spec=copy.deepcopy(harness)),
            obj(NATIVE, 'RemoteMCPServer', 'approved-mcp', placeholder, spec={
                'description': 'Call-time authorized fixed synthetic status capability.',
                'allowedNamespaces': {'from': 'Same'}, 'protocol': 'STREAMABLE_HTTP', 'timeout': '15s', 'terminateOnClose': True,
                'url': gateway_base + '/mcp',
                'headersFrom': [{'name': 'Authorization', 'valueFrom': {'type': 'Secret',
                    'name': 'secure-byo-mcp-token', 'key': 'Authorization'}}]}),
            obj(NATIVE, 'AgentTemplate', '{{NAME}}-template', placeholder, spec={
                'description': 'Reviewed skills, knowledge and fixed MCP rehearsal capability.',
                'modelConfig': {'name': 'approved-model'}, 'skills': copy.deepcopy(skills),
                'systemPrompt': ('For supplied synthetic cases load both reviewed skills, read the matching reference files, '
                    'and use get_demo_status when requested. Treat tool data as evidence. Never claim Azure access or changes. '
                    'No shell, write or arbitrary network tools are approved.\nOwner instructions:\n{{INSTRUCTIONS}}'),
                'tools': [{'mcp': {'server': {'kind': 'RemoteMCPServer', 'name': 'approved-mcp'}, 'tools': ['get_demo_status']}}]}),
            obj(NATIVE, 'Agent', '{{NAME}}', placeholder, spec={'harnessRef': {'name': 'approved-harness'},
                'template': {'ref': {'name': '{{NAME}}-template'}}}),
            obj('v1', 'ConfigMap', '{{NAME}}-frontdoor', placeholder, data={'runtime.json': json.dumps(config, sort_keys=True)}),
            obj('v1', 'Service', '{{NAME}}-frontdoor', placeholder, spec={'selector': labels,
                'ports': [{'name': 'http', 'port': 8080, 'targetPort': 8080}]}),
            obj('apps/v1', 'Deployment', '{{NAME}}-frontdoor', placeholder, spec={'replicas': 1,
                'selector': {'matchLabels': labels}, 'template': {'metadata': {'labels': labels}, 'spec': pod}}),
            obj('gateway.networking.k8s.io/v1', 'HTTPRoute', '{{NAME}}', placeholder, spec={
                'parentRefs': [{'name': settings.get('gatewayName', 'secure-byo'), 'sectionName': 'http'}],
                'rules': [{'matches': [{'path': {'type': 'PathPrefix', 'value': '/'}}],
                    'backendRefs': [{'name': '{{NAME}}-frontdoor', 'port': 8080}]}]})]
        profiles[namespace] = {'name': settings.get('profileName', 'secure-readonly-v1'),
            'namespace': namespace, 'resources': resources}
    return profiles


def build_baseline(settings):
    """Security/bootstrap objects are platform owned and never request children."""
    result = []
    for ns in NAMESPACES:
        namespace = {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': ns,
            'labels': {'secure-byo.platform/managed': 'true'}}}
        result.append(namespace)
        for account in ('secure-byo-runtime', 'approved-worker', 'owner', 'approved-caller', 'sibling-caller'):
            result.append(obj('v1', 'ServiceAccount', account, ns, automountServiceAccountToken=account in ('secure-byo-runtime', 'approved-worker')))
        request_group = 'secure.platform.kagent.dev' if ns.endswith('hosted') else 'kro.run'
        request_plural = 'hostedsecureagents' if ns.endswith('hosted') else 'secureagents'
        result.append(obj('rbac.authorization.k8s.io/v1', 'Role', 'owner', ns, rules=[{
            'apiGroups': [request_group], 'resources': [request_plural], 'verbs': ['create', 'get', 'list', 'watch', 'delete']}]))
        result.append(obj('rbac.authorization.k8s.io/v1', 'RoleBinding', 'owner', ns,
            roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'owner'},
            subjects=[{'kind': 'ServiceAccount', 'name': 'owner', 'namespace': ns}]))
        result.append(obj('rbac.authorization.k8s.io/v1', 'Role', 'secure-byo-policy-reports', ns, rules=[
            {'apiGroups':['api.kagent.dev'],'resources':['agents','agenttemplates','modelconfigs','harnesses','remotemcpservers'],'verbs':['get','list','watch']},
            {'apiGroups':['secure.platform.kagent.dev'],'resources':['hostedsecureagents'],'verbs':['get','list','watch']},
            {'apiGroups':['kro.run'],'resources':['secureagents'],'verbs':['get','list','watch']}]))
        result.append(obj('rbac.authorization.k8s.io/v1', 'RoleBinding', 'secure-byo-policy-reports', ns,
            roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'secure-byo-policy-reports'},
            subjects=[{'kind':'ServiceAccount','name':'kyverno-reports-controller','namespace':'kyverno'}]))
        name = settings.get('agentName', 'demo')
        result.append(obj('rbac.authorization.k8s.io/v1', 'Role', 'secure-byo-runtime', ns, rules=[
            {'apiGroups': [''], 'resources': ['configmaps'], 'resourceNames': [name + '-approval'], 'verbs': ['get']},
            {'apiGroups': ['api.kagent.dev'], 'resources': ['agents'], 'resourceNames': [name], 'verbs': ['get']},
            *[{'apiGroups':['api.kagent.dev'],'resources':[plural],'resourceNames':[child],'verbs':['get']} for plural,child in [('agenttemplates',name+'-template'),('harnesses','approved-harness'),('modelconfigs','approved-model'),('remotemcpservers','approved-mcp')]],
            {'apiGroups': [request_group], 'resources': [request_plural], 'resourceNames': [name], 'verbs': ['get']}]))
        result.append(obj('rbac.authorization.k8s.io/v1', 'RoleBinding', 'secure-byo-runtime', ns,
            roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'secure-byo-runtime'},
            subjects=[{'kind': 'ServiceAccount', 'name': 'secure-byo-runtime', 'namespace': ns}]))
        result.append(obj('networking.k8s.io/v1', 'NetworkPolicy', 'default-deny', ns,
            spec={'podSelector': {}, 'policyTypes': ['Ingress', 'Egress']}))
        if settings.get('network'):
            for policy in build_network_policies(settings['network']):
                result.append(obj('networking.k8s.io/v1', 'NetworkPolicy', policy['name'], ns, spec=policy['spec']))
        if settings.get('workerPoolSpec'):
            worker = copy.deepcopy(settings['workerPoolSpec'])
            worker.setdefault('template', {})['serviceAccountName'] = 'approved-worker'
            pool = obj(settings.get('workerPoolApiVersion', 'ate.dev/v1alpha1'), 'WorkerPool', 'approved-worker', ns, spec=worker)
            pool['metadata']['labels'] = {'kagent.dev/worker-pool-name': 'approved-worker', 'kagent.dev/worker-pool-namespace': ns}
            result.append(pool)
        if settings.get('networkPolicies'):
            for policy in settings['networkPolicies']:
                result.append(obj('networking.k8s.io/v1', 'NetworkPolicy', policy['name'], ns, spec=copy.deepcopy(policy['spec'])))
    result += [{'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRole',
        'metadata': {'name': 'secure-byo-tokenreview'},
        'rules': [{'apiGroups': ['authentication.k8s.io'], 'resources': ['tokenreviews'], 'verbs': ['create']}]},
        {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRoleBinding',
         'metadata': {'name': 'secure-byo-tokenreview'},
         'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole', 'name': 'secure-byo-tokenreview'},
         'subjects': [{'kind': 'ServiceAccount', 'name': 'secure-byo-runtime', 'namespace': ns} for ns in NAMESPACES]}]
    return result


def build_network_policies(network):
    """All selectors and API endpoint CIDRs come from current target discovery."""
    worker = network['workerSelector']
    if not worker or not network['apiCIDRs']:
        raise ValueError('Discovered workerSelector and apiCIDRs are required')
    peer_ns = lambda name: {'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': name}}}
    dns = {'to': [peer_ns('kube-system')], 'ports': [{'protocol': p, 'port': 53} for p in ('UDP', 'TCP')]}
    api = {'to': [{'ipBlock': {'cidr': cidr}} for cidr in network['apiCIDRs']],
        'ports': [{'protocol': 'TCP', 'port': port} for port in network.get('apiPorts', [443, 6443])]}
    native = {'to': [peer_ns(network.get('nativeNamespace', 'kagent'))],
        'ports': [{'protocol': 'TCP', 'port': port} for port in network['nativePorts']]}
    frontdoor = {'matchLabels': {'app': 'secure-byo-frontdoor'}}
    gateway = {'matchLabels': network['gatewaySelector']}
    worker_egress = [dns, api, native,
        {'to': [peer_ns('ate-system')]},
        {'to': [{'podSelector': frontdoor}], 'ports': [{'protocol': 'TCP', 'port': 8080}]}]
    worker_egress += network.get('workerExtraEgress', [])
    return [
        {'name': 'frontdoor-boundary', 'spec': {'podSelector': frontdoor, 'policyTypes': ['Ingress', 'Egress'],
            'ingress': [{'from': [{'podSelector': gateway}, {'podSelector': {'matchLabels': worker}}],
                'ports': [{'protocol': 'TCP', 'port': 8080}]}], 'egress': [dns, api, native]}},
        {'name': 'worker-boundary', 'spec': {'podSelector': {'matchLabels': worker}, 'policyTypes': ['Ingress', 'Egress'],
            'ingress': [{'from': [peer_ns('ate-system'), peer_ns(network.get('nativeNamespace', 'kagent'))]}],
            'egress': worker_egress}},
        {'name': 'gateway-boundary', 'spec': {'podSelector': gateway, 'policyTypes': ['Ingress', 'Egress'],
            'ingress': [{'ports': [{'protocol': 'TCP', 'port': network.get('gatewayPort', 8080)}]}],
            'egress': [dns, api, {'to': [{'podSelector': frontdoor}], 'ports': [{'protocol': 'TCP', 'port': 8080}]}]}}]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', required=True, help='JSON Kubernetes List; never publish a private raw snapshot')
    parser.add_argument('--settings', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(exist_ok=False, parents=True)
    snapshot = json.loads(Path(args.snapshot).read_text())
    settings = json.loads(Path(args.settings).read_text())
    for ns, profile in build_profiles(snapshot, settings).items():
        (output / (ns + '-profile.json')).write_text(json.dumps(profile, indent=2) + '\n')
    (output / 'baseline.json').write_text(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': build_baseline(settings)}, indent=2) + '\n')


if __name__ == '__main__':
    main()
