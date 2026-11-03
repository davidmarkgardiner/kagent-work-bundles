#!/usr/bin/env python3
"""Check the downloaded folder against its source inventory; no cluster access."""
import argparse
import ast
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re


class DocumentLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(value for key, value in attrs if key in ('href', 'src') and value)


def source_files(root):
    files = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise ValueError('Source symlink: ' + str(relative))
        if path.is_file() and relative.as_posix() != 'bundle.manifest.json':
            files[relative.as_posix()] = path.read_bytes()
    return files


def verify(root):
    manifest = json.loads((root / 'bundle.manifest.json').read_text())
    if manifest.get('format') != 'secure-kro-standalone-source-v1':
        raise ValueError('Unsupported source manifest')
    files = source_files(root)
    actual = {name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
              for name, data in files.items()}
    if actual != manifest.get('files'):
        raise ValueError('Source inventory, size or SHA256 mismatch')
    for name, data in files.items():
        if name.endswith('.py'):
            ast.parse(data, filename=name)
        if name.endswith('.json'):
            json.loads(data)
        links = []
        if name.endswith('.md'):
            links = re.findall(r'\]\(([^)]+)\)', data.decode())
        elif name.endswith('.html'):
            parser = DocumentLinks()
            parser.feed(data.decode())
            links = parser.links
        if links:
            for link in links:
                if link.startswith(('https:', 'http:', '#', 'mailto:', 'data:')):
                    continue
                target = link.split('#', 1)[0]
                parts = []
                for part in (PurePosixPath(name).parent / target).parts:
                    if part == '..':
                        if not parts:
                            raise ValueError('Link leaves bundle: ' + name)
                        parts.pop()
                    elif part != '.':
                        parts.append(part)
                resolved = '/'.join(parts).rstrip('/')
                if resolved not in files and not any(p.startswith(resolved + '/') for p in files):
                    raise ValueError('Broken local link: ' + name + ': ' + link)
    return {'sourceFiles': len(files), 'sha256Inventory': 'PASS',
            'pythonSyntax': 'PASS', 'jsonSyntax': 'PASS', 'localLinks': 'PASS',
            'liveClusterProof': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root), sort_keys=True))
    except (ValueError, OSError, SyntaxError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
