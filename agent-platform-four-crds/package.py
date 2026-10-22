#!/usr/bin/env python3
"""Build reviewable AKS documentation seeds locally. No Git, network or apply calls."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import urlsplit
import yaml

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'implementation/platform/skills-registry'
sys.path[:0] = [str(SOURCE), str(SOURCE / 'hosted')]
import controller as content
import resources as content_resources
import contract


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


hosted_resources = module('hosted_resources', SOURCE / 'hosted/resources.py')
golden_schema = module('golden_schema', SOURCE / 'golden/schema.py')
FIELDS = {'namespace', 'fluxNamespace', 'kagentNamespace', 'fluxServiceAccount',
          'platformServiceAccount', 'artifactOrigin', 'controllerImage', 'expectedRuntimeImage',
          'imageRegistry', 'modelConfig', 'modelSpecSha256', 'nodeSelector',
          'contentURL', 'contentCommit', 'contentSecret', 'gitopsURL', 'gitopsSecret'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_snapshot():
    lock = json.loads((HERE / 'snapshot.lock.json').read_text())['files']
    for path, expected in lock.items():
        if digest(HERE / path) != expected:
            raise ValueError('snapshot changed: ' + path)
    actual = {str(p.relative_to(HERE)) for p in (HERE / 'implementation').rglob('*')
              if p.is_file() and '__pycache__' not in p.parts}
    if actual != {p for p in lock if p.startswith('implementation/')}:
        raise ValueError('snapshot file set changed')


def slug(value):
    return isinstance(value, str) and re.fullmatch(r'[a-z](?:[a-z0-9-]{0,38}[a-z0-9])?', value)


def git_url(value):
    parsed = urlsplit(value)
    return (parsed.scheme == 'https' and bool(parsed.hostname) and parsed.username is None
            and parsed.password is None and not parsed.query and not parsed.fragment
            and parsed.path.endswith('.git') and not any(c.isspace() for c in value))


def config(path):
    result = json.loads(Path(path).read_text())
    if not isinstance(result, dict) or set(result) != FIELDS:
        raise ValueError('configuration must contain exactly: ' + ', '.join(sorted(FIELDS)))
    for key in ['namespace', 'fluxNamespace', 'kagentNamespace', 'fluxServiceAccount', 'platformServiceAccount', 'modelConfig']:
        if not slug(result[key]):
            raise ValueError('invalid name: ' + key)
    for key in ['contentSecret', 'gitopsSecret']:
        if result[key] is not None and not slug(result[key]):
            raise ValueError('invalid Secret reference: ' + key)
    if not re.fullmatch('[0-9a-f]{40}', result['contentCommit']):
        raise ValueError('contentCommit must be a reviewed full lowercase SHA1')
    if not re.fullmatch('[0-9a-f]{64}', result['modelSpecSha256']):
        raise ValueError('modelSpecSha256 must pin the existing ModelConfig spec')
    for key in ['contentURL', 'gitopsURL']:
        if not git_url(result[key]):
            raise ValueError('invalid credential-free HTTPS Git URL: ' + key)
    origin = urlsplit(result['artifactOrigin'])
    if (origin.scheme not in ['http', 'https'] or not origin.hostname or origin.username is not None
            or origin.password is not None or origin.path not in ['', '/'] or origin.query or origin.fragment):
        raise ValueError('artifactOrigin must be one exact approved HTTP(S) origin')
    origin.port  # Validate malformed ports before rendering.
    if not re.fullmatch(r'[a-zA-Z0-9._:/-]+@sha256:[0-9a-f]{64}', result['controllerImage']):
        raise ValueError('controllerImage requires an approved immutable image digest')
    if not re.fullmatch(r'[a-zA-Z0-9._:/@-]+', result['expectedRuntimeImage']):
        raise ValueError('expectedRuntimeImage must equal the target native runtime image reference')
    if not re.fullmatch(r'[a-zA-Z0-9._:/-]+', result['imageRegistry']):
        raise ValueError('imageRegistry is required; arbitrary native image/tag overrides are unsupported')
    if not isinstance(result['nodeSelector'], dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in result['nodeSelector'].items()):
        raise ValueError('nodeSelector must be a string map')
    if any('control-plane' in k or 'master' in k for k in result['nodeSelector']):
        raise ValueError('use approved workload scheduling')
    if '{{' in json.dumps(result):
        raise ValueError('replace all workplace placeholders')
    return result


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def documents(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump_all(values, sort_keys=False))


def new_output(path):
    if path.exists():
        raise ValueError('output must be a new directory')
    path.mkdir(parents=True)


def seed_content(output):
    for source, target in [('imports/aks-known-issues/payload', 'skills/aks-known-issues'),
                           ('knowledge/payload', 'knowledge/aks-bootstrap')]:
        shutil.copytree(SOURCE / source, output / target)


def source(c, name, namespace, url, commit, secret):
    spec = {'interval': '5m', 'url': url, 'ref': {'commit': commit}, 'timeout': '60s'}
    if secret:
        spec['secretRef'] = {'name': secret}
    return {'apiVersion': 'source.toolkit.fluxcd.io/v1', 'kind': 'GitRepository',
            'metadata': {'name': name, 'namespace': namespace}, 'spec': spec}


def role(c, name, plural):
    ns = c['namespace']
    return [
        {'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': {'name': name, 'namespace': ns},
         'automountServiceAccountToken': False},
        {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': {'name': name, 'namespace': ns},
         'rules': [{'apiGroups': [content.GROUP], 'resources': plural,
                    'verbs': ['get', 'list', 'watch', 'create', 'patch', 'update', 'delete']}]},
        {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': {'name': name, 'namespace': ns},
         'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': name},
         'subjects': [{'kind': 'ServiceAccount', 'name': name, 'namespace': ns}]}]


def projection(release, kind):
    spec = release['spec']
    name = kind.configmap_prefix + release['metadata']['name'] + '-' + spec['contentSha256'][:16]
    items = [{'key': f'file{i:02}', 'path': spec[kind.name_field] + '/' + path}
             for i, path in enumerate(sorted(spec['files']))]
    return {'contentSha256': spec['contentSha256'], 'projection': {'configMap': {'name': name, 'items': items}}}


def render(c, output):
    profile = contract.load_profile()
    profile.update(runtimeProfile='work-native-v1', modelProfile='work-gateway-v1', kagentNamespace=c['kagentNamespace'],
                   modelConfig={'name': c['modelConfig'], 'specSha256': c['modelSpecSha256']})
    profile['deployment'].update(nodeSelector=c['nodeSelector'], tolerations=[], imageRegistry=c['imageRegistry'])
    content_resources.NAMESPACE = c['namespace']
    content_resources.DEMO_SCHEDULING = {'nodeSelector': c['nodeSelector'], 'tolerations': []}
    hosted_resources.NS = c['namespace']
    objects = [content_resources.crd(), content_resources.crd(content.KNOWLEDGE_BASE), golden_schema.crd(),
               *content_resources.adapter(), *hosted_resources.resources(profile)]
    objects = [o for o in objects if o['metadata']['name'] not in
               ['skills-gitops', 'allow-kagent-front-door', 'hosted-gitops-impersonation']]
    objects += role(c, 'content-gitops', ['skills', 'knowledgebases']) + role(c, 'golden-gitops', ['goldenscenarios'])
    objects += [
        {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role',
         'metadata': {'name': 'registry-flux-impersonation', 'namespace': c['namespace']},
         'rules': [{'apiGroups': [''], 'resources': ['serviceaccounts'],
                    'resourceNames': ['content-gitops', 'hosted-gitops', 'golden-gitops'], 'verbs': ['impersonate']}]},
        {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding',
         'metadata': {'name': 'registry-flux-impersonation', 'namespace': c['namespace']},
         'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'registry-flux-impersonation'},
         'subjects': [{'kind': 'ServiceAccount', 'name': c['fluxServiceAccount'], 'namespace': c['fluxNamespace']}]}]
    for obj in objects:
        if obj['kind'] == 'CustomResourceDefinition':
            obj['metadata'].setdefault('annotations', {})['kustomize.toolkit.fluxcd.io/prune'] = 'disabled'
        if obj['kind'] == 'Deployment':
            container = obj['spec']['template']['spec']['containers'][0]
            container['image'] = c['controllerImage']
            container['env'].append({'name': 'SOURCE_CONTROLLER_ORIGIN', 'value': c['artifactOrigin']})
    documents(output / 'gitops/platform/resources.yaml', objects)
    releases = []
    for path, kind in [('imports/aks-known-issues/skill.yaml', content.SKILL), ('knowledge/knowledgebase.yaml', content.KNOWLEDGE_BASE)]:
        release = yaml.safe_load((SOURCE / path).read_text())
        release['metadata']['namespace'] = c['namespace']
        release['spec'].update(sourceCommit=c['contentCommit'], sourceRef={'name': 'reviewed-content-v1'})
        releases.append(release)
    documents(output / 'gitops/content/resources.yaml', releases)
    request = yaml.safe_load((SOURCE / 'hosted/hostedagent.yaml').read_text())
    request['metadata'].update(name='aks-platform-v1', namespace=c['namespace'])
    request['spec'].update(runtimeProfile=profile['runtimeProfile'], modelProfile=profile['modelProfile'],
        instructions='Read the skill and reference files requested by the current synthetic case. Read the knowledge article when the case asks for it. Cite only documents you read. Include the article evidence code when requested. State documentation only; propose checks without executing commands.')
    for field, release in zip(['skillRefs', 'knowledgeBaseRefs'], releases):
        request['spec'][field] = [{key: release['metadata']['name'] if key == 'name' else release['spec'][key]
                                 for key in ['name', 'sourceCommit', 'contentSha256']}]
    intent = contract.parse_intent(request, profile)
    transient = copy.deepcopy(request)
    transient['metadata']['uid'] = 'render-only-no-live-uid'
    bindings = [projection(r, k) for r, k in zip(releases, [content.SKILL, content.KNOWLEDGE_BASE])]
    agent = contract.desired_children(transient, intent, bindings, profile)[-1]
    scenario = yaml.safe_load((SOURCE / 'golden/scenario.yaml').read_text())
    scenario['metadata']['namespace'] = c['namespace']
    scenario['spec'].update(agentRef={'name': agent['metadata']['name']}, agentSpecSha256=contract.canonical(agent['spec']))
    documents(output / 'gitops/hosted/resources.yaml', [request])
    documents(output / 'gitops/golden/resources.yaml', [scenario])
    for folder in ['platform', 'content', 'hosted', 'golden']:
        documents(output / 'gitops' / folder / 'kustomization.yaml', [{
            'apiVersion': 'kustomize.config.k8s.io/v1beta1', 'kind': 'Kustomization', 'resources': ['resources.yaml']}])
    # Preserve the helper-root layout and use configured JSON rather than editing runtime code.
    shutil.copytree(HERE / 'implementation', output / 'acceptance')
    for file in (output / 'acceptance').rglob('*'):
        if file.is_file() and (file.suffix != '.py' and file.suffix != '.sh' or file.name.startswith('test_')):
            file.unlink()
    configured = output / 'acceptance/platform/skills-registry'
    write(configured / 'hosted/profile.json', profile)
    release = json.loads((SOURCE / 'hosted/release.json').read_text())
    for key in ['gitopsCommit', 'branch']:
        release.pop(key, None)
    release.update(name=request['metadata']['name'], namespace=c['namespace'], agent=agent['metadata']['name'],
                   specSha256=contract.canonical(request['spec']), expectedRuntimeImage=c['expectedRuntimeImage'])
    for key in ['skill', 'knowledge']:
        release[key]['contentCommit'] = c['contentCommit']
        release[key].pop('gitopsCommit', None)
    write(configured / 'hosted/release.json', release)
    write(output / 'render-receipt.json', {'mode': 'offlineRender', 'targetVerified': False,
          'configSha256': contract.canonical(c), 'agentSpecSha256': contract.canonical(agent['spec']),
          'contentCommit': c['contentCommit'], 'expectedRuntimeImage': c['expectedRuntimeImage'],
          'contentDigests': [r['spec']['contentSha256'] for r in releases]})


def bootstrap(c, commit, output):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('gitops commit must be full lowercase SHA1')
    def kust(name, ns, path, sa, deps=(), health=()):
        spec = {'interval': '5m', 'path': './' + path, 'prune': False, 'timeout': '5m',
                'serviceAccountName': sa, 'sourceRef': {'kind': 'GitRepository', 'name': 'agent-platform-v1'}}
        if deps:
            spec['dependsOn'] = [{'name': n} for n in deps]
        if health:
            spec['healthChecks'] = [{'apiVersion': api, 'kind': kind, 'name': n, 'namespace': c['namespace']}
                                    for api, kind, n in health]
        return {'apiVersion': 'kustomize.toolkit.fluxcd.io/v1', 'kind': 'Kustomization',
                'metadata': {'name': name, 'namespace': ns}, 'spec': spec}
    documents(output / '00-namespace.yaml', [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': c['namespace']}}])
    documents(output / '10-platform.yaml', [source(c, 'agent-platform-v1', c['fluxNamespace'], c['gitopsURL'], commit, c['gitopsSecret']),
        kust('agent-platform-v1', c['fluxNamespace'], 'platform', c['platformServiceAccount'], health=[
            ('apps/v1', 'Deployment', 'skill-adapter'), ('apps/v1', 'Deployment', 'hosted-agent-adapter')])])
    documents(output / '20-applications.yaml', [
        source(c, 'agent-platform-v1', c['namespace'], c['gitopsURL'], commit, c['gitopsSecret']),
        source(c, 'reviewed-content-v1', c['namespace'], c['contentURL'], c['contentCommit'], c['contentSecret']),
        kust('agent-content-v1', c['namespace'], 'content', 'content-gitops', health=[
            (content.API, 'Skill', 'aks-known-issues-v1'), (content.API, 'KnowledgeBase', 'aks-bootstrap-v1')]),
        kust('agent-hosted-v1', c['namespace'], 'hosted', 'hosted-gitops', ['agent-content-v1'], [
            (content.API, 'HostedAgent', 'aks-platform-v1')]),
        kust('agent-golden-v1', c['namespace'], 'golden', 'golden-gitops', ['agent-hosted-v1'])])
    write(output / 'bootstrap-receipt.json', {'mode': 'offlineBootstrapRender', 'targetVerified': False,
          'configSha256': contract.canonical(c), 'gitopsCommit': commit})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['content', 'render', 'bootstrap'])
    parser.add_argument('--config', type=Path)
    parser.add_argument('--gitops-commit')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    verify_snapshot()
    c = config(args.config) if args.command != 'content' else None
    if args.command == 'bootstrap' and not args.gitops_commit:
        parser.error('bootstrap requires --gitops-commit')
    new_output(args.output)
    if args.command == 'content':
        seed_content(args.output)
    elif args.command == 'render':
        render(c, args.output)
    else:
        bootstrap(c, args.gitops_commit, args.output)


if __name__ == '__main__':
    main()
