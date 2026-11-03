#!/usr/bin/env python3
"""Build the single standalone image from the preloaded approved Python base: no network, no pulls, no installs."""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_DIGEST = 'sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c'
APPROVED_BASE_DIGESTS = (BASE_DIGEST, 'sha256:2986c55feb36e6cae00fa1fefb454283e4b33f35e75ff8bdd123b134130be301')
TAG = re.compile(r'[a-z0-9][a-z0-9._/-]{0,200}(:[A-Za-z0-9._-]{1,128})?')


def command(engine, base, image, stage):
    return [engine, 'build', '--network=none', '--pull=false', '--build-arg', 'PYTHON_BASE=' + base,
            '-f', str(stage / 'build' / 'Dockerfile'), '-t', image, str(stage)]


def stage_into(stage):
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '*.patch')
    shutil.copytree(ROOT / 'app', stage / 'app', ignore=ignore)
    shutil.copytree(ROOT / 'content', stage / 'content', ignore=ignore)
    (stage / 'build').mkdir()
    shutil.copyfile(ROOT / 'build' / 'Dockerfile', stage / 'build' / 'Dockerfile')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, help='preloaded approved base, e.g. <registry>/python@' + BASE_DIGEST)
    parser.add_argument('--image', required=True, help='local tag to build; publish and record its digest afterwards')
    parser.add_argument('--engine', default='docker', choices=('docker', 'podman'))
    parser.add_argument('--dry-run', action='store_true', help='print the staged build command without running it')
    args = parser.parse_args(argv)
    if not any(args.base.endswith('@' + digest) for digest in APPROVED_BASE_DIGESTS) or re.search(r'\s', args.base):
        print('Rejected: base must use an approved source index or linux/amd64 manifest digest: ' + ', '.join(APPROVED_BASE_DIGESTS), file=sys.stderr)
        return 1
    if not TAG.fullmatch(args.image):
        print('Rejected: invalid local image tag', file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix='secure-kro-standalone-build-') as directory:
        stage = Path(directory)
        stage_into(stage)
        argv = command(args.engine, args.base, args.image, stage)
        if args.dry_run:
            print(' '.join(argv))
            return 0
        subprocess.run([args.engine, 'image', 'inspect', args.base], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(argv, check=True)
    print('Built ' + args.image + '. Publish to the approved registry and set settings.image to repository@sha256:<digest>.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
