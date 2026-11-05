"""Build the offline presentation and its browsable YAML files from bundle sources."""
import hashlib
import json
from pathlib import Path

import yaml

import compose
import gateway_baseline

ROOT = Path(__file__).resolve().parent


def build():
    notes = json.loads((ROOT / 'demo/resource-notes.json').read_text())
    catalog = json.loads((ROOT / 'demo/catalog.json').read_text())
    graphs = {}
    resources = []
    output = ROOT / 'demo/yaml'
    output.mkdir(exist_ok=True)
    for variant, profile_path in [('model', 'examples/platform-profile.json'), ('catalog', 'examples/platform-profile-with-catalog.json')]:
        profile = json.loads((ROOT / profile_path).read_text())
        graph, _ = compose.compose(profile)
        assert {node['id'] for node in graph['spec']['resources']} == set(notes)
        graphs[variant] = graph
        directory = output / variant
        directory.mkdir(exist_ok=True)
        for index, node in enumerate(graph['spec']['resources'], 1):
            path = directory / (str(index).zfill(2) + '-' + node['id'] + '.yaml')
            text = '# KRO template from spec.resources. CEL is resolved by KRO.\n' + yaml.safe_dump(node['template'], sort_keys=False, width=100)
            path.write_text(text)
            if variant == 'model':
                resources.append({'id': node['id'], **notes[node['id']], 'kind': node['template']['kind'],
                                  'owner': 'KRO', 'origin': 'Exact RGD resource template, not a live resource snapshot',
                                  'path': str(path.relative_to(ROOT)), 'yaml': {'model': text}})
            else:
                next(r for r in resources if r['id'] == node['id'])['yaml']['catalog'] = text
    profile = json.loads((ROOT / 'examples/platform-profile.json').read_text())
    for obj in gateway_baseline.resources(profile)['items']:
        if obj['kind'] == 'Namespace':
            continue
        ident = 'platform-' + obj['metadata']['name']
        path = output / (ident + '.yaml')
        text = '# Platform baseline, installed before any customer instance.\n' + yaml.safe_dump(obj, sort_keys=False, width=100)
        path.write_text(text)
        resources.append({'id': ident, 'title': obj['kind'] + ' / ' + obj['metadata']['name'],
                          'kind': obj['kind'], 'owner': 'Platform',
                          'origin': 'Exact public platform baseline with environment placeholders',
                          'explanation': 'The dedicated Gateway and its strict listener JWT policies exist before route creation. They bind verifier and caller listeners to distinct service-account subjects. Replace issuer and JWKS placeholders through the platform profile.',
                          'path': str(path.relative_to(ROOT)), 'yaml': {'model': text, 'catalog': text}})
    extras = [
        ('model', 'ModelConfig', 'Approved model reference', 'Platform',
         'Existing native ModelConfig. The customer selects its name. The provider credential remains a Secret reference; the example does not install a provider or contain a key.',
         {'apiVersion': 'kagent.dev/v1alpha2', 'kind': 'ModelConfig', 'metadata': {'name': 'approved-model', 'namespace': 'classic-agents'},
          'spec': {'provider': 'OpenAI', 'model': '{{APPROVED_MODEL_NAME}}', 'apiKeySecret': '{{EXISTING_PROVIDER_SECRET_NAME}}', 'apiKeySecretKey': '{{EXISTING_PROVIDER_SECRET_KEY}}', 'openAI': {'baseUrl': '{{APPROVED_MODEL_GATEWAY_BASE_URL}}'}}}),
        ('remoteMCP', 'RemoteMCPServer', 'Approved remote MCP', 'Platform',
         'Existing tool server reference. The native Agent gets only named operations from the approved catalog. The server service account and backend authorization determine actual execution permission. Resolve this example and its tool names before use.',
         {'apiVersion': 'kagent.dev/v1alpha2', 'kind': 'RemoteMCPServer', 'metadata': {'name': 'approved-kubernetes-mcp', 'namespace': 'classic-agents'},
          'spec': {'description': 'Approved read-only Kubernetes MCP server', 'url': '{{APPROVED_KUBERNETES_MCP_URL}}', 'protocol': 'STREAMABLE_HTTP'}}),
        ('referenceGrant', 'ReferenceGrant', 'Optional cross-namespace grant', 'Optional',
         'NOT installed by this composition. Routes and backend Services share classic-agents, so no grant is required. If a reviewed variant moves a route to another namespace, install an exact grant in the backend namespace. This grants a reference, not caller identity or network access.',
         {'apiVersion': 'gateway.networking.k8s.io/v1beta1', 'kind': 'ReferenceGrant', 'metadata': {'name': 'allow-reviewed-route-to-demo', 'namespace': 'classic-agents'},
          'spec': {'from': [{'group': 'gateway.networking.k8s.io', 'kind': 'HTTPRoute', 'namespace': '{{APPROVED_ROUTE_NAMESPACE}}'}],
                   'to': [{'group': '', 'kind': 'Service', 'name': 'demo'}]}}),
        ('nativeService', 'Service', 'Native runtime Service', 'kagent',
         'Illustrative controller-owned Service shape. kagent generates this from the native Agent; it is not another customer file to apply. Use demo.py show service to inspect the actual receiving-cluster YAML.',
         {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'demo', 'namespace': 'classic-agents'},
          'spec': {'type': 'ClusterIP', 'selector': {'app': 'kagent', 'kagent': 'demo'}, 'ports': [{'name': 'http', 'port': 8080, 'targetPort': 8080}]}}),
    ]
    for ident, kind, title, owner, explanation, obj in extras:
        path = output / (ident + '.yaml')
        text = '# Reference example only. Read its explanation before using it.\n' + yaml.safe_dump(obj, sort_keys=False, width=100)
        path.write_text(text)
        resources.append({'id': ident, 'kind': kind, 'title': title, 'owner': owner, 'origin': 'Reference example, not a live snapshot',
                          'explanation': explanation, 'path': str(path.relative_to(ROOT)), 'yaml': {'model': text, 'catalog': text}})
    for scenario in catalog['scenarios']:
        scenario['owner'] = yaml.safe_load((ROOT / scenario['file']).read_text())
    rgd_yaml = {variant: yaml.safe_dump(graph, sort_keys=False, width=100) for variant, graph in graphs.items()}
    for variant, text in rgd_yaml.items():
        (output / variant / 'resourcegraphdefinition.yaml').write_text(text)
    resources.insert(0, {'id': 'resourceGraph', 'title': 'ResourceGraphDefinition', 'kind': 'ResourceGraphDefinition',
                        'owner': 'Platform', 'origin': 'Exact RGD produced by compose.py for the selected public profile',
                        'explanation': 'Installed once by the platform. Defines the customer schema, approved catalog, native Agent and security graph. CEL references establish dependencies, including the successful Golden gate before the caller route.',
                        'path': 'demo/yaml/model/resourcegraphdefinition.yaml', 'yaml': rgd_yaml})
    recorded = ROOT / 'demo/recorded-native-deployment.yaml'
    if recorded.exists():
        text = recorded.read_text()
        resources.append({'id': 'nativeDeployment', 'title': 'Recorded native Deployment', 'kind': 'Deployment',
                          'owner': 'kagent', 'origin': 'Sanitized controller output recorded on 2026-11-04, not current live state',
                          'explanation': 'kagent created this ordinary Go runtime Deployment from the native Agent. Its configuration Secret is controller-owned. The customer does not apply this file. Use demo.py show deployment to inspect the current receiving-cluster output.',
                          'path': 'demo/recorded-native-deployment.yaml', 'yaml': {'model': text, 'catalog': text}})
    evidence = json.loads((ROOT / 'evidence/live-classic-0.10.4-2026-11-04.json').read_text())
    payload = {'catalog': catalog, 'resources': resources, 'graphs': graphs,
               'evidence': {k: evidence[k] for k in ('checkedAt', 'versions', 'instanceReady', 'golden', 'callerSmoke', 'callerNegativeControls')},
               'template': (ROOT / 'examples/agent-template.yaml').read_text(),
               'sources': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in [ROOT / 'compose.py', ROOT / 'gateway_baseline.py', ROOT / 'demo/catalog.json', ROOT / 'demo/resource-notes.json']}}
    template = (ROOT / 'demo/presentation.template.html').read_text()
    html = template.replace('__DEMO_DATA__', json.dumps(payload, separators=(',', ':')).replace('<', '\\u003c'))
    (ROOT / 'presentation.html').write_text(html)
    print('Built self-contained presentation and', len(resources), 'resource views from bundle sources.')


if __name__ == '__main__':
    build()
