"""Check the pinned non-Substrate kagent, native APIs and runtime settings."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def image_matches(image, expected):
    if '@' in image:
        return image.rsplit('@', 1)[1] == expected['digest']
    return image == expected['tag']


def schema_hash(version):
    return hashlib.sha256(json.dumps(version['schema']['openAPIV3Schema'], sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def check(get, args, lock):
    for name, expected in lock['crdSchemas'].items():
        versions = get('crd', name)['spec']['versions']
        version = next(v for v in versions if v['name'] == 'v1alpha2' and v['served'])
        if schema_hash(version) != expected:
            raise ValueError('CRD schema differs from the pinned 0.10.4 chart: ' + name)
    controller = get('deployment', args.kagent_deployment, '-n', args.kagent_namespace)
    containers = controller['spec']['template']['spec']['containers']
    image = next(c['image'] for c in containers if c['name'] == 'controller')
    if not image_matches(image, lock['images']['controller']):
        raise ValueError('Expected the pinned kagent 0.10.4 controller. Found ' + image)
    replicas = controller['spec'].get('replicas', 1)
    status = controller.get('status', {})
    if (replicas < 1 or status.get('observedGeneration', 0) < controller['metadata']['generation']
            or any(status.get(key, 0) != replicas for key in ('replicas', 'updatedReplicas', 'availableReplicas'))):
        raise ValueError('The pinned controller rollout is not complete and available.')
    settings = {}
    runtime = next(c for c in containers if c['name'] == 'controller')
    for source in runtime.get('envFrom', []):
        if 'configMapRef' in source:
            settings.update(get('configmap', source['configMapRef']['name'], '-n', args.kagent_namespace).get('data', {}))
    settings.update({entry['name']: entry['value'] for entry in runtime.get('env', []) if 'value' in entry})
    for key in ('SUBSTRATE_ATE_API_ENDPOINT', 'SUBSTRATE_ATENET_ROUTER_URL', 'SUBSTRATE_DEFAULT_WORKERPOOL_NAME'):
        if settings.get(key):
            raise ValueError('Substrate is enabled in the selected controller: ' + key)
    required = {'IMAGE_TAG': 'pythonAgent', 'GO_IMAGE_TAG': 'goAgent', 'SKILLS_INIT_IMAGE_TAG': 'skillsInit'}
    for key, role in required.items():
        entry = lock['images'][role]
        value = settings.get(key, '')
        expected_tag = entry['tag'].rsplit(':', 1)[1]
        if value not in (expected_tag, expected_tag + '@' + entry['digest']):
            raise ValueError('Runtime configuration differs from the lock: ' + key)
        prefix = key.removesuffix('TAG')
        reference = settings.get(prefix + 'REGISTRY', '') + '/' + settings.get(prefix + 'REPOSITORY', '') + ':' + value
        if not image_matches(reference, entry):
            raise ValueError('Runtime image differs from the lock: ' + key)
    for key, role in (('APP_FULL_IMAGE_DIGEST', 'pythonAgentWithSkills'), ('GOLANG_ADK_FULL_IMAGE_DIGEST', 'goAgentWithSkills')):
        if settings.get(key) and settings[key] != lock['images'][role]['digest']:
            raise ValueError('Full skills runtime digest differs from the lock: ' + key)
    kro = get('deployment', args.kro_deployment, '-n', args.kro_namespace)
    kro_images = [c['image'] for c in kro['spec']['template']['spec']['containers']]
    if not any(image_matches(value, lock['images']['kro']) for value in kro_images):
        raise ValueError('KRO image differs from the pinned 0.9.4 reference.')
    return {'result': 'NonSubstrateParityEstablished', 'kagent': lock['kagentReference'],
            'nativeAPI': lock['nativeAPI'], 'kagentControllerImage': image,
            'runtimeTags': {key: settings[key] for key in required}, 'kroControllerImages': kro_images,
            'nativeSchemaHashesMatch': True, 'substrateRequired': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--kubectl', default='kubectl')
    parser.add_argument('--kagent-namespace', default='kagent')
    parser.add_argument('--kagent-deployment', default='kagent-controller')
    parser.add_argument('--kro-namespace', default='kro-system')
    parser.add_argument('--kro-deployment', default='kro')
    args = parser.parse_args()
    def get(*command):
        result = subprocess.run([args.kubectl, '--context', args.context, 'get', *command, '-o', 'json'],
                                capture_output=True, text=True, timeout=30, check=True)
        return json.loads(result.stdout)
    lock = json.loads(Path(__file__).with_name('versions.lock.json').read_text())
    print(json.dumps(check(get, args, lock), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, StopIteration, subprocess.SubprocessError) as error:
        raise SystemExit('Preflight failed: ' + str(error))
