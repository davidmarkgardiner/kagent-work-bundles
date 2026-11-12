"""Render an isolated secured copy of the recorded Agent. Never applies resources."""
import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    namespace: str
    agent_name: str
    model_name: str
    issuer: str
    jwks_file: str
    api_server_cidr: str
    python_image: str
    gateway_image: str = 'cr.agentgateway.dev/agentgateway:v1.7.0@sha256:60216aafb03d37f94e952ff3d51d2f630a65b10ecaebdc0a864882f92610c45b'
    collector_image: str = 'otel/opentelemetry-collector-contrib:0.146.0@sha256:9742116fb9441d82900be0f35be168e14714fa64ff1f0f7aa182cfcf676832b1'
    tempo_image: str = 'grafana/tempo:2.9.0@sha256:65a5789759435f1ef696f1953258b9bbdb18eb571d5ce711ff812d2e128288a4'
    monitoring_namespace: str = 'monitoring'
    controller_namespace: str = 'kagent'
    model_namespace: str = 'agentgateway-system'
    model_app: str = 'agent-gw'
    model_port: int = 8081
    node_name: str = ''
    tolerate_control_plane: bool = False
    helper_memory_request: str = '64Mi'
    agent_memory_request: str = '192Mi'
    agent_memory_limit: str = '512Mi'

    def __post_init__(self):
        for value in (self.namespace, self.agent_name, self.model_name, self.monitoring_namespace,
                      self.controller_namespace, self.model_namespace, self.model_app):
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', value):
                raise ValueError('Resolve every Kubernetes name before rendering.')
        if not self.issuer.startswith('https://') or '{{' in self.issuer:
            raise ValueError('Resolve the approved HTTPS issuer.')


def obj(s, kind, name, api='v1', **fields):
    return {'apiVersion': api, 'kind': kind,
            'metadata': {'namespace': s.namespace, 'name': name,
                         'labels': {'app.kubernetes.io/part-of': 'dice-secured-demo'}}, **fields}


def service(s, name, ports, selector=None):
    return obj(s, 'Service', name, spec={'selector': selector or {'app': name},
        'ports': [{'name': n, 'port': p, 'targetPort': p} for n, p in ports]})


def deployment(s, name, image, command, ports, config, env=None, service_account=None):
    return obj(s, 'Deployment', name, 'apps/v1', spec={
        'replicas': 1, 'strategy': {'type': 'Recreate'}, 'selector': {'matchLabels': {'app': name}},
        'template': {'metadata': {'labels': {'app': name}}, 'spec': {
            'automountServiceAccountToken': bool(service_account),
            'serviceAccountName': service_account or 'default',
            'securityContext': {'runAsNonRoot': True, 'runAsUser': 1000,
                                'seccompProfile': {'type': 'RuntimeDefault'}},
            'containers': [{'name': name, 'image': image, 'command': command,
                'env': env or [], 'ports': [{'containerPort': p} for _, p in ports],
                'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                    'capabilities': {'drop': ['ALL']}},
                'resources': {'requests': {'cpu': '1m', 'memory': s.helper_memory_request},
                              'limits': {'cpu': '500m', 'memory': {'dice-agentgateway': '128Mi',
                                  'dice-collector': '128Mi', 'dice-tempo': '256Mi', 'dice-status-mcp': '64Mi'}[name]}},
                'volumeMounts': [{'name': 'config', 'mountPath': '/config', 'readOnly': True},
                                 {'name': 'data', 'mountPath': '/data'},
                                 {'name': 'tmp', 'mountPath': '/tmp'}]}],
            'volumes': [{'name': 'config', 'configMap': {'name': config}},
                        {'name': 'data', 'emptyDir': {}}, {'name': 'tmp', 'emptyDir': {}}]}}})


