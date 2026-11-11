#!/usr/bin/env python3
"""Trusted read-only executor; stdout is one bounded evidence JSON envelope."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from contract import (ROOT, MAX_CAPTURE, Rejected, code_digest, digest, pin_scenario,
                      pod_pin, profile, request_spec, unchanged)
from run import Cluster


class PinnedCluster(Cluster):
    def __init__(self, config):
        super().__init__('in-cluster', config['targetNamespace'])
        self.config = config

    def json(self, arguments):
        if arguments and arguments[0] == 'exec':
            # Check again immediately before executing; Kubernetes exec has no UID
            # precondition, so RBAC name pinning still needs a trusted stable lab Pod.
            pod = self.get('pod', self.config['targetPodName'])
            pod_pin(pod, self.config)
            if arguments[3] != self.config['targetPodName']:
                raise Rejected('ExecPodNameMismatch')
        return super().json(arguments)

    def snapshot(self, document):
        pod = self.get('pod', self.config['targetPodName'])
        pod_pin(pod, self.config)
        selected = self.json(['get', 'pods', '-n', self.namespace, '-l',
                              'kagent=' + document['spec']['agentRef']['name'], '-o', 'json'])['items']
        selected = [p for p in selected if not p['metadata'].get('deletionTimestamp')]
        if len(selected) != 1:
            raise Rejected('AmbiguousAgentPod')
        pod_pin(selected[0], self.config)
        snap = super().snapshot(document)
        if snap.identity['podUID'] != self.config['targetPodUID']:
            raise Rejected('AgentPodPinMismatch')
        skill = self.get('skills.skills.platform.kagent.dev', document['spec']['skillRef']['name'])
        source = self.get('gitrepositories.source.toolkit.fluxcd.io', skill['spec']['sourceRef']['name'])
        snap.identity.update(podName=self.config['targetPodName'], sourceCommit=skill['spec']['sourceCommit'],
                             skillSpecSha256=digest(skill['spec']), sourceUID=source['metadata']['uid'],
                             sourceGeneration=source['metadata']['generation'])
        return snap


def kubeconfig(work):
    import yaml
    sa = Path('/var/run/secrets/kubernetes.io/serviceaccount')
    config = {'apiVersion': 'v1', 'kind': 'Config', 'current-context': 'in-cluster',
              'clusters': [{'name': 'local', 'cluster': {'server': 'https://' + os.environ['KUBERNETES_SERVICE_HOST']
                  + ':' + os.environ['KUBERNETES_SERVICE_PORT'], 'certificate-authority': str(sa / 'ca.crt')}}],
              'users': [{'name': 'local', 'user': {'tokenFile': str(sa / 'token')}}],
              'contexts': [{'name': 'in-cluster', 'context': {'cluster': 'local', 'user': 'local',
                  'namespace': (sa / 'namespace').read_text().strip()}}]}
    path = work / 'kubeconfig'
    path.write_text(yaml.safe_dump(config))
    path.chmod(0o600)
    os.environ['KUBECONFIG'] = str(path)


def capture(request, config, cluster, work):
    ref = request_spec(request['spec'])
    document = cluster.get('goldenscenarios.skills.platform.kagent.dev', ref['name'])
    pin_scenario(document, ref, config)
    before = cluster.snapshot(document)
    context = 'se-' + request['metadata']['uid']
    raw = work / 'a2a.json'
    command = ['bash', str(ROOT / 'vendor/scripts/kagent-a2a-invoke.sh'), '--url', config['controllerURL'],
               '--ns', config['targetNamespace'], '--agent', document['spec']['agentRef']['name'],
               '--context-id', context, '--text', document['spec']['prompt'], '--timeout', '120',
               '--receipt-file', str(raw), '--json']
    result = subprocess.run(command, capture_output=True, timeout=155)
    if result.returncode != 0 or not raw.is_file():
        raise Rejected('A2ATransportOrTaskFailure')
    if raw.stat().st_size > MAX_CAPTURE:
        raise Rejected('EvidenceTooLarge')
    current = cluster.get('goldenscenarios.skills.platform.kagent.dev', ref['name'])
    pin_scenario(current, ref, config)
    after = cluster.snapshot(current)
    unchanged(before, after)
    return {'version': 1, 'requestUID': request['metadata']['uid'], 'contextID': context,
            'codeSha256': code_digest(), 'scenario': document,
            'before': {'identity': before.identity, 'content': before.content},
            'after': {'identity': after.identity, 'content': after.content}, 'a2a': json.loads(raw.read_bytes())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', default='/profile/profile.json')
    parser.add_argument('--request', required=True, help='Controller frozen JSON, never a shell expression')
    args = parser.parse_args()
    try:
        config = profile(json.loads(Path(args.profile).read_text()))
        request = json.loads(args.request)
        work = Path('/work')
        work.mkdir(exist_ok=True)
        kubeconfig(work)
        envelope = capture(request, config, PinnedCluster(config), work)
        data = json.dumps(envelope, separators=(',', ':'))
        if len(data.encode()) > MAX_CAPTURE:
            raise Rejected('EvidenceTooLarge')
        print(data, flush=True)
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps({'workerError': str(error) if isinstance(error, Rejected) else type(error).__name__}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
