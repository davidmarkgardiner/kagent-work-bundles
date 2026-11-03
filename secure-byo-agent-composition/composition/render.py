"""Emit JSON manifests without contacting Kubernetes."""
import argparse
import json
from pathlib import Path
from compose import crd, generate, rgd

parser = argparse.ArgumentParser()
parser.add_argument('command', choices=['hosted-crd', 'kro-rgd', 'preview'])
parser.add_argument('--profile')
parser.add_argument('--request')
args = parser.parse_args()
profile = json.loads(Path(args.profile).read_text()) if args.profile else None
if args.command == 'hosted-crd':
    output = crd()
elif args.command == 'kro-rgd':
    output = rgd(profile)
else:
    request = json.loads(Path(args.request).read_text())
    output = {'apiVersion': 'v1', 'kind': 'List', 'items': generate(profile, request, owner=False)}
print(json.dumps(output, indent=2))
