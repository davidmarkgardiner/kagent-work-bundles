"""Read the selected source into a private render directory. Never applies changes."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--source-namespace', required=True)
    parser.add_argument('--namespace', required=True)
    parser.add_argument('--agent', required=True)
    parser.add_argument('--api-server-cidr', required=True)
    parser.add_argument('--python-image', required=True)
    parser.add_argument('--private-dir', type=Path, required=True)
    parser.add_argument('--include-model-credential', action='store_true', required=True,
                        help='Read the referenced model Secret into the private prerequisites file.')
    args = parser.parse_args()
    directory = args.private_dir.resolve()
    if args.source_namespace == args.namespace:
        raise ValueError('Use a dedicated destination namespace.')
    if any((ancestor / '.git').exists() for ancestor in [directory, *directory.parents]):
        raise ValueError('Keep the private directory outside Git checkouts.')
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    def read(*arguments):
        return json.loads(subprocess.check_output(['kubectl', '--context', args.context,
                                                   '--request-timeout=15s', *arguments]))
    def save(name, value):
        fd = os.open(directory / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump(value, output, indent=2)
    agent = read('-n', args.source_namespace, 'get', 'agent', args.agent, '-o', 'json')
    model_name = agent['spec']['declarative']['modelConfig']
    model = read('-n', args.source_namespace, 'get', 'modelconfig', model_name, '-o', 'json')
    secret = read('-n', args.source_namespace, 'get', 'secret', model['spec']['apiKeySecret'], '-o', 'json')
    content = set()
    for volume in agent['spec']['declarative']['deployment'].get('volumes', []):
        if volume['name'] == 'ordinary-telemetry':
            continue
        if 'configMap' in volume:
            content.add(volume['configMap']['name'])
        for source in volume.get('projected', {}).get('sources', []):
            if 'configMap' in source:
                content.add(source['configMap']['name'])
    objects = [model, secret] + [read('-n', args.source_namespace, 'get', 'configmap', name, '-o', 'json')
                               for name in sorted(content)]
    prerequisites = []
    for source in objects:
        item = {'apiVersion': source['apiVersion'], 'kind': source['kind'],
                'metadata': {'name': source['metadata']['name'], 'namespace': args.namespace}}
        for field in ('spec', 'type', 'data', 'binaryData', 'immutable'):
            if field in source:
                item[field] = source[field]
        prerequisites.append(item)
    oidc = read('get', '--raw', '/.well-known/openid-configuration')
    save('jwks.json', read('get', '--raw', '/openid/v1/jwks'))
    save('agent.json', agent)
    save('status.json', read('-n', args.source_namespace, 'get', 'configmap', 'onboarding-status-data-v1', '-o', 'json'))
    save('prerequisites.json', {'apiVersion': 'v1', 'kind': 'List', 'items': prerequisites})
    save('settings.json', {'namespace': args.namespace, 'agent_name': args.agent,
        'model_name': model_name, 'issuer': oidc['issuer'], 'jwks_file': str(directory / 'jwks.json'),
        'api_server_cidr': args.api_server_cidr, 'python_image': args.python_image})
    print('Private snapshots prepared. Review settings, source mounts, model route and network peers before rendering.')


if __name__ == '__main__':
    main()
