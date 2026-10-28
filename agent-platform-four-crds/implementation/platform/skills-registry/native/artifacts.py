"""Reproducible data-only OCI images from reviewed UTF-8 releases."""

from dataclasses import dataclass
import io
import json
from pathlib import Path
import re
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller import MAX_CONTENT, SKILL, content_digest, relative_path, sha256, verify_documents, verify_skill_frontmatter

PACKAGING = 'reviewed-content-ustar-v3'
MANIFEST_TYPE = 'application/vnd.oci.image.manifest.v1+json'


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


@dataclass(frozen=True)
class Package:
    name: str
    files: dict[str, str]
    manifest: bytes
    blobs: dict[str, bytes]

    @property
    def digest(self):
        return 'sha256:' + sha256(self.manifest)

    def layout(self, target):
        target = Path(target)
        directory = target / 'blobs' / 'sha256'
        directory.mkdir(parents=True, exist_ok=False)
        for digest, body in {**self.blobs, self.digest: self.manifest}.items():
            (directory / digest.split(':')[1]).write_bytes(body)
        (target / 'oci-layout').write_bytes(encoded({'imageLayoutVersion': '1.0.0'}))
        (target / 'index.json').write_bytes(encoded({'schemaVersion': 2, 'manifests': [{
            'mediaType': MANIFEST_TYPE, 'digest': self.digest, 'size': len(self.manifest),
            'annotations': {'org.opencontainers.image.ref.name': 'reviewed'}}]}))


def build(kind, spec, texts):
    if (not re.fullmatch('[0-9a-f]{40}', spec['sourceCommit'])
            or content_digest(spec['files']) != spec['contentSha256']
            or set(texts) != set(spec['files']) or not 1 <= len(texts) <= 16
            or sum(len(t.encode()) for t in texts.values()) > MAX_CONTENT
            or any(sha256(texts[p].encode()) != h for p, h in spec['files'].items())):
        raise ValueError('UnverifiedPackage')
    name = spec[kind.name_field]
    if not re.fullmatch(r'[a-z](?:[a-z0-9-]{0,38}[a-z0-9])?', name):
        raise ValueError('InvalidPackageName')
    for path in texts:
        parts = relative_path(path).parts
        if path in ['release-proof.txt', 'references/release-proof.txt'] or any(p.startswith('.wh.') for p in parts):
            raise ValueError('ReservedPackagePath')
        if any(str(parent) in texts for parent in relative_path(path).parents if str(parent) != '.'):
            raise ValueError('PackagePathCollision')
    files = dict(texts)
    if kind == SKILL:
        verify_skill_frontmatter(files['SKILL.md'], name)
    else:
        if 'SKILL.md' in texts:
            raise ValueError('ReservedPackagePath')
        verify_documents(spec, texts)
        files = {'references/' + p: t for p, t in texts.items()}
        name = 'kb-' + name
        catalog = '\n'.join(f"- references/{d['path']} | {d['title']} | {d['sourceURL']} | reviewed {d['reviewedAt']}" for d in spec['documents'])
        files['SKILL.md'] = ('---\nname: ' + name + '\ndescription: Reviewed AKS documentation with source citations for synthetic analysis.\n---\n\n'
            'Read the relevant documents with load_skill_resource before answering. Cite the source URL. '
            'These are documentation and proposed checks, not a performed Azure investigation. '
            'Do not execute operational tools or change infrastructure.\n\n' + catalog + '\n')
    files['references/release-proof.txt'] = 'Reviewed release proof: ' + sha256(encoded({
        'kind': kind.kind, 'sourceCommit': spec['sourceCommit'], 'contentSha256': spec['contentSha256']})) + '\n'
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        paths = {'skill': None}
        for path, text in files.items():
            full = 'skill/' + str(relative_path(path))
            if path in ['release-proof.txt', 'references/release-proof.txt'] and path in texts:
                raise ValueError('ReservedPackagePath')
            for parent in Path(full).parents:
                if str(parent) != '.':
                    paths.setdefault(str(parent), None)
            if full in paths:
                raise ValueError('PackagePathCollision')
            paths[full] = text.encode()
        for path, raw in sorted(paths.items()):
            entry = tarfile.TarInfo(path)
            entry.mode = 0o755 if raw is None else 0o644
            entry.type = tarfile.DIRTYPE if raw is None else tarfile.REGTYPE
            entry.size = 0 if raw is None else len(raw)
            archive.addfile(entry, None if raw is None else io.BytesIO(raw))
    layer = stream.getvalue()
    layer_digest = 'sha256:' + sha256(layer)
    config = encoded({'architecture': 'amd64', 'os': 'linux', 'config': {},
                      'rootfs': {'type': 'layers', 'diff_ids': [layer_digest]}, 'history': []})
    config_digest = 'sha256:' + sha256(config)
    manifest = encoded({'schemaVersion': 2, 'mediaType': MANIFEST_TYPE,
        'config': {'mediaType': 'application/vnd.oci.image.config.v1+json', 'digest': config_digest, 'size': len(config)},
        'layers': [{'mediaType': 'application/vnd.oci.image.layer.v1.tar', 'digest': layer_digest, 'size': len(layer)}],
        'annotations': {'dev.kagent.platform.packaging': PACKAGING, 'dev.kagent.platform.kind': kind.kind,
                        'org.opencontainers.image.revision': spec['sourceCommit'],
                        'dev.kagent.platform.content-sha256': spec['contentSha256'],
                        'dev.kagent.platform.source-path': str(relative_path(spec['path'])),
                        'dev.kagent.platform.package-name': spec[kind.name_field]}})
    return Package(name, files, manifest, {config_digest: config, layer_digest: layer})
