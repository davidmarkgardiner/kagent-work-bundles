"""One real A2A PONG request through the verifier-only Gateway listener."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def request(url, token=None, payload=None):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, None if payload is None else json.dumps(payload).encode(), headers)
    try:
        response = urllib.request.build_opener(NoRedirect()).open(req, timeout=100 if payload else 5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(1048577)
        if len(raw) > 1048576:
            raise ValueError('ResponseTooLarge')
        try:
            value = json.loads(raw)
        except ValueError:
            value = {}
        return response.status, value


def completed_task(response):
    if response.get('error'):
        raise ValueError('A2AError')
    task = response.get('result', {})
    if not isinstance(task, dict) or task.get('status', {}).get('state') != 'completed' or not task.get('id') or not task.get('contextId'):
        raise ValueError('NativeTaskNotCompleted')
    containers = task.get('artifacts', []) or [m for m in task.get('history', []) if m.get('role') == 'agent'][-1:]
    texts = [part['text'].strip() for container in containers for part in container.get('parts', [])
             if part.get('kind') == 'text' and isinstance(part.get('text'), str)]
    if 'PONG' not in texts:
        raise ValueError('AssistantPongMissing')
    return task


def run(config):
    token = Path(config['tokenFile']).read_text().strip()
    for field in ('invokeURL', 'cardURL', 'callerURL'):
        url = urllib.parse.urlsplit(config[field])
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('InvalidFixedGatewayURL')
    deadline = time.monotonic() + min(config.get('timeoutSeconds', 480), 480)
    while True:
        try:
            code, card = request(config['cardURL'], token)
        except OSError:
            code, card = 503, {}
        if code == 200:
            break
        if code not in (404, 500, 502, 503, 504) or time.monotonic() >= deadline:
            raise ValueError('NativeCardUnavailableHTTP' + str(code))
        time.sleep(2)
    if card.get('name') != config['expectedAgent']:
        raise ValueError('UnexpectedAgentCard')
    checks = [{'name': 'NativeAgentCard', 'passed': True}]
    # No inference is performed by these negative requests.
    for name, url, auth in [('MissingTokenDenied', config['cardURL'], None),
                             ('InvalidTokenDenied', config['cardURL'], 'invalid.token'),
                             ('VerifierCannotUseCallerListener', config['callerURL'], token)]:
        code, _ = request(url, auth)
        if code not in (401, 403, 404):
            raise ValueError(name + '_HTTP' + str(code))
        checks.append({'name': name, 'passed': True, 'http': code})
    message = {'kind': 'message', 'messageId': str(uuid.uuid4()), 'contextId': str(uuid.uuid4()),
               'role': 'user', 'parts': [{'kind': 'text', 'text': 'Reply with exactly PONG. Do not call any tool.'}]}
    payload = {'jsonrpc': '2.0', 'id': str(uuid.uuid4()), 'method': 'message/send',
               'params': {'message': message, 'configuration': {'blocking': True}}}
    # Exactly one model-backed invocation. Startup retries above fetch only the card.
    code, response = request(config['invokeURL'], token, payload)
    if code != 200:
        raise ValueError('NativeInvokeHTTP' + str(code))
    task = completed_task(response)
    checks.append({'name': 'NativeModelPong', 'passed': True})
    return {'schemaVersion': 'classic-golden/v1', 'passed': True, 'scope': 'native-agent-model-pong',
            'requestUID': config['requestUID'], 'taskID': task['id'], 'contextID': task['contextId'],
            'checks': checks, 'responseSha256': canonical(response), 'completedAt': dt.datetime.now(dt.timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = run(json.loads(args.config.read_text()))
    except Exception as error:
        # HTTP bodies, provider details and bearer tokens never appear in the receipt.
        receipt = {'schemaVersion': 'classic-golden/v1', 'passed': False,
                   'reason': str(error) if isinstance(error, ValueError) else type(error).__name__}
    print(json.dumps(receipt, sort_keys=True))
    raise SystemExit(0 if receipt['passed'] else 1)


if __name__ == '__main__':
    main()
