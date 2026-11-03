"""Bounded client trace-context probe and metadata-only Tempo lookup. No token or body output."""
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import ssl
import stat
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
MAX_RESPONSE = 2 * 1024 * 1024
SAFE = {'gateway', 'listener', 'route', 'http.method', 'http.request.method', 'http.status',
        'http.status_code', 'http.response.status_code', 'gen_ai.operation.name',
        'gen_ai.request.model', 'gen_ai.response.model', 'gen_ai.tool.name', 'mcp.method.name',
        'mcp.tool.name', 'gen_ai.usage.input_tokens', 'gen_ai.usage.output_tokens',
        'gen_ai.conversation.id', 'a2a.task.id', 'platform.demo.profile'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def origin(value, allow_http=False):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme not in (['https', 'http'] if allow_http else ['https']) or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('Use an approved HTTPS endpoint without credentials, query or fragment; explicitly approve HTTP if needed')
    return value.rstrip('/')


def credential(path):
    if path is None:
        return None
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077 or metadata.st_size > 16384:
        raise ValueError('Credential file must be a private regular file, mode 0600 or narrower')
    value = path.read_text().strip()
    if not value or '\r' in value or '\n' in value:
        raise ValueError('Invalid credential file')
    return value


def exchange(url, method, headers, data=None, ca_file=None):
    context = ssl.create_default_context(cafile=str(ca_file) if ca_file else None)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                        urllib.request.HTTPSHandler(context=context))
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        response = opener.open(request, timeout=115)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError('Response exceeds the bounded probe limit')
        return response.code, raw


def canonical_id(value, size):
    if not isinstance(value, str):
        raise ValueError('Missing trace/span identifier')
    if re.fullmatch('[0-9a-fA-F]{' + str(size * 2) + '}', value):
        raw = bytes.fromhex(value)
    else:
        raw = base64.b64decode(value, validate=True)
    if len(raw) != size or not any(raw):
        raise ValueError('Invalid trace/span identifier')
    return raw.hex()


def attributes(items):
    result = {}
    for item in items[:128]:
        if item.get('key') not in SAFE | {'service.name'}:
            continue
        for key, value in item.get('value', {}).items():
            if key in ('stringValue', 'intValue', 'doubleValue', 'boolValue') and isinstance(value, (str, int, float, bool)):
                if isinstance(value, float) and not math.isfinite(value):
                    continue
                result[item['key']] = value[:256] if isinstance(value, str) else value
    return result


