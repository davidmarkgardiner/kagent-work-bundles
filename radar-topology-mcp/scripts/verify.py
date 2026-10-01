#!/usr/bin/env python3
"""Check rendered permission and tool boundaries before deployment. Needs PyYAML."""
import argparse
import hashlib
import json
import pathlib
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--out', type=pathlib.Path, required=True)
p.add_argument('--helm-manifest', type=pathlib.Path, required=True)
p.add_argument('--chart', type=pathlib.Path, required=True)
a = p.parse_args()
versions = json.loads((ROOT / 'versions.json').read_text())
for name, digest in versions['shared_helpers'].items():
    if hashlib.sha256((ROOT / 'scripts/shared' / name).read_bytes()).hexdigest() != digest:
        raise SystemExit('FAIL: bundled canonical helper differs: ' + name)
if hashlib.sha256(a.chart.read_bytes()).hexdigest() != versions['chart_sha256']:
    raise SystemExit('FAIL: chart archive differs from reviewed 1.15.0 package')
docs = []
for name in ['namespace.yaml', 'inventory-access.yaml', 'network-policy.yaml', 'kagent-agent.yaml', 'flux-helm.yaml']:
    raw = (a.out / name).read_text()
    if '{{' in raw or '}}' in raw:
        raise SystemExit('FAIL: unresolved placeholder in ' + name)
    docs += [d for d in yaml.safe_load_all(raw) if d]
role = next(d for d in docs if d['kind'] == 'ClusterRole')
for rule in role['rules']:
    if '*' in rule['apiGroups'] or '*' in rule['resources'] or '*' in rule['verbs']:
        raise SystemExit('FAIL: wildcard inventory permission')
    if any(r in {'secrets', 'pods/exec', 'pods/portforward', 'nodes/proxy'} for r in rule['resources']):
        raise SystemExit('FAIL: unapproved sensitive/subresource read')
    check = rule['apiGroups'] == ['authorization.k8s.io'] and rule['resources'] == ['selfsubjectaccessreviews']
    if (check and rule['verbs'] != ['create']) or (not check and not set(rule['verbs']) <= {'get', 'list', 'watch'}):
        raise SystemExit('FAIL: mutation permission')
remote = next(d for d in docs if d['kind'] == 'RemoteMCPServer')
if not remote['spec']['url'].endswith(':9280/mcp-readonly'):
    raise SystemExit('FAIL: MCP must use strict read-only endpoint')
agent = next(d for d in docs if d['kind'] == 'Agent')
tools = agent['spec']['declarative']['tools']
if len(tools) != 1 or tools[0]['mcpServer']['toolNames'] != ['get_neighborhood', 'get_topology']:
    raise SystemExit('FAIL: unexpected Agent tool grants')
values = yaml.safe_load((a.out / 'values.yaml').read_text())
release = next(d for d in docs if d['kind'] == 'HelmRelease')
if release['spec']['chart']['spec']['version'] != versions['chart_version'] or release['spec']['values'] != values:
    raise SystemExit('FAIL: Flux chart/values drift')
helm_docs = [d for d in yaml.safe_load_all(a.helm_manifest.read_text()) if d]
if any(d['kind'] in {'ClusterRole', 'ClusterRoleBinding', 'Role', 'RoleBinding', 'Ingress', 'HTTPRoute'} for d in helm_docs):
    raise SystemExit('FAIL: chart unexpectedly grants access or publishes a route')
deployment = next(d for d in helm_docs if d['kind'] == 'Deployment')
spec = deployment['spec']['template']['spec']
container = spec['containers'][0]
if deployment['spec']['replicas'] != 1 or spec['serviceAccountName'] != 'radar-topology':
    raise SystemExit('FAIL: unexpected deployment identity/replica count')
if container['image'] != values['image']['repository'] + ':1.15.0':
    raise SystemExit('FAIL: image version drift')
sec = container['securityContext']
if sec.get('allowPrivilegeEscalation') is not False or sec.get('readOnlyRootFilesystem') is not True or not sec.get('runAsNonRoot'):
    raise SystemExit('FAIL: container security profile drift')
env = {e['name']: e.get('value') for e in container.get('env', [])}
if any('CLOUD' in k or 'OIDC' in k for k in env):
    raise SystemExit('FAIL: unexpected external authentication/cloud configuration')
if values['cloud']['enabled'] or values['usageReporting']['enabled'] or values['rbac']['create']:
    raise SystemExit('FAIL: unexpected cloud reporting or chart RBAC')
print('PASS: pinned chart, selected inventory reads, internal Service, two Agent tools, and matching Flux values')
