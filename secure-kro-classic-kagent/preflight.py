"""Read installed CRDs and controller versions before rendering the classic bundle."""
import argparse
import json
import subprocess


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
        r = subprocess.run([args.kubectl, '--context', args.context, 'get', *command, '-o', 'json'], capture_output=True, text=True, timeout=30, check=True)
        return json.loads(r.stdout)
    crd = get('crd', 'agents.kagent.dev')
    version = next(v for v in crd['spec']['versions'] if v['name'] == 'v1alpha2' and v['served'])
    spec = version['schema']['openAPIV3Schema']['properties']['spec']['properties']
    if not {'type', 'declarative', 'skills'} <= set(spec):
        raise ValueError('Installed Agent is not the supported classic declarative API.')
    native = spec['declarative']['properties']
    if not {'systemMessage', 'modelConfig', 'tools', 'runtime', 'deployment'} <= set(native):
        raise ValueError('Required native declarative fields are missing.')
    for name in ('modelconfigs.kagent.dev', 'remotemcpservers.kagent.dev'):
        if not any(v['name'] == 'v1alpha2' and v['served'] for v in get('crd', name)['spec']['versions']):
            raise ValueError('Required v1alpha2 API is not served: ' + name)
    classic = get('deployment', args.kagent_deployment, '-n', args.kagent_namespace)
    kro = get('deployment', args.kro_deployment, '-n', args.kro_namespace)
    classic_images = [c['image'] for c in classic['spec']['template']['spec']['containers']]
    kro_images = [c['image'] for c in kro['spec']['template']['spec']['containers']]
    if any('substrate' in image or '1.0.0-alpha' in image for image in classic_images):
        raise ValueError('Select the actual classic 0.x controller, not the 1.x/Substrate deployment.')
    version_match = any(image.endswith(':0.9.4') or image.endswith(':v0.9.4') for image in kro_images)
    if not version_match:
        raise ValueError('KRO 0.9.4 was not established from the controller tag. Verify a digest-pinned deployment separately.')
    print(json.dumps({'result': 'ClassicSchemaAvailable', 'nativeAPI': 'kagent.dev/v1alpha2',
        'kagentControllerImages': classic_images, 'kroControllerImages': kro_images,
        'runtimeEnums': native['runtime'].get('enum', []), 'substrateRequired': False}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, StopIteration, subprocess.SubprocessError) as error:
        raise SystemExit('Preflight failed: ' + str(error))
