#!/usr/bin/env python3
"""Exercise actual Kyverno admission in a dedicated kind lab, without GitLab or models."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent
CONTEXT = 'kind-kyverno-agent-poc'
NAMESPACE = 'kyverno-recovery-demo'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kubeconfig', type=Path, required=True)
    parser.add_argument('--context', choices=[CONTEXT], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; preserve the previous receipt')
    kube = ['kubectl', '--kubeconfig', str(args.kubeconfig), '--context', args.context, '--request-timeout=15s']
    proof = {'schemaVersion': 1, 'scope': 'live Kyverno admission and HTTP fixture only',
             'context': args.context, 'namespace': NAMESPACE,
             'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'gitlab': 'NOT RUN', 'gitops': 'NOT RUN', 'classifier': 'NOT RUN',
             'agent': 'NOT RUN', 'otel': 'NOT RUN', 'checks': [], 'status': 'FAIL'}
    owned = False

    def call(*arguments, timeout=30):
        return subprocess.run(kube + list(arguments), text=True, capture_output=True, timeout=timeout)

    def checked(*arguments, timeout=30):
        result = call(*arguments, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr.strip()[:1500])
        return result.stdout

    def probe(phase, filename, allowed):
        result = call('create', '--dry-run=server', '-f', str(ROOT / 'fixtures' / filename))
        output = (result.stdout + result.stderr).strip()
        matches = result.returncode == 0 if allowed else result.returncode != 0 and 'approved-registry' in output and 'denied' in output.lower()
        proof['checks'].append({'phase': phase, 'fixture': filename, 'expected': 'allow' if allowed else 'policy-deny',
                                'passed': matches, 'observedAt': time.time(), 'returncode': result.returncode,
                                'output': output[:2000]})
        if not matches:
            raise RuntimeError(f'{phase}: unexpected admission result for {filename}')

    def phase(name, filename, allow_valid):
        path = ROOT / 'fixtures' / filename
        checked('apply', '-f', str(path))
        checked('-n', NAMESPACE, 'wait', '--for=condition=Ready', 'policy/approved-registry', '--timeout=45s', timeout=60)
        policy = json.loads(checked('-n', NAMESPACE, 'get', 'policy', 'approved-registry', '-o', 'json'))
        proof.setdefault('policyRevisions', []).append({'phase': name, 'generation': policy['metadata']['generation'],
                                                       'fixtureSha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        for _ in range(3):
            probe(name, 'valid-pod.yaml', allow_valid)
        probe(name, 'invalid-pod.yaml', False)

    def application(name):
        checked('-n', NAMESPACE, 'rollout', 'status', 'deployment/registry-demo', '--timeout=90s', timeout=105)
        deployment = json.loads(checked('-n', NAMESPACE, 'get', 'deployment', 'registry-demo', '-o', 'json'))
        status = deployment['status']
        passed = (status.get('observedGeneration') == deployment['metadata']['generation']
                  and all(status.get(key) == 1 for key in ('replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas'))
                  and not status.get('unavailableReplicas'))
        proof['checks'].append({'phase': name, 'passed': passed, 'observedAt': time.time(),
                                'generation': deployment['metadata']['generation'], 'deploymentStatus': status})
        if not passed:
            raise RuntimeError('Application rollout is not current and available')
        pods = json.loads(checked('-n', NAMESPACE, 'get', 'pods', '-l', 'app.kubernetes.io/name=registry-demo', '-o', 'json'))['items']
        pods = [p for p in pods if not p['metadata'].get('deletionTimestamp')]
        if len(pods) != 1:
            raise RuntimeError('Expected one current application pod')
        for _ in range(3):
            response = checked('get', '--raw', f'/api/v1/namespaces/{NAMESPACE}/pods/{pods[0]["metadata"]["name"]}:8080/proxy/')
            passed = response.strip() == 'recovered'
            proof['checks'].append({'phase': name + '-http', 'passed': passed, 'observedAt': time.time(),
                                    'responseSha256': hashlib.sha256(response.encode()).hexdigest()})
            if not passed:
                raise RuntimeError('Unexpected application HTTP body')

    try:
        nodes = json.loads(checked('get', 'nodes', '-o', 'json'))['items']
        if len(nodes) != 1 or nodes[0]['metadata']['name'] != 'kyverno-agent-poc-control-plane':
            raise RuntimeError('Unexpected lab node identity')
        proof['kubernetesVersion'] = nodes[0]['status']['nodeInfo']['kubeletVersion']
        existing = checked('get', 'namespace', NAMESPACE, '--ignore-not-found', '-o', 'name')
        if existing.strip():
            raise RuntimeError('Demo namespace already exists; inspect and preserve it before another run')
        checked('create', '-f', str(ROOT / 'fixtures' / 'namespace.yaml'))
        owned = True
        phase('baseline', 'policy-healthy.yaml', True)
        checked('create', '-f', str(ROOT / 'fixtures' / 'application.yaml'))
        application('baseline-application')
        phase('fault', 'policy-faulty.yaml', False)
        checked('-n', NAMESPACE, 'patch', 'deployment', 'registry-demo', '--type=merge',
                '-p', '{"spec":{"template":{"metadata":{"annotations":{"demo.example.invalid/revision":"fault"}}}}}')
        blocked = call('-n', NAMESPACE, 'rollout', 'status', 'deployment/registry-demo', '--timeout=20s', timeout=35)
        deployment = json.loads(checked('-n', NAMESPACE, 'get', 'deployment', 'registry-demo', '-o', 'json'))
        events = json.loads(checked('-n', NAMESPACE, 'get', 'events', '-o', 'json'))['items']
        denial = any(e.get('reason') == 'FailedCreate' and 'approved-registry' in e.get('message', '') for e in events)
        status = deployment['status']
        passed = (blocked.returncode != 0 and status.get('observedGeneration') == deployment['metadata']['generation']
                  and status.get('availableReplicas', 0) == 0 and status.get('updatedReplicas', 0) == 0 and denial)
        proof['checks'].append({'phase': 'fault-blocked-rollout', 'passed': passed, 'observedAt': time.time(),
                                'generation': deployment['metadata']['generation'], 'deploymentStatus': status,
                                'policySpecificFailedCreate': denial})
        if not passed:
            raise RuntimeError('Expected an unavailable rollout with policy-specific FailedCreate evidence')
        phase('recovery', 'policy-healthy.yaml', True)
        application('recovered-application')
        proof['status'] = 'PASS'
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        proof['error'] = str(error)[:2000]
    finally:
        if owned:
            try:
                checked('apply', '-f', str(ROOT / 'fixtures' / 'policy-healthy.yaml'))
                proof['faultCleanup'] = 'healthy policy restored; dedicated namespace retained'
            except (RuntimeError, OSError, subprocess.SubprocessError) as error:
                proof['faultCleanup'] = 'FAILED: ' + str(error)[:1000]
                proof['status'] = 'FAIL'
        proof['finishedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            json.dump(proof, stream, indent=2, allow_nan=False)
            stream.write('\n')
    print(json.dumps({'status': proof['status'], 'checks': len(proof['checks']), 'receipt': str(args.output),
                      'scope': proof['scope'], 'error': proof.get('error')}))
    return 0 if proof['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
