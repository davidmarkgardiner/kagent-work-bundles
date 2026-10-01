#!/usr/bin/env python3
"""Render public templates from non-secret workplace configuration."""
import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--config', type=pathlib.Path, required=True)
parser.add_argument('--out', type=pathlib.Path, required=True)
parser.add_argument('--runtime', choices=['go', 'legacy'], default='go',
                    help='legacy omits the unsupported runtime field on older kagent CRDs')
args = parser.parse_args()
config = json.loads(args.config.read_text())
expected = {'radar_namespace', 'kagent_namespace', 'model_config', 'image_repository'}
if set(config) != expected:
    parser.error('Configuration must contain exactly: ' + ', '.join(sorted(expected)))
for key, value in config.items():
    if not isinstance(value, str) or not value or '{{' in value or '}}' in value:
        parser.error(f'{key} must be a resolved nonempty string')
    if key != 'image_repository' and not re.fullmatch(r'[a-z0-9]([-a-z0-9]*[a-z0-9])?', value):
        parser.error(f'{key} must be a DNS label')
    if key != 'image_repository' and len(value) > 63:
        parser.error(f'{key} exceeds 63 characters')
    if key == 'image_repository' and not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9./:_-]*', value):
        parser.error('image_repository must be a repository path without a tag or digest')
    if key == 'image_repository' and (':' in value.split('/')[-1] or '@' in value):
        parser.error('image_repository must not include a tag or digest')
args.out.mkdir(parents=True, exist_ok=True)
if config['radar_namespace'] == config['kagent_namespace']:
    parser.error('Use a dedicated Radar namespace distinct from kagent_namespace')
replacements = {key.upper(): value for key, value in config.items()}
values = (ROOT / 'templates/values.yaml.tmpl').read_text()
for key, value in replacements.items():
    values = values.replace('{{' + key + '}}', value)
replacements['HELM_VALUES'] = '\n'.join('    ' + line for line in values.splitlines())
for path in sorted((ROOT / 'templates').glob('*.tmpl')):
    content = path.read_text()
    for key, value in replacements.items():
        content = content.replace('{{' + key + '}}', value)
    if '{{' in content or '}}' in content:
        parser.error(f'Unresolved placeholder in {path.name}')
    if args.runtime == 'legacy' and path.name == 'kagent-agent.yaml.tmpl':
        content = content.replace('    runtime: go\n', '')
    (args.out / path.name.removesuffix('.tmpl')).write_text(content)
print('Rendered:', args.out.resolve())
