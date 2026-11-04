#!/usr/bin/env python3
"""Exercise the rollback shell against a simulated API. No cluster access."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

script = Path(__file__).resolve().parents[1] / 'rollback-one-deployment.sh'
mock = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
scenario = os.environ['SCENARIO']
with open(os.environ['CALLS'], 'a') as f: f.write(json.dumps(args) + '\\n')
ns = {"metadata":{"resourceVersion":"1","labels":{"istio.io/rev":"other" if scenario == 'wrong-namespace' else "1-29"}}}
dep = {"metadata":{"resourceVersion":"2"},"spec":{"replicas":1,"template":{"metadata":{"labels":{"app":"demo","istio.io/rev":"1-29"}},"spec":{"containers":[{"name":"app","image":"example/app:1"}]}}}}
if 'get' in args:
    print(json.dumps(ns if 'namespace' in args else dep))
elif 'patch' in args:
    obj = ns if 'namespace' in args else dep
    patch = json.loads(Path(args[args.index('--patch-file')+1]).read_text())
    for op in patch:
        if op['op'] == 'test': continue
        parts = [p.replace('~1','/') for p in op['path'].split('/')[1:]]
        target = obj
        for part in parts[:-1]: target = target[part]
        target[parts[-1]] = op['value']
    if scenario == 'policy-active' and 'namespace' in args:
        obj['metadata']['labels']['istio.io/rev'] = '1-29'
    print(json.dumps(obj))
elif 'create' in args:
    pod = json.loads(Path(args[args.index('-f')+1]).read_text())
    pod['spec']['containers'].append({'name':'istio-proxy','image':'example/proxy:1.29' if scenario == 'wrong-proxy' else 'example/proxy:1.23'})
    print(json.dumps(pod))
elif 'rollout' in args:
    print('deployment successfully rolled out')
else: sys.exit(20)
'''
for scenario, apply, expected, expected_writes in [
    ('normal', False, 0, []),
    ('wrong-namespace', True, 1, []),
    ('policy-active', True, 1, []),
    ('wrong-proxy', True, 1, ['namespace']),
    ('normal', True, 0, ['namespace', 'deployment']),
]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / 'kubectl').write_text(mock)
        (root / 'kubectl').chmod(0o755)
        env = dict(os.environ, PATH=f'{root}:{os.environ["PATH"]}', SCENARIO=scenario,
                   CALLS=str(root / 'calls'), TMPDIR=directory)
        args = ['bash', str(script), 'test-context', 'demo', 'demo', '1-29', '1-23', 'example/proxy:1.23']
        if apply: args.append('--apply')
        result = subprocess.run(args, env=env, text=True, capture_output=True)
        calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
        writes = [call[call.index('patch')+1] for call in calls if 'patch' in call and '--dry-run=server' not in call]
        assert result.returncode == expected, (scenario, result.stdout, result.stderr)
        assert writes == expected_writes, (scenario, writes)
        if scenario == 'wrong-proxy': assert not any('rollout' in c for c in calls)
        print(f'PASS {scenario} apply={apply}: writes={writes}')
print('5 API-simulation cases passed. This does not prove live injection or application recovery.')
