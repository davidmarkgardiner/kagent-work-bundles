#!/usr/bin/env python3
"""Render the complete portable installation from operator-controlled configuration."""
import argparse
import copy
import json
from pathlib import Path
import yaml
from contract import API, GROUP, SCENARIO_GROUP, digest, profile
from eval_controller import executor_job


def resource(kind, name, ns, **fields):
    versions = {'Role': 'rbac.authorization.k8s.io/v1', 'RoleBinding': 'rbac.authorization.k8s.io/v1',
                'Deployment': 'apps/v1'}
    return {'apiVersion': versions.get(kind, 'v1'), 'kind': kind,
            'metadata': {'name': name, **({'namespace': ns} if ns else {})}, **fields}


def role(name, ns, rules):
    return resource('Role', name, ns, rules=rules)


def binding(name, ns, sa, sa_ns):
    return resource('RoleBinding', name, ns,
        roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': name},
        subjects=[{'kind': 'ServiceAccount', 'name': sa, 'namespace': sa_ns}])


def rule(group, resources, verbs, names=None):
    return {'apiGroups': [group], 'resources': resources, 'verbs': verbs,
            **({'resourceNames': names} if names else {})}


def crd():
    ref = {'type': 'object', 'required': ['name', 'uid', 'specSha256'], 'properties': {
        'name': {'type': 'string', 'maxLength': 253}, 'uid': {'type': 'string', 'minLength': 1, 'maxLength': 128},
        'specSha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}}}
    return {'apiVersion': 'apiextensions.k8s.io/v1', 'kind': 'CustomResourceDefinition',
        'metadata': {'name': 'skillevaluations.' + GROUP},
        'spec': {'group': GROUP, 'scope': 'Namespaced',
            'names': {'kind': 'SkillEvaluation', 'plural': 'skillevaluations', 'singular': 'skillevaluation', 'shortNames': ['seval']},
            'versions': [{'name': 'v1alpha1', 'served': True, 'storage': True, 'subresources': {'status': {}},
                'additionalPrinterColumns': [{'name': 'Phase', 'type': 'string', 'jsonPath': '.status.phase'}],
                'schema': {'openAPIV3Schema': {'type': 'object', 'required': ['spec'], 'properties': {
                    'spec': {'type': 'object', 'required': ['scenarioRef'], 'properties': {'scenarioRef': ref},
                             'x-kubernetes-validations': [{'rule': 'self == oldSelf', 'message': 'Create a new immutable evaluation request'}]},
                    'status': {'type': 'object', 'x-kubernetes-preserve-unknown-fields': True}}}}}]}}


def render(config):
    config = profile(config)
    ns, target = config['evaluationNamespace'], config['targetNamespace']
    namespace = resource('Namespace', ns, None)
    namespace['metadata']['labels'] = {'pod-security.kubernetes.io/enforce': 'restricted',
                                        'pod-security.kubernetes.io/enforce-version': 'v1.31'}
    docs = [namespace, resource('ResourceQuota', 'skill-eval-bounds', ns, spec={'hard': {
        'count/skillevaluations.' + GROUP: '50', 'count/jobs.batch': '20', 'count/configmaps': '100',
        'pods': '20', 'requests.cpu': '2', 'requests.memory': '2Gi',
        'limits.cpu': '8', 'limits.memory': '8Gi'}})]
    for name in ['skill-eval-controller', 'skill-eval-worker', 'skill-eval-submitter']:
        docs.append(resource('ServiceAccount', name, ns, automountServiceAccountToken=False))
    profile_name = 'skill-eval-profile-' + digest(config)[:16]
    docs.append(resource('ConfigMap', profile_name, ns, immutable=True,
                         data={'profile.json': json.dumps(config, sort_keys=True)}))
    docs += [role('skill-eval-controller', ns, [
        rule(GROUP, ['skillevaluations'], ['get', 'list']),
        rule(GROUP, ['skillevaluations/status'], ['get', 'patch']),
        rule('batch', ['jobs'], ['get', 'create']),
        rule('', ['pods'], ['get', 'list']), rule('', ['pods/log'], ['get']),
        rule('', ['configmaps'], ['get', 'create'])]),
        binding('skill-eval-controller', ns, 'skill-eval-controller', ns),
        role('skill-eval-submitter', ns, [rule(GROUP, ['skillevaluations'], ['get', 'list', 'create'])]),
        binding('skill-eval-submitter', ns, 'skill-eval-submitter', ns),
        role('skill-eval-controller-inputs', target, [
            rule(SCENARIO_GROUP, ['goldenscenarios'], ['get'], config['scenarioNames']),
            rule(SCENARIO_GROUP, ['skills'], ['get']),
            rule('kagent.dev', ['agents'], ['get']),
            rule('source.toolkit.fluxcd.io', ['gitrepositories'], ['get']),
            rule('', ['configmaps'], ['get']), rule('', ['pods'], ['get'], [config['targetPodName']])]),
        binding('skill-eval-controller-inputs', target, 'skill-eval-controller', ns),
        role('skill-eval-worker', target, [
            rule(SCENARIO_GROUP, ['goldenscenarios'], ['get'], config['scenarioNames']),
            rule(SCENARIO_GROUP, ['skills'], ['get']),
            rule('kagent.dev', ['agents'], ['get']),
            rule('source.toolkit.fluxcd.io', ['gitrepositories'], ['get']),
            rule('', ['configmaps'], ['get']), rule('', ['pods'], ['get', 'list']),
            rule('', ['pods/exec'], ['create'], [config['targetPodName']])]),
        binding('skill-eval-worker', target, 'skill-eval-worker', ns)]
    dummy = {'metadata': {'name': 'render-only', 'uid': '00000000-0000-0000-0000-000000000001'},
             'spec': {'scenarioRef': {'name': 'render-only', 'uid': 'render-only', 'specSha256': '0' * 64}}}
    pod = executor_job(dummy, config)['spec']['template']['spec']
    pod['serviceAccountName'] = 'skill-eval-controller'
    pod.pop('restartPolicy')
    pod['containers'][0]['name'] = 'controller'
    pod['containers'][0]['command'] = ['python', '/app/eval_controller.py']
    pod['containers'][0].pop('args')
    docs.append(resource('Deployment', 'skill-eval-controller', ns, spec={
        'replicas': 1, 'strategy': {'type': 'Recreate'}, 'selector': {'matchLabels': {'app': 'skill-eval-controller'}},
        'template': {'metadata': {'labels': {'app': 'skill-eval-controller'}}, 'spec': pod}}))
    return docs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    config = profile(yaml.safe_load(args.config.read_text()))
    documents = render(config)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'crd.yaml').write_text(yaml.safe_dump(crd(), sort_keys=False))
    (args.output / 'namespace.yaml').write_text(yaml.safe_dump(documents[0], sort_keys=False))
    (args.output / 'install.yaml').write_text(yaml.safe_dump_all(documents, sort_keys=False))
    print(str(args.output.resolve()))


if __name__ == '__main__':
    main()
