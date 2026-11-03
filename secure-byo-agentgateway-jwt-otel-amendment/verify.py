"""Verify a copied amendment offline. Never reads cluster credentials or contacts a service."""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
MANIFEST = 'amendment.manifest.json'


def files(root):
    result = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if '__pycache__' in relative.parts or path.name == '.DS_Store':
            continue
        if path.is_symlink():
            raise ValueError('Source links are forbidden: ' + str(relative))
        if not path.is_file() or relative.as_posix() == MANIFEST:
            continue
        if path.suffix not in ('.py', '.md', '.json', '.tsv') and path.name != '.gitignore':
            raise ValueError('Unexpected source file: ' + str(relative))
        result[relative.as_posix()] = path.read_bytes()
    return result


def inventory(source):
    return {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)} for name, raw in source.items()}


def verify(source):
    for name, raw in source.items():
        if name.endswith('.py'):
            ast.parse(raw, filename=name)
        if name.endswith('.json'):
            json.loads(raw)
        if name.endswith('.md'):
            for link in re.findall(r'\]\(([^)]+)\)', raw.decode()):
                if link.startswith(('http:', 'https:', '#', 'mailto:')):
                    continue
                target = link.split('#')[0]
                parts = []
                for part in (PurePosixPath(name).parent / target).parts:
                    if part == '..':
                        if not parts:
                            raise ValueError('Link leaves amendment: ' + name)
                        parts.pop()
                    elif part != '.':
                        parts.append(part)
                resolved = '/'.join(parts)
                if resolved not in source and not any(p.startswith(resolved + '/') for p in source):
                    raise ValueError('Broken local link: ' + name + ' -> ' + link)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='store_true', help='Syntax/links only; no source authenticity claim')
    parser.add_argument('--write-manifest', action='store_true', help='Publisher preparation after review, not a repair for failed transfer integrity')
    parser.add_argument('--tests', action='store_true')
    args = parser.parse_args()
    source = files(ROOT)
    verify(source)
    if args.write_manifest:
        (ROOT / MANIFEST).write_text(json.dumps({'format': 'secure-gateway-amendment-v1', 'files': inventory(source)}, indent=2, sort_keys=True) + '\n')
    if not args.source:
        manifest = json.loads((ROOT / MANIFEST).read_text())
        if manifest.get('format') != 'secure-gateway-amendment-v1' or manifest.get('files') != inventory(source):
            raise ValueError('Amendment inventory changed; compare with the reviewed transfer. Do not regenerate the manifest as a fix.')
    if args.tests:
        subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'), '-p', 'test_*.py'], check=True)
    print(json.dumps({'files': len(source), 'syntaxAndLinks': 'PASS', 'manifestVerified': not args.source, 'clusterContacted': False}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, SyntaxError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
