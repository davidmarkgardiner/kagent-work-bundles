"""Simulate unavailable admission on one labeled dry-run object without stopping shared Kyverno."""
import argparse
import copy
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--kubeconfig', required=True)
p.add_argument('--context', required=True)
p.add_argument('--namespace', required=True, choices=['secure-byo-hosted', 'secure-byo-kro'])
p.add_argument('--output', required=True)
a = p.parse_args()
out = Path(a.output)
out.mkdir(parents=True, mode=0o700, exist_ok=False)
k = ['kubectl', '--kubeconfig', a.kubeconfig, '--context', a.context]


def run(args, value=None):
    return subprocess.run(k + args, input=None if value is None else json.dumps(value),
                          text=True, capture_output=True, timeout=30)


configs = run(['get', 'validatingwebhookconfigurations', '-o', 'json'])
configs.check_returncode()
source = next(w for cfg in json.loads(configs.stdout)['items'] if 'kyverno' in cfg['metadata']['name']
              for w in cfg['webhooks'] if w.get('failurePolicy') == 'Fail'
              and '/validate/' in w['clientConfig'].get('service', {}).get('path', ''))
name = 'secure-byo-outage-harness'
if run(['get', 'validatingwebhookconfiguration', name]).returncode == 0:
    raise ValueError('Refusing to replace an existing outage harness')
webhook = copy.deepcopy(source)
webhook.update(name='unavailable.secure-byo.test', failurePolicy='Fail', timeoutSeconds=1,
    sideEffects='None', admissionReviewVersions=['v1'],
    namespaceSelector={'matchLabels': {'kubernetes.io/metadata.name': a.namespace}},
    objectSelector={'matchLabels': {'secure-byo-outage-test': 'true'}},
    rules=[{'apiGroups': [''], 'apiVersions': ['v1'], 'operations': ['CREATE'],
            'resources': ['configmaps'], 'scope': 'Namespaced'}])
webhook.pop('matchConditions', None)
webhook['clientConfig']['service']['name'] = 'secure-byo-intentionally-unavailable'
manifest = {'apiVersion': 'admissionregistration.k8s.io/v1', 'kind': 'ValidatingWebhookConfiguration',
    'metadata': {'name': name}, 'webhooks': [webhook]}
specimen = {'apiVersion': 'v1', 'kind': 'ConfigMap',
    'metadata': {'name': 'secure-byo-outage-dry-run', 'namespace': a.namespace,
                 'labels': {'secure-byo-outage-test': 'true'}}, 'data': {'test': 'synthetic'}}
before = run(['create', '--dry-run=server', '-f', '-'], specimen)
before.check_returncode()
try:
    run(['create', '-f', '-'], manifest).check_returncode()
    denied = run(['create', '--dry-run=server', '-f', '-'], specimen)
    unaffected = copy.deepcopy(specimen)
    unaffected['metadata']['labels'] = {}
    control = run(['create', '--dry-run=server', '-f', '-'], unaffected)
finally:
    run(['delete', 'validatingwebhookconfiguration', name, '--wait=true']).check_returncode()
after = run(['create', '--dry-run=server', '-f', '-'], specimen)
checks = [
    {'name': 'unavailable-matching-webhook-fails-closed', 'passed': denied.returncode != 0
        and 'unavailable.secure-byo.test' in denied.stderr and 'not found' in denied.stderr},
    {'name': 'unmatched-control-still-admitted', 'passed': control.returncode == 0},
    {'name': 'admission-recovers-after-harness-removal', 'passed': after.returncode == 0},
]
receipt = {'namespace': a.namespace, 'checks': checks, 'passed': all(c['passed'] for c in checks),
    'scope': 'Scoped clone of a live fail-closed Kyverno validating webhook with an unavailable Service. Shared Kyverno was not stopped.',
    'denial': denied.stderr}
(out / 'summary.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt))
raise SystemExit(0 if receipt['passed'] else 1)
