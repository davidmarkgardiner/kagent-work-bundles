"""Render the optional guidance extension; no deployment or credentials."""
import argparse
import json
from pathlib import Path
import re
import yaml
from store import GuidanceStore

parser = argparse.ArgumentParser()
parser.add_argument('--config', type=Path, required=True)
parser.add_argument('--catalog', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--runtime', choices=['go', 'legacy'], default='go')
args = parser.parse_args()
config = json.loads(args.config.read_text())
expected = {'radar_namespace', 'kagent_namespace', 'model_config', 'guidance_image', 'guidance_cluster'}
if set(config) != expected:
    parser.error('Required keys: ' + ', '.join(sorted(expected)))
for key, value in config.items():
    if not isinstance(value, str) or '{{' in value or '}}' in value:
        parser.error('Unresolved input: ' + key)
    if key == 'guidance_image':
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9./:_-]*@sha256:[0-9a-f]{64}', value):
            parser.error('guidance_image requires an approved repository and sha256 digest')
    elif not re.fullmatch(r'[a-z0-9]([-a-z0-9]*[a-z0-9])?', value) or len(value) > 63:
        parser.error(key + ' must be a DNS label')
if config['radar_namespace'] == config['kagent_namespace']:
    parser.error('Use a dedicated Radar namespace')
catalog_text = args.catalog.read_text()
if '{{' in catalog_text or '}}' in catalog_text:
    parser.error('Resolve catalog placeholders')
catalog = json.loads(catalog_text)
store = GuidanceStore(catalog)
if any(key[0] != config['guidance_cluster'] for key in store.bindings):
    parser.error('Catalog bindings must match guidance_cluster')
template = (Path(__file__).parent / 'kubernetes.yaml.tmpl').read_text()
for key, value in config.items():
    template = template.replace('{{' + key.upper() + '}}', value)
if '{{' in template or '}}' in template:
    parser.error('Unresolved template')
docs = list(yaml.safe_load_all(template))
assert not any(d['kind'] in {'ClusterRole', 'Role', 'RoleBinding', 'ClusterRoleBinding'} for d in docs)
agent = next(d for d in docs if d['kind'] == 'Agent')
if args.runtime == 'legacy':
    agent['spec']['declarative'].pop('runtime')
assert [t['mcpServer']['toolNames'] for t in agent['spec']['declarative']['tools']] == [
    ['get_neighborhood', 'get_topology'], ['find_guidance', 'read_guidance']]
configmap = dict(apiVersion='v1', kind='ConfigMap',
                 metadata=dict(name='workload-guidance-catalog', namespace=config['radar_namespace']),
                 data={'catalog.json': catalog_text})
args.out.mkdir(parents=True, exist_ok=True)
(args.out / 'guidance.yaml').write_text(yaml.safe_dump_all([configmap] + docs, sort_keys=False))
print('Rendered guidance extension:', args.out.resolve())
