"""Loopback dashboard control bridge with exact-head human approval."""
import argparse
from collections import OrderedDict
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit, parse_qs
from urllib.request import urlopen
import uuid

from flow_controller import FlowController, FlowError, ApprovalConflict, ApprovalUnknown, ResumeConflict
from lab_adapter import LabAdapter
from demo_flow import build_demo_flow
from core import endpoint


ASSETS = {'/': 'index.html', '/index.html': 'index.html', '/app.js': 'app.js',
          '/demo.js': 'demo.js', '/style.css': 'style.css', '/logs.css': 'logs.css',
          '/favicon.svg': 'favicon.svg'}
MIME = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml'}


def make_handler(controller, assets, upstream, authority, nonce):
    adapter = getattr(controller, 'adapter', None)
    configured_api = endpoint(getattr(adapter, 'base', {}).get('gitlab_api', 'https://gitlab.com/api/v4'))
    if '\\' in configured_api or any(ord(char) < 32 or ord(char) == 127 for char in configured_api):
        raise ValueError('Invalid configured GitLab endpoint')
    gitlab = urlsplit(configured_api)
    if '@' in gitlab.netloc or gitlab.port is not None and not 1 <= gitlab.port <= 65535:
        raise ValueError('Invalid configured GitLab authority')
    gitlab_origin = gitlab.scheme + '://' + gitlab.netloc
    log_cache = {'at': 0, 'revision': None, 'value': None}
    cache_lock = threading.Lock()
    viewer_arrivals = OrderedDict()

    def budget_state(force=False):
        adapter = getattr(controller, 'adapter', None)
        read = getattr(adapter, 'budget_state', None)
        if not callable(read):
            return None
        try:
            value = read(force=True) if force else read()
            return value if isinstance(value, dict) else {'available': False, 'reason': 'Model budget is unverified.'}
        except Exception:
            return {'available': False, 'reason': 'Model budget is unavailable.'}

    def budget_blocked(value):
        if value is None:
            return False
        return (value.get('available') is not True or value.get('enabled') is False
                or any(isinstance(value.get(k), (int, float)) and value[k] <= 0
                       for k in ('requestsRemaining', 'inputBytesRemaining')))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, value, content_type='application/json'):
            body = json.dumps(value).encode() if content_type == 'application/json' else value
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def local(self):
            return self.client_address[0] == '127.0.0.1' and self.headers.get('Host') == authority

        def upstream_json(self, path):
            with urlopen(upstream + path, timeout=5) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError('Receiver response exceeds limit')
            return json.loads(raw)

        def do_GET(self):
            if not self.local():
                return self.send(403, {'error': 'Loopback host required'})
            parsed = urlsplit(self.path)
            if parsed.path == '/api/state' and not parsed.query:
                try:
                    value = self.upstream_json('/api/state')
                except Exception:
                    value = {'traces': [], 'logs': [], 'revision': 0, 'receiverConnected': False,
                             'invocation': {'status': 'idle'}, 'sessionActivity': None, 'nativeActivities': {},
                             'runtime': {'readOnlyViewer': True, 'executionTargets': [],
                                         'label': 'OTel receiver unavailable'}}
                value['receiverConnected'] = value.get('receiverConnected', True)
                demo = dict(controller.public_state(), csrf=nonce, gitlabOrigin=gitlab_origin)
                read_context = getattr(controller, 'evidence_context', None)
                context = read_context() if callable(read_context) else {'runId': demo.get('runId'), 'tasks': {}}
                revision = value.get('revision')
                with cache_lock:
                    if time.monotonic() - log_cache['at'] >= 0.75 or log_cache['revision'] != revision:
                        try:
                            logs = self.upstream_json('/api/logs')
                            if not isinstance(logs, dict) or not isinstance(logs.get('logs'), list):
                                raise ValueError('Invalid metadata log feed')
                            records = []
                            for record in logs['logs'][:200]:
                                if not isinstance(record, dict):
                                    continue
                                record = dict(record)
                                identity = record.get('id')
                                if isinstance(identity, str) and len(identity) <= 64 and not record.get('receivedAt'):
                                    if identity not in viewer_arrivals:
                                        viewer_arrivals[identity] = time.time()
                                    record['viewerReceivedAt'] = viewer_arrivals[identity]
                                records.append(record)
                            while len(viewer_arrivals) > 1000:
                                viewer_arrivals.popitem(last=False)
                            logs = dict(logs, logs=records)
                        except Exception:
                            logs = None
                        log_cache.update(at=time.monotonic(), revision=revision, value=logs)
                    logs = log_cache['value']
                demo['flow'] = build_demo_flow(demo, value, logs, context)
                for role, field in (('triage', 'native'), ('merge', 'merge'), ('verify', 'verification')):
                    task_traces = demo['flow']['tasks'][role]['traceIds']
                    if isinstance(demo.get(field), dict):
                        demo[field]['traceId'] = task_traces[0] if len(task_traces) == 1 else None
                if demo.get('phase') in {'blocked', 'unknown'} or any(demo.get('actions', {}).get(name, {}).get('enabled') for name in ('start', 'resume')):
                    budget = budget_state()
                    demo['budget'] = budget
                    if budget_blocked(budget):
                        reason = budget.get('reason') or 'The existing model budget is exhausted or unavailable.'
                        for name in ('start', 'resume'):
                            if demo.get('actions', {}).get(name, {}).get('enabled'):
                                demo['actions'][name] = {'enabled': False, 'reason': reason}
                        if demo.get('phase') == 'blocked':
                            demo['actions']['start']['reason'] = 'This incident is stopped. ' + reason
                budget = demo.get('budget')
                if isinstance(budget,dict) and budget.get('boundRunId') is not None:
                    reason = 'This allowance is reserved for the existing incident; another demo requires a separate allowance.'
                    demo.setdefault('actions',{})['start'] = {'enabled':False,'reason':reason}
                    if budget['boundRunId'] != demo.get('runId'):
                        demo['actions']['resume'] = {'enabled':False,'reason':reason}
                value['demo'] = demo
                return self.send(200, value)
            if parsed.path == '/api/logs':
                params = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
                if set(params) - {'traceId', 'service'} or any(len(v) != 1 or len(v[0]) > 160 for v in params.values()):
                    return self.send(400, {'error': 'Unsupported log filter'})
                try:
                    return self.send(200, self.upstream_json(self.path))
                except Exception:
                    return self.send(503, {'error': 'Read-only receiver unavailable'})
            if parsed.query or parsed.path not in ASSETS:
                return self.send(404, {'error': 'Unknown endpoint'})
            path = assets / ASSETS[parsed.path]
            return self.send(200, path.read_bytes(), MIME[path.suffix])

        def do_POST(self):
            if (not self.local() or self.headers.get('Origin') != 'http://' + authority
                    or not hmac.compare_digest(self.headers.get('X-Demo-CSRF', ''), nonce)):
                return self.send(403, {'error': 'Same-origin control token required'})
            if self.path not in {'/api/demo/start', '/api/demo/approve', '/api/demo/resume'}:
                return self.send(404, {'error': 'Unknown endpoint'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if self.headers.get('Transfer-Encoding') or not 1 <= length <= 1024 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError()
                body = json.loads(self.rfile.read(length))
                fields = {'/api/demo/start': {'requestId'}, '/api/demo/resume': {'requestId', 'runId'}, '/api/demo/approve': {'requestId', 'runId', 'headSha'}}[self.path]
                if type(body) is not dict or set(body) != fields or str(uuid.UUID(body['requestId'])) != body['requestId']:
                    raise ValueError()
                if self.path == '/api/demo/start':
                    budget = budget_state()
                    if isinstance(budget,dict) and budget.get('boundRunId') is not None:
                        return self.send(409, {'error':'This allowance is reserved for the existing incident; another demo requires a separate allowance.'})
                    if budget_blocked(budget):
                        return self.send(409, {'error': 'Start is blocked by the existing model budget; no new fault was created.'})
                    result = controller.start(body['requestId'])
                elif self.path == '/api/demo/resume':
                    result = controller.resume_readback(body['requestId'], body['runId'])
                    if result is None:
                        budget = budget_state(force=True)
                        if isinstance(budget,dict) and budget.get('boundRunId') is not None and budget['boundRunId'] != body['runId']:
                            return self.send(409, {'error':'This allowance is reserved for another incident; no operation was repeated.'})
                        if budget_blocked(budget):
                            return self.send(409, {'error': 'This incident is stopped. Resume requires a separately authorized available model allowance; no operation was repeated.'})
                        result = controller.resume_fault(body['requestId'], body['runId'])
                else:
                    result = controller.approve(body['requestId'], body['runId'], body['headSha'])
            except ResumeConflict as error:
                return self.send(409, {'error': str(error)})
            except ApprovalConflict:
                return self.send(409, {'error': 'The active reviewed commit no longer matches this approval'})
            except ApprovalUnknown:
                return self.send(502, {'error': 'Approval outcome is unknown; read back the original grant before continuing'})
            except (ValueError, TypeError, KeyError, AttributeError, FlowError):
                return self.send(400, {'error': 'A canonical requestId and exact endpoint fields are required'})
            return self.send(202, {'demo': result})

        def do_OPTIONS(self):
            self.send(405, {'error': 'Cross-origin control is unavailable'})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', required=True)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--upstream', default='http://127.0.0.1:8792')
    parser.add_argument('--port', type=int, default=8791)
    args = parser.parse_args()
    if urlsplit(args.upstream).hostname != '127.0.0.1':
        parser.error('Upstream must use loopback')
    args.data.mkdir(parents=True, exist_ok=True, mode=0o700)
    adapter = LabAdapter(args.settings)
    scope = {k: adapter.settings[k] for k in ('namespace', 'target_branch', 'project_id')}
    telemetry = None
    endpoint = adapter.settings.get('controller_otlp_endpoint', '')
    if endpoint:
        from flow_telemetry import FlowTelemetry
        telemetry = FlowTelemetry(endpoint)
    controller = FlowController(args.data / 'flow.sqlite', adapter, scope,
                                closure_verifier=adapter.closure_verifier, telemetry=telemetry)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(
        controller, args.assets, args.upstream.rstrip('/'), '127.0.0.1:' + str(args.port), secrets.token_urlsafe(32)))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        try:
            controller.close(timeout=5)
        finally:
            if telemetry is not None:
                telemetry.close()


if __name__ == '__main__':
    main()
