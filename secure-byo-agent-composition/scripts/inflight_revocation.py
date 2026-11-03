"""Revoke one synthetic native call after observing model dispatch and retain bounded receipts."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import threading
import time
import urllib.error
import urllib.request

p = argparse.ArgumentParser()
p.add_argument('--kubeconfig', required=True)
p.add_argument('--context', required=True)
p.add_argument('--namespace', required=True, choices=['secure-byo-hosted', 'secure-byo-kro'])
p.add_argument('--url', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
out = Path(a.output)
out.mkdir(parents=True, mode=0o700, exist_ok=False)
k = ['kubectl', '--kubeconfig', a.kubeconfig, '--context', a.context, '-n', a.namespace]


def token(name):
    return subprocess.check_output(k + ['create', 'token', name, '--audience=secure-byo',
        '--duration=1h'], text=True).strip()


caller, worker = token('approved-caller'), token('approved-worker')


def request(path, auth, value, timeout=115):
    req = urllib.request.Request(a.url + path, json.dumps(value).encode(),
        {'Authorization': 'Bearer ' + auth, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def counters():
    status, value = request('/witness', caller, {}, 5)
    if status != 200:
        raise AssertionError('Authorized witness unavailable')
    return value.get('counters', value)


cm = json.loads(subprocess.check_output(k + ['get', 'cm', 'demo-approval', '-o', 'json'], text=True))
saved = {'apiVersion': 'v1', 'kind': 'ConfigMap',
    'metadata': {'name': 'demo-approval', 'namespace': a.namespace}, 'data': cm['data']}
before = counters()
result = {}


def invoke():
    try:
        status, body = request('/invoke', caller, {'prompt':
            'Synthetic revocation proof. Load both approved skills and their references, then call get_demo_status. No Azure actions.'})
        result.update(http=status, error=body.get('error'), returnedTask='task' in body)
    except Exception as error:
        result.update(error=type(error).__name__, returnedTask=False)


thread = threading.Thread(target=invoke, daemon=True)
thread.start()
observed = None
until = time.monotonic() + 30
while time.monotonic() < until and thread.is_alive():
    current = counters()
    if current['authorizedModelCalls'] > before['authorizedModelCalls']:
        observed = current
        break
    time.sleep(.05)
if observed is None or not thread.is_alive():
    thread.join(timeout=115)
    raise AssertionError('Did not observe model dispatch during unfinished native call')
revoked = copy.deepcopy(saved)
record = json.loads(revoked['data']['approval.json'])
record['state'] = 'Revoked'
revoked['data']['approval.json'] = json.dumps(record)
start = time.monotonic()
try:
    subprocess.run(k + ['apply', '-f', '-'], input=json.dumps(revoked), text=True,
                   check=True, stdout=subprocess.DEVNULL)
    mcp_code, _ = request('/mcp', worker,
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'get_demo_status', 'arguments': {}}})
    invoke_code, _ = request('/invoke', caller, {'prompt': 'Must be denied.'})
    thread.join(timeout=115)
    elapsed = round(time.monotonic() - start, 3)
finally:
    subprocess.run(k + ['apply', '-f', '-'], input=json.dumps(saved), text=True,
                   check=True, stdout=subprocess.DEVNULL)
after = counters()
checks = [
    {'name': 'model-dispatch-observed-before-revocation', 'passed': True},
    {'name': 'new-tool-and-invoke-denied', 'passed': mcp_code == invoke_code == 403},
    {'name': 'unfinished-native-call-returns-no-task', 'passed': not thread.is_alive()
        and result.get('http') in (403, 502, 504) and result.get('returnedTask') is False},
    {'name': 'no-further-authorized-dispatch', 'passed': all(after[key] == observed[key]
        for key in ['authorizedModelCalls', 'authorizedMcpCalls', 'authorizedInvocations'])},
    {'name': 'client-call-settled-within-request-bound', 'passed': elapsed <= 110 and not thread.is_alive()},
]
receipt = {'namespace': a.namespace, 'checks': checks, 'passed': all(c['passed'] for c in checks),
    'observedSettlementUpperBoundSeconds': elapsed, 'clientResult': result,
    'before': before, 'atObservedDispatch': observed, 'afterApprovalRestore': after,
    'limit': 'Already-dispatched provider work may complete. This measures client settlement and authorization counters, not provider cancellation or token renewal.'}
(out / 'summary.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt))
raise SystemExit(0 if receipt['passed'] else 1)
