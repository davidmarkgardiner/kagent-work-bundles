#!/usr/bin/env python3
"""Render only the lab image and existing native Kagent references."""
import argparse
import pathlib
import re
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True)
    parser.add_argument('--model-config', required=True)
    parser.add_argument('--harness', required=True)
    parser.add_argument('--part', choices=['lab', 'kagent', 'all'], default='all')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/:@-]{0,255}', args.image):
        parser.error('invalid image reference')
    for name in (args.model_config, args.harness):
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,61}[a-z0-9])?', name):
            parser.error('invalid Kubernetes reference name')
    root = pathlib.Path(__file__).resolve().parent.parent
    parts = ['lab', 'kagent'] if args.part == 'all' else [args.part]
    content = '\n---\n'.join((root / 'deploy' / f'{part}.yaml.template').read_text() for part in parts)
    for key, value in {'IMAGE': args.image, 'MODEL_CONFIG': args.model_config, 'HARNESS': args.harness}.items():
        content = content.replace('{{' + key + '}}', value)
    if '{{' in content:
        parser.error('unresolved placeholder')
    sys.stdout.write(content)


if __name__ == '__main__':
    main()
