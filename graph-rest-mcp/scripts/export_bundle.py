#!/usr/bin/env python3
"""Export source and sanitized evidence; omit generated state and binaries."""
import argparse
import hashlib
import pathlib
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=pathlib.Path)
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    if output.is_relative_to(root):
        parser.error('write archive outside the source bundle')
    excluded_dirs = {'__pycache__', '.pytest_cache', '.venv', '.git', 'wheelhouse'}
    excluded_suffixes = {'.pyc', '.duckdb', '.wal', '.zip', '.gz', '.log', '.whl', '.pem', '.key', '.crt', '.p12', '.pfx'}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*')):
            relative = path.relative_to(root)
            if not path.is_file() or path.is_symlink() or excluded_dirs.intersection(relative.parts) or path.suffix in excluded_suffixes:
                continue
            if path.name == '.DS_Store' or path.name.startswith('.env') or '.private.' in path.name or (path.suffix == '.env' and not path.name.endswith('.template')):
                continue
            archive.write(path, pathlib.Path(root.name) / relative)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(digest + '  ' + output.name + '\n')
    print(output)
    print(digest)


if __name__ == '__main__':
    main()
