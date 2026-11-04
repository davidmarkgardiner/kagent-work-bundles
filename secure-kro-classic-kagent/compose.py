"""Render a native non-Substrate kagent Agent and its KRO security composition."""
import argparse
import copy
import json
from pathlib import Path

import gateway_baseline


def cel(value):
    if isinstance(value, dict):
        return '{' + ','.join(json.dumps(k) + ':dyn(' + cel(v) + ')' for k, v in value.items()) + '}'
    if isinstance(value, list):
        return '[' + ','.join('dyn(' + cel(v) + ')' for v in value) + ']'
    return json.dumps(value)


def compose(profile):
    p = copy.deepcopy(profile)
    if p.get('nativeAPI') != 'kagent.dev/v1alpha2' or not p.get('models') or p.get('runtime') not in ('go', 'python'):
        raise ValueError('A reviewed 0.x API, model catalog and native runtime are required.')
    for tool in p['tools'].values():
        mcp = tool.get('mcpServer', {})
        if tool.get('type') != 'McpServer' or mcp.get('apiGroup') != 'kagent.dev' or mcp.get('kind') != 'RemoteMCPServer' or not mcp.get('toolNames'):
            raise ValueError('Require same-namespace named MCP servers and explicit operations.')
        if mcp.get('namespace') not in (None, p['namespace']):
            raise ValueError('Cross-namespace MCP references require a separately reviewed profile.')
    skill_modes = {entry['mode'] for entry in p['skills'].values()}
    if len(skill_modes) > 1 or skill_modes - {'oci', 'git'}:
        raise ValueError('Use one reviewed skill source mode per profile, OCI or Git.')
    name = '${schema.metadata.name}'
    ns = '${schema.metadata.namespace}'
    def obj(api, kind, suffix='', namespace=None, **values):
        return {'apiVersion': api, 'kind': kind, 'metadata': {'name': name + suffix, 'namespace': namespace or ns}, **values}
    nodes = []
    def add(ident, template, **options):
        nodes.append({'id': ident, 'template': template, **options})
    def selection(catalog, typename):
        return ('[]' + typename + ' | default=[] maxItems=' + str(len(catalog)) + ' uniqueItems=true immutable=true') if catalog else '[]string | default=[] maxItems=0 immutable=true'
    types = {}
    for catalog, typename in [(p['skills'], 'SkillID'), (p['tools'], 'ToolID')]:
        if catalog:
            types[typename] = 'string | enum=' + ','.join(catalog)
    spec = {'modelConfig': 'string | required=true enum=' + ','.join(p['models']) + ' immutable=true',
            'systemPrompt': 'string | required=true minLength=1 maxLength=4096 immutable=true',
            'skills': selection(p['skills'], 'SkillID'), 'tools': selection(p['tools'], 'ToolID')}
    if p['skills']:
        # The 0.x native CRD requires a nonempty refs/gitRefs array when skills is present.
        spec['skills'] = spec['skills'].replace('default=[]', 'required=true minItems=1')
    agent_spec = {'type': 'Declarative', 'description': 'KRO-composed native agent without Substrate',
        'declarative': {'runtime': p['runtime'], 'modelConfig': '${schema.spec.modelConfig}',
            'systemMessage': '${schema.spec.systemPrompt}', 'stream': False,
            'tools': '${schema.spec.tools.map(id, ' + cel(p['tools']) + '[id])}' if p['tools'] else [],
            'deployment': {'serviceAccountName': '${runtimeAccount.metadata.name}',
                'resources': {'requests': {'cpu': '25m', 'memory': '64Mi'}, 'limits': {'cpu': '1000m', 'memory': '256Mi'}},
                'env': [{'name': 'HOME', 'value': '/tmp'}],
                'podSecurityContext': {'runAsNonRoot': True, 'runAsUser': 1000, 'fsGroup': 1000, 'seccompProfile': {'type': 'RuntimeDefault'}},
                'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}},
                'volumes': [{'name': 'writable-tmp', 'emptyDir': {'sizeLimit': '64Mi'}}],
                'volumeMounts': [{'name': 'writable-tmp', 'mountPath': '/tmp'}]}}}
    if skill_modes == {'oci'}:
        mapping = {k: v['ref'] for k, v in p['skills'].items()}
        if any('@sha256:' not in ref for ref in mapping.values()):
            raise ValueError('OCI skill artifacts must be digest-pinned.')
        agent_spec['skills'] = {'refs': '${schema.spec.skills.map(id, ' + cel(mapping) + '[id])}'}
    if skill_modes == {'git'}:
        mapping = {k: v['git'] for k, v in p['skills'].items()}
        agent_spec['skills'] = {'gitRefs': '${schema.spec.skills.map(id, ' + cel(mapping) + '[id])}'}
        if p.get('gitAuthSecretName'):
            agent_spec['skills']['gitAuthSecretRef'] = {'name': p['gitAuthSecretName']}
    add('runtimeAccount', obj('v1', 'ServiceAccount', '-runtime', automountServiceAccountToken=False))
    add('verifierAccount', obj('v1', 'ServiceAccount', '-verifier', automountServiceAccountToken=False))
    add('callerAccount', obj('v1', 'ServiceAccount', '-caller', automountServiceAccountToken=False))
    add('agent', obj('kagent.dev/v1alpha2', 'Agent', spec=agent_spec), readyWhen=[
        '${agent.status.conditions.exists(c, c.type == "Accepted" && c.status == "True" && c.observedGeneration == agent.metadata.generation)}',
        '${agent.status.conditions.exists(c, c.type == "Ready" && c.status == "True" && c.observedGeneration == agent.metadata.generation)}'])
    add('network', obj('networking.k8s.io/v1', 'NetworkPolicy', '-boundary', spec={
        'podSelector': {'matchLabels': {'app': 'kagent', 'kagent': name}}, 'policyTypes': ['Ingress', 'Egress'],
        'ingress': [{'from': [{'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': p['gatewayNamespace']}},
                              'podSelector': {'matchLabels': {'gateway.networking.k8s.io/gateway-name': p['gatewayName']}}}],
                     'ports': [{'protocol': 'TCP', 'port': 8080}]}],
        'egress': p['agentEgress']}))
    base_path = '/classic/' + p['namespace'] + '/' + name
    verify_subject = 'system:serviceaccount:' + p['namespace'] + ':' + name + '-verifier'
    caller_subject = 'system:serviceaccount:' + p['namespace'] + ':' + name + '-caller'
    def policy(ident, suffix, subject):
        expression = 'jwt.sub == ' + json.dumps(subject)
        add(ident, obj('agentgateway.dev/v1alpha1', 'AgentgatewayPolicy', suffix, spec={
            'targetRefs': [{'group': 'gateway.networking.k8s.io', 'kind': 'HTTPRoute', 'name': name + suffix}],
            'traffic': {'jwtAuthentication': {'mode': 'Strict', 'preserveToken': False,
                         'providers': [{'issuer': p['issuer'], 'audiences': [p['audience']], 'jwks': {'inline': p['jwks']}}]},
                        'authorization': {'action': 'Require', 'policy': {'matchExpressions': [expression]}}}}))
    policy('verifierPolicy', '-verify', verify_subject)
    policy('cardPolicy', '-card', verify_subject)
    policy('callerPolicy', '-invoke', caller_subject)
    def route(ident, suffix, path, rewrite, policy_node, gated=False):
        annotations = {'classic.kagent.dev/policy': '${' + policy_node + '.metadata.name}'}
        if gated:
            annotations['classic.kagent.dev/verified-job'] = '${golden.metadata.name}'
        add(ident, obj('gateway.networking.k8s.io/v1', 'HTTPRoute', suffix,
            annotations=annotations, spec={
                'parentRefs': [{'name': p['gatewayName'], 'namespace': p['gatewayNamespace'], 'sectionName': p['callerListener'] if gated else p['verifyListener']}],
                'rules': [{'matches': [{'path': {'type': 'Exact', 'value': path}}],
                    'filters': [{'type': 'URLRewrite', 'urlRewrite': {'path': {'type': 'ReplaceFullPath', 'replaceFullPath': rewrite}}}],
                    'backendRefs': [{'name': '${agent.metadata.name}', 'namespace': '${agent.metadata.namespace}', 'port': 8080}]}]}))
        nodes[-1]['readyWhen'] = [
            '${' + ident + '.status.parents.exists(p, p.conditions.exists(c, c.type == "Accepted" && c.status == "True" && c.observedGeneration == ' + ident + '.metadata.generation) && p.conditions.exists(c, c.type == "ResolvedRefs" && c.status == "True" && c.observedGeneration == ' + ident + '.metadata.generation))}']
    route('verifyRoute', '-verify', base_path + '/verify', '/', 'verifierPolicy')
    route('cardRoute', '-card', base_path + '/card', '/.well-known/agent-card.json', 'cardPolicy')
    config = {'invokeURL': p['verifyGatewayURL'] + base_path + '/verify', 'cardURL': p['verifyGatewayURL'] + base_path + '/card',
              'callerURL': p['callerGatewayURL'] + base_path + '/invoke', 'expectedAgent': name,
              'requestUID': '${schema.metadata.uid}', 'tokenFile': '/var/run/golden/token', 'timeoutSeconds': 480}
    add('goldenConfig', obj('v1', 'ConfigMap', '-golden', data={'config.json': json.dumps(config)}))
    verifier_peer = {'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': p['gatewayNamespace']}},
                     'podSelector': {'matchLabels': {'gateway.networking.k8s.io/gateway-name': p['gatewayName']}}}
    add('verifierNetwork', obj('networking.k8s.io/v1', 'NetworkPolicy', '-verifier', spec={
        'podSelector': {'matchLabels': {'classic.kagent.dev/verifier': name}}, 'policyTypes': ['Ingress', 'Egress'],
        'egress': [p['dnsEgress'], {'to': [verifier_peer], 'ports': [{'protocol': 'TCP', 'port': port}
                    for port in sorted({p['gatewayPort'], p['callerPort']})]}]}))
    add('golden', obj('batch/v1', 'Job', '-golden', annotations={
        'classic.kagent.dev/agent': '${agent.metadata.name}', 'classic.kagent.dev/route': '${verifyRoute.metadata.name}',
        'classic.kagent.dev/card-route': '${cardRoute.metadata.name}'}, spec={
        'backoffLimit': 0, 'activeDeadlineSeconds': 600,
        'template': {'metadata': {'labels': {'classic.kagent.dev/verifier': name, 'classic.kagent.dev/request-uid': '${schema.metadata.uid}'}},
            'spec': {'serviceAccountName': '${verifierAccount.metadata.name}', 'automountServiceAccountToken': False, 'restartPolicy': 'Never',
                'securityContext': {'runAsNonRoot': True, 'runAsUser': 65532, 'seccompProfile': {'type': 'RuntimeDefault'}},
                'containers': [{'name': 'golden', 'image': p['verifierImage'],
                    'command': ['python3', '-B', '/app/golden.py', '--config', '/golden/config.json'],
                    'securityContext': {'readOnlyRootFilesystem': True, 'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
                    'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'}, 'limits': {'cpu': '500m', 'memory': '128Mi'}},
                    'volumeMounts': [{'name': 'config', 'mountPath': '/golden', 'readOnly': True},
                                     {'name': 'jwt', 'mountPath': '/var/run/golden', 'readOnly': True}]}],
                'volumes': [{'name': 'config', 'configMap': {'name': '${goldenConfig.metadata.name}'}},
                    {'name': 'jwt', 'projected': {'sources': [{'serviceAccountToken': {'audience': p['audience'], 'expirationSeconds': 600, 'path': 'token'}}]}}]}}}),
        readyWhen=['${golden.status.succeeded == 1}'])
    route('callerRoute', '-invoke', base_path + '/invoke', '/', 'callerPolicy', gated=True)
    graph = {'apiVersion': 'kro.run/v1alpha1', 'kind': 'ResourceGraphDefinition', 'metadata': {'name': 'classic-secure-agent'},
        'spec': {'schema': {'apiVersion': 'v1alpha1', 'group': 'demo.kagent.dev', 'kind': 'ClassicSecureAgent',
            'types': types, 'spec': spec, 'status': {'goldenSucceeded': '${golden.status.succeeded}', 'agentName': '${agent.metadata.name}'}},
            'resources': nodes}}
    # Annotations belong to metadata, not to the resource body.
    for node in nodes:
        resource = node['template']
        if 'annotations' in resource:
            resource['metadata']['annotations'] = resource.pop('annotations')
    owner = {'apiVersion': 'demo.kagent.dev/v1alpha1', 'kind': 'ClassicSecureAgent',
        'metadata': {'name': 'demo', 'namespace': p['namespace']},
        'spec': {'modelConfig': p['models'][0], 'systemPrompt': 'Reply accurately and concisely. Use only the approved tools when asked.',
                 'skills': list(p['skills'])[:1], 'tools': []}}
    return graph, owner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    graph, owner = compose(json.loads(args.profile.read_text()))
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (args.output / 'resourcegraphdefinition.json').write_text(json.dumps(graph, indent=2) + '\n')
    (args.output / 'agent.json').write_text(json.dumps(owner, indent=2) + '\n')
    (args.output / 'platform.json').write_text(json.dumps(gateway_baseline.resources(json.loads(args.profile.read_text())), indent=2) + '\n')
    print('Rendered native 0.x Agent composition without Substrate.')


if __name__ == '__main__':
    main()
