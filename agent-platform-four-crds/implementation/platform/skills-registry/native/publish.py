#!/usr/bin/env python3
"""Build a reviewed OCI layout from the exact Git object, never the worktree."""

import argparse
import json
from pathlib import Path
import subprocess

from artifacts import build
from controller import KNOWLEDGE_BASE, SKILL, relative_path


def from_git(root, release):
    spec = release['spec']
    commit = spec['sourceCommit']
    resolved = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--verify', commit + '^{commit}'], text=True).strip()
    if resolved != commit:
        raise ValueError('SourceCommitMismatch')
    texts = {}
    for path in spec['files']:
        full = str(relative_path(spec['path']) / relative_path(path))
        entry = subprocess.check_output(['git', '-C', str(root), 'ls-tree', commit, '--', full], text=True).strip()
        if not entry.startswith(('100644 blob ', '100755 blob ')) or entry.split('\t', 1)[-1] != full:
            raise ValueError('UnsafeGitFile')
        raw = subprocess.check_output(['git', '-C', str(root), 'show', commit + ':' + full])
        texts[path] = raw.decode('utf-8', errors='strict')
    kind = {'Skill': SKILL, 'KnowledgeBase': KNOWLEDGE_BASE}[release['kind']]
    return build(kind, spec, texts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--git', required=True, type=Path)
    parser.add_argument('--release', required=True, type=Path, help='Reviewed release JSON')
    parser.add_argument('--layout', required=True, type=Path)
    args = parser.parse_args()
    package = from_git(args.git, json.loads(args.release.read_text()))
    package.layout(args.layout)
    print(json.dumps({'name': package.name, 'digest': package.digest, 'path': 'skill'}))
