"""Issue one-hour caller and agent credentials for a dedicated lab rehearsal."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--namespace', required=True)
    parser.add_argument('--agent', required=True)
    parser.add_argument('--private-dir', type=Path, required=True)
    args = parser.parse_args()
    directory = args.private_dir.resolve()
    if any((ancestor / '.git').exists() for ancestor in [directory, *directory.parents]):
        raise ValueError('Keep credentials outside Git checkouts.')
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    command = ['kubectl', '--context', args.context, '-n', args.namespace]
    tokens = {}
    for name, sa, audience in [('caller', 'dice-caller', 'dice-a2a'), ('agent', args.agent, 'dice-mcp')]:
        tokens[name] = subprocess.check_output(command + ['create', 'token', sa,
            '--audience=' + audience, '--duration=1h']).decode().strip()
        fd = os.open(directory / (name + '.token'), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as output:
            output.write(tokens[name] + '\n')
    secret = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {
        'name': 'dice-agent-mcp-credential', 'namespace': args.namespace},
        'stringData': {'authorization': 'Bearer ' + tokens['agent']}}
    subprocess.run(command + ['apply', '-f', '-'], input=json.dumps(secret).encode(), check=True,
                   stdout=subprocess.DEVNULL)
    patch = {'spec': {'declarative': {'deployment': {'annotations': {
        'demo.kagent.dev/credential-renewed-at': datetime.now(timezone.utc).isoformat()}}}}}
    subprocess.run(command + ['patch', 'agent', args.agent, '--type', 'merge', '-p', json.dumps(patch)],
                   check=True, stdout=subprocess.DEVNULL)
    print('One-hour credentials prepared privately. Verify MCP and Agent reconciliation before invocation.')


if __name__ == '__main__':
    main()
