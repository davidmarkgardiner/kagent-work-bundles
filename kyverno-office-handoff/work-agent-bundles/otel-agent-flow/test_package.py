import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


class PackageTests(unittest.TestCase):
    def test_exported_dashboard_imports_in_both_onboarding_modes(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'handoff.zip'
            subprocess.run([sys.executable, '-B', str(root / 'scripts/package.py'),
                            '--output', str(output)], check=True, capture_output=True)
            with zipfile.ZipFile(output) as archive:
                archive.extractall(Path(temporary) / 'extracted')
            exported = Path(temporary) / 'extracted/otel-agent-flow'
            for mode in ('native', 'ordinary'):
                with self.subTest(mode=mode):
                    environment = dict(os.environ, ONBOARDING_RUNTIME=mode,
                                       READ_ONLY_VIEWER='true')
                    environment.pop('PRICING_FILE', None)
                    result = subprocess.run([sys.executable, '-B', '-c', 'import backend'],
                                            cwd=exported, env=environment,
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
