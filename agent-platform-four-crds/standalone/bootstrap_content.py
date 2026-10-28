#!/usr/bin/env python3
"""Prepare pinned content and standalone requests from local Git objects, offline."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

import yaml
import prepare

sys.path.insert(0, str(prepare.HERE.parent))
import package
from controller import KNOWLEDGE_BASE, MAX_ARCHIVE, MAX_CONTENT, MAX_EXPANDED, SKILL

RELEASES = [('imports/aks-known-issues/skill.yaml', SKILL, 'aks-known-issues'),
            ('knowledge/knowledgebase.yaml', KNOWLEDGE_BASE, 'aks-bootstrap')]
FILES = ('source-and-releases.json', 'requests.json', 'bootstrap-receipt.json')
IGNORE = '/*\n!/skills/\n!/knowledge/\n/skills/*\n!/skills/aks-known-issues/\n/knowledge/*\n!/knowledge/aks-bootstrap/\n'


def concrete(value):
    prepare.require(not re.search(r'\{\{|\}\}|\$\{|<[^>]+>', prepare.encoded(value)), 'UnresolvedPlaceholder')


def git(root, *args):
    try:
        return subprocess.check_output(['git', '-c', 'protocol.allow=never', '-C', str(root), *args],
            stderr=subprocess.DEVNULL, env={**os.environ, 'GIT_NO_LAZY_FETCH': '1',
                'GIT_TERMINAL_PROMPT': '0', 'GIT_NO_REPLACE_OBJECTS': '1'})
    except subprocess.CalledProcessError:
        raise ValueError('GitObjectUnavailable') from None


def git_url(value):
    concrete(value)
    try:
        p = urlsplit(value)
        valid = (len(value) <= 2048 and not re.search(r'[\s\x00-\x1f%\\]', value)
                 and p.scheme == 'https' and p.hostname and p.port != 0 and p.username is None
                 and p.password is None and not p.query and not p.fragment and p.path.endswith('.git')
                 and '..' not in p.path.split('/'))
    except ValueError:
        valid = False
    prepare.require(valid, 'InvalidGitURL')
    return value


def render(cfg, checkout, url, commit, release_id, secret=None):
    package.verify_snapshot()
    concrete(cfg); cfg = prepare.config(cfg)
    prepare.require(re.fullmatch(r'[a-z](?:[a-z0-9-]{0,14}[a-z0-9])?', release_id), 'InvalidReleaseID')
    prepare.require(re.fullmatch('[0-9a-f]{40}', commit), 'FullCommitRequired')
    if secret is not None:
        concrete(secret)
        prepare.require(re.fullmatch(prepare.NAME, secret), 'InvalidGitSecretName')
    source_name = 'content-' + release_id
    source = {'apiVersion': 'source.toolkit.fluxcd.io/v1', 'kind': 'GitRepository',
        'metadata': {'name': source_name, 'namespace': cfg['namespace']}, 'spec': {
            'interval': '1m', 'timeout': '60s', 'url': git_url(url), 'ref': {'commit': commit},
            'ignore': IGNORE}}
    if secret is not None:
        source['spec']['secretRef'] = {'name': secret}
    prepare.require(git(checkout, 'rev-parse', '--verify', commit + '^{commit}').decode().strip() == commit,
                    'SourceCommitMismatch')
    blobs = {}
    for entry in git(checkout, 'ls-tree', '-rz', commit, '--', 'skills/aks-known-issues', 'knowledge/aks-bootstrap').split(b'\0'):
        if entry:
            fields, path = entry.split(b'\t', 1)
            mode, kind, oid = fields.split()
            prepare.require(mode in (b'100644', b'100755') and kind == b'blob', 'UnsafeGitFile')
            blobs[path.decode('utf-8', errors='strict')] = oid.decode('ascii')
    releases, count, size = [], 0, 0
    for path, kind, name in RELEASES:
        release = yaml.safe_load((prepare.REGISTRY / path).read_text())
        release['metadata'].update(name=name + '-' + release_id, namespace=cfg['namespace'])
        spec = release['spec']; spec.update(sourceRef={'name': source_name}, sourceCommit=commit)
        texts = {}
        for path, digest in spec['files'].items():
            oid = blobs.get(spec['path'] + '/' + path)
            prepare.require(oid is not None, 'MissingGitFile')
            prepare.require(int(git(checkout, 'cat-file', '-s', oid)) <= MAX_CONTENT, 'GitFileTooLarge')
            raw = git(checkout, 'cat-file', 'blob', oid)
            prepare.require(prepare.sha256(raw) == digest, 'GitFileDigestMismatch')
            texts[path] = raw.decode('utf-8', errors='strict'); count += 1; size += len(raw)
        prepare.build(kind, spec, texts)
        releases.append(release)
    hosted = next(doc for doc in yaml.safe_load_all((prepare.REGISTRY / 'native/examples/requests.yaml').read_text())
                  if doc['kind'] == 'HostedAgent')
    hosted['metadata'].update(name='docs-' + release_id, namespace=cfg['namespace'])
    hosted['spec'].update(runtimeProfile=prepare.RUNTIME, modelProfile=prepare.MODEL_PROFILE,
                         purpose='Reviewed AKS documentation agent on the standalone reference runtime')
    for field, release in zip(('skillRefs', 'knowledgeBaseRefs'), releases):
        hosted['spec'][field] = [{'name': release['metadata']['name'],
            **{key: release['spec'][key] for key in ('sourceCommit', 'contentSha256')}}]
    prepare.parse_intent(hosted, {'runtimeProfile': prepare.RUNTIME, 'modelProfile': prepare.MODEL_PROFILE})
    golden = yaml.safe_load((prepare.REGISTRY / 'native/examples/golden-exact-citation.yaml').read_text())
    golden['metadata'].update(name='docs-proof-' + release_id, namespace=cfg['namespace'])
    golden['spec'].update(policy=prepare.POLICY, hostedAgentRef={'name': hosted['metadata']['name']},
                          hostedAgentSpecSha256=prepare.canonical(hosted['spec']))
    receipt = {'mode': 'offlineContentBootstrap', 'namespace': cfg['namespace'], 'sourceName': source_name,
        'skillRelease': releases[0]['metadata']['name'], 'knowledgeRelease': releases[1]['metadata']['name'],
        'hostedName': hosted['metadata']['name'], 'goldenName': golden['metadata']['name'], 'contentCommit': commit,
        'configSha256': prepare.canonical(cfg), 'bundledSnapshotVerified': True, 'gitBytesVerified': True,
        'selectedFileCount': count, 'selectedContentBytes': size, 'publishedSourceVerified': False,
        'workplaceContentReady': False, 'fluxArtifactBoundsVerified': False,
        'artifactLimitsBytes': {'compressed': MAX_ARCHIVE, 'expanded': MAX_EXPANDED, 'perReleaseContent': MAX_CONTENT}}
    listing = lambda objects: {'apiVersion': 'v1', 'kind': 'List', 'items': objects}
    return dict(zip(FILES, [listing([source, *releases]), listing([hosted, golden]), receipt]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'checkout', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('git-url', 'commit', 'release-id'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--git-auth-secret')
    args = parser.parse_args()
    try:
        files = render(prepare.read(args.config), args.checkout, args.git_url, args.commit, args.release_id, args.git_auth_secret)
        args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
        for name, value in files.items():
            with open(args.output / name, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
                stream.write(json.dumps(value, indent=2) + '\n')
        print(json.dumps({'result': 'Prepared', 'files': sorted(files)}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[A-Za-z][A-Za-z0-9]{0,63}', str(error)) else type(error).__name__
        print(json.dumps({'result': 'Rejected', 'reason': reason}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
