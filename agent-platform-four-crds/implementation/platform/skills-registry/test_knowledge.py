import copy
import io
import tarfile
import unittest
from unittest.mock import patch

from controller import API, Controller, FINALIZER, GROUP, KNOWLEDGE_BASE, Rejected, content_digest, sha256, verify_archive


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.document = {'path': 'runbook.md', 'title': 'Demo runbook', 'sourceURL': 'https://example.com/runbook', 'reviewedAt': '2026-10-21'}
        self.body = '# Demo runbook\n\nSource: https://example.com/runbook\nReviewed: 2026-10-21\n\nSynthetic proposed checks.\n'
        files = {'runbook.md': sha256(self.body.encode())}
        self.release = {'metadata': {'name': 'demo-v1', 'namespace': 'skills-demo', 'uid': 'kb-owner', 'generation': 1,
                                     'resourceVersion': '1', 'finalizers': [FINALIZER]},
                        'spec': {'knowledgeBaseName': 'demo', 'path': 'knowledge/demo', 'sourceRef': {'name': 'source'},
                                 'sourceCommit': 'a' * 40, 'files': files, 'contentSha256': content_digest(files), 'documents': [self.document]}}
        self.source = {'metadata': {'generation': 1}, 'spec': {'ref': {'commit': 'a' * 40}}, 'status': {
            'conditions': [{'type': 'Ready', 'status': 'True', 'observedGeneration': 1}],
            'artifact': {'revision': 'sha1:' + 'a' * 40, 'url': 'http://source-controller.skills-demo.svc.cluster.local/artifact'}}}
        self.archive = self.tar(self.body)

    def tar(self, body, symlink=False):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            entry = tarfile.TarInfo('knowledge/demo/runbook.md')
            if symlink:
                entry.type = tarfile.SYMTYPE
                entry.linkname = '/etc/passwd'
            else:
                entry.size = len(body.encode())
            archive.addfile(entry, None if symlink else io.BytesIO(body.encode()))
        raw = stream.getvalue()
        self.source['status']['artifact']['digest'] = 'sha256:' + sha256(raw)
        return raw

    def verify(self, archive=None):
        return verify_archive(self.release, self.source, self.archive if archive is None else archive, KNOWLEDGE_BASE)

    def test_document_without_skill_metadata_is_materialized(self):
        data, items, _ = self.verify()
        self.assertEqual(data, {'file00': self.body})
        self.assertEqual(items, [{'key': 'file00', 'path': 'demo/runbook.md'}])

    def test_changed_bytes_are_rejected(self):
        with self.assertRaisesRegex(Rejected, 'FileDigestMismatch'):
            self.verify(self.tar(self.body + 'altered'))

    def test_changed_artifact_is_rejected(self):
        self.source['status']['artifact']['digest'] = 'sha256:' + '0' * 64
        with self.assertRaisesRegex(Rejected, 'ArtifactDigestMismatch'):
            self.verify()

    def test_changed_revision_is_rejected(self):
        self.source['spec']['ref']['commit'] = 'b' * 40
        with self.assertRaisesRegex(Rejected, 'SourceNotPinnedAndReady'):
            self.verify()

    def test_duplicate_document_is_rejected(self):
        self.release['spec']['documents'].append(copy.deepcopy(self.document))
        with self.assertRaisesRegex(Rejected, 'InvalidDocumentManifest'):
            self.verify()

    def test_undeclared_selected_file_is_rejected(self):
        self.release['spec']['documents'] = []
        with self.assertRaisesRegex(Rejected, 'InvalidDocumentManifest'):
            self.verify()

    def test_provenance_must_match_hashed_document(self):
        for field, value in [('title', 'Different title'), ('sourceURL', 'https://example.com/other'), ('reviewedAt', '2026-10-20')]:
            with self.subTest(field=field):
                original = self.document[field]
                self.document[field] = value
                with self.assertRaisesRegex(Rejected, 'DocumentProvenanceMismatch'):
                    self.verify()
                self.document[field] = original

    def test_http_citation_is_rejected(self):
        self.document['sourceURL'] = 'http://example.com/runbook'
        with self.assertRaisesRegex(Rejected, 'InvalidDocumentCitation'):
            self.verify()

    def test_invalid_review_date_is_rejected(self):
        self.document['reviewedAt'] = '2026-02-30'
        with self.assertRaisesRegex(Rejected, 'InvalidDocumentReviewDate'):
            self.verify()

    def test_symlink_is_rejected(self):
        with self.assertRaisesRegex(Rejected, 'UnsafeSkillFile'):
            self.verify(self.tar(self.body, symlink=True))

    def test_kb_configmap_collision_does_not_become_ready(self):
        calls = []
        source = self.source
        class Kube:
            namespace = 'skills-demo'
            def call(self, path, method='GET', value=None):
                calls.append((path, method, value))
                if '/gitrepositories/' in path:
                    return source
                if '/configmaps/' in path:
                    return {'metadata': {'ownerReferences': []}, 'immutable': True, 'data': {'file00': 'unreviewed'}}
                return value
        with patch('controller.artifact_bytes', return_value=self.archive):
            Controller(Kube(), KNOWLEDGE_BASE).reconcile(self.release)
        self.assertTrue(calls[-1][0].endswith('/knowledgebases/demo-v1/status'))
        self.assertEqual(calls[-1][2]['status']['conditions'][0]['reason'], 'ConfigMapCollision')
        self.assertFalse(any(method == 'POST' for _, method, _ in calls))

    def test_kb_deletion_is_blocked_while_agent_mounts_owned_content(self):
        calls = []
        class Kube:
            namespace = 'skills-demo'
            def call(self, path, method='GET', value=None):
                calls.append((path, method, value))
                if path.endswith('/configmaps'):
                    return {'items': [{'metadata': {'name': 'kb-demo-v1-digest', 'ownerReferences': [{'uid': 'kb-owner'}]}}]}
                if path.endswith('/agents'):
                    return {'items': [{'spec': {'declarative': {'deployment': {'volumes': [{'configMap': {'name': 'kb-demo-v1-digest'}}]}}}}]}
                return value
        self.release['metadata']['deletionTimestamp'] = '2026-10-21T00:00:00Z'
        Controller(Kube(), KNOWLEDGE_BASE).reconcile(self.release)
        self.assertEqual(calls[-1][2]['status']['conditions'][0]['reason'], 'InUseByAgent')
        self.assertFalse(any(value and 'finalizers' in value.get('metadata', {}) for _, _, value in calls))


if __name__ == '__main__':
    unittest.main()
