#!/usr/bin/env python3
"""Render a secret-free manifest for review; never applies it."""
import argparse
import json
from pathlib import Path
import re

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--config', required=True)
p.add_argument('--read-only', action='store_true')
a = p.parse_args()
root = Path(__file__).resolve().parent
config = json.loads(Path(a.config).read_text())
text = (root / 'kubernetes.template.json').read_text()
for key in set(re.findall(r'\{\{([A-Z_]+)\}\}', text)):
    value = config.get(key)
    if not isinstance(value, str) or not value or '{{' in value:
        p.error('Missing concrete configuration: ' + key)
    text = text.replace('{{' + key + '}}', json.dumps(value)[1:-1])
if '{{' in text:
    p.error('Unresolved placeholder')
if not re.fullmatch(r'[a-zA-Z0-9_-]+', config['ADO_ORGANIZATION']):
    p.error('Organization must be a slug')
if not re.fullmatch(r'[a-z0-9]([-a-z0-9]*[a-z0-9])?', config['NAMESPACE']):
    p.error('Invalid namespace')
if not re.search(r'@sha256:[0-9a-f]{64}$', config['MCP_IMAGE']):
    p.error('Use the digest returned by the internal registry after pushing')
if config['SOURCE_BRANCH'] == config['TARGET_BRANCH']:
    p.error('Source and target must differ')
if any(config[k].startswith('refs/') for k in ['SOURCE_BRANCH', 'TARGET_BRANCH']):
    p.error('Supply branch names without refs/heads/')
manifest = json.loads(text)
if a.read_only:
    for obj in manifest['items']:
        if obj['kind'] == 'Deployment':
            container = obj['spec']['template']['spec']['containers'][0]
            container['env'] = [e for e in container['env'] if e['name'] not in ['ENABLE_PR_CREATE', 'PR_PROJECT', 'PR_REPOSITORY', 'PR_SOURCE_REF', 'PR_TARGET_REF']]
        elif obj['kind'] == 'Agent':
            dec = obj['spec']['declarative']
            dec['tools'][0]['mcpServer']['toolNames'].remove('repo_pull_request_write')
            dec['systemMessage'] += '\nThis deployment is read-only: never create a PR or perform any write.\n'
print(json.dumps(manifest, indent=2))
