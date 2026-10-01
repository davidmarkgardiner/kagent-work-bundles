#!/usr/bin/env python3
"""Install hidden-input PAT and bridge key in the selected cluster only."""
import argparse
import base64
import getpass
import json
import secrets
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--context', required=True)
p.add_argument('--namespace', default='kagent')
a = p.parse_args()
if not sys.stdin.isatty():
    p.error('Use an interactive terminal for hidden input')
pat = getpass.getpass('Organization-scoped Azure DevOps PAT (hidden): ').strip()
if not pat:
    p.error('PAT is empty')
base = ['kubectl', '--context', a.context, '-n', a.namespace]
existing = subprocess.run(base + ['get', 'secret', 'azure-devops-mcp-bridge-key', '--ignore-not-found', '-o', 'name'], capture_output=True, text=True, check=True)
items = [{'apiVersion':'v1', 'kind':'Secret', 'metadata':{'name':'azure-devops-mcp-pat', 'namespace':a.namespace}, 'type':'Opaque', 'stringData':{'PERSONAL_ACCESS_TOKEN':base64.b64encode(('mcp@example.invalid:' + pat).encode()).decode()}}]
if not existing.stdout:
    items.append({'apiVersion':'v1', 'kind':'Secret', 'metadata':{'name':'azure-devops-mcp-bridge-key', 'namespace':a.namespace}, 'type':'Opaque', 'stringData':{'key':secrets.token_hex(32)}})
subprocess.run(base + ['apply','--server-side','--field-manager=azure-devops-mcp-credential','-f','-'], input=json.dumps({'apiVersion':'v1','kind':'List','items':items}), text=True, check=True, stdout=subprocess.DEVNULL)
print('Secrets installed. No token printed or saved locally. Restart the bridge after credential rotation.')
