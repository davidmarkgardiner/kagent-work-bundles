#!/usr/bin/env python3
"""Copy only explicit public handoff assets; --check detects stale downloads."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
FILES = {
    'evidence/owner-confirmed-history.json': 'owner-confirmed-history.json',
    'AGENTS.md': 'AGENTS.md.txt',
    'delivery/update-template.yml': 'update-template.yml',
    'delivery/roadmap.yml': 'roadmap.yml',
    'delivery/updates.yml': 'updates.yml',
    'WORK-AGENT-PROMPT.md': 'WORK-AGENT-PROMPT.md.txt',
    'versions.lock.json': 'versions.lock.json',
    'source-manifest.json': 'source-manifest.json',
    'evidence/validation.json': 'validation.json',
    **{'labs/kagent-1.0.1/' + x: x for x in [
        'agent-canary.yaml', 'kagent-values.yaml', 'kagent-values-candidate.yaml',
        'servicenow-a2a-route.yaml', 'a2a-request.json', 'preflight.py', 'verify_offline.py']},
}
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--check', action='store_true')
a = p.parse_args()
errors = []
for source, dest in FILES.items():
    path = ROOT / 'docs/downloads' / dest
    content = (ROOT / source).read_bytes()
    if a.check:
        if not path.exists() or path.read_bytes() != content:
            errors.append(dest)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
if errors:
    sys.exit('Stale downloads: ' + ', '.join(errors))
print('DOWNLOADS_FRESH' if a.check else 'DOWNLOADS_SYNCED')
