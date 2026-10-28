import copy
import io
import json
import sys
import tarfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from artifacts import build
from controller import KNOWLEDGE_BASE, SKILL, content_digest, sha256


def fixture():
    texts = {'SKILL.md': '---\nname: demo\ndescription: Reviewed demo instructions.\n---\n\nRead references/check.md.\n',
             'references/check.md': 'Unique proof from source\n'}
    files = {p: sha256(t.encode()) for p, t in texts.items()}
    return {'path': 'skills/demo', 'skillName': 'demo', 'sourceCommit': 'a' * 40, 'files': files, 'contentSha256': content_digest(files)}, texts


class PackageTests(unittest.TestCase):
    def test_exact_bytes_and_metadata(self):
        spec, texts = fixture()
        package = build(SKILL, spec, texts)
        self.assertEqual(package.digest, build(SKILL, spec, dict(reversed(list(texts.items())))).digest)
        manifest = json.loads(package.manifest)
        raw = package.blobs[manifest['layers'][0]['digest']]
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            entries = archive.getmembers()
            self.assertEqual([e.name for e in entries], sorted(e.name for e in entries))
            self.assertTrue(all(e.uid == e.gid == e.mtime == 0 and not e.issym() for e in entries))
            found = {e.name.removeprefix('skill/'): archive.extractfile(e).read().decode() for e in entries if e.isfile()}
        self.assertEqual(found, package.files)
        self.assertTrue(all(found[p] == t for p, t in texts.items()))

    def test_tampered_and_extra_bytes_rejected(self):
        spec, texts = fixture()
        texts['references/check.md'] += 'tampered'
        with self.assertRaises(ValueError):
            build(SKILL, spec, texts)
        spec, texts = fixture()
        texts['unreviewed'] = 'extra'
        with self.assertRaises(ValueError):
            build(SKILL, spec, texts)

    def test_oci_special_paths_rejected(self):
        for path in ['.wh.deleted', 'references/.wh..wh..opq', 'release-proof.txt']:
            spec, texts = fixture()
            texts[path] = 'reviewed but unsafe'
            spec['files'] = {p: sha256(t.encode()) for p, t in texts.items()}
            spec['contentSha256'] = content_digest(spec['files'])
            with self.assertRaises(ValueError):
                build(SKILL, spec, texts)

    def test_commit_changes_manifest(self):
        spec, texts = fixture()
        original = build(SKILL, spec, texts)
        spec['sourceCommit'] = 'b' * 40
        self.assertNotEqual(original.digest, build(SKILL, spec, texts).digest)

    def test_kb_wrapper_preserves_document(self):
        text = '# Test\n\nSource: https://example.invalid/runbook\nReviewed: 2026-10-21\n\nEvidence 7341\n'
        files = {'runbook.md': sha256(text.encode())}
        spec = {'path': 'knowledge/bootstrap', 'knowledgeBaseName': 'bootstrap', 'sourceCommit': 'c' * 40, 'files': files,
                'contentSha256': content_digest(files), 'documents': [{'path': 'runbook.md', 'title': 'Test',
                'sourceURL': 'https://example.invalid/runbook', 'reviewedAt': '2026-10-21'}]}
        package = build(KNOWLEDGE_BASE, spec, {'runbook.md': text})
        self.assertEqual(package.name, 'kb-bootstrap')
        self.assertEqual(package.files['references/runbook.md'], text)
        self.assertIn('runbook.md', package.files['SKILL.md'])


if __name__ == '__main__':
    unittest.main()
