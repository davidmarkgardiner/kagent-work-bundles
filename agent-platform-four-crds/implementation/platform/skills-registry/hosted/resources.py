#!/usr/bin/env python3
"""Render the namespaced onboarding API and fixed-profile controller."""

import json
from pathlib import Path

from contract import GROUP, MCP_KINDS, canonical, crd, load_profile, mcp_pins

NS = 'skills-demo'
HERE = Path(__file__).resolve().parent


def obj(api, kind, name, **fields):
    return {'apiVersion': api, 'kind': kind, 'metadata': {'name': name, 'namespace': NS}, **fields}


def resources(profile=None):
    profile = load_profile() if profile is None else profile
    code = {name: (HERE / name).read_text() for name in ['contract.py', 'reconcile.py', 'profile.json']}
    code['profile.json'] = json.dumps(profile, sort_keys=True)
    code['controller.py'] = (HERE.parent / 'controller.py').read_text()
    yield crd(profile)
    yield obj('v1', 'ConfigMap', 'hosted-agent-code', data=code)
    yield obj('v1', 'ServiceAccount', 'hosted-agent-adapter')
    capability_rules = []
    if 'mcpProfile' in profile:
        for pin in mcp_pins(profile['mcpProfile']):
            api, plural = MCP_KINDS[pin['kind']]
            capability_rules.append({'apiGroups': ['' if api == 'v1' else api.split('/')[0]],
                'resources': [plural], 'resourceNames': [pin['name']], 'verbs': ['get']})
    yield obj('rbac.authorization.k8s.io/v1', 'Role', 'hosted-agent-adapter', rules=[
        {'apiGroups': [GROUP], 'resources': ['hostedagents'], 'verbs': ['get', 'list']},
        {'apiGroups': [GROUP], 'resources': ['hostedagents/status'], 'verbs': ['get', 'patch']},
        {'apiGroups': [GROUP], 'resources': ['skills', 'knowledgebases'], 'verbs': ['get']},
        {'apiGroups': ['source.toolkit.fluxcd.io'], 'resources': ['gitrepositories'], 'verbs': ['get']},
        {'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get']},
        {'apiGroups': ['kagent.dev'], 'resources': ['modelconfigs'], 'verbs': ['get']},
        {'apiGroups': ['kagent.dev'], 'resources': ['agents'], 'verbs': ['get', 'create', 'update']},
        {'apiGroups': [''], 'resources': ['serviceaccounts'], 'verbs': ['get', 'create', 'patch']},
        {'apiGroups': ['networking.k8s.io'], 'resources': ['networkpolicies'], 'verbs': ['get', 'create', 'update']}] + capability_rules)
    yield obj('rbac.authorization.k8s.io/v1', 'RoleBinding', 'hosted-agent-adapter',
              roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'hosted-agent-adapter'},
              subjects=[{'kind': 'ServiceAccount', 'name': 'hosted-agent-adapter', 'namespace': NS}])
    security = {'allowPrivilegeEscalation': False, 'runAsNonRoot': True, 'runAsUser': 1000,
                'capabilities': {'drop': ['ALL']}, 'readOnlyRootFilesystem': True}
    scheduling = profile['deployment']
    yield obj('apps/v1', 'Deployment', 'hosted-agent-adapter', spec={
        'replicas': 1, 'strategy': {'type': 'Recreate'}, 'selector': {'matchLabels': {'app': 'hosted-agent-adapter'}}, 'template': {
            'metadata': {'labels': {'app': 'hosted-agent-adapter'}, 'annotations': {GROUP + '/code': canonical(code)}},
            'spec': {'terminationGracePeriodSeconds': 5, 'serviceAccountName': 'hosted-agent-adapter', 'nodeSelector': scheduling['nodeSelector'],
                'tolerations': scheduling['tolerations'], 'securityContext': {'seccompProfile': {'type': 'RuntimeDefault'}},
                'containers': [{'name': 'controller', 'image': 'python:3.12.12-slim-bookworm',
                    'command': ['python', '-B', '/app/reconcile.py'], 'securityContext': security,
                    'env': [{'name': 'NAMESPACE', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.namespace'}}}],
                    'resources': {'requests': {'cpu': '20m', 'memory': '32Mi'}, 'limits': {'cpu': '250m', 'memory': '96Mi'}},
                    'volumeMounts': [{'name': 'code', 'mountPath': '/app', 'readOnly': True}]}],
                'volumes': [{'name': 'code', 'configMap': {'name': 'hosted-agent-code'}}]}}})
    yield obj('v1', 'ServiceAccount', 'hosted-gitops', automountServiceAccountToken=False)
    yield obj('rbac.authorization.k8s.io/v1', 'Role', 'hosted-gitops-impersonation', rules=[
        {'apiGroups': [''], 'resources': ['serviceaccounts'], 'resourceNames': ['hosted-gitops'], 'verbs': ['impersonate']}])
    yield obj('rbac.authorization.k8s.io/v1', 'RoleBinding', 'hosted-gitops-impersonation',
              roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'hosted-gitops-impersonation'},
              subjects=[{'kind': 'ServiceAccount', 'name': 'kustomize-controller', 'namespace': NS}])
    yield obj('rbac.authorization.k8s.io/v1', 'Role', 'hosted-gitops', rules=[
        {'apiGroups': [GROUP], 'resources': ['hostedagents'], 'verbs': ['get', 'list', 'watch', 'create', 'patch', 'update', 'delete']}])
    yield obj('rbac.authorization.k8s.io/v1', 'RoleBinding', 'hosted-gitops',
              roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'hosted-gitops'},
              subjects=[{'kind': 'ServiceAccount', 'name': 'hosted-gitops', 'namespace': NS}])


if __name__ == '__main__':
    print(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': list(resources())}))
