#!/usr/bin/env python3
"""Offline, snapshot-only preparation of a standalone reference-agent Job."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
import urllib.parse

HERE = Path(__file__).resolve().parent
REGISTRY = HERE.parent / 'implementation/platform/skills-registry'
sys.path[:0] = [str(REGISTRY), str(REGISTRY / 'hosted'), str(REGISTRY / 'native')]
from controller import API, GROUP, SKILL, KNOWLEDGE_BASE, sha256
from contract import canonical, parse_intent
from reconcile import Onboarding
from artifacts import build

RUNTIME, MODEL_PROFILE, POLICY = 'standalone-reference-v1', 'standalone-qwen-v1', 'aks-docs-standalone-v1'
NAME = r'[a-z][a-z0-9-]{0,61}[a-z0-9]|[a-z]'
LIMITS = {'maxModelCalls': (2, 8), 'maxToolCalls': (6, 24), 'maxTokens': (128, 4096),
          'requestTimeoutSeconds': (1, 60), 'deadlineSeconds': (10, 300), 'maxResponseBytes': (1024, 262144)}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def read(path):
    require(path.stat().st_size <= 2 * 1024 * 1024, 'SnapshotTooLarge')
    def pairs(items):
        require(len(items) == len(dict(items)), 'DuplicateJSONKey')
        return dict(items)
    return json.loads(path.read_text(), object_pairs_hook=pairs)


def url(value, origin=False):
    require(isinstance(value, str) and len(value) <= 2048 and not re.search(r'[\s\x00-\x1f]', value), 'InvalidURL')
    p = urllib.parse.urlsplit(value)
    require(p.scheme in ('http', 'https') and p.hostname and p.port != 0
            and p.username is None and p.password is None and not p.query and not p.fragment
            and '%' not in value and '..' not in p.path.split('/'), 'InvalidURL')
    require(p.path in ('', '/') if origin else p.path.endswith('/chat/completions'), 'InvalidURLPath')
    return value


def config(value):
    fields = {'namespace', 'helperImage', 'endpoint', 'model', 'sourceControllerOrigin', 'imagePullSecrets', 'limits'}
    require(isinstance(value, dict) and fields <= set(value) <= fields | {'credentialSecret', 'caConfigMap'}, 'InvalidConfigFields')
    require(re.fullmatch(NAME, value['namespace']) is not None, 'InvalidNamespace')
    require(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/-]+@sha256:[0-9a-f]{64}', value['helperImage']) is not None,
            'HelperImageMustBeDigestPinned')
    url(value['endpoint']); url(value['sourceControllerOrigin'], True)
    require(isinstance(value['model'], str) and 1 <= len(value['model']) <= 256
            and not re.search(r'[\s\x00-\x1f]', value['model']), 'InvalidModel')
    require(isinstance(value['imagePullSecrets'], list) and len(value['imagePullSecrets']) <= 4
            and len(set(value['imagePullSecrets'])) == len(value['imagePullSecrets'])
            and all(isinstance(v, str) and re.fullmatch(NAME, v) for v in value['imagePullSecrets']), 'InvalidImagePullSecrets')
    require(isinstance(value['limits'], dict) and set(value['limits']) == set(LIMITS), 'InvalidLimits')
    for field, (lo, hi) in LIMITS.items():
        require(type(value['limits'][field]) is int and lo <= value['limits'][field] <= hi, 'InvalidLimit')
    for field in ('credentialSecret', 'caConfigMap'):
        if field in value:
            ref = value[field]
            require(isinstance(ref, dict) and set(ref) == {'name', 'key'}
                    and isinstance(ref['name'], str) and re.fullmatch(NAME, ref['name'])
                    and isinstance(ref['key'], str) and re.fullmatch(r'[-._A-Za-z0-9]{1,253}', ref['key']), 'InvalidLocalReference')
    return value


def identity(obj, kind, ns, api=API):
    m = obj.get('metadata', {})
    require(obj.get('apiVersion') == api and obj.get('kind') == kind and m.get('namespace') == ns
            and isinstance(m.get('name'), str) and re.fullmatch(NAME, m['name'])
            and isinstance(m.get('uid'), str) and m['uid'] and not m.get('deletionTimestamp'), 'InvalidSnapshotIdentity')
    if api != 'v1':
        require(type(m.get('generation')) is int and m['generation'] > 0, 'InvalidGeneration')


def items(doc):
    require(isinstance(doc, dict) and isinstance(doc.get('items'), list), 'ExpectedKubernetesList')
    return doc['items']


class Snapshot:
    def __init__(self, directory, namespace):
        self.namespace, self.data = namespace, {}
        for filename, kind, api, plural in [('skill.json', 'Skill', API, 'skills'),
                ('knowledge.json', 'KnowledgeBase', API, 'knowledgebases'),
                ('sources.json', 'GitRepository', 'source.toolkit.fluxcd.io/v1', 'gitrepositories'),
                ('configmaps.json', 'ConfigMap', 'v1', 'configmaps')]:
            doc = read(directory / filename)
            for obj in items(doc) if filename.endswith('s.json') else [doc]:
                identity(obj, kind, namespace, api)
                if kind in ('Skill', 'KnowledgeBase'):
                    required = {'sourceRef', 'sourceCommit', 'path', 'files', 'contentSha256',
                                'skillName' if kind == 'Skill' else 'knowledgeBaseName'}
                    if kind == 'KnowledgeBase':
                        required.add('documents')
                    require(set(obj['spec']) == required and set(obj['spec']['sourceRef']) == {'name'}, 'InvalidReleaseSpec')
                if kind != 'ConfigMap':
                    require(obj.get('status', {}).get('observedGeneration') == obj['metadata']['generation'], 'StaleDependencyGeneration')
                prefix = '/api/v1' if api == 'v1' else '/apis/' + api
                path = f'{prefix}/namespaces/{namespace}/{plural}/' + obj['metadata']['name']
                require(path not in self.data, 'DuplicateSnapshotIdentity')
                self.data[path] = obj

    def call(self, path, method='GET', value=None):
        require(method == 'GET' and value is None, 'OfflineSnapshotOnly')
        require(path in self.data, 'MissingDependencySnapshot')
        return self.data[path]


def patches(directory):
    docs = items(read(directory / 'crds.json'))
    require({d['metadata']['name'] for d in docs} == {p + '.' + GROUP for p in
            ('skills', 'knowledgebases', 'hostedagents', 'goldenscenarios')} and len(docs) == 4, 'ExactlyFourCRDsRequired')
    result = {}
    for doc in docs:
        require(doc.get('kind') == 'CustomResourceDefinition' and doc.get('apiVersion') == 'apiextensions.k8s.io/v1'
                and doc['spec']['group'] == GROUP and doc['spec']['scope'] == 'Namespaced'
                and doc['metadata'].get('resourceVersion')
                and any(c.get('type') == 'Established' and c.get('status') == 'True'
                        for c in doc.get('status', {}).get('conditions', [])), 'CRDNotEstablished')
        name = doc['metadata']['name']
        fields = ({'runtimeProfile': RUNTIME, 'modelProfile': MODEL_PROFILE} if name.startswith('hostedagents.') else
                  {'policy': POLICY} if name.startswith('goldenscenarios.') else {})
        patch = [{'op': 'test', 'path': '/metadata/resourceVersion', 'value': doc['metadata']['resourceVersion']}]
        for index, version in enumerate(doc['spec']['versions']):
            if not version.get('served'):
                continue
            require(version['name'] == 'v1alpha1', 'UnsupportedServedCRDVersion')
            for field, entry in fields.items():
                path = f'/spec/versions/{index}/schema/openAPIV3Schema/properties/spec/properties/{field}/enum'
                enum = version['schema']['openAPIV3Schema']['properties']['spec']['properties'][field]['enum']
                require(isinstance(enum, list) and enum and all(isinstance(e, str) for e in enum), 'ExpectedExplicitEnum')
                if entry not in enum:
                    patch += [{'op': 'test', 'path': path, 'value': enum}, {'op': 'add', 'path': path + '/-', 'value': entry}]
        if len(patch) > 1:
            result[name + '.patch.json'] = patch
    return result


def adapter(cfg, directory):
    discovery = read(directory / 'native-api-resources.json')
    require(discovery.get('groupVersion') == 'api.kagent.dev/v1alpha3'
            and any(r.get('name') == 'agenttemplates' and r.get('namespaced') is True
                    and {'get', 'list'} <= set(r.get('verbs', [])) for r in discovery.get('resources', [])),
            'NativeTemplateFinalizerAPINotVerified')
    spec = importlib.util.spec_from_file_location('standalone_content_resources', REGISTRY / 'resources.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.NAMESPACE = cfg['namespace']
    objects = [o for o in module.adapter() if o['metadata']['name'].startswith('skill-adapter')]
    for obj in objects:
        if obj['kind'] == 'Role':
            obj['rules'][-1] = {'apiGroups': ['api.kagent.dev'], 'resources': ['agenttemplates'], 'verbs': ['get', 'list']}
            obj['rules'].append({'apiGroups': [GROUP], 'resources': ['hostedagents'], 'verbs': ['get', 'list']})
        if obj['kind'] == 'Deployment':
            pod = obj['spec']['template']['spec']; pod.pop('nodeSelector', None); pod.pop('tolerations', None)
            pod['imagePullSecrets'] = [{'name': n} for n in cfg['imagePullSecrets']]
            container = pod['containers'][0]; container['image'] = cfg['helperImage']
            container['env'] += [{'name': 'NATIVE_KAGENT', 'value': '1'},
                                 {'name': 'SOURCE_CONTROLLER_ORIGIN', 'value': cfg['sourceControllerOrigin']}]
    return {'apiVersion': 'v1', 'kind': 'List', 'items': objects}


def render(cfg, directory):
    ns = cfg['namespace']; kube = Snapshot(directory, ns)
    hosted, golden = (read(directory / name) for name in ('hosted.json', 'golden.json'))
    identity(hosted, 'HostedAgent', ns); identity(golden, 'GoldenScenario', ns)
    profile = {'runtimeProfile': RUNTIME, 'modelProfile': MODEL_PROFILE}
    intent = parse_intent(hosted, profile)
    spec = golden['spec']
    require(set(spec) == {'policy', 'inputOrigin', 'hostedAgentRef', 'hostedAgentSpecSha256', 'prompt',
                         'referenceFile', 'knowledgeFile', 'answerTerms', 'citations'}, 'InvalidGoldenContract')
    require(spec['policy'] == POLICY and spec['inputOrigin'] == 'synthetic'
            and spec['hostedAgentRef'] == {'name': hosted['metadata']['name']}
            and spec['hostedAgentSpecSha256'] == canonical(hosted['spec']), 'GoldenPinMismatch')
    require(isinstance(spec['prompt'], str) and 1 <= len(spec['prompt']) <= 4096, 'InvalidPrompt')
    for field, limit in [('answerTerms', 12), ('citations', 4)]:
        require(isinstance(spec[field], list) and 1 <= len(spec[field]) <= limit
                and all(isinstance(s, str) and 1 <= len(s) <= (128 if field == 'answerTerms' else 2048)
                        for s in spec[field]), 'InvalidAnswerChecks')
    packages, bindings, verified_texts = [], [], []
    onboarding = Onboarding(kube, profile)
    for index, (kind, pin) in enumerate([(SKILL, intent.skill), (KNOWLEDGE_BASE, intent.knowledge)]):
        binding = onboarding.binding(kind, pin); bindings.append(binding)
        release = kube.call(f'/apis/{API}/namespaces/{ns}/{kind.plural}/' + pin.name)
        cm = kube.call(f'/api/v1/namespaces/{ns}/configmaps/' + binding['configMapName'])
        files = release['spec']['files']
        texts = {p: cm['data'][f'file{i:02}'] for i, p in enumerate(sorted(files))}
        verified_texts.extend(texts.values())
        package = build(kind, release['spec'], texts)
        mounts = {('references/' if kind == KNOWLEDGE_BASE else '') + p: f'{index}/file{i:02}'
                  for i, p in enumerate(sorted(files))}
        packages.append({'name': package.name, 'contentSha256': pin.content_sha256, 'sourceCommit': pin.source_commit,
            'files': {p: {'sha256': sha256(t.encode()), **({'mount': mounts[p]} if p in mounts else {'text': t})}
                      for p, t in package.files.items()}})
    require(len({p['name'] for p in packages}) == 2, 'AmbiguousPackageNames')
    required = [[packages[0]['name'], spec['referenceFile']], [packages[1]['name'], spec['knowledgeFile']]]
    require(all(path in packages[i]['files'] for i, (_, path) in enumerate(required)), 'RequiredFileMissing')
    proofs = [p['files']['references/release-proof.txt']['text'].strip().split()[-1] for p in packages]
    require(all(p not in spec['prompt'] + intent.instructions for p in proofs), 'ProofSeededInPrompt')
    all_text = '\n'.join(verified_texts)
    require(all(c.startswith('https://') and c in all_text for c in spec['citations']), 'CitationNotInVerifiedContent')
    runtime = {'runtime': RUNTIME, 'endpoint': cfg['endpoint'], 'model': cfg['model'], 'limits': cfg['limits'],
        'instructions': intent.instructions, 'prompt': spec['prompt'], 'packages': packages,
        'required': required + [[p['name'], 'references/release-proof.txt'] for p in packages],
        'proofs': proofs, 'answerTerms': spec['answerTerms'], 'citations': spec['citations'],
        'intentSha256': canonical(hosted['spec']), 'scenarioSha256': canonical(spec)}
    raw = encoded(runtime); digest = sha256(raw.encode()); name = 'standalone-' + digest[:16]
    def obj(kind, suffix='', **fields):
        return {'apiVersion': 'batch/v1' if kind == 'Job' else 'v1', 'kind': kind,
                'metadata': {'name': name + suffix, 'namespace': ns}, **fields}
    env = []
    mounts = [{'name': 'code', 'mountPath': '/app', 'readOnly': True}, {'name': 'input', 'mountPath': '/input', 'readOnly': True},
              {'name': 'receipt', 'mountPath': '/receipt'}]
    volumes = [{'name': 'code', 'configMap': {'name': name + '-code'}}, {'name': 'input', 'configMap': {'name': name + '-input'}},
               {'name': 'receipt', 'emptyDir': {'sizeLimit': '1Mi'}}]
    for i, binding in enumerate(bindings):
        volumes.append({'name': f'content-{i}', 'configMap': {'name': binding['configMapName']}})
        mounts.append({'name': f'content-{i}', 'mountPath': f'/content/{i}', 'readOnly': True})
    if 'credentialSecret' in cfg:
        env.append({'name': 'MODEL_TOKEN', 'valueFrom': {'secretKeyRef': cfg['credentialSecret']}})
    if 'caConfigMap' in cfg:
        ref = cfg['caConfigMap']; env.append({'name': 'MODEL_CA_FILE', 'value': '/ca/ca.crt'})
        volumes.append({'name': 'ca', 'configMap': {'name': ref['name'], 'items': [{'key': ref['key'], 'path': 'ca.crt'}]}})
        mounts.append({'name': 'ca', 'mountPath': '/ca', 'readOnly': True})
    pod = {'automountServiceAccountToken': False, 'serviceAccountName': name, 'restartPolicy': 'Never',
        'imagePullSecrets': [{'name': n} for n in cfg['imagePullSecrets']], 'securityContext': {'seccompProfile': {'type': 'RuntimeDefault'}},
        'volumes': volumes, 'containers': [{'name': 'agent', 'image': cfg['helperImage'], 'env': env,
            'command': ['python', '-B', '/app/worker.py', '--input', '/input/input.json', '--sha256', digest,
                        '--receipt', '/receipt/receipt.json'], 'volumeMounts': mounts,
            'securityContext': {'runAsNonRoot': True, 'runAsUser': 1000, 'allowPrivilegeEscalation': False,
                                'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}},
            'resources': {'requests': {'cpu': '50m', 'memory': '64Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}}]}
    pod['securityContext']['fsGroup'] = 1000
    objects = [obj('ServiceAccount', automountServiceAccountToken=False),
        obj('ConfigMap', '-code', immutable=True, data={'worker.py': (HERE / 'worker.py').read_text()}),
        obj('ConfigMap', '-input', immutable=True, data={'input.json': raw}),
        obj('Job', spec={'backoffLimit': 0, 'activeDeadlineSeconds': cfg['limits']['deadlineSeconds'] + 15,
                        'template': {'metadata': {'labels': {'app': name}}, 'spec': pod}})]
    return {'apiVersion': 'v1', 'kind': 'List', 'items': objects}, {
        'runtime': RUNTIME, 'proofScope': 'standalone reference agent; not native kagent runtime or Harness proof',
        'jobName': name, 'namespace': ns, 'inputSha256': digest, 'intentSha256': canonical(hosted['spec']),
        'scenarioSha256': canonical(spec), 'bindings': [{k: v for k, v in b.items() if k != 'projection'} for b in bindings]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('config', 'snapshot', 'output'):
        parser.add_argument('--' + field, type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--schema-only', action='store_true'); mode.add_argument('--adapter-only', action='store_true')
    args = parser.parse_args()
    try:
        cfg = config(read(args.config)); files = patches(args.snapshot)
        if args.adapter_only:
            files = {'content-adapter.json': adapter(cfg, args.snapshot)}
        elif not args.schema_only:
            job, report = render(cfg, args.snapshot); files.update({'job.json': job, 'preparation.json': report})
        args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
        for name, value in files.items():
            path = args.output / name; path.write_text(json.dumps(value, indent=2) + '\n'); path.chmod(0o600)
        print(json.dumps({'result': 'Prepared', 'files': sorted(files)}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(json.dumps({'result': 'Rejected', 'reason': str(error) if isinstance(error, ValueError) else type(error).__name__}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
