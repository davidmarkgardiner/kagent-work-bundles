import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_content', ROOT / 'scripts/build_content.py')
content = importlib.util.module_from_spec(spec)
spec.loader.exec_module(content)


class Content(unittest.TestCase):
    def test_exact_native_digests_and_repeatable_layout_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            for name in ('first', 'second'):
                result = content.build(ROOT / 'content', base / name)
                self.assertEqual({k: v['manifestDigest'] for k, v in result.items()}, content.EXPECTED)
            def files(root):
                return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(files(base / 'first'), files(base / 'second'))
            for package, digest in content.EXPECTED.items():
                path = base / 'first' / package
                manifest = (path / 'blobs/sha256' / digest.split(':')[1]).read_bytes()
                self.assertEqual(content.digest(manifest), digest)
                self.assertEqual(json.loads((path / 'index.json').read_text())['manifests'][0]['digest'], digest)

    def test_changed_or_added_source_is_rejected_before_writing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / 'source'
            shutil.copytree(ROOT / 'content', source)
            skill = source / 'aks-known-issues/SKILL.md'
            original = skill.read_bytes()
            skill.write_bytes(original + b'changed')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                content.build(source, base / 'changed')
            self.assertFalse((base / 'changed').exists())
            skill.write_bytes(original)
            (source / 'aks-known-issues/extra.md').write_text('unreviewed')
            with self.assertRaisesRegex(ValueError, 'inventory'):
                content.build(source, base / 'extra')
            self.assertFalse((base / 'extra').exists())

    def test_links_and_manifest_mutation_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / 'source'
            shutil.copytree(ROOT / 'content', source)
            document = source / 'kb-aks-bootstrap/references/oras-pull-unauthorized.md'
            raw = document.read_bytes()
            document.unlink()
            outside = base / 'outside.md'
            outside.write_bytes(raw)
            document.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'links'):
                content.build(source, base / 'linked')
            document.unlink()
            document.write_bytes(raw)
            recipe = json.loads((source / 'recipe.json').read_text())
            recipe['packages']['aks-known-issues']['manifest']['annotations']['new'] = 'mutation'
            (source / 'recipe.json').write_text(json.dumps(recipe))
            with self.assertRaisesRegex(ValueError, 'Manifest identity'):
                content.build(source, base / 'manifest')


if __name__ == '__main__':
    unittest.main()
