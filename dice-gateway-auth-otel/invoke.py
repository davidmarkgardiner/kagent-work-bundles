"""Send one protected A2A request and retain its native response privately."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import urllib.error
import urllib.parse
import urllib.request
import uuid


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--token-file', type=Path, required=True)
    parser.add_argument('--receipt-file', type=Path, required=True)
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--expect')
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--allow-loopback-http', action='store_true', help='Loopback gateway rehearsal only')
    args = parser.parse_args()
    url = urllib.parse.urlsplit(args.url)
    fixture = args.allow_loopback_http and url.scheme == 'http' and url.hostname in ('127.0.0.1', '::1')
    if (url.scheme != 'https' and not fixture) or not url.hostname or url.username or url.password or url.query or url.fragment or '{{' in args.url:
        raise ValueError('Use the exact approved HTTPS A2A URL without embedded credentials, query or fragment.')
    if not 1 <= len(args.prompt) <= 8192 or not 1 <= args.timeout <= 180:
        raise ValueError('Use a prompt of 1 to 8192 characters and timeout of 1 to 180 seconds.')
    if stat.S_IMODE(args.token_file.stat().st_mode) & 0o077:
        raise ValueError('The private token file must have mode 0600 or stricter.')
    token = args.token_file.read_text().strip()
    if not token or '\n' in token or '\r' in token or '{{' in token:
        raise ValueError('The token file must contain one resolved credential.')
    receipt = args.receipt_file.resolve()
    if receipt.is_relative_to(Path(__file__).resolve().parent):
        raise ValueError('Keep native receipts outside this public bundle.')
    payload = {'jsonrpc': '2.0', 'id': str(uuid.uuid4()), 'method': 'message/send', 'params': {
        'message': {'kind': 'message', 'messageId': str(uuid.uuid4()), 'contextId': str(uuid.uuid4()),
                    'role': 'user', 'parts': [{'kind': 'text', 'text': args.prompt}]},
        'configuration': {'blocking': True}}}
    requested_trace = uuid.uuid4().hex
    req = urllib.request.Request(args.url, json.dumps(payload).encode(),
                                 {'Content-Type': 'application/json', 'Accept': 'application/json',
                                  'Authorization': 'Bearer ' + token,
                                  'traceparent': '00-' + requested_trace + '-' + uuid.uuid4().hex[:16] + '-01'})
    fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as saved:
        try:
            response = urllib.request.build_opener(NoRedirect()).open(req, timeout=args.timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise ValueError('Response exceeded 1 MiB. No automatic paging or retry.')
            saved.write(raw)
            code = response.status
    if code != 200:
        raise ValueError('Invocation returned HTTP ' + str(code) + '. Inspect the private receipt. No retry.')
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError('Response is not a native JSON-RPC object.')
    if body.get('error'):
        raise ValueError('JSON-RPC error. Inspect the private receipt. No retry.')
    task = body.get('result', {})
    if (not isinstance(task, dict) or task.get('status', {}).get('state') != 'completed'
            or not all(isinstance(task.get(key), str) and task[key] for key in ('id', 'contextId'))):
        raise ValueError('The native task did not complete. Do not resubmit to poll it.')
    artifacts = [p['text'] for a in task.get('artifacts', []) for p in a.get('parts', [])
                 if p.get('kind') == 'text' and isinstance(p.get('text'), str)]
    history = ['\n'.join(p['text'] for p in m.get('parts', [])
                         if p.get('kind') == 'text' and isinstance(p.get('text'), str))
               for m in task.get('history', []) if m.get('role') == 'agent']
    text = '\n'.join(artifacts) if artifacts else next((v for v in reversed(history) if v.strip()), '')
    text = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.S).strip()
    if not text or (args.expect is not None and text != args.expect):
        raise ValueError('Expected assistant output is missing. Retain the receipt and inspect the cause.')
    print(text[:12000] + ('\n[Display truncated. Private receipt retained.]' if len(text) > 12000 else ''))
    print(json.dumps({'taskId': task['id'], 'contextId': task['contextId'], 'taskCompleted': True,
                      'requestedTraceId': requested_trace,
                      'expectedReplyMatched': True if args.expect is not None else None,
                      'responseSha256': hashlib.sha256(raw).hexdigest(), 'receiptFile': str(receipt)}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        raise SystemExit('Invocation stopped: ' + message)
