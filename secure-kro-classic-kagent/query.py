"""Invoke the protected classic Agent route with the caller's JWT."""
import argparse
import importlib.util
import json
from pathlib import Path
import uuid
import urllib.parse

spec = importlib.util.spec_from_file_location('classic_transport', Path(__file__).parent / 'runtime/golden.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--token-file', type=Path, required=True)
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--expect')
    args = parser.parse_args()
    url = urllib.parse.urlsplit(args.url)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise SystemExit('Use the approved HTTP or HTTPS invoke URL without embedded credentials, query or fragment.')
    token = args.token_file.read_text().strip()
    if not token or '\n' in token or '\r' in token or not 1 <= len(args.prompt) <= 8192:
        raise SystemExit('A single token and a prompt of 1 to 8192 characters are required.')
    payload = {'jsonrpc': '2.0', 'id': str(uuid.uuid4()), 'method': 'message/send', 'params': {
        'message': {'kind': 'message', 'messageId': str(uuid.uuid4()), 'contextId': str(uuid.uuid4()), 'role': 'user',
                    'parts': [{'kind': 'text', 'text': args.prompt}]}, 'configuration': {'blocking': True}}}
    code, body = transport.request(args.url, token, payload)
    if code != 200 or body.get('error'):
        raise SystemExit('Invocation failed. HTTP ' + str(code) + '. No automatic retry.')
    result = body.get('result', {})
    if result.get('status', {}).get('state') != 'completed' or not result.get('id') or not result.get('contextId'):
        raise SystemExit('The native task did not complete.')
    containers = result.get('artifacts', []) or [m for m in result.get('history', []) if m.get('role') == 'agent'][-1:]
    texts = [p['text'].strip() for m in containers for p in m.get('parts', []) if p.get('kind') == 'text' and isinstance(p.get('text'), str)]
    if not texts or (args.expect and args.expect not in texts):
        raise SystemExit('Expected assistant output is missing.')
    print('\n'.join(texts)[:12000])
    print(json.dumps({'taskID': result['id'], 'contextID': result['contextId'], 'responseSha256': transport.canonical(body), 'passed': True}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit('Invocation failed: ' + type(error).__name__ + '. No automatic retry.')
