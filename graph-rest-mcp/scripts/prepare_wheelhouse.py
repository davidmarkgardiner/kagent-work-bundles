#!/usr/bin/env python3
"""Download hash-checked Linux CPython 3.12 wheels on a connected machine."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=['amd64', 'arm64'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        parser.error('use Python 3.12 so dependency markers match the runtime')
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('output must be empty; preserve previous attempts separately')
    output.mkdir(parents=True, exist_ok=True)
    lock = Path(__file__).resolve().parents[1] / 'requirements.lock'
    arch = {'amd64': 'x86_64', 'arm64': 'aarch64'}[args.arch]
    command = [sys.executable, '-m', 'pip', 'download', '--only-binary=:all:', '--require-hashes', '--python-version', '312', '--implementation', 'cp', '--abi', 'cp312']
    for tag in ('manylinux2014', 'manylinux_2_17', 'manylinux_2_28'):
        command.extend(['--platform', f'{tag}_{arch}'])
    subprocess.run([*command, '-r', str(lock), '--dest', str(output)], check=True)
    wheels = sorted(output.glob('*.whl'))
    if not wheels:
        raise SystemExit('no wheels downloaded')
    manifest = {'architecture': args.arch, 'python': '3.12', 'requirements_sha256': hashlib.sha256(lock.read_bytes()).hexdigest(), 'wheels': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in wheels}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Prepared {len(wheels)} wheels for linux/{args.arch}')


if __name__ == '__main__':
    main()
