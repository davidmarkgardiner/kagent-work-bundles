#!/usr/bin/env python3
"""Render four native platform APIs and narrowly scoped adapters."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / 'hosted'))
from contract import canonical, crd as hosted_crd
from controller import GROUP, KNOWLEDGE_BASE
module_spec = importlib.util.spec_from_file_location('content_resources', HERE.parent / 'resources.py')
content_resources = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(content_resources)
from golden_native import crd as golden_crd


def render(profile, namespace='kagent'):
    content_resources.NAMESPACE = namespace
    yield content_resources.crd()
    yield content_resources.crd(KNOWLEDGE_BASE)
    hosted = hosted_crd(profile)
    status = hosted['spec']['versions'][0]['schema']['openAPIV3Schema']['properties']['status']['properties']
    for field in ['templateSpecSha256', 'harnessSpecSha256', 'profileSha256']:
        status[field] = {'type': 'string'}
    for field in ['nativeName', 'image', 'packaging']:
        status['bindings']['items']['properties'][field] = {'type': 'string'}
    yield hosted
    yield golden_crd()
    for obj in content_resources.adapter():
        kind, name = obj['kind'], obj['metadata']['name']
        if kind == 'NetworkPolicy':
            continue
        if kind == 'Role' and name == 'skills-gitops':
            obj['rules'] = [{'apiGroups': [GROUP], 'resources': ['skills', 'knowledgebases', 'hostedagents', 'goldenscenarios'],
                             'verbs': ['get', 'list', 'watch', 'create', 'patch', 'update', 'delete']}]
        if kind == 'Role' and name == 'skill-adapter':
            obj['rules'][-1] = {'apiGroups': ['api.kagent.dev'], 'resources': ['agenttemplates'], 'verbs': ['get', 'list']}
            obj['rules'].append({'apiGroups': [GROUP], 'resources': ['hostedagents'], 'verbs': ['get', 'list']})
        if kind == 'Deployment':
            obj['spec']['template']['spec']['containers'][0]['env'].append({'name': 'NATIVE_KAGENT', 'value': '1'})
        yield obj
    def obj(api, kind, name, **fields):
        return {'apiVersion': api, 'kind': kind, 'metadata': {'name': name, 'namespace': namespace}, **fields}
    code = {name: (HERE / name).read_text() for name in ['artifacts.py', 'reconcile_native.py']}
    code.update({name: (HERE.parent / 'hosted' / name).read_text() for name in ['contract.py', 'reconcile.py']})
    code['controller.py'] = (HERE.parent / 'controller.py').read_text()
    code_name = 'hosted-native-code-' + canonical(code)[:12]
    yield obj('v1', 'ConfigMap', code_name, immutable=True, data=code)
    yield obj('v1', 'ConfigMap', 'hosted-native-profile', data={'profile.json': json.dumps(profile, sort_keys=True)})
    yield obj('v1', 'ServiceAccount', 'hosted-native-adapter')
    rules = [
        {'apiGroups': [GROUP], 'resources': ['hostedagents'], 'verbs': ['get', 'list']},
        {'apiGroups': [GROUP], 'resources': ['hostedagents/status'], 'verbs': ['get', 'patch']},
        {'apiGroups': [GROUP], 'resources': ['skills', 'knowledgebases'], 'verbs': ['get']},
        {'apiGroups': ['source.toolkit.fluxcd.io'], 'resources': ['gitrepositories'], 'verbs': ['get']},
        {'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get']},
        {'apiGroups': ['api.kagent.dev'], 'resources': ['modelconfigs', 'harnesses'], 'verbs': ['get']},
        {'apiGroups': ['api.kagent.dev'], 'resources': ['agents', 'agenttemplates'], 'verbs': ['get', 'create', 'update']},
    ]
    yield obj('rbac.authorization.k8s.io/v1', 'Role', 'hosted-native-adapter', rules=rules)
    yield obj('rbac.authorization.k8s.io/v1', 'RoleBinding', 'hosted-native-adapter',
        roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'hosted-native-adapter'},
        subjects=[{'kind': 'ServiceAccount', 'name': 'hosted-native-adapter', 'namespace': namespace}])
    yield obj('apps/v1', 'Deployment', 'hosted-native-adapter', spec={
        'replicas': 1, 'strategy': {'type': 'Recreate'}, 'selector': {'matchLabels': {'app': 'hosted-native-adapter'}},
        'template': {'metadata': {'labels': {'app': 'hosted-native-adapter'}, 'annotations': {GROUP + '/code': canonical(code)}},
        'spec': {'serviceAccountName': 'hosted-native-adapter', 'securityContext': {'seccompProfile': {'type': 'RuntimeDefault'}},
            'containers': [{'name': 'controller', 'image': 'python:3.12.12-slim-bookworm',
                'command': ['python', '-B', '/app/reconcile_native.py'],
                'env': [{'name': 'NAMESPACE', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.namespace'}}}],
                'securityContext': {'allowPrivilegeEscalation': False, 'runAsNonRoot': True, 'runAsUser': 1000,
                                    'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}},
                'resources': {'requests': {'cpu': '20m', 'memory': '32Mi'}, 'limits': {'cpu': '250m', 'memory': '96Mi'}},
                'volumeMounts': [{'name': 'code', 'mountPath': '/app', 'readOnly': True},
                                 {'name': 'profile', 'mountPath': '/profile', 'readOnly': True}]}],
            'volumes': [{'name': 'code', 'configMap': {'name': code_name}},
                        {'name': 'profile', 'configMap': {'name': 'hosted-native-profile'}}]}}})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--namespace', default='kagent')
    args = parser.parse_args()
    print(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': list(render(json.loads(args.profile.read_text()), args.namespace))}))
