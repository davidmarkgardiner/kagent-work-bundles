"""Exercise approval, grant, reconciliation and request lifecycle in the two POC namespaces."""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

p = argparse.ArgumentParser()
p.add_argument('--kubeconfig', required=True)
p.add_argument('--context', required=True)
p.add_argument('--namespace', required=True, choices=['secure-byo-hosted', 'secure-byo-kro'])
p.add_argument('--url', required=True)
p.add_argument('--rendered', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
out = Path(a.output)
out.mkdir(parents=True, mode=0o700, exist_ok=False)
k = ['kubectl', '--kubeconfig', a.kubeconfig, '--context', a.context]
ns = ['-n', a.namespace]
checks = []


def run(*args, value=None, check=True):
    return subprocess.run(k + list(args), input=None if value is None else json.dumps(value),
                          text=True, capture_output=True, check=check, timeout=65)


def get(kind, name, namespace=None):
    r = run('-n', namespace or a.namespace, 'get', kind, name, '-o', 'json', check=False)
    if r.returncode and 'NotFound' in r.stderr:
        return None
    r.check_returncode()
    return json.loads(r.stdout)


def clean(o):
    return {'apiVersion': o['apiVersion'], 'kind': o['kind'],
            'metadata': {v: copy.deepcopy(o['metadata'][v]) for v in ('name', 'namespace', 'ownerReferences') if v in o['metadata']},
            **{v: copy.deepcopy(o[v]) for v in ('spec', 'data') if v in o}}


def apply(o):
    run('apply', '-f', '-', value=o)


def wait(predicate, description, seconds=160):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if predicate():
            return
        time.sleep(1)
    raise TimeoutError(description)


def record(name, passed, details=None):
    checks.append({'name': name, 'passed': bool(passed), 'details': details})
    (out / 'summary.json').write_text(json.dumps({'namespace': a.namespace, 'checks': checks,
        'passed': all(v['passed'] for v in checks)}, indent=2))
    print(name, 'PASS' if passed else 'FAIL', flush=True)
    if not passed:
        raise AssertionError(name)


def token(name):
    return run(*ns, 'create', 'token', name, '--audience=secure-byo', '--duration=1h').stdout.strip()


caller, worker = token('approved-caller'), token('approved-worker')


def request(path, auth, payload):
    req = urllib.request.Request(a.url + path, json.dumps(payload).encode(),
        {'Authorization': 'Bearer ' + auth, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read(65536)
        try:
            body = json.loads(raw)
        except ValueError:
            body = {'error': raw.decode(errors='replace')[:200]}
        return e.code, body


def mcp():
    return request('/mcp', worker, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})


def counters():
    code, body = request('/witness', caller, {})
    if code != 200:
        raise AssertionError('witness unavailable')
    return {key: value for key, value in body.get('counters', body).items() if key != 'deniedRequests'}


approval = clean(get('configmap', 'demo-approval'))
original = json.loads(approval['data']['approval.json'])
request_kind = 'hostedsecureagent' if a.namespace.endswith('hosted') else 'secureagent'
parent = get(request_kind, 'demo')
profile = json.loads((Path(a.rendered) / (a.namespace + '-profile.json')).read_text())
children = [(o['kind'], o['metadata']['name'].replace('{{NAME}}', 'demo')) for o in profile['resources']]


def publish(value):
    cm = copy.deepcopy(approval)
    cm['data']['approval.json'] = json.dumps(value)
    apply(cm)


def refresh():
    subprocess.run(['python3', str(Path(__file__).with_name('approval.py')),
        '--kubeconfig', a.kubeconfig, '--context', a.context, '--namespace', a.namespace,
        '--state', 'Active'], check=True, stdout=subprocess.DEVNULL)


def ready():
    agent = get('agent', 'demo')
    if not agent:
        return False
    status = agent.get('status', {})
    return (status.get('desiredRevision') == status.get('latestSuccessfulRevision')
        and bool(status.get('desiredRevision'))
        and all(any(c['type'] == t and c['status'] == 'True'
            and c.get('observedGeneration') == agent['metadata']['generation']
            for c in status.get('conditions', []))
            for t in ['Accepted', 'ResolvedRefs', 'Compatible', 'EgressPoliciesApplied', 'Ready']))


for name, change in [
    ('expired-approval', lambda r: r.update(expiresAt=(dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=5)).isoformat())),
    ('wrong-request-uid', lambda r: r.update(requestUID='00000000-0000-0000-0000-000000000000')),
    ('wrong-agent-uid', lambda r: r.update(agentUID='00000000-0000-0000-0000-000000000000')),
    ('dependency-pins-missing', lambda r: r.update(dependencies=[])),
]:
    before = counters()
    changed = copy.deepcopy(original)
    change(changed)
    try:
        publish(changed)
        mcp_code, mcp_body = mcp()
        invoke_code, invoke_body = request('/invoke', caller, {'prompt': 'Must be denied before dispatch.'})
    finally:
        publish(original)
    record(name, mcp_code == 403 and invoke_code == 403 and counters() == before,
           {'mcp': mcp_code, 'invoke': invoke_code, 'noDispatch': counters() == before})

before = counters()
try:
    run(*ns, 'delete', 'configmap', 'demo-approval', '--wait=true')
    code, _ = mcp()
    invoke_code, _ = request('/invoke', caller, {'prompt': 'Must be denied.'})
finally:
    publish(original)
record('authority-unavailable-no-dispatch', code == 503 and invoke_code == 503 and counters() == before,
       {'mcp': code, 'invoke': invoke_code})

composer_ns = a.namespace if a.namespace.endswith('hosted') else 'secure-byo-kro-system'
composer_name = 'hosted-composer' if a.namespace.endswith('hosted') else 'secure-byo-kro'
deployment = get('deployment', composer_name, composer_ns)
if deployment is None:
    raise ValueError('Expected dedicated POC composer not found')
replicas = deployment['spec']['replicas']
try:
    run('-n', composer_ns, 'scale', 'deployment/' + composer_name, '--replicas=0')
    wait(lambda: not get('deployment', composer_name, composer_ns).get('status', {}).get('replicas'), 'composer stop')
    grant = get('referencegrant', 'demo-frontdoor')
    before = counters()
    try:
        run(*ns, 'delete', 'referencegrant', 'demo-frontdoor', '--wait=true')
        def unresolved():
            route = get('httproute', a.namespace, 'secure-byo-gateway-system')
            return any(c.get('type') == 'ResolvedRefs' and c.get('status') == 'False'
                for parent in route.get('status', {}).get('parents', []) for c in parent.get('conditions', []))
        wait(unresolved, 'destination grant removal', 25)
        code, _ = mcp()
    finally:
        apply(clean(grant))
    wait(lambda: mcp()[0] == 200, 'grant recovery', 25)
    record('referencegrant-removal-blocks-route', code in (500, 502, 503) and counters() == before,
           {'http': code, 'resolvedRefsFalse': True, 'noDispatch': counters() == before})
    model = get('modelconfig', 'approved-model')
    before = counters()
    run(*ns, 'delete', 'modelconfig', 'approved-model', '--wait=true')
    try:
        apply(clean(model))
    finally:
        if get('modelconfig', 'approved-model') is None:
            apply(clean(model))
    code, body = mcp()
    record('same-name-dependency-replacement-denied', code == 403,
           {'http': code, 'newUID': get('modelconfig', 'approved-model')['metadata']['uid'] != model['metadata']['uid']})
finally:
    run('-n', composer_ns, 'scale', 'deployment/' + composer_name, '--replicas=' + str(replicas))
    run('-n', composer_ns, 'rollout', 'status', 'deployment/' + composer_name, '--timeout=55s')
refresh()
wait(ready, 'native ready after dependency replacement')
record('fresh-dependency-approval-restores-access', mcp()[0] == 200)

service_uid = get('service', 'demo-frontdoor')['metadata']['uid']
run(*ns, 'delete', 'service', 'demo-frontdoor', '--wait=true')
wait(lambda: get('service', 'demo-frontdoor') is not None, 'service reconcile')
wait(lambda: mcp()[0] == 200, 'reconciled service route', 30)
record('composer-repairs-deleted-child', get('service', 'demo-frontdoor')['metadata']['uid'] != service_uid)

old_agent_uid = get('agent', 'demo')['metadata']['uid']
run(*ns, 'delete', request_kind, 'demo', '--wait=false')
wait(lambda: get(request_kind, 'demo') is None and all(get(kind, name) is None for kind, name in children),
     'parent and owned child cleanup', 230)
record('request-deletion-removes-all-owned-children', True, {'ownedChildren': len(children)})
run('--as', 'system:serviceaccount:' + a.namespace + ':owner', 'apply', '-f', '-', value=clean(parent))
wait(lambda: get('agent', 'demo') is not None and get('deployment', 'demo-frontdoor') is not None, 'request recreation')
run(*ns, 'rollout', 'status', 'deployment/demo-frontdoor', '--timeout=55s')
wait(lambda: mcp()[0] in (403, 503), 'recreated frontdoor binding rejection', 30)
code, _ = mcp()
record('same-name-request-recreation-rejects-old-approval', code == 403
    and get(request_kind, 'demo')['metadata']['uid'] != parent['metadata']['uid']
    and get('agent', 'demo')['metadata']['uid'] != old_agent_uid, {'http': code})
refresh()
wait(ready, 'native ready after reapproval')
record('fresh-request-approval-restores-access', mcp()[0] == 200)
uid = get('agent', 'demo')['metadata']['uid']
run('-n', composer_ns, 'rollout', 'restart', 'deployment/' + composer_name)
run('-n', composer_ns, 'rollout', 'status', 'deployment/' + composer_name, '--timeout=55s')
wait(ready, 'native ready after composer restart')
record('composer-restart-preserves-owned-agent', mcp()[0] == 200 and get('agent', 'demo')['metadata']['uid'] == uid)
