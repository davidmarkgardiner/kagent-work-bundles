import pathlib
import subprocess
import sys
import tempfile
import unittest
import zipfile


class ExportTests(unittest.TestCase):
    def test_private_inputs_and_generated_state_are_excluded(self):
        script = pathlib.Path(__file__).with_name('export_bundle.py')
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            bundle = root / 'graph-rest-mcp'
            (bundle / 'scripts').mkdir(parents=True)
            (bundle / 'scripts/export_bundle.py').write_text(script.read_text())
            keep = ['README.md', 'requirements.lock', 'deploy/remote.env.template']
            omit = ['.env', 'config.private.json', 'ca.pem', 'client.key', 'wheelhouse/example.whl',
                    '__pycache__/x.pyc', '.venv/config', 'data/graph.duckdb', '.DS_Store']
            for name in keep + omit:
                path = bundle / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('synthetic placeholder')
            (bundle / 'linked-config').symlink_to(bundle / '.env')
            archive = root / 'export.zip'
            subprocess.run([sys.executable, str(bundle / 'scripts/export_bundle.py'), str(archive)], check=True, capture_output=True)
            with zipfile.ZipFile(archive) as result:
                self.assertEqual(set(result.namelist()), {'graph-rest-mcp/' + n for n in keep + ['scripts/export_bundle.py']})


if __name__ == '__main__':
    unittest.main()