def project_trace(document, trace_id, expected_service):
    trace_id = canonical_id(trace_id, 16)
    if isinstance(document.get('trace'), dict):
        document = document['trace']
    batches = document.get('resourceSpans', document.get('batches'))
    if not isinstance(batches, list):
        raise ValueError('Unknown Tempo JSON envelope; adapt to the actual API instead of fabricating spans')
    spans = []
    observed_service = False
    for batch in batches:
        service = attributes(batch.get('resource', {}).get('attributes', [])).get('service.name')
        scopes = batch.get('scopeSpans', batch.get('instrumentationLibrarySpans', []))
        for scope in scopes:
            for span in scope.get('spans', []):
                if len(spans) >= 1000:
                    raise ValueError('Trace exceeds the span limit')
                observed_id = canonical_id(span.get('traceId'), 16)
                if observed_id != trace_id:
                    raise ValueError('Tempo response does not match the requested trace')
                parent = span.get('parentSpanId')
                if parent and parent not in ('0' * 16, 'AAAAAAAAAAA='):
                    parent = canonical_id(parent, 8)
                else:
                    parent = None
                start, end = span.get('startTimeUnixNano'), span.get('endTimeUnixNano')
                duration = None
                if start is not None or end is not None:
                    if (not all(isinstance(value, (str, int)) and not isinstance(value, bool)
                                and re.fullmatch(r'\d{1,20}', str(value)) for value in (start, end))
                            or not 0 <= int(start) <= int(end) < 2 ** 64):
                        raise ValueError('Invalid observed span timestamps')
                    start, end = str(start), str(end)
                    duration = int(end) - int(start)
                spans.append({'traceId': observed_id, 'spanId': canonical_id(span.get('spanId'), 8),
                    'parentSpanId': parent, 'serviceName': service,
                    'startTimeUnixNano': start, 'endTimeUnixNano': end, 'durationNanoseconds': duration,
                    'attributes': attributes(span.get('attributes', []))})
                observed_service |= service == expected_service
    if not spans or not observed_service:
        raise ValueError('Requested Gateway service was not observed in this trace')
    return {'traceId': trace_id, 'expectedServiceObserved': True, 'spans': spans,
            'limit': 'Observed Tempo metadata only. This does not prove complete workflow ancestry, denial side effects, metrics or log export.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    probe = commands.add_parser('request')
    probe.add_argument('--url', required=True)
    probe.add_argument('--payload', required=True, type=Path)
    probe.add_argument('--token-file', type=Path)
    probe.add_argument('--expected-status', required=True, type=int)
    lookup = commands.add_parser('trace')
    lookup.add_argument('--tempo-url', required=True)
    lookup.add_argument('--trace-id', required=True)
    lookup.add_argument('--expected-service', required=True)
    lookup.add_argument('--auth-file', type=Path)
    lookup.add_argument('--tenant')
    for command in (probe, lookup):
        command.add_argument('--ca-file', type=Path)
        command.add_argument('--allow-http', action='store_true')
        command.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output == ROOT or ROOT in output.parents:
        parser.error('Use a new private output file outside the amendment source')
    headers = {'Accept': 'application/json'}
    if args.command == 'request':
        url = origin(args.url, args.allow_http)
        with args.payload.open('rb') as stream:
            raw = stream.read(16385)
        if len(raw) > 16384 or not isinstance(json.loads(raw), dict):
            raise ValueError('Use a bounded reviewed JSON object payload')
        trace_id, span_id = secrets.token_hex(16), secrets.token_hex(8)
        headers.update({'Content-Type': 'application/json', 'traceparent': '00-' + trace_id + '-' + span_id + '-01'})
        token = credential(args.token_file)
        if token:
            headers['Authorization'] = 'Bearer ' + token
        started = time.time_ns()
        status, response = exchange(url, 'POST', headers, raw, args.ca_file)
        result = {'kind': 'client-probe-not-workflow-proof', 'targetOutcome': 'unverified',
            'requestedTraceId': trace_id, 'requestedParentSpanId': span_id,
            'startedUnixNano': started, 'endedUnixNano': time.time_ns(),
            'status': status, 'expectedStatus': args.expected_status, 'matchedExpectedStatus': status == args.expected_status,
            'responseBytes': len(response), 'responseSha256': hashlib.sha256(response).hexdigest(),
            'note': 'Requested trace context is not an observed Gateway span. Retrieve real trace and backend evidence separately.'}
        passed = status == args.expected_status
    else:
        trace_id = canonical_id(args.trace_id, 16)
        url = origin(args.tempo_url, args.allow_http) + '/api/traces/' + trace_id
        token = credential(args.auth_file)
        if token:
            headers['Authorization'] = 'Bearer ' + token
        if args.tenant:
            if len(args.tenant) > 200 or any(c in args.tenant for c in '\r\n'):
                raise ValueError('Invalid approved Tempo tenant')
            headers['X-Scope-OrgID'] = args.tenant
        status, response = exchange(url, 'GET', headers, ca_file=args.ca_file)
        if status == 200:
            result = project_trace(json.loads(response), trace_id, args.expected_service)
            result.update(kind='tempo-observation', targetOutcome='unverified', queryStatus=status)
            passed = True
        else:
            result = {'kind': 'tempo-observation', 'targetOutcome': 'unverified', 'traceId': trace_id,
                'queryStatus': status, 'observed': False,
                'reason': 'not-observed' if status == 404 else 'query-unavailable-or-access-blocked',
                'note': 'Missing telemetry is not a pass. No automatic retry or alternate provider.'}
            passed = False
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    output.chmod(0o600)
    print(json.dumps({'receiptWritten': True, 'matchedProbeOrObservedTrace': passed, 'targetOutcome': 'unverified'}))
    return 0 if passed else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, urllib.error.URLError) as error:
        print(json.dumps({'error': type(error).__name__, 'reason': str(error) if isinstance(error, ValueError) else 'Probe input or network operation failed; inspect the approved private context',
                          'targetOutcome': 'unverified', 'receiptWritten': False}))
        raise SystemExit(2)
