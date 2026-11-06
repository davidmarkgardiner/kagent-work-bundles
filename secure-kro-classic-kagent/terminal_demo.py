"""Run the live onboarding demo from a terminal, using the same gates as the UI."""
import argparse
import json
from pathlib import Path
import shlex
import time

from live_demo import Backend, DemoError, validate_agent_url

ROOT = Path(__file__).resolve().parent
HELP = """Commands (each mutation/model call is explicit):
  platform                  Inspect pinned platform and approved choices
  deploy [payload.json]     Create one new owner; default examples/onboarding-payload.json
  connect                   Attach to the existing owner without replacing it
  status                    Show stages, resource kinds/names and API when verified
  verify                    Test caller JWT rejection + one real model PONG
  ask <question>            One real answer using the current platform facts
  counts                    Ask about actual backend-read namespace counts
  challenge <case>          missing-jwt | other-identity | wrong-audience
  delete <agent-name>       Tear down the connected UID and track captured resources
  help                      Show these commands
  quit                      Exit; leaves the agent running
Use demo.py show or kubectl in a second terminal to inspect full resource YAML.
"""


def show_status(state):
    for stage in state['stages']:
        print(('PASS' if stage['passed'] else 'FAIL' if stage.get('failed') else 'WAIT')+'  '+stage['label'])
    print('\nKIND                    NAME')
    for row in state['resources']:
        print(f"{row['kind']:<24}{row['name']}"+(' (deleting)' if row['deleting'] else ''))
    print('\nInstance UID: '+str(state['uid']))
    print('API: '+str(state['endpoint'] or 'locked until all checks pass'))
    print('Network enforcement: not proven by JWT checks.')


def execute(backend, line):
    parts = line.split(None, 1) if line.startswith('ask ') else shlex.split(line)
    if not parts:
        return
    command, args = parts[0], parts[1:]
    if command == 'help' and not args:
        print(HELP)
    elif command == 'platform' and not args:
        print(json.dumps(backend.platform(), indent=2))
    elif command == 'deploy' and len(args) <= 1:
        path = Path(args[0]) if args else ROOT/'examples/onboarding-payload.json'
        payload = json.loads(path.read_text())
        print(json.dumps(payload, indent=2))
        print(json.dumps(backend.create(payload), indent=2))
        print('Submitted once. Use status to watch reconciliation; verify when its first four stages pass.')
    elif command == 'connect' and not args:
        print(json.dumps(backend.attach(), indent=2))
        show_status(backend.inspect())
    elif command == 'status' and not args:
        show_status(backend.inspect())
    elif command == 'verify' and not args:
        print(json.dumps(backend.verify_access(), indent=2))
        show_status(backend.inspect())
    elif command in ('ask', 'counts') and ((command == 'ask' and args) or not args):
        prompt = line.split(None, 1)[1] if command == 'ask' else 'Summarise the supplied namespace counts. State their source.'
        print('Sending one real agent request…', flush=True)
        response = backend.chat(dict(prompt=prompt, namespaceCounts=command == 'counts'))
        print('\n'+response['text']+'\n')
        print(json.dumps({k:response[k] for k in ['taskID','contextID','responseSha256']}))
    elif command == 'challenge' and len(args) == 1:
        print(json.dumps(backend.challenge(dict(case=args[0])), indent=2))
    elif command == 'delete' and len(args) == 1:
        backend.delete(dict(uid=backend.uid, confirmName=args[0]))
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            backend.cleanup_orphans_once()
            result = backend.inspect()['deletion']
            print(f"Captured resources remaining: {len(result['remaining'])}/{result['capturedCount']}", flush=True)
            if result['complete']:
                print('Teardown complete for captured UIDs. Shared platform retained.')
                if getattr(backend.args, 'in_cluster', False):
                    print('Operator must separately confirm native Secret cleanup; this account cannot read Secrets.')
                return
            time.sleep(2)
        raise DemoError('Teardown is incomplete. Inspect remaining resources; no force or finalizer removal performed.')
    else:
        raise DemoError('Unknown command or wrong arguments. Type help.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument('--context')
    target.add_argument('--in-cluster', action='store_true')
    p.add_argument('--environment', choices=['aks','home-lab'], required=True)
    p.add_argument('--agent-url')
    p.add_argument('--kubectl', default='kubectl')
    for name, default in [('namespace','classic-agents'),('name','demo'),('gateway','classic-demo'),('audience','secure-agent-classic'),('read-namespace','classic-agents'),('kagent-namespace','kagent'),('kagent-deployment','kagent-controller'),('kro-namespace','kro-system'),('kro-deployment','kro')]:
        p.add_argument('--'+name, default=default)
    p.add_argument('--allow-tool', action='append', default=[])
    p.add_argument('--allow-skill', action='append', default=[])
    a = p.parse_args()
    if a.environment == 'aks' and not a.agent_url:
        p.error('AKS mode requires the exact HTTPS VirtualService --agent-url.')
    if a.agent_url:
        if a.environment != 'aks':
            p.error('--agent-url is for AKS mode.')
        try:
            validate_agent_url(a.agent_url)
        except ValueError as error:
            p.error(str(error))
    if a.in_cluster and a.environment != 'aks':
        p.error('In-cluster mode requires AKS and its exact HTTPS agent URL.')
    if a.in_cluster:
        a.context = 'in-cluster ServiceAccount'
    backend = Backend(a)
    print('DICE live terminal · '+a.environment+' · '+a.namespace+'/'+a.name)
    print('No HTTP server. Kubernetes credentials stay in this process. No automatic model retries.')
    print(HELP)
    while True:
        try:
            line = input('dice> ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\nExited. The agent is not deleted.')
            return
        if line in ('quit','exit'):
            print('Exited. The agent is not deleted.')
            return
        try:
            execute(backend, line)
        except (DemoError, ValueError, OSError) as error:
            print('Stopped: '+str(error))
        except KeyboardInterrupt:
            print('\nInterrupted. Inspect status before another action; submitted work may still be running.')


if __name__ == '__main__':
    main()
