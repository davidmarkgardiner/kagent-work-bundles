#!/usr/bin/env python3
"""Render an optional dedicated native lab worker and harness."""
import argparse
import pathlib
import re
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker-image', required=True)
    parser.add_argument('--worker-service-account', required=True)
    parser.add_argument('--sandbox-config', required=True)
    parser.add_argument('--snapshot-location', required=True)
    args = parser.parse_args()
    for value in (args.worker_service_account, args.sandbox_config):
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,61}[a-z0-9])?', value):
            parser.error('invalid Kubernetes reference')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/:@-]{0,255}', args.worker_image):
        parser.error('invalid image reference')
    if not re.fullmatch(r's3://[a-z0-9.-]+/[a-zA-Z0-9_./-]*', args.snapshot_location):
        parser.error('invalid snapshot location')
    root = pathlib.Path(__file__).resolve().parent.parent
    text = (root / 'deploy/runtime.yaml.template').read_text()
    values = {'WORKER_IMAGE': args.worker_image, 'WORKER_SERVICE_ACCOUNT': args.worker_service_account, 'SANDBOX_CONFIG': args.sandbox_config, 'SNAPSHOT_LOCATION': args.snapshot_location}
    for key, value in values.items():
        text = text.replace('{{' + key + '}}', value)
    sys.stdout.write(text)


if __name__ == '__main__':
    main()
