#!/usr/bin/env python3
"""Package reviewed source with deterministic bytes and an embedded inventory."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT_NAME = 'secure-byo-agent-composition'
EXTENSIONS = {'.py', '.md', '.json', '.yaml', '.yml', '.lock', '.tsv', '.sh', '.txt',
    '.go', '.mod', '.sum', '.sql', '.html', '.pdf'}
OMIT_PARTS = {'__pycache__', '.git', '.rendered', 'private', 'evidence-private', 'node_modules', '.venv'}
OMIT_NAMES = {'bundle.manifest.json', 'settings.json', 'profile.json', 'kubeconfig', 'kagent'}


def source_files(root):
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(part in OMIT_PARTS or part.startswith('.') and relative.as_posix() != '.gitignore'
                for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError('Source symlink is forbidden: ' + str(relative))
        if not path.is_file() or path.name in OMIT_NAMES:
            continue
        if path.name.startswith(('private-', 'settings.', 'profile.', 'native-objects')):
            continue
        if path.suffix not in EXTENSIONS and not path.name.startswith('Dockerfile') and path.name not in ('.gitignore', 'LICENSE'):
            continue
        if path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('Source exceeds file limit: ' + str(relative))
        yield relative.as_posix(), path.read_bytes()


def create(root, output):
    root, output = root.resolve(), output.resolve()
    if output == root or root in output.parents:
        raise ValueError('Write the archive outside the source tree')
    if output.exists():
        raise ValueError('Archive already exists')
    files = dict(source_files(root))
    manifest = {'format': 'secure-byo-source-v1', 'root': ROOT_NAME, 'files': {
        name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        for name, data in files.items()}}
    files['bundle.manifest.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(ROOT_NAME + '/' + name, (1980, 1, 1, 0, 0, 0))
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    print(json.dumps({'archive': str(output), 'files': len(manifest['files']),
        'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        create(args.root, args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
