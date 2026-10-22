"""Exercise the opt-in startup hook in a fresh interpreter."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


class BootstrapTests(unittest.TestCase):
    def run_hook(self, **overrides):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('HOSTED_', 'OTEL_'))}
        env.update(OTEL_TRACING_ENABLED='false', **overrides)
        code = ('import os,runpy,json;runpy.run_path(' + repr(str(Path(__file__).with_name('sitecustomize.py'))) +
                ');print(json.dumps({k:v for k,v in os.environ.items() if k.startswith("OTEL_")}))')
        return subprocess.run([sys.executable, '-S', '-c', code], env=env, capture_output=True, text=True)

    def test_no_opt_in_preserves_controller_setting(self):
        result = self.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {'OTEL_TRACING_ENABLED': 'false'})

    def test_opt_in_overrides_duplicate_global_setting_before_runtime_import(self):
        result = self.run_hook(HOSTED_TRACE_PROFILE='ordinary-v1', HOSTED_OTLP_ENDPOINT='http://collector.demo.svc:4317')
        self.assertEqual(result.returncode, 0)
        values = json.loads(result.stdout)
        self.assertEqual(values['OTEL_TRACING_ENABLED'], 'true')
        self.assertEqual(values['OTEL_EXPORTER_OTLP_ENDPOINT'], 'http://collector.demo.svc:4317')

    def test_invalid_endpoint_stops_runtime_startup(self):
        for endpoint in ('', 'http://user:password@collector:4317', 'http://collector:4317/path', 'file:///tmp/data'):
            with self.subTest(endpoint=endpoint):
                result = self.run_hook(HOSTED_TRACE_PROFILE='ordinary-v1', HOSTED_OTLP_ENDPOINT=endpoint)
                self.assertEqual(result.returncode, 78)
                self.assertEqual(result.stdout, '')
