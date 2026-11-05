"""Apply one customer YAML, inspect its resources and call the JWT-protected route."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
RESOURCES = {
    'instance': ('classicsecureagent', 'demo'),
    'agent': ('agents.kagent.dev', 'demo'),
    'deployment': ('deployment', 'demo'),
    'service': ('service', 'demo'),
    'runtimeAccount': ('serviceaccount', 'demo-runtime'),
    'verifierAccount': ('serviceaccount', 'demo-verifier'),
    'callerAccount': ('serviceaccount', 'demo-caller'),
    'network': ('networkpolicy', 'demo-boundary'),
    'verifierNetwork': ('networkpolicy', 'demo-verifier'),
    'verifierPolicy': ('agentgatewaypolicy', 'demo-verify'),
    'cardPolicy': ('agentgatewaypolicy', 'demo-card'),
    'callerPolicy': ('agentgatewaypolicy', 'demo-invoke'),
    'verifyRoute': ('httproute', 'demo-verify'),
    'cardRoute': ('httproute', 'demo-card'),
    'callerRoute': ('httproute', 'demo-invoke'),
    'goldenConfig': ('configmap', 'demo-golden'),
    'golden': ('job', 'demo-golden'),
    'model': ('modelconfigs.kagent.dev', 'approved-model'),
    'kubernetesMCP': ('remotemcpservers.kagent.dev', 'approved-kubernetes-mcp'),
    'gitlabMCP': ('remotemcpservers.kagent.dev', 'approved-gitlab-mcp'),
    'denodoMCP': ('remotemcpservers.kagent.dev', 'approved-denodo-mcp'),
}
LIST = 'classicsecureagent,agents.kagent.dev,deployments,pods,services,jobs,httproutes,agentgatewaypolicies,networkpolicies,serviceaccounts,configmaps'


def ready(resource):
    return any(c.get('type') == 'Ready' and c.get('status') == 'True'
               and c.get('observedGeneration', resource['metadata']['generation']) == resource['metadata']['generation']
               for c in resource.get('status', {}).get('conditions', []))


def validate_receipt(owner, job, receipt):
    uid = owner['metadata']['uid']
    if (job['metadata'].get('labels', {}).get('kro.run/instance-id') != uid
            or receipt.get('requestUID') != uid or not receipt.get('passed')
            or receipt.get('schemaVersion') != 'classic-golden/v1'
            or not receipt.get('taskID') or not receipt.get('contextID')
            or not job.get('status', {}).get('succeeded')):
        raise ValueError('Golden receipt does not prove this instance. No automatic retry.')


class Demo:
    def __init__(self, args):
        self.args = args
        self.base = [args.kubectl, '--context', args.context, '--request-timeout=20s', '-n', 'classic-agents']

    def run(self, *command, capture=True, check=True, timeout=30, input_text=None):
        result = subprocess.run(self.base + list(command), capture_output=capture, text=True,
                                input=input_text, check=False, timeout=timeout)
        if check and result.returncode:
            raise ValueError('kubectl failed. ' + (result.stderr or '').strip()[:500])
        return result

    def get(self, kind, name):
        result = self.run('get', kind, name, '--ignore-not-found', '-o', 'json')
        return json.loads(result.stdout) if result.stdout.strip() else None

    def apply(self):
        path = self.args.file.resolve()
        text = path.read_text()
        if len(text.encode()) > 65536 or '{{' in text:
            raise ValueError('Fill the customer template first. No unresolved placeholders are accepted.')
        print('Customer file: ' + str(path), flush=True)
        print('SHA256: ' + hashlib.sha256(text.encode()).hexdigest(), flush=True)
        print(text, flush=True)
        owner = json.loads(self.run('apply', '--dry-run=server', '--validate=strict', '-f', '-', '-o', 'json', input_text=text).stdout)
        if (owner.get('apiVersion') != 'demo.kagent.dev/v1alpha1' or owner.get('kind') != 'ClassicSecureAgent'
                or owner['metadata']['name'] != 'demo' or owner['metadata']['namespace'] != 'classic-agents'):
            raise ValueError('This demonstration supports only the approved classic-agents/demo slot.')
        if self.get('classicsecureagent', 'demo'):
            raise ValueError('The demo slot already exists. This runner does not delete it or reuse an old Golden as a fresh apply.')
        self.run('apply', '--validate=strict', '-f', '-', capture=False, input_text=text)
        print('One customer YAML applied. Run watch in another terminal, then verify.', flush=True)

    def verify(self):
        deadline = time.monotonic() + self.args.timeout
        owner = self.get('classicsecureagent', 'demo')
        if not owner:
            raise ValueError('Apply the customer YAML first.')
        uid = owner['metadata']['uid']
        while time.monotonic() < deadline:
            job = self.get('job', 'demo-golden')
            if job and (job.get('status', {}).get('failed', 0)
                        or any(c['type'] == 'Failed' and c['status'] == 'True' for c in job.get('status', {}).get('conditions', []))):
                raise ValueError('Golden failed. Inspect logs job/demo-golden. No retry or cleanup was performed.')
            if job and job.get('status', {}).get('succeeded'):
                break
            print('Waiting for the native Agent and Golden Job...', flush=True)
            time.sleep(2)
        else:
            raise ValueError('Timed out waiting for Golden. No retry was performed.')
        receipts = [json.loads(line) for line in self.run('logs', 'job/demo-golden').stdout.splitlines() if line.startswith('{')]
        receipt = next(r for r in reversed(receipts) if r.get('schemaVersion') == 'classic-golden/v1')
        validate_receipt(owner, job, receipt)
        while time.monotonic() < deadline:
            current = self.get('classicsecureagent', 'demo')
            agent = self.get('agents.kagent.dev', 'demo')
            route = self.get('httproute', 'demo-invoke')
            if not current or current['metadata']['uid'] != uid:
                raise ValueError('The owner instance changed during verification.')
            if ready(current) and agent and ready(agent) and route:
                print(json.dumps({'verifiedInstanceUID': uid, 'instanceReady': True, 'agentReady': True,
                                  'callerRouteCreated': True, 'golden': receipt}, indent=2))
                return
            time.sleep(2)
        raise ValueError('Golden passed, but the current instance and caller route are not Ready.')

    def query(self):
        owner = self.get('classicsecureagent', 'demo')
        if not owner or not ready(owner):
            raise ValueError('The current owner instance is not Ready. Run verify first.')
        with tempfile.TemporaryDirectory(prefix='classic-caller-') as directory:
            token_path = self.args.token_file
            if self.args.mint_token:
                token_path = Path(directory) / 'caller.jwt'
                token = self.run('create', 'token', 'demo-caller', '--audience=secure-agent-classic', '--duration=10m').stdout.strip()
                with token_path.open('x', opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
                    stream.write(token)
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            command = self.base + ['port-forward', '--address=127.0.0.1', 'service/' + self.args.gateway, str(port) + ':8080']
            forward = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if forward.poll() is not None:
                        raise ValueError('Gateway port-forward exited before becoming ready.')
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise ValueError('Gateway port-forward did not become ready.')
                invocation = [sys.executable, str(ROOT / 'query.py'), '--url',
                              'http://127.0.0.1:' + str(port) + '/classic/classic-agents/demo/invoke',
                              '--token-file', str(token_path), '--prompt', self.args.prompt]
                if self.args.expect:
                    invocation += ['--expect', self.args.expect]
                result = subprocess.run(invocation, check=False, timeout=120)
                if result.returncode:
                    raise ValueError('The single agent invocation failed. No automatic retry.')
            finally:
                forward.terminate()
                try:
                    forward.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    forward.kill()
                    forward.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--kubectl', default='kubectl')
    commands = parser.add_subparsers(dest='action', required=True)
    apply = commands.add_parser('apply', help='Display and apply exactly one new customer instance.')
    apply.add_argument('--file', type=Path, default=ROOT / 'examples/agent-demo.yaml')
    commands.add_parser('watch', help='Watch the actual namespace resources. Stop with Ctrl-C.')
    commands.add_parser('status', help='Print the actual namespace resources.')
    show = commands.add_parser('show', help='Print actual resource YAML, excluding Secrets.')
    show.add_argument('resource', choices=RESOURCES)
    verify = commands.add_parser('verify', help='Require current-instance Golden proof and readiness.')
    verify.add_argument('--timeout', type=int, default=300)
    query = commands.add_parser('query', help='Send one model request through the caller Gateway.')
    auth = query.add_mutually_exclusive_group(required=True)
    auth.add_argument('--token-file', type=Path)
    auth.add_argument('--mint-token', action='store_true', help='Use operator permission to mint a 10-minute demo-caller token.')
    query.add_argument('--gateway', default='classic-demo')
    query.add_argument('--prompt', required=True)
    query.add_argument('--expect')
    args = parser.parse_args()
    demo = Demo(args)
    if args.action in ('apply', 'verify', 'query'):
        getattr(demo, args.action)()
    elif args.action == 'show':
        demo.run('get', *RESOURCES[args.resource], '-o', 'yaml', capture=False)
    else:
        while True:
            if args.action == 'watch' and sys.stdout.isatty():
                print('\033[2J\033[H', end='', flush=True)
            demo.run('get', LIST, '-o', 'wide', capture=False)
            if args.action != 'watch':
                break
            time.sleep(2)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
    except (ValueError, OSError, StopIteration, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
