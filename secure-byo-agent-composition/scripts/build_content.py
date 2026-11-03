#!/usr/bin/env python3
"""Rebuild the two pinned, data-only native OCI packages without a registry or Git history."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

EXPECTED = {
    'aks-known-issues': 'sha256:84b5a6a8f85db941e2ec588016e0b48d4906bcf4001f45f6ebcc33a2075a34fc',
    'kb-aks-bootstrap': 'sha256:99872678014bef62bc8709ae30342246f7616d7f20d695b8a16500d3c54c1e2b',
}
ROOT = Path(__file__).resolve().parents[1]


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def safe_path(name):
    if (not isinstance(name, str) or not name or '\\' in name
            or PurePosixPath(name).is_absolute()
            or any(p in ('', '.', '..') or p.startswith('.wh.') for p in name.split('/'))):
        raise ValueError('Unsafe content path')
    return PurePosixPath(name)


def package(content, name, recipe):
    if name not in EXPECTED or recipe['expectedManifestDigest'] != EXPECTED[name]:
        raise ValueError('Unexpected package identity')
    source = content / name
    if source.is_symlink() or not source.is_dir():
        raise ValueError('Unsafe package directory')
    actual = set()
    for path in source.rglob('*'):
        if path.is_symlink():
            raise ValueError('Content links are forbidden')
        if path.is_file():
            actual.add(path.relative_to(source).as_posix())
    if actual != set(recipe['files']) or not 1 <= len(actual) <= 16:
        raise ValueError('Content inventory mismatch')
    paths = {'skill': None}
    total = 0
    for relative, expected in recipe['files'].items():
        safe_path(relative)
        raw = (source / relative).read_bytes()
        raw.decode('utf-8', errors='strict')
        total += len(raw)
        if hashlib.sha256(raw).hexdigest() != expected or total > 128 * 1024:
            raise ValueError('Content checksum or size mismatch')
        full = 'skill/' + relative
        for parent in PurePosixPath(full).parents:
            if str(parent) != '.':
                if str(parent) in paths and paths[str(parent)] is not None:
                    raise ValueError('Content path collision')
                paths.setdefault(str(parent), None)
        if full in paths:
            raise ValueError('Content path collision')
        paths[full] = raw
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for path, raw in sorted(paths.items()):
            entry = tarfile.TarInfo(path)
            entry.mode = 0o755 if raw is None else 0o644
            entry.type = tarfile.DIRTYPE if raw is None else tarfile.REGTYPE
            entry.size = 0 if raw is None else len(raw)
            archive.addfile(entry, None if raw is None else io.BytesIO(raw))
    layer, config, manifest = stream.getvalue(), encoded(recipe['config']), encoded(recipe['manifest'])
    if digest(manifest) != EXPECTED[name]:
        raise ValueError('Manifest identity mismatch')
    parsed = recipe['manifest']
    if (parsed['config']['digest'] != digest(config) or parsed['config']['size'] != len(config)
            or len(parsed['layers']) != 1 or parsed['layers'][0]['digest'] != digest(layer)
            or parsed['layers'][0]['size'] != len(layer)
            or recipe['config']['rootfs']['diff_ids'] != [digest(layer)]):
        raise ValueError('OCI blob mismatch')
    return manifest, {digest(config): config, digest(layer): layer, EXPECTED[name]: manifest}


def build(content, output):
    content, output = content.resolve(), output.resolve()
    if output == ROOT or ROOT in output.parents or output == content or content in output.parents:
        raise ValueError('Output must be outside the source bundle')
    recipe_file = content / 'recipe.json'
    if recipe_file.is_symlink():
        raise ValueError('Recipe links are forbidden')
    recipe = json.loads(recipe_file.read_text())
    if recipe['format'] != 'secure-byo-reviewed-content-v1' or set(recipe['packages']) != set(EXPECTED):
        raise ValueError('Unexpected content recipe')
    packages = {name: package(content, name, recipe['packages'][name]) for name in EXPECTED}
    output.mkdir(parents=True, exist_ok=False)
    for name, (manifest, blobs) in packages.items():
        target = output / name
        directory = target / 'blobs' / 'sha256'
        directory.mkdir(parents=True)
        for key, raw in blobs.items():
            (directory / key.split(':')[1]).write_bytes(raw)
        (target / 'oci-layout').write_bytes(encoded({'imageLayoutVersion': '1.0.0'}))
        (target / 'index.json').write_bytes(encoded({'schemaVersion': 2, 'manifests': [{
            'mediaType': 'application/vnd.oci.image.manifest.v1+json', 'digest': EXPECTED[name],
            'size': len(manifest), 'annotations': {'org.opencontainers.image.ref.name': 'reviewed'}}]}))
    return {name: {'manifestDigest': EXPECTED[name], 'layout': str(output / name)} for name in EXPECTED}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--content', type=Path, default=ROOT / 'content')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    try:
        print(json.dumps(build(a.content, a.output), sort_keys=True))
    except (OSError, ValueError, KeyError) as error:
        p.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
