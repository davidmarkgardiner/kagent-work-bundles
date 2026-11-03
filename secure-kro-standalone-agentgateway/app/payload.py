"""Bounded, deterministic Python and content payload for immutable ConfigMap projection."""
import base64
import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import NamedTuple

MAX_FILES = 128
MAX_FILE_BYTES = 131072
MAX_TOTAL_BYTES = 393216
MAX_OBJECT_BYTES = 786432
HASH_FIELDS = ('payloadSha256', 'runtimeSha256', 'workerSha256')
COMMAND = ('/usr/local/bin/python3', '-B', '-E', '-s', '/agent/main.py')
CODE_MOUNT = {'name': 'code', 'mountPath': '/agent', 'readOnly': True}
PATH = re.compile(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,63}(?:/[A-Za-z0-9_-][A-Za-z0-9_.-]{0,63})*')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_path(path):
    return (isinstance(path, str) and len(path) <= 192 and PATH.fullmatch(path) is not None
            and str(PurePosixPath(path)) == path and all(p not in ('.', '..') for p in path.split('/')))


class Payload(NamedTuple):
    files: tuple
    encoded_files: tuple
    projections: tuple
    sha256: str

    @classmethod
    def from_files(cls, files):
        entries = list(files.items()) if isinstance(files, dict) else list(files)
        if not 1 <= len(entries) <= MAX_FILES:
            raise ValueError('PayloadFileCount')
        seen, total = set(), 0
        for path, raw in entries:
            if not safe_path(path) or path.casefold() in seen:
                raise ValueError('UnsafePayloadPath')
            seen.add(path.casefold())
            if not isinstance(raw, bytes) or len(raw) > MAX_FILE_BYTES:
                raise ValueError('PayloadFileTooLarge')
            total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise ValueError('PayloadTooLarge')
        if any(str(p).casefold() in seen for name, _ in entries for p in PurePosixPath(name).parents if str(p) != '.'):
            raise ValueError('PayloadPathCollision')
        entries = tuple(sorted(entries))
        manifest = [[path, len(raw), digest(raw)] for path, raw in entries]
        # Encode and assign projection keys once; all ConfigMaps and admission reuse this payload.
        encoded_files = tuple(('f%04d' % i, base64.b64encode(raw).decode('ascii')) for i, (_, raw) in enumerate(entries))
        projections = tuple(('f%04d' % i, path) for i, (path, _) in enumerate(entries))
        out = cls(entries, encoded_files, projections,
                  digest(json.dumps(manifest, separators=(',', ':'), ensure_ascii=True).encode()))
        if len(json.dumps({'binaryData': out.binary_data, 'items': out.items}).encode()) > MAX_OBJECT_BYTES:
            raise ValueError('PayloadObjectTooLarge')
        return out

    @property
    def manifest(self):
        return [[path, len(raw), digest(raw)] for path, raw in self.files]

    @property
    def binary_data(self):
        return dict(self.encoded_files)

    @property
    def items(self):
        return [{'key': key, 'path': path} for key, path in self.projections]

    @property
    def hashes(self):
        files = dict(self.files)
        return {'payloadSha256': self.sha256, 'runtimeSha256': digest(files['agent.py']),
                'workerSha256': digest(files['vendor/worker_base.py'])}

    def volume(self, name):
        return {'name': 'code', 'configMap': {'name': name, 'defaultMode': 0o444, 'items': self.items}}

    def config_map(self, metadata):
        return {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': metadata, 'immutable': True,
                'binaryData': self.binary_data}

    def from_config_map(self, cm):
        """Decode with the independently mounted projection, rejecting alternate keys and encodings."""
        if cm.get('immutable') is not True or 'data' in cm or not isinstance(cm.get('binaryData'), dict):
            raise ValueError('RuntimeCodeShape')
        data = cm['binaryData']
        if set(data) != set(self.binary_data):
            raise ValueError('RuntimeCodeKeyset')
        try:
            files = [(item['path'], base64.b64decode(data[item['key']], validate=True)) for item in self.items]
        except (ValueError, TypeError):
            raise ValueError('RuntimeCodeEncoding') from None
        out = Payload.from_files(files)
        if out.binary_data != data:
            raise ValueError('RuntimeCodeEncoding')
        return out


def _files(root, prefix='', budget=None):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('UnsafePayloadRoot')
    budget = [0, 0, 0] if budget is None else budget
    entries = []
    for entry in root.iterdir():
        budget[0] += 1
        if budget[0] > MAX_FILES * 4:
            raise ValueError('UnsafePayloadPath')
        entries.append(entry)
    for entry in sorted(entries):
        mode = entry.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError('UnsafePayloadPath')
        if stat.S_ISDIR(mode):
            yield from _files(entry, prefix + entry.name + '/', budget)
        elif stat.S_ISREG(mode):
            if not safe_path(prefix + entry.name):
                raise ValueError('UnsafePayloadPath')
            descriptor = os.open(entry, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(descriptor, 'rb') as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise ValueError('UnsafePayloadPath')
                raw = handle.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                raise ValueError('PayloadFileTooLarge')
            budget[1] += len(raw)
            budget[2] += 1
            if budget[1] > MAX_TOTAL_BYTES or budget[2] > MAX_FILES:
                raise ValueError('PayloadTooLarge')
            yield entry, raw
        else:
            raise ValueError('UnsafePayloadPath')


def collect(app_root, content_root):
    """Same paths for source app/vendor + content and a resolved mounted /agent tree."""
    app_root, content_root = Path(app_root), Path(content_root)
    files = []
    for path, raw in _files(app_root):
        relative = path.relative_to(app_root)
        if relative.parts[0] == 'content' and content_root == app_root / 'content':
            continue
        if not ((len(relative.parts) == 1 and relative.suffix == '.py') or relative.parts[0] == 'vendor'):
            raise ValueError('UnexpectedPayloadFile')
        files.append((relative.as_posix(), raw))
    files.extend(('content/' + path.relative_to(content_root).as_posix(), raw) for path, raw in _files(content_root))
    return Payload.from_files(files)


def matches(value, expected):
    return (isinstance(value, dict) and isinstance(expected, dict)
            and all(isinstance(expected.get(k), str) and re.fullmatch(r'[0-9a-f]{64}', expected[k])
                    and value.get(k) == expected[k] for k in HASH_FIELDS))
