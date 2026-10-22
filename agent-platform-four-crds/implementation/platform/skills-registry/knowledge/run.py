#!/usr/bin/env python3
"""Capture and verify one fresh live document lookup against the pinned demo."""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import sys
import tempfile
import uuid

from evidence_check import PROMPT, canonical, check_execution
from controller import API, GROUP, Rejected, verify_documents

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAX_BYTES = 1024 * 1024


def limit_file_size():
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_BYTES, MAX_BYTES))


def invoke(arguments, timeout=155):
    with subprocess.Popen(arguments, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          preexec_fn=limit_file_size, start_new_session=True) as process:
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
            raise Rejected('A2ATimeout') from None


class Cluster:
    def __init__(self, context, release):
        self.command = ['kubectl', '--context', context, '--request-timeout=15s']
        self.release = release
        self.ns = release['namespace']

    def json(self, arguments):
        with tempfile.TemporaryFile() as stream:
            subprocess.run(self.command + arguments, stdout=stream, stderr=subprocess.DEVNULL,
                           check=True, timeout=25, preexec_fn=limit_file_size)
            stream.seek(0)
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise Rejected('ClusterResponseTooLarge')
        return json.loads(raw)

    def get(self, kind, name):
        return self.json(['get', kind, name, '-n', self.ns, '-o', 'json'])

    def snapshot(self):
        release = self.release
        kb = self.get('knowledgebases.' + GROUP, release['name'])
        agent = self.get('agents.kagent.dev', release['agent'])
        for resource in [kb, agent]:
            if not any(c.get('type') == 'Ready' and c.get('status') == 'True'
                       and c.get('observedGeneration') == resource['metadata']['generation']
                       for c in resource.get('status', {}).get('conditions', [])):
                raise Rejected('ReferencedResourceNotCurrentReady')
        spec = kb['spec']
        if (spec['knowledgeBaseName'] != release['knowledgeBaseName'] or spec['files'] != release['files']
                or spec['contentSha256'] != release['contentSha256'] or spec['documents'] != release['documents']
                or spec['sourceCommit'] != release['contentCommit'] or kb['status'].get('contentSha256') != release['contentSha256']
                or canonical(agent['spec']) != release['agentSpecSha256']):
            raise Rejected('ReleaseOrAgentPinMismatch')
        source = self.get('gitrepositories.source.toolkit.fluxcd.io', spec['sourceRef']['name'])
        revision = 'sha1:' + release['contentCommit']
        if (source['spec'].get('ref', {}).get('commit') != release['contentCommit']
                or source.get('status', {}).get('artifact', {}).get('revision') != revision
                or kb['status'].get('observedSourceRevision') != revision
                or not any(c.get('type') == 'Ready' and c.get('status') == 'True'
                           and c.get('observedGeneration') == source['metadata']['generation']
                           for c in source.get('status', {}).get('conditions', []))):
            raise Rejected('SourceNotCurrentAndPinned')
        cm = self.get('configmap', release['configMap'])
        owner = {'apiVersion': API, 'kind': 'KnowledgeBase', 'name': release['name'], 'uid': kb['metadata']['uid'], 'controller': True}
        if (not cm.get('immutable') or owner not in cm['metadata'].get('ownerReferences', [])
                or kb['status'].get('configMapRef', {}).get('name') != release['configMap']):
            raise Rejected('ContentNotOwnedAndImmutable')
        texts = {path: cm['data'][f'file{i:02}'] for i, path in enumerate(sorted(release['files']))}
        if any(hashlib.sha256(texts[p].encode()).hexdigest() != digest for p, digest in release['files'].items()):
            raise Rejected('MaterializedContentMismatch')
        verify_documents(spec, texts)
        pods = self.json(['get', 'pods', '-n', self.ns, '-l', 'kagent=' + release['agent'], '-o', 'json'])['items']
        pods = [p for p in pods if not p['metadata'].get('deletionTimestamp')]
        if len(pods) != 1 or len(pods[0]['spec']['containers']) != 1:
            raise Rejected('AmbiguousAgentPod')
        pod = pods[0]
        statuses = pod.get('status', {}).get('containerStatuses', [])
        if len(statuses) != 1 or not statuses[0].get('ready'):
            raise Rejected('AgentPodNotReady')
        container = pod['spec']['containers'][0]
        if (container.get('securityContext', {}).get('privileged')
                or pod['spec'].get('serviceAccountName') != release['agent']
                or not any(m.get('mountPath') == '/knowledge' and m.get('readOnly') for m in container.get('volumeMounts', []))):
            raise Rejected('ReviewedPodMountMissing')
        script = """import hashlib,json
from pathlib import Path
from kagent.skills import discover_skills
root=Path('/knowledge/aks-bootstrap')
print(json.dumps({'files':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()},'skills':[s.name for s in discover_skills(Path('/skills'))]}))
"""
        mounted = self.json(['exec', '-n', self.ns, pod['metadata']['name'], '--', 'python', '-c', script])
        if mounted.get('files') != release['files'] or mounted.get('skills') != []:
            raise Rejected('MountedDocumentsMismatch')
        runtime = statuses[0]
        identity = {'knowledgeBaseUID': kb['metadata']['uid'], 'knowledgeBaseGeneration': kb['metadata']['generation'],
                    'knowledgeBaseSpecSha256': canonical(spec), 'contentSha256': release['contentSha256'],
                    'sourceUID': source['metadata']['uid'], 'sourceRevision': revision,
                    'agentUID': agent['metadata']['uid'], 'agentGeneration': agent['metadata']['generation'],
                    'agentSpecSha256': canonical(agent['spec']), 'configMapUID': cm['metadata']['uid'],
                    'podUID': pod['metadata']['uid'], 'imageID': runtime.get('imageID'),
                    'containerID': runtime.get('containerID'), 'restartCount': runtime['restartCount'], 'mountedFileHashes': mounted['files']}
        return identity, texts['oras-pull-unauthorized.md']


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
    receipt = {'phase': 'Rejected', 'mode': 'liveNativeDocument', 'inputOrigin': 'synthetic',
               'knowledgeBase': release['name'], 'agent': release['agent'], 'invocationAttempted': False,
               'liveAzureInvestigation': False, 'sandboxExecuted': False,
               'limits': ['Direct mounted-document reading; no search or vector retrieval service.',
                          'Tool checks are retrospective and do not enforce runtime permissions.',
                          'Stable Pod identity does not attest which Pod served A2A.',
                          'Answer checks require specific text and citation, not general semantic correctness.']}
    try:
        cluster = Cluster(args.context, release)
        before = cluster.snapshot()
        (args.output_dir / 'snapshot-before.json').write_text(json.dumps(before[0], indent=2) + '\n')
        context = 'knowledge-' + uuid.uuid4().hex
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        raw_path = args.output_dir / 'a2a-response.json'
        receipt['invocationAttempted'] = True
        returncode = invoke([str(REPO / 'scripts/kagent-a2a-invoke.sh'), '--context', args.context,
            '--ns', release['namespace'], '--agent', release['agent'], '--controller-ns', args.controller_namespace, '--local-port', str(port),
            '--context-id', context, '--text', PROMPT, '--timeout', '120', '--receipt-file', str(raw_path), '--json'])
        if returncode != 0 or not raw_path.is_file():
            raise Rejected('A2ATransportOrTaskFailure')
        with raw_path.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise Rejected('A2AResponseTooLarge')
        after = cluster.snapshot()
        (args.output_dir / 'snapshot-after.json').write_text(json.dumps(after[0], indent=2) + '\n')
        if before != after:
            raise Rejected('DeploymentChangedDuringInvocation')
        receipt.update(check_execution(json.loads(raw), context, before[1], release), deployment=before[0],
                       a2aResponseSha256=hashlib.sha256(raw).hexdigest())
    except (Rejected, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        receipt['reason'] = str(error) if isinstance(error, Rejected) else type(error).__name__
    receipt['completedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (args.output_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'phase': receipt['phase'], 'reason': receipt.get('reason'), 'receipt': str(args.output_dir / 'receipt.json')}))
    return {'Passed': 0, 'Failed': 1, 'Rejected': 2}[receipt['phase']]


if __name__ == '__main__':
    sys.exit(main())
