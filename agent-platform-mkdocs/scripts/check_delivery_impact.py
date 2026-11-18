#!/usr/bin/env python3
"""Gate relevant Git changes on a reviewed roadmap impact decision; never writes Git."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parent.parent


def git(*args, input=None, check=True):
    return subprocess.run(['git', *args], cwd=ROOT, input=input, text=True, capture_output=True, check=check).stdout


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', help='Base commit for CI/review. Defaults to merge-request or push CI variables.')
    p.add_argument('--head', default='HEAD')
    p.add_argument('--staged', action='store_true', help='Inspect the Git index, including staged file contents.')
    args = p.parse_args()
    top = Path(git('rev-parse', '--show-toplevel').strip())
    prefix = ROOT.relative_to(top).as_posix()
    prefix = '' if prefix == '.' else prefix + '/'
    base = args.base or os.environ.get('CI_MERGE_REQUEST_DIFF_BASE_SHA') or os.environ.get('CI_COMMIT_BEFORE_SHA')
    first = not base or set(base) == {'0'}
    if args.staged:
        paths = git('diff', '--cached', '--name-only').splitlines()
        base = 'HEAD'
        first = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=ROOT, capture_output=True).returncode != 0
    elif first:
        if not base:
            p.error('provide --base, --staged, or a supported CI base variable')
        paths = git('ls-tree', '-r', '--name-only', args.head).splitlines()
    else:
        paths = git('diff', '--name-only', base, args.head).splitlines()
    def read(path, previous=False):
        if previous and first:
            return None
        spec = (base + ':' if previous else ':' if args.staged else args.head + ':') + prefix + path
        raw = git('show', spec, check=False)
        return yaml.safe_load(raw) if raw else None
    relevant = [x for x in paths if x.startswith(prefix) and x[len(prefix):].startswith(('docs/', 'delivery/', 'labs/', 'custom_theme/', 'scripts/', 'AGENTS.md', 'WORK-AGENT-PROMPT.md', 'requirements.txt', 'mkdocs.yml'))]
    # These extra watched paths are source-repository defaults; adapt to the receiving repository.
    if prefix:
        relevant += [x for x in paths if x.startswith(('agents/', 'platform/agentgateway/', 'docs/security/', 'docs/entra-agent-id/', 'docs/agent-substrate-', 'docs/AGENT-PLATFORM-DOCS.md', 'work-agent-bundles/agent-substrate/', 'work-agent-bundles/kagent-agentgateway-tenant-isolation/', 'work-agent-bundles/postgres-fastmcp-entra-uami/'))]
    if not relevant:
        print('DELIVERY_IMPACT: no tracked delivery changes')
        return
    changed = {x[len(prefix):] for x in paths if x.startswith(prefix)}
    roadmap = read('delivery/roadmap.yml')
    updates = read('delivery/updates.yml')
    if not roadmap or not updates:
        sys.exit('DELIVERY_IMPACT_FAILED: maintained roadmap and update sources are required')
    decisions = {'delivery/roadmap.yml', 'delivery/updates.yml', 'delivery/change-note.yml'} & changed
    if not decisions:
        sys.exit('DELIVERY_IMPACT_FAILED: update roadmap/updates or add a reviewed delivery/change-note.yml in this commit')
    if decisions == {'delivery/change-note.yml'}:
        note = read('delivery/change-note.yml') or {}
        if note.get('impact') != 'none' or len(str(note.get('reason', '')).strip()) < 20:
            sys.exit('DELIVERY_IMPACT_FAILED: no-impact note needs impact: none and a substantive reason')
    old_roadmap = read('delivery/roadmap.yml', previous=True) or {'milestones': []}
    old_updates = read('delivery/updates.yml', previous=True) or {'updates': []}
    old_states = {m['id']: m['state'] for m in old_roadmap['milestones']}
    old_ids = {u['id'] for u in old_updates['updates']}
    new_updates = [u for u in updates['updates'] if u['id'] not in old_ids]
    for milestone in roadmap['milestones']:
        state = milestone['state']
        if state not in {'built', 'live'} or old_states.get(milestone['id']) == state:
            continue
        history = milestone.get('historical') or {}
        owner_history = history.get('confirmed_on') and history.get('precision') == 'approximate-quarter' and history.get('period') == milestone['window'] and any(e['scope'] == 'owner-confirmation' for e in milestone['evidence'])
        if not milestone['evidence'] or (not milestone['built_on'] and not owner_history):
            sys.exit('DELIVERY_IMPACT_FAILED: built/live needs dated evidence: ' + milestone['id'])
        if state == 'live' and (not milestone['built_on'] or not milestone['live_on'] or not any(e['scope'] == 'target-service' for e in milestone['evidence'])):
            sys.exit('DELIVERY_IMPACT_FAILED: live needs dated service acceptance: ' + milestone['id'])
        accepted_states = {state} | ({'delivered'} if state == 'built' and not old_states else set())
        if not any(any(a['milestone'] == milestone['id'] and a['evidence'] for a in u['achievements']) and any(m['milestone'] == milestone['id'] and m['to'] in accepted_states for m in u['moved']) for u in new_updates):
            sys.exit('DELIVERY_IMPACT_FAILED: new built/live state needs a new achievement and state-change record: ' + milestone['id'])
    # Published snapshots remain immutable; explicit corrections belong in a new snapshot.
    current = {u['id']: u for u in updates['updates']}
    for old in old_updates['updates']:
        if current.get(old['id']) != old:
            sys.exit('DELIVERY_IMPACT_FAILED: preserve published update ' + old['id'] + '; append a correction instead')
    print(json.dumps({'delivery_impact': 'PASS', 'tracked_changes': len(relevant), 'decision_files': sorted(decisions)}))


if __name__ == '__main__':
    main()
