import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package = load('source_package', 'package.py')
verify = load('source_verify', 'verify-bundle.py')


class Packaging(unittest.TestCase):
    def fixture(self, directory):
        root = directory / 'source'
        root.mkdir()
        for name, body in {'README.md': '[probe](diagnostics/main.go)',
                'diagnostics/main.go': 'package main\nfunc main() {}\n',
                'diagnostics/go.mod': 'module probe\ngo 1.23\n',
                'diagnostics/go.sum': 'approved-module-checksums\n',
                'diagnostics/build.sh': '#!/bin/sh\nexit 0\n',
                'prerequisites/schema.sql': 'CREATE SCHEMA secure_byo;\n',
                'docs/guide.html': '<!doctype html><title>Offline delivery guide</title>\n',
                'docs/guide.pdf': '%PDF-1.4\n',
                '.gitignore': '__pycache__/\n', 'private-token.json': '{"private":true}',
                'actor-probe': 'binary input', 'settings.json': '{}',
                '__pycache__/stale.pyc': 'cache'}.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body)
        return root

    def test_complete_reproducible_archive_and_extracted_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            root = self.fixture(directory)
            first, second = directory / 'first.zip', directory / 'second.zip'
            with contextlib.redirect_stdout(io.StringIO()):
                package.create(root, first)
                package.create(root, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertTrue(verify.from_archive(first)['manifestVerified'])
            unpacked = directory / 'unpacked'
            with zipfile.ZipFile(first) as archive:
                names = {name.removeprefix(package.ROOT_NAME + '/') for name in archive.namelist()}
                for expected in ('diagnostics/main.go', 'diagnostics/go.mod', 'diagnostics/go.sum',
                        'diagnostics/build.sh', 'prerequisites/schema.sql', '.gitignore',
                        'docs/guide.html', 'docs/guide.pdf'):
                    self.assertIn(expected, names)
                self.assertEqual(archive.getinfo(package.ROOT_NAME + '/diagnostics/build.sh').external_attr >> 16, 0o100755)
                for private in ('private-token.json', 'actor-probe', 'settings.json', '__pycache__/stale.pyc'):
                    self.assertNotIn(private, names)
                archive.extractall(unpacked)
            extracted = unpacked / package.ROOT_NAME
            self.assertTrue(verify.from_directory(extracted)['manifestVerified'])
            (extracted / 'unexpected-binary').write_bytes(b'not in the manifest')
            with self.assertRaisesRegex(ValueError, 'inventory'):
                verify.from_directory(extracted)

    def test_archive_rejects_traversal_and_unlisted_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            root = self.fixture(directory)
            for addition in ('../escape', package.ROOT_NAME + '/unexpected.bin'):
                archive_path = directory / ('path.zip' if addition.startswith('..') else 'extra.zip')
                with contextlib.redirect_stdout(io.StringIO()):
                    package.create(root, archive_path)
                with zipfile.ZipFile(archive_path, 'a') as archive:
                    archive.writestr(addition, b'unexpected')
                with self.assertRaises(ValueError):
                    verify.from_archive(archive_path)

    def test_extracted_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'linked-file').symlink_to(ROOT / 'README.md')
            with self.assertRaisesRegex(ValueError, 'links'):
                verify.from_directory(root)

    def test_changed_bytes_fail_integrity(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            archive_path = directory / 'source.zip'
            with contextlib.redirect_stdout(io.StringIO()):
                package.create(self.fixture(directory), archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(directory / 'unpacked')
            extracted = directory / 'unpacked' / package.ROOT_NAME
            (extracted / 'diagnostics/main.go').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                verify.from_directory(extracted)