def gateway_config(s, jwks):
    routes = []
    for port, name, audience, subject, backend in [
        (8080, 'caller-to-agent', 'dice-a2a', 'dice-caller', s.agent_name + ':8080'),
        (8081, 'agent-to-mcp', 'dice-mcp', s.agent_name, 'dice-status-mcp:8084')]:
        policies = {
            'jwtAuth': {'mode': 'strict', 'issuer': s.issuer, 'audiences': [audience],
                        'jwks': json.dumps(jwks), 'preserveToken': False,
                        'jwtValidationOptions': {'requiredClaims': ['exp', 'iss', 'aud', 'sub']}},
            'authorization': {'rules': [{'require': 'jwt.sub == ' + json.dumps(
                'system:serviceaccount:' + s.namespace + ':' + subject)}]},
            'requestHeaderModifier': {'remove': ['cookie']},
            'timeout': {'requestTimeout': '180s'}}
        matches = ([{'path': {'exact': '/'}, 'method': 'POST'},
                    {'path': {'exact': '/.well-known/agent-card.json'}, 'method': 'GET'}] if port == 8080
                   else [{'path': {'exact': '/mcp'}, 'method': method} for method in ('POST', 'GET', 'DELETE')])
        routes.append({'port': port, 'listeners': [{'routes': [{
            'name': name, 'matches': matches, 'policies': policies, 'backends': [{'host': backend}]}]}]})
    return {'config': {'adminAddr': 'off', 'readinessAddr': '0.0.0.0:8086',
                       'statsAddr': '0.0.0.0:9090',
                       'tracing': {'otlpEndpoint': 'http://dice-collector:4317', 'randomSampling': True,
                                   'fields': {'add': {'demo.name': '"dice-secured-demo"'}}}},
            'binds': routes}


def collector_config(s):
    allowed = ['http.request.method', 'http.response.status_code', 'http.method', 'http.status_code',
        'rpc.method', 'rpc.system', 'mcp.tool.name', 'gen_ai.tool.name', 'gen_ai.operation.name',
        'gen_ai.request.model', 'gen_ai.response.model', 'gen_ai.usage.input_tokens',
        'gen_ai.usage.output_tokens', 'gen_ai.task.id', 'gen_ai.conversation.id',
        'flow.execution.id', 'flow.component', 'flow.simulated', 'demo.name']
    return {
        'receivers': {'otlp': {'protocols': {'grpc': {'endpoint': '0.0.0.0:4317'},
                                            'http': {'endpoint': '0.0.0.0:4318'}}}},
        'processors': {
            'filter/events': {'error_mode': 'propagate', 'traces': {'spanevent': ['true']}},
            'transform/privacy': {'error_mode': 'propagate', 'trace_statements': [
                {'context': 'resource', 'statements': ['keep_keys(attributes, ["service.name", "service.namespace"])']},
                {'context': 'span', 'statements': ['keep_keys(attributes, ' + json.dumps(allowed) + ')']}]},
            'batch': {'timeout': '500ms'}},
        'connectors': {'spanmetrics': {'namespace': 'dice', 'histogram': {'unit': 'ms'},
                                      'metrics_flush_interval': '5s',
                                      'dimensions': [{'name': 'mcp.tool.name'}, {'name': 'http.response.status_code'}]}},
        'exporters': {'otlp/tempo': {'endpoint': 'dice-tempo:4317', 'tls': {'insecure': True}},
                      'otlp_http/loki': {'endpoint': 'http://loki.' + s.monitoring_namespace + '.svc.cluster.local:3100/otlp'},
                      'prometheus': {'endpoint': '0.0.0.0:8889'}},
        'service': {'pipelines': {
            'traces': {'receivers': ['otlp'], 'processors': ['filter/events', 'transform/privacy', 'batch'],
                       'exporters': ['otlp/tempo', 'spanmetrics']},
            'metrics': {'receivers': ['spanmetrics'], 'exporters': ['prometheus']},
            'logs': {'receivers': ['otlp'], 'processors': ['batch'], 'exporters': ['otlp_http/loki']}}}}


def tempo_config():
    return {'auth_enabled': False, 'server': {'http_listen_port': 3200},
        'distributor': {'receivers': {'otlp': {'protocols': {
            'grpc': {'endpoint': '0.0.0.0:4317'}, 'http': {'endpoint': '0.0.0.0:4318'}}}}},
        'ingester': {'max_block_duration': '1m'},
        'compactor': {'compaction': {'block_retention': '24h'}},
        'storage': {'trace': {'backend': 'local', 'wal': {'path': '/data/wal'},
                             'local': {'path': '/data/blocks'}}},
        'usage_report': {'reporting_enabled': False}}


