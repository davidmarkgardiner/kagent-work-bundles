"""Deploy or observe the bounded KRO demo, then query its protected invoke endpoint."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

NS = 'secure-byo-kro'
NAME = 'demo'


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def write_json(directory, name, value):
    path = directory / name
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def announce(message, passed=False):
    prefix = '\033[32mPASS\033[0m' if passed and sys.stdout.isatty() else ('PASS' if passed else 'WAIT')
    print(prefix + '  ' + message, flush=True)


def kubectl(args, *command, optional=False):
    result = subprocess.run([args.kubectl, '--context', args.context, *command],
                            capture_output=True, text=True, timeout=35)
    if result.returncode:
        raise ValueError('kubectl failed: ' + result.stderr.strip()[:1200])
    if optional and not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def current(args, resource, name, optional=False):
    command = ['-n', NS, 'get', resource, name, '-o', 'json']
    if optional:
        command.append('--ignore-not-found')
    return kubectl(args, *command, optional=optional)


def ready(agent):
    required = {'Accepted', 'ResolvedRefs', 'Compatible', 'EgressPoliciesApplied', 'Ready'}
    return (required <= {c['type'] for c in agent.get('status', {}).get('conditions', [])
                        if c.get('status') == 'True' and c.get('observedGeneration') == agent['metadata']['generation']}
            and agent['status'].get('desiredRevision')
            and agent['status']['desiredRevision'] == agent['status'].get('latestSuccessfulRevision'))


def verify_completed(args, owner, job, record, report):
    receipt = report.get('receipt', {})
    agent = current(args, 'agents.api.kagent.dev', NAME)
    now = dt.datetime.now(dt.timezone.utc)
    expiry = dt.datetime.fromisoformat(record['expiresAt'].replace('Z', '+00:00'))
    if (report.get('passed') is not True or record.get('state') != 'Active' or expiry <= now
            or not ready(agent) or receipt.get('requestUID') != owner['metadata']['uid']
            or job['metadata'].get('labels', {}).get('secure-byo.platform/request-uid') != owner['metadata']['uid']
            or receipt.get('jobUID') != job['metadata']['uid']
            or receipt.get('agentUID') != agent['metadata']['uid']
            or receipt.get('agentSpecSha256') != canonical(agent['spec'])
            or receipt.get('nativeRevision') != agent['status']['desiredRevision']
            or record.get('goldenProof', {}).get('receipt') != receipt
            or record['goldenProof'].get('sha256') != canonical(receipt)
            or report.get('receiptSha256') != canonical(receipt)
            or report.get('callerSmoke', {}).get('passed') is not True
            or report.get('callerSmoke') != record.get('callerSmoke')):
        raise ValueError('Completed Job does not have a current, matching Golden proof and caller smoke.')
    for key in ('attemptID', 'jobUID', 'podUID', 'requestUID', 'agentUID', 'agentSpecSha256', 'expiresAt', 'dependencies'):
        if receipt.get(key) != record.get(key):
            raise ValueError('Golden approval binding changed: ' + key)
    for pin in receipt['dependencies']:
        obj = current(args, pin['plural'] + '.api.kagent.dev', pin['name'])
        if obj['metadata'].get('deletionTimestamp') or obj['metadata']['uid'] != pin['uid'] or canonical(obj['spec']) != pin['specSha256']:
            raise ValueError('Native dependency changed: ' + pin['name'])
    required = {'NativeInvocationHTTP', 'StructuredNativeEvidence', 'PositiveModelAndMcpWitnesses',
                'NativeCurrentReadyAndPins', 'OrdinaryCallerDeniedWhileVerifying', 'MissingTokenDenied',
                'WrongAudienceDenied', 'WorkerCannotInvoke', 'VerifierCannotUseWorkerLane',
                'CallerCannotUseWorkerLane', 'ForbiddenMcpOperationDenied', 'NegativeControlsNoBackendDispatch'}
    checks = receipt.get('checks', [])
    if not required <= {check.get('name') for check in checks} or not all(check.get('passed') is True for check in checks):
        raise ValueError('Golden contains a failed check.')
    if not all(receipt.get('witnessDeltas', {}).get(key, 0) > 0 for key in ('modelCalls', 'mcpCalls')):
        raise ValueError('Golden lacks positive model and MCP witnesses.')
    return {'mode': args.command, 'checkedAt': now.isoformat(), 'ownerUID': owner['metadata']['uid'],
            'goldenCompletedAt': receipt['completedAt'], 'expiresAt': record['expiresAt'],
            'witnessDeltas': receipt['witnessDeltas'], 'callerSmoke': report['callerSmoke'],
            'receiptSha256': canonical(receipt), 'passed': True}


def watch(args, owner):
    deadline = time.monotonic() + args.timeout
    previous = None
    while time.monotonic() < deadline:
        actual = current(args, 'secureagents.kro.run', NAME)
        if actual['metadata']['uid'] != owner['metadata']['uid']:
            raise ValueError('The owner instance was replaced during the demo.')
        job = current(args, 'jobs', NAME + '-golden', optional=True)
        state = actual.get('status', {}).get('state', 'reconciling')
        job_state = 'waiting for Job'
        if job:
            conditions = job.get('status', {}).get('conditions', [])
            if any(c['type'] == 'Failed' and c['status'] == 'True' for c in conditions):
                raise ValueError('Golden Job failed. Inspect kubectl logs job/demo-golden; this script does not retry or reset approval.')
            job_state = 'complete' if any(c['type'] == 'Complete' and c['status'] == 'True' for c in conditions) else 'running'
        status = state + ' | Golden ' + job_state
        if status != previous:
            announce(status)
            previous = status
        owner_ready = any(c['type'] == 'Ready' and c['status'] == 'True'
                          and c.get('observedGeneration') == actual['metadata']['generation']
                          for c in actual.get('status', {}).get('conditions', []))
        if job_state == 'complete' and owner_ready:
            report = kubectl(args, '-n', NS, 'logs', 'job/' + NAME + '-golden')
            record = json.loads(current(args, 'configmaps', NAME + '-approval')['data']['approval.json'])
            summary = verify_completed(args, actual, job, record, report)
            for name, value in [('owner.json', actual), ('golden-job.json', job),
                                ('golden-receipt.json', report), ('demo-result.json', summary)]:
                write_json(args.evidence_dir, name, value)
            announce('KRO instance Ready; current native revision verified.', True)
            announce('Golden completed at ' + summary['goldenCompletedAt'] + '; ' + json.dumps(summary['witnessDeltas']), True)
            announce('Ordinary-caller PONG passed; lease expires ' + summary['expiresAt'], True)
            if args.command == 'observe':
                print('Observed the recorded run. No new deployment or model inference was performed.')
            else:
                print('Fresh instance and verification completed. Run the query command for your next live question.')
            return
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    raise ValueError('Timed out waiting for the real KRO and Golden result. No success was recorded.')


def deployment(args):
    existing = current(args, 'secureagents.kro.run', NAME, optional=True)
    if args.command == 'deploy':
        if existing:
            raise ValueError('secure-byo-kro/demo already exists. Use observe to inspect that run. Prepare a fresh demo through the documented retirement process; applying again does not rerun Golden.')
        owner = kubectl(args, 'apply', '--dry-run=server', '--validate=strict', '-f', str(args.instance), '-o', 'json')
        if owner.get('apiVersion') != 'kro.run/v1alpha1' or owner.get('kind') != 'SecureAgent' or owner['metadata']['name'] != NAME or owner['metadata'].get('namespace') != NS:
            raise ValueError('This runner supports only the reviewed secure-byo-kro/demo SecureAgent.')
        args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        announce('Applying one SecureAgent instance to context ' + args.context)
        owner = kubectl(args, 'apply', '--validate=strict', '-f', str(args.instance), '-o', 'json')
    else:
        if not existing:
            raise ValueError('No existing demo to observe.')
        args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        print('Observing existing deployment; this is not a fresh deployment replay.', flush=True)
        owner = existing
    watch(args, owner)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def task_output(result):
    task = result.get('task', {})
    if task.get('status', {}).get('state') != 'TASK_STATE_COMPLETED' or not task.get('id') or not task.get('contextId'):
        raise ValueError('The native task did not complete with a task and context ID.')
    containers = [*task.get('artifacts', []), *[m for m in task.get('history', []) if m.get('role') in ('ROLE_AGENT', 'ROLE_ASSISTANT')]]
    texts = [p['text'].strip() for m in containers for p in m.get('parts', []) if isinstance(p.get('text'), str)]
    if not texts:
        raise ValueError('The native task contains no assistant output.')
    return task, texts


def tool_evidence(task, expected):
    pending, proved = {}, set()
    for message in [*task.get('history', []), *task.get('artifacts', [])]:
        if message.get('role') == 'ROLE_USER':
            continue
        for part in message.get('parts', []):
            tag = part.get('metadata', {}).get('kagent.dev/a2a/part-type')
            data = part.get('data', {})
            if not isinstance(data, dict):
                continue
            name = data.get('name', '')
            matched = next((tool for tool in expected if name == tool or name.endswith('_' + tool)), None)
            if matched is None:
                continue
            ident = data.get('id', data.get('callId', data.get('tool_call_id')))
            key = (name, ident)
            if tag == 'function_call':
                pending[key] = data
            if tag == 'function_response' and key in pending:
                returned = data.get('response', data.get('result', {}))
                if isinstance(returned, dict) and (returned.get('isError') is True or returned.get('error')):
                    raise ValueError('MCP tool returned an error: ' + matched)
                if not returned:
                    raise ValueError('MCP tool returned no evidence: ' + matched)
                proved.add(matched)
    if set(expected) - proved:
        raise ValueError('Missing paired native tool responses: ' + ', '.join(sorted(set(expected) - proved)))
    return sorted(proved)


def query(args):
    url = urllib.parse.urlsplit(args.url)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Provide the approved invoke listener URL without credentials, query or fragment.')
    token = args.token_file.read_text().strip()
    prompt = args.prompt_file.read_text().strip()
    if not token or '\n' in token or '\r' in token or not 1 <= len(prompt) <= 8192:
        raise ValueError('A single bearer token and a prompt of 1 to 8192 characters are required.')
    request = urllib.request.Request(args.url.rstrip('/') + '/invoke', json.dumps({'prompt': prompt}).encode(),
                                     {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=115) as response:
            raw = response.read(1048577)
    except urllib.error.HTTPError as error:
        raise ValueError('Invoke HTTP ' + str(error.code) + '. Check caller identity, route, approval and lease; no automatic retry.') from None
    if len(raw) > 1048576:
        raise ValueError('Native response exceeds one MiB.')
    result = json.loads(raw)
    task, texts = task_output(result)
    tools = tool_evidence(task, args.require_tool)
    if args.expect and args.expect not in texts:
        raise ValueError('Assistant output did not match the expected response.')
    write_json(args.evidence_dir, 'native-response.json', result)
    write_json(args.evidence_dir, 'query-result.json', {'passed': True, 'taskID': task['id'],
               'contextID': task['contextId'], 'pairedTools': tools,
               'completedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'responseSha256': canonical(result)})
    print('\n'.join(texts)[:12000])
    announce('Native task ' + task['id'] + ' completed; context ' + task['contextId'], True)
    if tools:
        announce('Paired native tool responses: ' + ', '.join(tools), True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for mode in ('deploy', 'observe'):
        p = commands.add_parser(mode)
        p.add_argument('--context', required=True)
        p.add_argument('--kubectl', default='kubectl')
        p.add_argument('--evidence-dir', type=Path, required=True)
        p.add_argument('--timeout', type=int, default=600)
        if mode == 'deploy':
            p.add_argument('--instance', type=Path, required=True)
    p = commands.add_parser('query')
    p.add_argument('--url', required=True)
    p.add_argument('--token-file', type=Path, required=True)
    p.add_argument('--prompt-file', type=Path, required=True)
    p.add_argument('--expect')
    p.add_argument('--require-tool', action='append', default=[], help='Require a paired native call and nonempty response for this operation; repeat as needed')
    p.add_argument('--evidence-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'query':
            query(args)
        else:
            deployment(args)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print('FAIL  ' + str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
