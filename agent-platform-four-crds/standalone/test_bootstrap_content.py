"""Offline Git and renderer tests. Synthetic Ready metadata is test-only evidence."""
import copy
import gzip
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

import yaml
import bootstrap_content as bootstrap
import prepare
from controller import API, GROUP, KNOWLEDGE_BASE, SKILL, sha256, verify_archive

FILES = ('source-and-releases.json', 'requests.json', 'bootstrap-receipt.json')


class BootstrapContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.checkout = self.root / 'content'; self.sequence = 0
        bootstrap.package.seed_content(self.checkout)
        self.git('init', '-q'); self.git('config', 'user.name', 'Offline test')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('add', 'skills', 'knowledge'); self.git('commit', '-qm', 'Bundled reviewed content')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()
        self.cfg = {'namespace': 'reference-test', 'helperImage': 'registry.example.invalid/helper@sha256:' + 'a' * 64,
            'endpoint': 'https://private-model.example.invalid/v1/chat/completions', 'model': 'private-qwen-model',
            'sourceControllerOrigin': 'http://private-source.example.invalid:9090', 'imagePullSecrets': [],
            'credentialSecret': {'name': 'private-model-token', 'key': 'token'},
            'limits': {'maxModelCalls': 6, 'maxToolCalls': 16, 'maxTokens': 2048,
                       'requestTimeoutSeconds': 30, 'deadlineSeconds': 180, 'maxResponseBytes': 131072}}
        self.config = self.root / 'config.json'; self.config.write_text(json.dumps(self.cfg))
        self.url = 'https://private-git.example.invalid/platform/content.git'

    def git(self, *args):
        return subprocess.check_output(['git', '-c', 'protocol.allow=never', '-C', str(self.checkout), *args],
            stderr=subprocess.PIPE, env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_NO_LAZY_FETCH': '1'})

    def cli(self, **changes):
        self.sequence += 1
        values = {'config': str(self.config), 'checkout': str(self.checkout), 'git-url': self.url,
                  'commit': self.commit, 'release-id': 'crd-poc-v1', 'git-auth-secret': 'private-git-token',
                  'output': str(self.root / ('prepared-' + str(self.sequence))), **changes}
        args = [sys.executable, '-B', str(prepare.HERE / 'bootstrap_content.py')]
        for key, value in values.items():
            if value is not None:
                args.extend(['--' + key, str(value)])
        result = subprocess.run(args, capture_output=True, text=True, timeout=20)
        for private in (self.url, self.cfg['endpoint'], self.cfg['sourceControllerOrigin'],
                        self.cfg['credentialSecret']['name'], 'private-git-token'):
            self.assertNotIn(private, result.stdout + result.stderr)
        return result, Path(values['output'])

    def prepared(self, **changes):
        result, output = self.cli(**changes)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), {'result': 'Prepared', 'files': sorted(FILES)})
        return {name: json.loads((output / name).read_text()) for name in FILES}, output

    def rejected(self, reason=None, **changes):
        result, output = self.cli(**changes)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, '')
        receipt = json.loads(result.stderr); self.assertEqual(receipt['result'], 'Rejected')
        if reason:
            self.assertEqual(receipt['reason'], reason)
        self.assertFalse(output.exists())

    def synthetic_source(self, source):
        """Supply test-only status for the real committed Git archive."""
        archive = gzip.compress(self.git('archive', '--format=tar', self.commit, '--', 'skills', 'knowledge'))
        source = copy.deepcopy(source)
        source['metadata'].update(uid='test-source-uid', generation=1)
        source['status'] = {'observedGeneration': 1,
            'conditions': [{'type': 'Ready', 'status': 'True', 'observedGeneration': 1}],
            'artifact': {'revision': 'sha1:' + self.commit, 'digest': 'sha256:' + sha256(archive)}}
        return source, archive

    def test_cli_preserves_releases_and_controller_accepts_actual_git_archive(self):
        files, output = self.prepared()
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
        self.assertEqual({p.name for p in output.iterdir()}, set(FILES))
        self.assertTrue(all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in output.iterdir()))
        source, *releases = files['source-and-releases.json']['items']
        self.assertEqual(source['spec'], {'url': self.url, 'interval': '1m', 'timeout': '60s',
            'ref': {'commit': self.commit},
            'ignore': '/*\n!/skills/\n!/knowledge/\n/skills/*\n!/skills/aks-known-issues/\n/knowledge/*\n!/knowledge/aks-bootstrap/\n',
            'secretRef': {'name': 'private-git-token'}})
        self.assertEqual(source['metadata'], {'name': 'content-crd-poc-v1', 'namespace': self.cfg['namespace']})
        self.assertTrue(all('status' not in obj for obj in [source, *releases]))
        test_source, archive = self.synthetic_source(source)
        for release, (path, kind, name) in zip(releases, bootstrap.RELEASES):
            expected = yaml.safe_load((prepare.REGISTRY / path).read_text())
            expected['metadata'].update(name=name + '-crd-poc-v1', namespace=self.cfg['namespace'])
            expected['spec'].update(sourceRef={'name': source['metadata']['name']}, sourceCommit=self.commit)
            self.assertEqual(release, expected)
            data, projection, revision = verify_archive(release, test_source, archive, kind)
            self.assertEqual(revision, 'sha1:' + self.commit)
            self.assertEqual(len(data), len(release['spec']['files']))
            self.assertEqual(len(projection), len(data))
            for index, (path, digest) in enumerate(sorted(release['spec']['files'].items())):
                raw = self.git('show', self.commit + ':' + release['spec']['path'] + '/' + path)
                self.assertEqual(raw, data[f'file{index:02}'].encode())
                self.assertEqual(sha256(raw), digest)
        receipt = files['bootstrap-receipt.json']
        self.assertTrue(receipt['bundledSnapshotVerified']); self.assertTrue(receipt['gitBytesVerified'])
        self.assertEqual(receipt['selectedFileCount'], 6)
        for flag in ('publishedSourceVerified', 'workplaceContentReady', 'fluxArtifactBoundsVerified'):
            self.assertFalse(receipt[flag])

    def test_generated_requests_pass_standalone_renderer_with_test_only_ready_metadata(self):
        files, _ = self.prepared()
        source, *releases = files['source-and-releases.json']['items']
        hosted, golden = files['requests.json']['items']
        original = yaml.safe_load((prepare.REGISTRY / 'native/examples/golden-exact-citation.yaml').read_text())
        self.assertEqual(golden['spec']['prompt'], original['spec']['prompt'])
        self.assertEqual(golden['spec']['inputOrigin'], 'synthetic')
        self.assertEqual(golden['spec']['hostedAgentSpecSha256'], prepare.canonical(hosted['spec']))
        source, archive = self.synthetic_source(source)
        cms = []
        for index, (release, kind) in enumerate(zip(releases, (SKILL, KNOWLEDGE_BASE))):
            release['metadata'].update(uid='test-release-' + str(index), generation=1)
            spec = release['spec']; cm_name = kind.configmap_prefix + release['metadata']['name'] + '-' + spec['contentSha256'][:16]
            release['status'] = {'observedGeneration': 1, 'contentSha256': spec['contentSha256'],
                'observedSourceRevision': 'sha1:' + self.commit, 'configMapRef': {'name': cm_name},
                'conditions': [{'type': 'Ready', 'status': 'True', 'observedGeneration': 1}]}
            data, _, _ = verify_archive(release, source, archive, kind)
            cms.append({'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True, 'data': data, 'metadata': {
                'name': cm_name, 'namespace': self.cfg['namespace'], 'uid': 'test-cm-' + str(index),
                'labels': {GROUP + '/' + kind.label: release['metadata']['name']},
                'annotations': {GROUP + '/digest': spec['contentSha256']}, 'ownerReferences': [{
                    'apiVersion': API, 'kind': kind.kind, 'name': release['metadata']['name'],
                    'uid': release['metadata']['uid'], 'controller': True}]}})
        for obj in (hosted, golden):
            obj['metadata'].update(uid='test-' + obj['kind'], generation=1)
        snapshot = self.root / 'snapshot'; snapshot.mkdir()
        documents = {'skill.json': releases[0], 'knowledge.json': releases[1], 'hosted.json': hosted,
            'golden.json': golden, 'sources.json': {'items': [source]}, 'configmaps.json': {'items': cms}}
        for name, doc in documents.items():
            (snapshot / name).write_text(json.dumps(doc))
        objects, receipt = prepare.render(self.cfg, snapshot)
        runtime = json.loads(next(o for o in objects['items'] if o['kind'] == 'ConfigMap' and 'input.json' in o['data'])['data']['input.json'])
        self.assertEqual(runtime['intentSha256'], golden['spec']['hostedAgentSpecSha256'])
        self.assertEqual(receipt['intentSha256'], runtime['intentSha256'])
        self.assertEqual(runtime['runtime'], 'standalone-reference-v1')
        for package, release, pin in zip(runtime['packages'], releases, (hosted['spec']['skillRefs'][0], hosted['spec']['knowledgeBaseRefs'][0])):
            self.assertEqual(package['sourceCommit'], self.commit)
            self.assertEqual(package['contentSha256'], pin['contentSha256'])
            self.assertEqual(pin['name'], release['metadata']['name'])
        self.assertTrue(all(proof not in runtime['prompt'] + runtime['instructions'] for proof in runtime['proofs']))
        self.assertEqual({o['kind'] for o in objects['items']}, {'ServiceAccount', 'ConfigMap', 'Job'})
        self.assertTrue(all(o['apiVersion'] in ('v1', 'batch/v1') for o in objects['items']))
        self.assertNotIn('substrate', json.dumps(objects).lower())

    def test_committed_bytes_are_authoritative_despite_dirty_worktree(self):
        _, first = self.prepared()
        (self.checkout / 'skills/aks-known-issues/LICENSE').write_text('Dirty uncommitted bytes')
        (self.checkout / 'knowledge/aks-bootstrap/oras-pull-unauthorized.md').unlink()
        _, second = self.prepared()
        self.assertEqual({p.name: p.read_bytes() for p in first.iterdir()}, {p.name: p.read_bytes() for p in second.iterdir()})

    def test_wrong_committed_bytes_in_either_full_manifest_are_rejected(self):
        for path in ('skills/aks-known-issues/LICENSE', 'knowledge/aks-bootstrap/oras-pull-unauthorized.md'):
            self.git('checkout', '-q', self.commit, '--', '.')
            target = self.checkout / path; target.write_bytes(target.read_bytes() + b'changed')
            self.git('add', 'skills', 'knowledge'); self.git('commit', '-qm', 'Changed fixture bytes')
            with self.subTest(path=path):
                self.rejected('GitFileDigestMismatch', commit=self.git('rev-parse', 'HEAD').decode().strip())

    def test_symlink_and_submodule_in_retained_tree_are_rejected(self):
        target = self.checkout / 'skills/aks-known-issues/LICENSE'; target.unlink(); target.symlink_to('SKILL.md')
        self.git('add', 'skills'); self.git('commit', '-qm', 'Symlink fixture')
        self.rejected('UnsafeGitFile', commit=self.git('rev-parse', 'HEAD').decode().strip())
        self.git('checkout', '-q', self.commit, '--', '.')
        self.git('update-index', '--add', '--cacheinfo', '160000,' + self.commit + ',skills/aks-known-issues/submodule')
        self.git('commit', '-qm', 'Gitlink fixture')
        self.rejected('UnsafeGitFile', commit=self.git('rev-parse', 'HEAD').decode().strip())

    def test_unresolved_config_and_git_placeholders_are_rejected(self):
        for change in ({'model': '{{UNRESOLVED_MODEL}}'}, {'model': '${UNRESOLVED_MODEL}'}, {'model': '<MODEL_ID>'}):
            self.config.write_text(json.dumps({**self.cfg, **change}))
            self.rejected('UnresolvedPlaceholder')
        self.config.write_text(json.dumps(self.cfg))
        self.rejected('UnresolvedPlaceholder', **{'git-url': 'https://{{GIT_HOST}}/content.git'})

    def test_url_credentials_queries_fragments_and_non_https_git_are_rejected(self):
        for url in ('http://git.example.invalid/content.git', 'https://user@git.example.invalid/content.git',
                    'https://user:password@git.example.invalid/content.git', self.url + '?token=private',
                    self.url + '#main', self.url[:-4], 'https://git.example.invalid/a/../content.git',
                    'https://git.example.invalid/%63ontent.git', 'https://git.example.invalid:bad/content.git'):
            with self.subTest(url=url):
                self.rejected('InvalidGitURL', **{'git-url': url})

    def test_commit_must_be_full_existing_exact_commit_object(self):
        for commit, reason in ((self.commit[:12], 'FullCommitRequired'), ('HEAD', 'FullCommitRequired'),
                               ('0' * 40, 'GitObjectUnavailable'), (self.git('rev-parse', 'HEAD^{tree}').decode().strip(), 'GitObjectUnavailable')):
            with self.subTest(commit=commit):
                self.rejected(reason, commit=commit)

    def test_local_replacement_refs_cannot_substitute_a_different_commit(self):
        self.git('rm', '-r', '--cached', 'skills', 'knowledge'); self.git('commit', '-qm', 'Empty fixture tree')
        empty = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('replace', empty, self.commit)
        self.rejected('MissingGitFile', commit=empty)

    def test_release_ids_secret_names_and_optional_auth(self):
        files, _ = self.prepared(**{'release-id': 'a' * 16, 'git-auth-secret': None})
        self.assertNotIn('secretRef', files['source-and-releases.json']['items'][0]['spec'])
        self.assertTrue(all(len(o['metadata']['name']) < 40 for name in FILES[:2] for o in files[name]['items']))
        for release_id in ('a' * 17, 'a-', 'Upper', '{{RELEASE_ID}}'):
            self.rejected('InvalidReleaseID', **{'release-id': release_id})
        self.rejected('InvalidGitSecretName', **{'git-auth-secret': 'other/secret'})
        shared, _ = self.prepared(**{'git-auth-secret': 'private-model-token'})
        self.assertEqual(shared['source-and-releases.json']['items'][0]['spec']['secretRef'], {'name': 'private-model-token'})

    def test_existing_output_is_preserved(self):
        output = self.root / 'exists'; output.mkdir(); sentinel = output / 'keep'; sentinel.write_text('owner data')
        result, _ = self.cli(output=output)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stderr)['reason'], 'FileExistsError')
        self.assertEqual(sentinel.read_text(), 'owner data')
        self.assertEqual(list(output.iterdir()), [sentinel])


if __name__ == '__main__':
    unittest.main()
