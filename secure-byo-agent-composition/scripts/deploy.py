#!/usr/bin/env python3
"""Render the complete local rehearsal before applying to an explicit target."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'composition'))
sys.path.insert(0, str(ROOT / 'policies'))
from lab_resources import NAMESPACES, build_baseline, build_profiles, obj
from compose import API, KIND, crd, generate, rgd, digest
from generate import build as build_policies


def listing(items):
    return {'apiVersion': 'v1', 'kind': 'List', 'items': items}


def hosted_platform(profile, settings):
    ns = profile['namespace']
    name = settings.get('agentName', 'demo')
    resources = profile['resources']
    managed = {}
    for child in resources:
        api = child['apiVersion']
        group = '' if api == 'v1' else api.rsplit('/', 1)[0]
        plural = {'AgentTemplate': 'agenttemplates', 'Agent': 'agents', 'ModelConfig': 'modelconfigs',
            'Harness': 'harnesses', 'EgressPolicy': 'egresspolicies', 'RemoteMCPServer': 'remotemcpservers', 'Service': 'services',
            'Deployment': 'deployments', 'NetworkPolicy': 'networkpolicies', 'ConfigMap': 'configmaps',
            'ReferenceGrant': 'referencegrants', 'HTTPRoute': 'httproutes',
            'AgentgatewayPolicy': 'agentgatewaypolicies', 'AgentgatewayBackend': 'agentgatewaybackends',
            'ServiceAccount': 'serviceaccounts'}[child['kind']]
        child_name = child['metadata']['name'].replace('{{NAME}}', name)
        managed.setdefault((group, plural), []).append(child_name)
    rules = [
        {'apiGroups': ['secure.platform.kagent.dev'], 'resources': ['hostedsecureagents'], 'verbs': ['get', 'list', 'watch']},
        {'apiGroups': ['secure.platform.kagent.dev'], 'resources': ['hostedsecureagents', 'hostedsecureagents/status', 'hostedsecureagents/finalizers'],
            'resourceNames': [name], 'verbs': ['get', 'update', 'patch']}]
    for (group, plural), names in managed.items():
        rules.append({'apiGroups': [group], 'resources': [plural], 'verbs': ['create']})
        rules.append({'apiGroups': [group], 'resources': [plural], 'resourceNames': sorted(set(names)),
            'verbs': ['get', 'update', 'patch', 'delete']})
    platform = [obj('v1', 'ServiceAccount', 'hosted-composer', ns),
        obj('rbac.authorization.k8s.io/v1', 'Role', 'hosted-composer', ns, rules=rules),
        obj('rbac.authorization.k8s.io/v1', 'RoleBinding', 'hosted-composer', ns,
            roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'hosted-composer'},
            subjects=[{'kind': 'ServiceAccount', 'name': 'hosted-composer', 'namespace': ns}]),
        obj('v1', 'ConfigMap', 'hosted-composer-profile', ns, data={'profile.json': json.dumps(profile, sort_keys=True)}),
        obj('apps/v1', 'Deployment', 'hosted-composer', ns, spec={'replicas': 1, 'strategy': {'type': 'Recreate'},
            'selector': {'matchLabels': {'app': 'hosted-composer'}},
            'template': {'metadata': {'labels': {'app': 'hosted-composer'}, 'annotations': {'secure-byo.platform/profile-sha256': digest(profile)}}, 'spec': {
                'serviceAccountName': 'hosted-composer',
                'securityContext': {'runAsNonRoot': True, 'runAsUser': 65532, 'seccompProfile': {'type': 'RuntimeDefault'}},
                'containers': [{'name': 'controller', 'image': settings['runtimeImage'],
                    'command': ['python3', '/app/composition/controller.py', '--profile', '/config/profile.json'],
                    'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                        'capabilities': {'drop': ['ALL']}},
                    'env': [{'name': 'PYTHONDONTWRITEBYTECODE', 'value': '1'}],
                    'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'}, 'limits': {'cpu': '250m', 'memory': '128Mi'}},
                    'volumeMounts': [{'name': 'profile', 'mountPath': '/config', 'readOnly': True}]}],
                'volumes': [{'name': 'profile', 'configMap': {'name': 'hosted-composer-profile'}}]}}})]
    network = settings.get('network', {})
    if network.get('apiCIDRs'):
        platform.append(obj('networking.k8s.io/v1', 'NetworkPolicy', 'hosted-composer-api', ns,
            spec={'podSelector': {'matchLabels': {'app': 'hosted-composer'}}, 'policyTypes': ['Ingress', 'Egress'],
                'ingress': [], 'egress': [{'to': [{'ipBlock': {'cidr': v}} for v in network['apiCIDRs']],
                    'ports': [{'protocol': 'TCP', 'port': p} for p in network.get('apiPorts', [443, 6443])]}]}))
    return platform


def central_routing(profiles, settings):
    namespace = settings.get('gatewayNamespace', 'secure-byo-gateway-system')
    result = []
    name = settings.get('agentName', 'demo')
    for ns, profile in profiles.items():
        profile['resources'] = [o for o in profile['resources'] if o['kind'] != 'HTTPRoute']
        profile['resources'].append(obj('gateway.networking.k8s.io/v1beta1', 'ReferenceGrant', '{{NAME}}-frontdoor', '{{NAMESPACE}}',
            spec={'from': [{'group': 'gateway.networking.k8s.io', 'kind': 'HTTPRoute', 'namespace': namespace}],
                'to': [{'group': '', 'kind': 'Service', 'name': '{{NAME}}-frontdoor'}]}))
        result.append(obj('gateway.networking.k8s.io/v1', 'HTTPRoute', ns, namespace,
            spec={'parentRefs': [{'name': settings.get('gatewayName', 'secure-byo'), 'sectionName': ns.rsplit('-', 1)[1]}],
                'rules': [{'matches': [{'path': {'type': 'PathPrefix', 'value': '/'}}],
                    'backendRefs': [{'name': name + '-frontdoor', 'namespace': ns, 'port': 8080}]}]}))
    for route in list(result):
        model_route = copy.deepcopy(route)
        model_route['metadata']['name'] += '-model'
        model_route['spec']['parentRefs'][0]['sectionName'] += '-model'
        result.append(model_route)
    return result


def configmap_writer_policy(profile, settings):
    ns = profile['namespace']
    user = 'system:serviceaccount:' + ns + ':hosted-composer'
    name = settings.get('agentName', 'demo')
    names = [o['metadata']['name'].replace('{{NAME}}', name) for o in profile['resources'] if o['kind'] == 'ConfigMap']
    expression = 'request.userInfo.username != ' + json.dumps(user) + ' || object.metadata.name in ' + json.dumps(names)
    return {'apiVersion': 'kyverno.io/v1', 'kind': 'ClusterPolicy',
        'metadata': {'name': 'secure-byo-composer-configmap-boundary'},
        'spec': {'background': False, 'failurePolicy': 'Fail', 'rules': [{
            'name': 'composer-cannot-publish-approval',
            'match': {'any': [{'resources': {'kinds': ['v1/ConfigMap'], 'namespaces': [ns], 'operations': ['CREATE', 'UPDATE']}}]},
            'validate': {'failureAction': 'Enforce', 'allowExistingViolations': False,
                'cel': {'expressions': [{'expression': expression,
                    'message': 'The hosting composer may write only its fixed generated frontdoor configuration.'}]}}}]}}


def render(snapshot, settings):
    profiles = build_profiles(snapshot, settings)
    for ns, profile in profiles.items():
        for resource in profile['resources']:
            if resource['kind'] == 'ConfigMap' and 'runtime.json' in resource.get('data', {}):
                config = json.loads(resource['data']['runtime.json'])
                if config.get('nativeUserID') and not config['nativeUserID'].endswith(ns):
                    config['nativeUserID'] += '-' + ns
                resource['data']['runtime.json'] = json.dumps(config, sort_keys=True)
    baseline = build_baseline(settings) + copy.deepcopy(settings.get('baselineExtra', []))
    routes = central_routing(profiles, settings) if settings.get('centralRouting') else []
    policy_config = copy.deepcopy(settings['policyConfig'])
    expected = set(NAMESPACES)
    if set(policy_config['namespaces']) != expected:
        raise ValueError('policyConfig namespaces must exactly match the two isolated POC namespaces')
    composer_user = 'system:serviceaccount:secure-byo-hosted:hosted-composer'
    if composer_user not in policy_config['composerUsers']:
        raise ValueError('policyConfig must admit the exact namespaced hosted composer identity')
    policies = build_policies(policy_config) + [configmap_writer_policy(profiles['secure-byo-hosted'], settings)]
    hosted = hosted_platform(profiles['secure-byo-hosted'], settings)
    name = settings.get('agentName', 'demo')
    instructions = settings.get('instructions', 'Load both reviewed skills, read their references, and call get_demo_status. Report only observed synthetic evidence.')
    requests = {}
    for ns in NAMESPACES:
        requests[ns] = {'apiVersion': API if ns.endswith('hosted') else 'kro.run/v1alpha1',
            'kind': KIND if ns.endswith('hosted') else 'SecureAgent',
            'metadata': {'name': name, 'namespace': ns},
            'spec': {'profileRef': profiles[ns]['name'], 'instructions': instructions}}
        generate(profiles[ns], requests[ns], owner=False)
    return {'profiles': profiles, 'baseline': listing(baseline), 'routes': listing(routes),
        'hosted-platform': listing(hosted), 'policies': listing(policies), 'hosted-crd': crd(),
        'kro-rgd': rgd(profiles['secure-byo-kro']), 'requests': requests}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kubeconfig', required=True)
    parser.add_argument('--context', required=True)
    parser.add_argument('--snapshot', required=True, help='JSON Kubernetes native object List')
    parser.add_argument('--settings', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--render-only', action='store_true')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    settings = json.loads(Path(args.settings).read_text())
    snapshot = json.loads(Path(args.snapshot).read_text())
    artifacts = render(snapshot, settings)
    for key in ('baseline', 'routes', 'hosted-platform', 'policies', 'hosted-crd', 'kro-rgd'):
        (output / (key + '.json')).write_text(json.dumps(artifacts[key], indent=2) + '\n')
    for ns, profile in artifacts['profiles'].items():
        (output / (ns + '-profile.json')).write_text(json.dumps(profile, indent=2) + '\n')
        (output / (ns + '-request.json')).write_text(json.dumps(artifacts['requests'][ns], indent=2) + '\n')
    if args.render_only:
        return
    kubectl = ['kubectl', '--kubeconfig', args.kubeconfig, '--context', args.context]
    def run(*argv):
        subprocess.run(kubectl + list(argv), check=True, timeout=180)
    run('get', 'nodes')
    for key in ('baseline', 'hosted-crd', 'policies', 'kro-rgd', 'hosted-platform', 'routes'):
        if artifacts[key].get('kind') == 'List' and not artifacts[key]['items']:
            continue
        run('apply', '-f', str(output / (key + '.json')))
        if key == 'hosted-crd':
            run('wait', '--for=condition=Established', 'crd/hostedsecureagents.secure.platform.kagent.dev', '--timeout=90s')
        if key == 'kro-rgd':
            run('wait', '--for=jsonpath={.status.state}=Active', 'resourcegraphdefinition/' + artifacts[key]['metadata']['name'], '--timeout=120s')
            run('wait', '--for=condition=Established', 'crd/secureagents.kro.run', '--timeout=90s')
        if key == 'hosted-platform':
            run('-n', 'secure-byo-hosted', 'rollout', 'status', 'deployment/hosted-composer', '--timeout=120s')
    for ns in NAMESPACES:
        run('--as', 'system:serviceaccount:' + ns + ':owner', 'apply', '-f', str(output / (ns + '-request.json')))
    print(json.dumps({'applied': True, 'output': str(output), 'acceptance': 'PENDING'}))


if __name__ == '__main__':
    main()
