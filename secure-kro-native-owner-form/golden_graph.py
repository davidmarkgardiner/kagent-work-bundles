"""Attach the bounded native verifier to the native KRO composition."""
import copy
import json
from pathlib import Path

import owner_schema

HERE = Path(__file__).resolve().parent


def compose(profile, golden_config):
    graph = owner_schema.rgd(profile)
    deployment = next(r for r in graph['spec']['resources'] if r['template']['kind'] == 'Deployment')
    config = next(r for r in graph['spec']['resources'] if r['template']['kind'] == 'ConfigMap')
    deploy_id, config_id = deployment['id'], config['id']
    pod = deployment['template']['spec']['template']['spec']
    container = pod['containers'][0]
    container['command'] = ['python3', '-B', '/app/server.py', '--config', '/config/runtime.json']
    container.pop('args', None)
    next(v for v in pod['volumes'] if v['name'] == 'config')['configMap']['name'] = '${' + config_id + '.metadata.name}'
    deployment['readyWhen'].extend([
        '${' + deploy_id + '.status.updatedReplicas == ' + deploy_id + '.spec.replicas}',
        '${' + deploy_id + '.status.replicas == ' + deploy_id + '.spec.replicas}'])
    verifier_config = copy.deepcopy(golden_config)
    verifier_config['requestUID'] = '${schema.metadata.uid}'
    graph['spec']['resources'].append({'id': 'goldenConfig', 'template': {
        'apiVersion': 'v1', 'kind': 'ConfigMap',
        'metadata': {'name': 'demo-golden-config', 'namespace': 'secure-byo-kro'},
        'data': {'config.json': json.dumps(verifier_config, sort_keys=True)}}})
    job = json.loads((HERE / 'examples/golden-job.json').read_text())
    job['spec']['template']['spec']['containers'][0]['image'] = container['image']
    job['metadata']['annotations']['secure-byo.platform/frontdoor'] = '${' + deploy_id + '.metadata.name}'
    graph['spec']['resources'].append({'id': 'nativeGolden', 'template': job,
        'readyWhen': ['${nativeGolden.status.succeeded == 1}']})
    graph['spec']['schema']['status']['goldenSucceeded'] = '${nativeGolden.status.succeeded}'
    return graph
