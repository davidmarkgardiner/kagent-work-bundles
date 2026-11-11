#!/usr/bin/env python3
"""Offline checks only: vendor integrity, meaningful behaviors and render contract."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def main():
    expected = json.loads((ROOT / 'vendor-lock.json').read_text())
    actual = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (ROOT / 'vendor').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if actual != expected:
        raise SystemExit('Vendor integrity mismatch; restore reviewed copies, do not rewrite the lock to bypass review')
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                   cwd=ROOT, env=env, check=True)
    with tempfile.TemporaryDirectory(prefix='skill-eval-render-') as directory:
        subprocess.run([sys.executable, str(ROOT / 'render.py'), '--config', str(ROOT / 'config.example.yaml'),
                        '--output', directory], cwd=ROOT, env=env, check=True)
        import yaml
        crd = yaml.safe_load((Path(directory) / 'crd.yaml').read_text())
        assert crd['spec']['versions'][0]['subresources'] == {'status': {}}
        docs = list(yaml.safe_load_all((Path(directory) / 'install.yaml').read_text()))
        assert len([d for d in docs if d['kind'] == 'Deployment']) == 1
    subprocess.run(['bash', str(ROOT / 'vendor/scripts/public-safe-scan.sh'), str(ROOT),
                    '--allowlist', str(ROOT / 'scan-allowlist.txt')], cwd=ROOT, check=True)
    print('OFFLINE_VERIFIED: vendor integrity, behavioral tests, renderer, public scan. No cluster or provider contacted.')


if __name__ == '__main__':
    main()
