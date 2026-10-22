"""One bounded MCP operation backed by a named Kubernetes ConfigMap GET."""
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import threading
import time
import urllib.request
import uuid

TOOL = 'get_demo_status'
LIMIT = 4096


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ValueError('RedirectDenied')


class KubernetesSource:
    def __init__(self, namespace, name, token_file, ca_file):
        if any(not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', x) for x in (namespace, name)):
            raise ValueError('InvalidSource')
        self.namespace, self.name, self.token = namespace, name, Path(token_file)
        self.url = 'https://kubernetes.default.svc/api/v1/namespaces/' + namespace + '/configmaps/' + name
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca_file)), NoRedirect())

    def __call__(self):
        request = urllib.request.Request(self.url, headers={'Authorization': 'Bearer ' + self.token.read_text().strip()})
        with self.opener.open(request, timeout=5) as response:
            data = response.read(16385)
        if len(data) > 16384:
            raise ValueError('SourceTooLarge')
        document = json.loads(data)
        meta = document['metadata']
        if document.get('kind') != 'ConfigMap' or meta['namespace'] != self.namespace or meta['name'] != self.name:
            raise ValueError('WrongSource')
        return document


class Capability:
    def __init__(self, source, export=None):
        self.source, self.export = source, export
        self.audit, self.lock = deque(maxlen=32), threading.Lock()

    def read(self, trace, parent):
        execution, span, start = uuid.uuid4().hex, uuid.uuid4().hex[:16], time.time_ns()
        event = {'executionId': execution, 'traceId': trace, 'spanId': span, 'startedNs': str(start), 'result': 'failed'}
        try:
            document = self.source()
            data, meta = document['data'], document['metadata']
            if (not isinstance(data, dict) or not isinstance(meta, dict)
                    or data.get('status') not in {'available', 'blocked'}
                    or not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', data.get('caseCode', ''))
                    or not re.fullmatch(r'[a-f0-9]{32}', data.get('evidenceCode', ''))
                    or not re.fullmatch(r'[A-Za-z0-9-]{1,64}', meta.get('uid', ''))
                    or not re.fullmatch(r'[0-9]{1,24}', meta.get('resourceVersion', ''))):
                raise ValueError('InvalidSourceData')
            result = {key: data[key] for key in ('status', 'caseCode', 'evidenceCode')}
            result.update(sourceUID=meta['uid'], resourceVersion=meta['resourceVersion'], executionId=execution)
            if len(encoded(result)) > 1024:
                raise ValueError('ResultTooLarge')
            event.update(result='passed', resultSha256=hashlib.sha256(encoded(result)).hexdigest(),
                         sourceUID=meta['uid'], resourceVersion=meta['resourceVersion'])
            return result
        finally:
            event['endedNs'] = str(time.time_ns())
            if self.export:
                try:
                    event['telemetryOutcome'] = 'exported' if self.export(event, parent) else 'unavailable'
                except Exception:
                    # Telemetry is a separate I/O boundary and must not replace a read result.
                    event['telemetryOutcome'] = 'unavailable'
            with self.lock:
                self.audit.append(event)

    def events(self):
        with self.lock:
            return list(self.audit)