def peer(namespace=None, labels=None):
    result = {}
    if namespace:
        result['namespaceSelector'] = {'matchLabels': {'kubernetes.io/metadata.name': namespace}}
    if labels is not None:
        result['podSelector'] = {'matchLabels': labels}
    return result


def rule(direction, peers, ports):
    return {('from' if direction == 'ingress' else 'to'): peers,
            'ports': [{'protocol': protocol, 'port': port} for port, protocol in ports]}


def policy(s, name, labels, ingress=None, egress=None):
    spec = {'podSelector': {'matchLabels': labels}, 'policyTypes': []}
    for direction, value in [('ingress', ingress), ('egress', egress)]:
        if value is not None:
            spec['policyTypes'].append(direction.title())
            spec[direction] = value
    return obj(s, 'NetworkPolicy', name, 'networking.k8s.io/v1', spec=spec)


def render(s, agent, jwks, status):
    if agent['metadata']['name'] != s.agent_name or agent['spec']['type'] != 'Declarative':
        raise ValueError('Supply the selected declarative Agent snapshot.')
    if any('d' in key or key.get('kty') == 'oct' for key in jwks.get('keys', [])):
        raise ValueError('Only asymmetric public JWKS keys are allowed.')
    if not jwks.get('keys'):
        raise ValueError('Require actual issuer public keys.')
    ns = {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': s.namespace,
          'labels': {'app.kubernetes.io/part-of': 'dice-secured-demo'}}}
    items = [ns]
    for name in ('dice-caller', s.agent_name, 'dice-status-mcp'):
        items.append(obj(s, 'ServiceAccount', name, automountServiceAccountToken=False))
    for name, data in [('dice-agentgateway', {'config.yaml': json.dumps(gateway_config(s, jwks))}),
                       ('dice-collector', {'config.yaml': json.dumps(collector_config(s))}),
                       ('dice-tempo', {'config.yaml': json.dumps(tempo_config())}),
                       ('dice-status-code', {'fixed_mcp.py': (HERE / 'fixed_mcp.py').read_text()}),
                       ('dice-runtime-telemetry', {'sitecustomize.py': (HERE / 'bootstrap.py').read_text()}),
                       ('onboarding-status-data-v1', status)]:
        items.append(obj(s, 'ConfigMap', name, data=data))
    for name, image, command, ports in [
        ('dice-agentgateway', s.gateway_image, ['/app/agentgateway', '-f', '/config/config.yaml'],
            [('a2a', 8080), ('mcp', 8081), ('metrics', 9090)]),
        ('dice-collector', s.collector_image, ['/otelcol-contrib', '--config=/config/config.yaml'],
            [('grpc', 4317), ('http', 4318), ('metrics', 8889)]),
        ('dice-tempo', s.tempo_image, ['/tempo', '-config.file=/config/config.yaml'],
            [('http', 3200), ('grpc', 4317)])]:
        items.extend([deployment(s, name, image, command, ports, name), service(s, name, ports)])
    mcp = deployment(s, 'dice-status-mcp', s.python_image, ['python', '-B', '/config/fixed_mcp.py'],
        [('mcp', 8084)], 'dice-status-code', service_account='dice-status-mcp', env=[
            {'name': 'POD_NAMESPACE', 'value': s.namespace},
            {'name': 'STATUS_CONFIGMAP', 'value': 'onboarding-status-data-v1'},
            {'name': 'OTEL_HTTP_ENDPOINT', 'value': 'http://dice-collector:4318'}])
    items.extend([mcp, service(s, 'dice-status-mcp', [('mcp', 8084)]),
        obj(s, 'Role', 'dice-status-read', 'rbac.authorization.k8s.io/v1', rules=[{
            'apiGroups': [''], 'resources': ['configmaps'], 'resourceNames': ['onboarding-status-data-v1'], 'verbs': ['get']}]),
        obj(s, 'RoleBinding', 'dice-status-read', 'rbac.authorization.k8s.io/v1',
            roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'dice-status-read'},
            subjects=[{'kind': 'ServiceAccount', 'name': 'dice-status-mcp', 'namespace': s.namespace}]),
        obj(s, 'RemoteMCPServer', 'dice-gateway-mcp', 'kagent.dev/v1alpha2', spec={
            'description': 'Gateway-authenticated fixed synthetic status read',
            'protocol': 'STREAMABLE_HTTP', 'url': 'http://dice-agentgateway.' + s.namespace + '.svc.cluster.local:8081/mcp',
            'headersFrom': [{'name': 'Authorization', 'valueFrom': {
                'type': 'Secret', 'name': 'dice-agent-mcp-credential', 'key': 'authorization'}}],
            'timeout': '10s', 'sseReadTimeout': '5m0s', 'terminateOnClose': True})])
    cloned = obj(s, 'Agent', s.agent_name, 'kagent.dev/v1alpha2', spec=copy.deepcopy(agent['spec']))
    decl = cloned['spec']['declarative']
    decl['systemMessage'] += '\nFor the exact health-check request "Reply with exactly PONG. Do not call tools.", reply only PONG without loading skills or calling tools. For other requests follow the recorded demonstration instructions above.'
    decl['modelConfig'] = s.model_name
    decl['tools'] = [{'type': 'McpServer', 'mcpServer': {'apiGroup': 'kagent.dev', 'kind': 'RemoteMCPServer',
        'namespace': s.namespace, 'name': 'dice-gateway-mcp', 'toolNames': ['get_demo_status']}}]
    d = decl['deployment']
    d['serviceAccountName'] = s.agent_name
    d['resources'] = {'requests': {'cpu': '1m', 'memory': s.agent_memory_request},
                      'limits': {'cpu': '500m', 'memory': s.agent_memory_limit}}
    if s.node_name:
        d['nodeSelector'] = {'kubernetes.io/hostname': s.node_name}
    if s.tolerate_control_plane:
        d['tolerations'] = [{'key': 'node-role.kubernetes.io/control-plane',
                             'operator': 'Exists', 'effect': 'NoSchedule'}]
    d['env'] = [x for x in d.get('env', []) if x['name'] not in {
        'PYTHONPATH', 'HOSTED_TRACE_PROFILE', 'HOSTED_OTLP_ENDPOINT', 'KAGENT_PROPAGATE_TOKEN', 'STS_WELL_KNOWN_URI'}]
    d['env'].extend([{'name': 'PYTHONPATH', 'value': '/dice-telemetry'},
                     {'name': 'DICE_OTLP_ENDPOINT', 'value': 'http://dice-collector:4317'}])
    d['volumes'] = [x for x in d.get('volumes', []) if x['name'] != 'ordinary-telemetry']
    d['volumeMounts'] = [x for x in d.get('volumeMounts', []) if x['name'] != 'ordinary-telemetry']
    d['volumes'].append({'name': 'dice-telemetry', 'configMap': {'name': 'dice-runtime-telemetry'}})
    d['volumeMounts'].append({'name': 'dice-telemetry', 'mountPath': '/dice-telemetry', 'readOnly': True})
    d.setdefault('annotations', {})['demo.kagent.dev/telemetry-sha256'] = hashlib.sha256((HERE / 'bootstrap.py').read_bytes()).hexdigest()
    items.append(cloned)
    dns = rule('egress', [peer('kube-system', {'k8s-app': 'kube-dns'})], [(53, 'UDP'), (53, 'TCP')])
    col = rule('egress', [peer(labels={'app': 'dice-collector'})], [(4317, 'TCP'), (4318, 'TCP')])
    gateway = peer(labels={'app': 'dice-agentgateway'})
    agent_peer = peer(labels={'kagent': s.agent_name})
    mcp_peer = peer(labels={'app': 'dice-status-mcp'})
    collector_peer = peer(labels={'app': 'dice-collector'})
    items.extend([
        policy(s, 'default-deny', {}, [], []),
        policy(s, 'gateway', {'app': 'dice-agentgateway'}, [rule('ingress', [{'namespaceSelector': {}}], [(8080, 'TCP')]),
            rule('ingress', [agent_peer, peer(s.controller_namespace, {'app.kubernetes.io/component': 'controller'})], [(8081, 'TCP')])],
            [dns, col, rule('egress', [agent_peer], [(8080, 'TCP')]), rule('egress', [mcp_peer], [(8084, 'TCP')])]),
        policy(s, 'agent', {'kagent': s.agent_name}, [rule('ingress', [gateway], [(8080, 'TCP')])],
            [dns, col, rule('egress', [gateway], [(8081, 'TCP')]),
             rule('egress', [peer(s.controller_namespace, {'app.kubernetes.io/component': 'controller'})], [(8083, 'TCP')]),
             rule('egress', [peer(s.model_namespace, {'app.kubernetes.io/name': s.model_app})], [(s.model_port, 'TCP')])]),
        policy(s, 'mcp', {'app': 'dice-status-mcp'}, [rule('ingress', [gateway], [(8084, 'TCP')])],
            [dns, col, rule('egress', [{'ipBlock': {'cidr': s.api_server_cidr}}], [(443, 'TCP'), (6443, 'TCP')])]),
        policy(s, 'collector', {'app': 'dice-collector'},
            [rule('ingress', [gateway, agent_peer, mcp_peer], [(4317, 'TCP'), (4318, 'TCP')]),
             rule('ingress', [peer(s.monitoring_namespace, {'app.kubernetes.io/name': 'prometheus'})], [(8889, 'TCP')])],
            [dns, rule('egress', [peer(labels={'app': 'dice-tempo'})], [(4317, 'TCP')]),
             rule('egress', [peer(s.monitoring_namespace, {'app.kubernetes.io/name': 'loki'})], [(3100, 'TCP')])]),
        policy(s, 'tempo', {'app': 'dice-tempo'},
            [rule('ingress', [collector_peer], [(4317, 'TCP')]),
             rule('ingress', [peer(s.monitoring_namespace, {'app.kubernetes.io/name': 'grafana'})], [(3200, 'TCP')])], [dns]),
        obj(s, 'ServiceMonitor', 'dice-spanmetrics', 'monitoring.coreos.com/v1', spec={
            'selector': {'matchLabels': {'demo': 'dice-spanmetrics'}},
            'endpoints': [{'port': 'metrics', 'interval': '5s'}]})])
    items[-1]['metadata']['labels']['release'] = 'kube-prom'
    for item in items:
        if item['kind'] == 'Service' and item['metadata']['name'] == 'dice-collector':
            item['metadata']['labels']['demo'] = 'dice-spanmetrics'
    config_hashes = {item['metadata']['name']: hashlib.sha256(json.dumps(item['data'], sort_keys=True).encode()).hexdigest()
                     for item in items if item['kind'] == 'ConfigMap'}
    for item in items:
        if item['kind'] == 'Deployment':
            pod = item['spec']['template']['spec']
            config = next(v['configMap']['name'] for v in pod['volumes'] if v['name'] == 'config')
            item['spec']['template']['metadata']['annotations'] = {'demo.kagent.dev/config-sha256': config_hashes[config]}
            if s.node_name:
                pod['nodeSelector'] = {'kubernetes.io/hostname': s.node_name}
            if s.tolerate_control_plane:
                pod['tolerations'] = [{'key': 'node-role.kubernetes.io/control-plane',
                                      'operator': 'Exists', 'effect': 'NoSchedule'}]
    return {'apiVersion': 'v1', 'kind': 'List', 'items': items}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--agent', type=Path, required=True)
    parser.add_argument('--status', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    s = Settings(**json.loads(args.settings.read_text()))
    result = render(s, json.loads(args.agent.read_text()), json.loads(Path(s.jwks_file).read_text()),
                    json.loads(args.status.read_text())['data'])
    with args.output.open('x') as output:
        json.dump(result, output, indent=2)
    args.output.chmod(0o600)


if __name__ == '__main__':
    main()
