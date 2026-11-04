#!/usr/bin/env python3
"""Test patch write boundaries using a simulated API; never access a cluster."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

script = Path(__file__).resolve().parents[1] / 'patch-peerauthentication-revision.sh'
mock = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args=sys.argv[1:]
scenario=os.environ['SCENARIO']
root=Path(os.environ['CASE_ROOT'])
with (root/'calls').open('a') as f: f.write(json.dumps(args)+'\\n')
state=root/'state'
obj=json.loads(state.read_text()) if state.exists() else {
  'apiVersion':'security.istio.io/v1','kind':'PeerAuthentication',
  'metadata':{'uid':'synthetic-policy-id','resourceVersion':'5','labels':{'istio.io/rev':
     '1-29' if scenario=='already-good' else 'unexpected' if scenario=='wrong-label' else '1-23'}},
  'spec':{'mtls':{'mode':'STRICT'},'selector':{'matchLabels':{'app':'demo'}},'portLevelMtls':{'8080':{'mode':'PERMISSIVE'}}}}
if 'patch' in args:
    patch=json.loads(Path(args[args.index('--patch-file')+1]).read_text())
    for operation in patch:
        target=obj
        parts=[s.replace('~1','/') for s in operation['path'].split('/')[1:]]
        for part in parts[:-1]: target=target[part]
        if operation['op']=='test':
            if scenario=='conflict' and '--dry-run=server' not in args: sys.exit(1)
            assert target[parts[-1]]==operation['value']
        else: target[parts[-1]]=operation['value']
    if scenario=='active-mutator': obj['metadata']['labels']['istio.io/rev']='1-23'
    if scenario=='mutated-spec': obj['spec']['mtls']['mode']='DISABLE'
    if scenario=='reverted-after-write' and '--dry-run=server' not in args:
        obj['metadata']['labels']['istio.io/rev']='1-23'
    if '--dry-run=server' not in args: state.write_text(json.dumps(obj))
print(json.dumps(obj))
'''
for scenario, apply, expected, writes in [
    ('normal',False,0,0), ('normal',True,0,1), ('already-good',True,0,0),
    ('wrong-label',True,1,0), ('active-mutator',True,1,0),
    ('mutated-spec',True,1,0), ('reverted-after-write',True,1,1),
    ('conflict',True,1,1),
]:
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        (root/'kubectl').write_text(mock)
        (root/'kubectl').chmod(0o755)
        env=dict(os.environ, PATH=f'{root}:{os.environ["PATH"]}', SCENARIO=scenario,
                 CASE_ROOT=directory,TMPDIR=directory)
        args=['bash',str(script),'test-context','demo','policy','1-23','1-29']
        if apply: args.append('--apply')
        result=subprocess.run(args,env=env,text=True,capture_output=True)
        calls=[json.loads(line) for line in (root/'calls').read_text().splitlines()]
        actual_writes=[c for c in calls if 'patch' in c and '--dry-run=server' not in c]
        assert result.returncode==expected,(scenario,result.stdout,result.stderr)
        assert len(actual_writes)==writes,(scenario,calls)
        assert all('peerauthentications.security.istio.io' in c for c in calls),calls
        if scenario=='normal' and apply:
            stored=json.loads((root/'state').read_text())
            assert stored['metadata']['labels']['istio.io/rev']=='1-29'
            assert stored['spec']['mtls']['mode']=='STRICT'
            assert stored['spec']['portLevelMtls']['8080']['mode']=='PERMISSIVE'
            assert stored['spec']['selector']['matchLabels']=={'app':'demo'}
        print(f'PASS {scenario} apply={apply}: patch attempts={writes}; exit={expected}')
print('8 simulated API cases passed. No live policy propagation or traffic recovery was tested.')
