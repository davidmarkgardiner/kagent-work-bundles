#!/usr/bin/env python3
"""Read-only inventory of one explicit lab context; output remains private."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--context', required=True)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    if not args.context.strip() or '{{' in args.context:
        p.error('replace the explicit context placeholder')
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    checks = [
        ('version', ['kubectl', '--context', args.context, '--request-timeout=8s', 'get', '--raw=/version']),
        ('certificate-api', ['kubectl', '--context', args.context, '--request-timeout=8s', 'get', '--raw=/apis/certificates.k8s.io/v1']),
        ('kagent-api', ['kubectl', '--context', args.context, '--request-timeout=8s', 'get', '--raw=/apis/api.kagent.dev/v1alpha3']),
        ('helm-releases', ['helm', 'list', '--all-namespaces', '--kube-context', args.context, '--output', 'json']),
    ]
    records = []
    for name, cmd in checks:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            record = {'check': name, 'argv': cmd, 'exit_code': r.returncode,
                      'stdout': r.stdout, 'stderr': r.stderr,
                      'status': 'PASS' if r.returncode == 0 else 'BLOCKED'}
        except subprocess.TimeoutExpired:
            record = {'check': name, 'argv': cmd, 'status': 'BLOCKED', 'reason': '20-second process timeout'}
        records.append(record)
        if name == 'version' and record['status'] != 'PASS':
            break
    ok = len(records) == len(checks) and all(x['status'] == 'PASS' for x in records)
    prereqs = []
    if ok:
        version = json.loads(records[0]['stdout'])
        minor = int(''.join(x for x in version['minor'] if x.isdigit()))
        resources = {x['name'] for x in json.loads(records[1]['stdout'])['resources']}
        prereqs = [int(version['major']) == 1 and minor >= 37,
                   {'podcertificaterequests', 'clustertrustbundles'} <= resources]
        ok = all(prereqs)
    receipt = {'collected_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'context': args.context, 'mutation': False, 'checks': records,
               'kubernetes_certificate_prerequisites': prereqs,
               'status': 'DISCOVERY_PASS' if ok else 'BLOCKED',
               'limits': 'Discovery only; no security, runtime or deployment acceptance.'}
    target = args.output / 'preflight.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    target.chmod(0o600)
    print(receipt['status'])
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
