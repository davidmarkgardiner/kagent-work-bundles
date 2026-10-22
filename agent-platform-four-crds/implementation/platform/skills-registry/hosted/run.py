#!/usr/bin/env python3
"""Run fresh manual acceptance for the GitOps-onboarded documentation agent."""

import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import uuid

from acceptance import PROMPT, check
from contract import API, Rejected, canonical, desired_children, load_profile, parse_intent, selected_profile
from reconcile import Onboarding, ready

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
module_spec = importlib.util.spec_from_file_location('knowledge_transport', HERE.parent / 'knowledge/run.py')
transport = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(transport)


class Reader:
    def __init__(self, cluster):
        self.cluster = cluster
        self.namespace = cluster.ns

    def call(self, path, method='GET', value=None):
        if method != 'GET':
            raise Rejected('AcceptanceReaderCannotWrite')
        return self.cluster.json(['get', '--raw', path])


class Cluster(transport.Cluster):
    def __init__(self, context, release, profile=None):
        super().__init__(context, release)
        self.profile = load_profile() if profile is None else profile

    def snapshot(self):
        release = self.release
        document = self.get('hostedagents.' + API.split('/')[0], release['name'])
        if (not ready(document) or not ready(document, 'Accepted') or document['metadata'].get('deletionTimestamp')
                or canonical(document['spec']) != release['specSha256']):
            raise Rejected('HostedAgentNotCurrentAndPinned')
        profile = self.profile
        intent = parse_intent(document, profile)
        reader = Reader(self)
        onboarding = Onboarding(reader, profile)
        from controller import SKILL, KNOWLEDGE_BASE
        bindings = [onboarding.binding(SKILL, intent.skill), onboarding.binding(KNOWLEDGE_BASE, intent.knowledge)]
        desired = desired_children(document, intent, bindings, profile)
        objects = [self.get(kind, child['metadata']['name']) for kind, child in zip(['serviceaccount', 'networkpolicy', 'agents.kagent.dev'], desired)]
        for expected, actual in zip(desired[1:], objects[1:]):
            if actual['metadata'].get('ownerReferences') != expected['metadata']['ownerReferences'] or actual['metadata'].get('deletionTimestamp'):
                raise Rejected('GeneratedChildOwnershipMismatch')
        account, policy, agent = objects
        onboarding.preflight(desired[0], agent)
        if (account.get('automountServiceAccountToken') is not False or policy['spec'] != desired[1]['spec']
                or agent['spec'] != desired[-1]['spec'] or not ready(agent) or not ready(agent, 'Accepted')
                or document['status'].get('agentSpecSha256') != canonical(agent['spec'])):
            raise Rejected('GeneratedWiringNotCurrent')
        selected = selected_profile(profile, intent.runtime_profile)
        capability_pins = onboarding.verify_mcp(selected)
        model = self.get('modelconfigs.kagent.dev', selected['modelConfig']['name'])
        if model['metadata'].get('deletionTimestamp') or canonical(model['spec']) != selected['modelConfig']['specSha256']:
            raise Rejected('ModelProfileMismatch')
        pods = self.json(['get', 'pods', '-n', self.ns, '-l', 'kagent=' + release['agent'], '-o', 'json'])['items']
        pods = [p for p in pods if not p['metadata'].get('deletionTimestamp')]
        if len(pods) != 1 or len(pods[0]['spec']['containers']) != 1:
            raise Rejected('AmbiguousAgentPod')
        pod = pods[0]
        statuses = pod.get('status', {}).get('containerStatuses', [])
        if (len(statuses) != 1 or not statuses[0].get('ready')
                or pod['spec'].get('serviceAccountName') != account['metadata']['name']
                or pod['spec']['containers'][0].get('securityContext', {}).get('privileged')):
            raise Rejected('AgentPodNotReady')
        if release.get('expectedRuntimeImage') and pod['spec']['containers'][0].get('image') != release['expectedRuntimeImage']:
            raise Rejected('RuntimeImageMismatch')
        for root in ['/skills', '/knowledge']:
            if not any(m.get('mountPath') == root and m.get('readOnly') for m in pod['spec']['containers'][0].get('volumeMounts', [])):
                raise Rejected('ReadOnlyMountMissing')
        script = """import hashlib,json
from pathlib import Path
from kagent.skills import discover_skills
roots={'skill':Path('/skills/aks-known-issues'),'knowledge':Path('/knowledge/aks-bootstrap')}
print(json.dumps({'files':{k:{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()} for k,root in roots.items()},'skills':[s.name for s in discover_skills(Path('/skills'))]}))
"""
        mounted = self.json(['exec', '-n', self.ns, pod['metadata']['name'], '--', 'python', '-c', script])
        expected_files = {'skill': release['skill']['files'], 'knowledge': release['knowledge']['files']}
        if mounted.get('files') != expected_files or mounted.get('skills') != ['aks-known-issues']:
            raise Rejected('MountedContentMismatch')
        contents = {}
        for kind, binding, files in zip(['skill', 'knowledge'], bindings, [release['skill']['files'], release['knowledge']['files']]):
            cm = self.get('configmap', binding['configMapName'])
            contents[kind] = {path: cm['data'][f'file{i:02}'] for i, path in enumerate(sorted(files))}
        runtime = statuses[0]
        summary = [{k: v for k, v in b.items() if k != 'projection'} for b in bindings]
        identity = {'hostedAgentUID': document['metadata']['uid'], 'hostedAgentGeneration': document['metadata']['generation'],
                    'hostedAgentSpecSha256': canonical(document['spec']), 'agentUID': agent['metadata']['uid'],
                    'agentGeneration': agent['metadata']['generation'], 'agentSpecSha256': canonical(agent['spec']),
                    'accountUID': account['metadata']['uid'], 'policyUID': policy['metadata']['uid'], 'policySpecSha256': canonical(policy['spec']),
                    'modelConfigUID': model['metadata']['uid'], 'modelConfigSpecSha256': canonical(model['spec']), 'bindings': summary,
                    'podUID': pod['metadata']['uid'], 'imageID': runtime.get('imageID'), 'containerID': runtime.get('containerID'),
                    'restartCount': runtime['restartCount'], 'mountedFileHashes': mounted['files']}
        if capability_pins:
            identity['mcpDependencyPins'] = capability_pins
            identity['profileSha256'] = canonical(profile)
        return identity, contents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--controller-namespace', default='kagent')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('output directory must be new; previous evidence is never overwritten')
    args.output_dir.mkdir(parents=True)
    release = json.loads((HERE / 'release.json').read_text())
    receipt = {'phase': 'Rejected', 'mode': 'liveHostedAgentAcceptance', 'inputOrigin': 'synthetic',
               'hostedAgent': release['name'], 'agent': release['agent'], 'invocationAttempted': False,
               'liveAzureInvestigation': False, 'sandboxExecuted': False,
               'limits': ['Manual acceptance, separate from reconciliation readiness.',
                          'Answer checks verify required text and citations, not general semantic correctness.',
                          'Tool checks are retrospective and do not enforce runtime permissions.',
                          'Stable Pod identity does not attest which Pod served A2A.',
                          'A pinned ModelConfig spec does not freeze gateway configuration or credentials.',
                          'Documentation-only native profile; arbitrary BYO images and operational grants are unsupported.']}
    try:
        cluster = Cluster(args.context, release)
        before = cluster.snapshot()
        (args.output_dir / 'snapshot-before.json').write_text(json.dumps(before[0], indent=2) + '\n')
        context = 'hosted-' + uuid.uuid4().hex
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
        raw_path = args.output_dir / 'a2a-response.json'
        receipt['invocationAttempted'] = True
        returncode = transport.invoke([str(REPO / 'scripts/kagent-a2a-invoke.sh'), '--context', args.context, '--ns', release['namespace'],
            '--agent', release['agent'], '--controller-ns', args.controller_namespace, '--local-port', str(port), '--context-id', context,
            '--text', PROMPT, '--timeout', '120', '--receipt-file', str(raw_path), '--json'])
        if returncode != 0 or not raw_path.is_file():
            raise Rejected('A2ATransportOrTaskFailure')
        with raw_path.open('rb') as stream:
            raw = stream.read(transport.MAX_BYTES + 1)
        if len(raw) > transport.MAX_BYTES:
            raise Rejected('A2AResponseTooLarge')
        after = cluster.snapshot()
        (args.output_dir / 'snapshot-after.json').write_text(json.dumps(after[0], indent=2) + '\n')
        if before != after:
            raise Rejected('DeploymentChangedDuringInvocation')
        policy_release = {**release, 'agentSpecSha256': before[0]['agentSpecSha256']}
        receipt.update(check(json.loads(raw), context, before[1], policy_release), deployment=before[0],
                       a2aResponseSha256=hashlib.sha256(raw).hexdigest())
    except (ValueError, OSError, KeyError, TypeError, transport.subprocess.SubprocessError) as error:
        receipt['reason'] = str(error) if type(error).__name__ == 'Rejected' else type(error).__name__
    receipt['completedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (args.output_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'phase': receipt['phase'], 'reason': receipt.get('reason'), 'receipt': str(args.output_dir / 'receipt.json')}))
    return {'Passed': 0, 'Failed': 1, 'Rejected': 2}[receipt['phase']]


if __name__ == '__main__':
    sys.exit(main())
