#!/usr/bin/env python3
"""Verify source hashes, archive paths, Python syntax and local document links."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

ROOT_NAME = 'secure-byo-agent-composition'
LIMIT = 64 * 1024 * 1024


def safe_name(name):
    path = PurePosixPath(name)
    return bool(name and not path.is_absolute() and '\\' not in name
        and all(part not in ('', '.', '..') for part in name.split('/')))


def inspect_files(files, require_manifest):
    manifest_bytes = files.pop('bundle.manifest.json', None)
    if require_manifest and manifest_bytes is None:
        raise ValueError('Missing bundle.manifest.json')
    if manifest_bytes:
        manifest = json.loads(manifest_bytes)
        if manifest.get('format') != 'secure-byo-source-v1' or manifest.get('root') != ROOT_NAME:
            raise ValueError('Unsupported manifest')
        if set(manifest['files']) != set(files):
            raise ValueError('Manifest inventory does not match the source files')
        for name, expected in manifest['files'].items():
            if not safe_name(name) or expected != {'sha256': hashlib.sha256(files[name]).hexdigest(), 'bytes': len(files[name])}:
                raise ValueError('Hash, size or path mismatch: ' + name)
    for name, data in files.items():
        if name.endswith('.py'):
            compile(data, name, 'exec')
        if name.endswith('.md'):
            for link in re.findall(r'\]\(([^)]+)\)', data.decode()):
                if link.startswith(('https:', 'http:', '#', 'mailto:')):
                    continue
                target = link.split('#')[0]
                if not target:
                    continue
                parts = []
                for part in (PurePosixPath(name).parent / target).parts:
                    if part == '..':
                        if not parts:
                            raise ValueError('Document link leaves the bundle: ' + name)
                        parts.pop()
                    elif part != '.':
                        parts.append(part)
                resolved = '/'.join(parts).rstrip('/')
                if resolved not in files and not any(f.startswith(resolved + '/') for f in files):
                    raise ValueError('Broken local link in ' + name + ': ' + link)
    return {'files': len(files), 'manifestVerified': manifest_bytes is not None,
        'pythonSyntax': 'PASS', 'localLinks': 'PASS'}


def from_archive(path):
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if sum(item.file_size for item in entries) > LIMIT:
            raise ValueError('Archive exceeds the uncompressed limit')
        files = {}
        for item in entries:
            if not safe_name(item.filename) or not item.filename.startswith(ROOT_NAME + '/'):
                raise ValueError('Unsafe archive path')
            if stat.S_ISLNK(item.external_attr >> 16) or item.is_dir():
                raise ValueError('Archive links and directory entries are forbidden')
            name = item.filename[len(ROOT_NAME) + 1:]
            if name in files:
                raise ValueError('Duplicate archive path')
            files[name] = archive.read(item)
    return inspect_files(files, True)


def from_directory(root, source=False):
    if source:
        import importlib.util
        spec = importlib.util.spec_from_file_location('bundle_package', Path(__file__).with_name('package.py'))
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        return inspect_files(dict(package.source_files(root)), False)
    files = {}
    total = 0
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Extracted source links are forbidden')
        if not path.is_file():
            continue
        total += path.stat().st_size
        if total > LIMIT:
            raise ValueError('Extracted source exceeds the size limit')
        files[path.relative_to(root).as_posix()] = path.read_bytes()
    return inspect_files(files, True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source', action='store_true', help='Check unpackaged source without a hash manifest')
    args = parser.parse_args()
    try:
        if args.archive:
            result = from_archive(args.archive)
        else:
            result = from_directory(args.root, args.source)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError, KeyError, SyntaxError, zipfile.BadZipFile) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
