"""Run negative authentication checks without invoking a model or retrying."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import urllib.error
import urllib.parse
import urllib.request
import uuid


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def token(path):
    path = Path(path)
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('Credential files must have mode 0600 or stricter.')
    value = path.read_text().strip()
    if not value or '\n' in value or '\r' in value:
        raise ValueError('Require one resolved credential per file.')
    return value


def probe(url, credential):
    parsed = urllib.parse.urlsplit(url)
    loopback = parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', '::1')
    if (parsed.scheme != 'https' and not loopback) or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use the exact HTTPS gateway or its loopback rehearsal forward.')
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    trace_id = uuid.uuid4().hex
    headers['traceparent'] = '00-' + trace_id + '-' + uuid.uuid4().hex[:16] + '-01'
    if credential:
        headers['Authorization'] = 'Bearer ' + credential
    payload = {'jsonrpc': '2.0', 'id': 'auth-probe', 'method': 'dice/authentication-probe', 'params': {}}
    request = urllib.request.Request(url, json.dumps(payload).encode(), headers)
    try:
        response = urllib.request.build_opener(NoRedirect()).open(request, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read(65537)
        if len(body) > 65536:
            raise ValueError('Probe response exceeded the bound.')
        return response.status, hashlib.sha256(body).hexdigest(), trace_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('a2a-url', 'mcp-url', 'caller-token', 'agent-token', 'wrong-caller-subject-token',
                 'wrong-agent-subject-token', 'wrong-audience-token'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--expired-caller-token')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = []
    for hop, url, wrong_subject, swapped in [
        ('caller', args.a2a_url, args.wrong_caller_subject_token, args.agent_token),
        ('agent', args.mcp_url, args.wrong_agent_subject_token, args.caller_token)]:
        cases = [('missing', None, 401), ('invalid', 'invalid.signature.token', 401),
                 ('wrong-audience', token(args.wrong_audience_token), 401),
                 ('wrong-subject', token(wrong_subject), 403), ('swapped', token(swapped), 401)]
        if hop == 'caller' and args.expired_caller_token:
            cases.append(('expired', token(args.expired_caller_token), 401))
        for name, credential, expected in cases:
            code, digest, trace_id = probe(url, credential)
            results.append({'hop': hop, 'case': name, 'httpStatus': code,
                            'expectedStatus': expected, 'responseSha256': digest,
                            'requestedTraceId': trace_id, 'passed': code == expected})
    receipt = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'cases': results,
               'allDeniedAsExpected': all(r['passed'] for r in results)}
    fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(receipt, output, indent=2)
    print(json.dumps(receipt, indent=2))
    if not receipt['allDeniedAsExpected']:
        raise SystemExit('Authentication denial gate failed.')


if __name__ == '__main__':
    main()
