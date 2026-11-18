#!/usr/bin/env python3
"""Validate maintained sources and build the portable documentation site."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
for command in [
    [sys.executable, 'scripts/render_delivery.py', '--check'],
    [sys.executable, 'scripts/sync_assets.py', '--check'],
    [sys.executable, '-m', 'mkdocs', 'build', '--strict'],
]:
    subprocess.run(command, cwd=root, check=True)