def export_event(event, parent):
    values = {'flow.component': 'mcp', 'flow.tool.system': 'Kubernetes MCP: synthetic status', 'flow.simulated': False,
              'flow.evidence.source': 'mcp-handler',
              'mcp.tool.name': TOOL, 'gen_ai.tool.name': TOOL, 'flow.execution.id': event['executionId']}
    attributes = [{'key': k, 'value': {'boolValue': v} if type(v) is bool else {'stringValue': v}}
                  for k, v in values.items()]
    payload = {'resourceSpans': [{'resource': {'attributes': [
        {'key': 'service.name', 'value': {'stringValue': 'onboarding-status-mcp'}}]}, 'scopeSpans': [{'spans': [{
            'traceId': event['traceId'], 'spanId': event['spanId'], 'parentSpanId': parent,
            'name': 'MCP ' + TOOL, 'kind': 2, 'startTimeUnixNano': event['startedNs'], 'endTimeUnixNano': event['endedNs'],
            'status': {'code': 1 if event['result'] == 'passed' else 2}, 'attributes': attributes}]}]}]}
    try:
        request = urllib.request.Request(os.environ['OTEL_HTTP_ENDPOINT'] + '/v1/traces', encoded(payload),
                                         {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=3) as response:
            response.read(1024)
        return True
    except (KeyError, OSError, ValueError):
        print('MCP telemetry export unavailable', flush=True)
        return False


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *_args):
        pass

    def reply(self, code, value=None):
        data = encoded(value) if value is not None else b''
        if len(data) > LIMIT:
            code, data = 500, b'{"error":"EnvelopeTooLarge"}'
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/healthz':
            return self.reply(200, {'mode': 'live-read-only-single-configmap'})
        if self.path == '/audit':
            if self.client_address[0] not in {'127.0.0.1', '::1'}:
                return self.reply(403, {'error': 'LocalEvidenceReaderOnly'})
            return self.reply(200, {'events': self.server.capability.events()[-8:]})
        self.reply(405 if self.path == '/mcp' else 404)

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if self.path != '/mcp' or not 0 < length <= LIMIT:
                return self.reply(400, {'error': 'InvalidRequest'})
            self.connection.settimeout(5)
            request = json.loads(self.rfile.read(length))
            if (not isinstance(request, dict) or request.get('jsonrpc') != '2.0'
                    or not isinstance(request.get('params', {}), dict)
                    or len(encoded(request.get('id'))) > 80):
                raise ValueError('InvalidRequest')
            method, params, request_id = request.get('method'), request.get('params', {}), request.get('id')
            if method == 'notifications/initialized' and 'id' not in request:
                return self.reply(202)
            if 'id' not in request or type(request_id) not in (str, int):
                raise ValueError('InvalidRequest')
        except (ValueError, TypeError, OSError):
            return self.reply(400, {'error': 'InvalidRequest'})
        if method == 'initialize':
            version = params.get('protocolVersion')
            if not isinstance(version, str) or version not in {'2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25'}:
                return self.reply(200, {'jsonrpc': '2.0', 'id': request_id, 'error': {'code': -32602, 'message': 'UnsupportedProtocol'}})
            result = {'protocolVersion': version, 'capabilities': {'tools': {}},
                      'serverInfo': {'name': 'onboarding-status-read-only', 'version': '1.0'}}
        elif method == 'tools/list':
            result = {'tools': [{'name': TOOL, 'description': 'Read one fixed synthetic Kubernetes onboarding-status record.',
                'annotations': {'readOnlyHint': True}, 'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}}]}
        elif method == 'ping':
            result = {}
        elif method == 'tools/call':
            if params.get('name') != TOOL or params.get('arguments', {}) != {}:
                result = {'content': [{'type': 'text', 'text': 'Only the fixed no-argument read is permitted.'}], 'isError': True}
            else:
                # The pooled legacy MCP transport can retain an earlier task's context.
                # Export an independent root; the runner joins by the returned execution ID.
                trace, parent = uuid.uuid4().hex, ''
                try:
                    value = self.server.capability.read(trace, parent)
                    result = {'content': [{'type': 'text', 'text': encoded(value).decode()}], 'isError': False}
                except (ValueError, OSError, KeyError, TypeError):
                    result = {'content': [{'type': 'text', 'text': 'The fixed Kubernetes read failed.'}], 'isError': True}
        else:
            return self.reply(200, {'jsonrpc': '2.0', 'id': request_id, 'error': {'code': -32601, 'message': 'UnsupportedMethod'}})
        self.reply(200, {'jsonrpc': '2.0', 'id': request_id, 'result': result})


if __name__ == '__main__':
    source = KubernetesSource(os.environ['POD_NAMESPACE'], os.environ['STATUS_CONFIGMAP'],
        '/var/run/secrets/kubernetes.io/serviceaccount/token', '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')
    server = ThreadingHTTPServer(('0.0.0.0', 8084), Handler)
    server.capability = Capability(source, export_event)
    server.serve_forever()
