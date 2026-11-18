#!/usr/bin/env python3
"""Build the exact staged documentation snapshot without changing the index."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
repo = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, text=True).strip())
prefix = ROOT.relative_to(repo).as_posix()
prefix = '' if prefix == '.' else prefix + '/'
files = subprocess.check_output(['git', 'ls-files', '-z', '--', prefix or '.'], cwd=repo).decode().split('\0')
with tempfile.TemporaryDirectory(prefix='staged-platform-docs-') as directory:
    target = Path(directory)
    for name in files:
        if not name:
            continue
        relative = name[len(prefix):]
        path = target / relative
        content = subprocess.check_output(['git', 'show', ':' + name], cwd=repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    subprocess.run([sys.executable, 'scripts/build_docs.py'], cwd=target, check=True)
print('STAGED_DOCUMENTATION: PASS')
