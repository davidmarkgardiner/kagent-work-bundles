"""Metadata-only telemetry for actual demo-controller operations.

Each logical step owns a persisted caller context. Export is best effort and
never retries an operation or reconstructs history from workflow receipts.
"""
import http.client
import json
import os
from pathlib import Path
import queue
import re
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit


STEPS = frozenset(('triage_continuation', 'classification_followup', 'recheck_fault', 'prepare', 'inject_fault', 'observe_fault', 'classify', 'dispatch',
                   'triage', 'review', 'await_approval', 'merge', 'observe_merge',
                   'await_recovery', 'measure_recovery', 'verify', 'close'))
STATES = frozenset(('completed', 'pending', 'suppressed', 'blocked', 'unknown'))


def post(endpoint, signal, payload):
    parsed = urlsplit(endpoint)
    connection = (http.client.HTTPSConnection if parsed.scheme == 'https' else
                  http.client.HTTPConnection)(parsed.hostname, parsed.port, timeout=2)
    connected_socket, response = [None], None
    def abort():
        sock = connected_socket[0] or connection.sock
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        connection.close()
    deadline = threading.Timer(2, abort)
    deadline.daemon = True
    deadline.start()
    try:
        connection.request('POST', '/v1/' + signal, json.dumps(payload).encode(),
                           {'Content-Type': 'application/json'})
        connected_socket[0] = connection.sock
        response = connection.getresponse()
        if not 200 <= response.status < 300:
            raise OSError('OTLP export rejected')
        response.read(65537)
    finally:
        deadline.cancel()
        if response is not None:
            response.close()
        connection.close()


class FlowTelemetry:
    def __init__(self, endpoint='', *, transport=None, clock_ns=time.time_ns, queue_size=256):
        if endpoint:
            parsed = urlsplit(endpoint)
            if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.path not in {'', '/'} or parsed.query or parsed.fragment
                    or any(c.isspace() or ord(c) < 32 for c in endpoint)
                    or (parsed.port is not None and not 1 <= parsed.port <= 65535)):
                raise ValueError('A trusted OTLP origin without credentials is required')
        if type(queue_size) is not int or not 1 <= queue_size <= 256:
            raise ValueError('Invalid bounded telemetry queue')
        self.enabled = bool(endpoint)
        self._endpoint, self._transport, self._clock = endpoint.rstrip('/'), transport or post, clock_ns
        self._queue, self._lock, self._closed = queue.Queue(queue_size), threading.RLock(), threading.Event()
        self._counts = {'exported': 0, 'dropped': 0, 'failures': 0}
        self._thread = None
        if self.enabled:
            self._thread = threading.Thread(target=self._export, name='demo-otlp-export', daemon=True)
            self._thread.start()

    def _path(self, run, step):
        if step not in STEPS or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', run['runId']):
            raise ValueError('Invalid telemetry operation identity')
        workspace = Path(run['workspace'])
        if not workspace.is_absolute() or workspace.is_symlink() or not workspace.is_dir():
            raise ValueError('Existing private workspace required')
        path = workspace / ('.flow-telemetry-' + step + '.json')
        if path.is_symlink():
            raise ValueError('Invalid telemetry context path')
        return path

    def _read(self, path, run, step):
        if not path.exists():
            return None
        value = json.loads(path.read_text())
        if (value.get('runId') != run['runId'] or value.get('step') != step
                or not re.fullmatch(r'[0-9a-f]{32}', value.get('traceId', ''))
                or not int(value['traceId'], 16)
                or not re.fullmatch(r'[0-9a-f]{16}', value.get('spanId', ''))
                or not int(value['spanId'], 16) or type(value.get('started_ns')) is not int
                or value['started_ns'] < 1 or type(value.get('ended')) is not bool):
            raise ValueError('Invalid persisted telemetry context')
        return value

    @staticmethod
    def _write(path, value):
        temporary = path.with_name(path.name + '.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    def _enqueue(self, signal, value):
        if self._closed.is_set():
            return
        try:
            self._queue.put_nowait((signal, value))
        except queue.Full:
            self._counts['dropped'] += 1

    @staticmethod
    def _attributes(context, state):
        values = {'flow.run.id': context['runId'], 'flow.demo.step': context['step'],
                  'flow.demo.state': state, 'flow.evidence.source': 'demo-controller',
                  'flow.component': 'client', 'flow.workflow': 'kyverno-demo.' + context['step'],
                  'flow.result': state}
        return [{'key': key, 'value': {'stringValue': value}} for key, value in values.items()]

    @staticmethod
    def _resource():
        return {'attributes': [{'key': 'service.name', 'value': {'stringValue': 'kyverno-demo-controller'}}]}

    def _log(self, context, state, now):
        record = {'timeUnixNano': str(now), 'observedTimeUnixNano': str(now),
                  'traceId': context['traceId'], 'spanId': context['spanId'], 'flags': 1,
                  'severityNumber': 9, 'severityText': 'INFO',
                  'body': {'stringValue': 'Demo controller: ' + context['step'] + ' ' + state},
                  'attributes': self._attributes(context, state)}
        self._enqueue('logs', {'resourceLogs': [{'resource': self._resource(),
                      'scopeLogs': [{'scope': {'name': 'kyverno-demo-flow'}, 'logRecords': [record]}]}]})

    def begin(self, run, step):
        if not self.enabled or self._closed.is_set():
            return None
        with self._lock:
            path = self._path(run, step)
            context = self._read(path, run, step)
            if context is None:
                if run.get('_call', {}).get('mode') == 'observe':
                    return None
                context = {'runId': run['runId'], 'step': step, 'traceId': secrets.token_hex(16),
                           'spanId': secrets.token_hex(8), 'started_ns': self._clock(),
                           'ended': False, 'lastState': 'started'}
                self._write(path, context)
                self._log(context, 'started', context['started_ns'])
            if context['ended']:
                return None
            return '00-' + context['traceId'] + '-' + context['spanId'] + '-01'

    def observe(self, run, step, result=None, error=None):
        if not self.enabled or self._closed.is_set():
            return
        with self._lock:
            path = self._path(run, step)
            context = self._read(path, run, step)
            if context is None or context['ended']:
                return
            state = 'unknown' if error is not None else (result.get('status') if isinstance(result, dict)
                                                         else getattr(result, 'status', None))
            if state not in STATES:
                state = 'unknown'
            if state == context['lastState']:
                return
            now = max(context['started_ns'], self._clock())
            context.update(lastState=state, ended=state != 'pending')
            self._write(path, context)
            self._log(context, state, now)
            if not context['ended']:
                return
            span = {'traceId': context['traceId'], 'spanId': context['spanId'],
                    'name': 'demo.' + step, 'kind': 3, 'startTimeUnixNano': str(context['started_ns']),
                    'endTimeUnixNano': str(now), 'attributes': self._attributes(context, state),
                    'status': {'code': 2 if state in {'unknown', 'blocked'} else 1}}
            self._enqueue('traces', {'resourceSpans': [{'resource': self._resource(),
                          'scopeSpans': [{'scope': {'name': 'kyverno-demo-flow'}, 'spans': [span]}]}]})

    def _export(self):
        while not self._closed.is_set() or not self._queue.empty():
            try:
                signal, payload = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._transport(self._endpoint, signal, payload)
                with self._lock:
                    self._counts['exported'] += 1
            except Exception:
                with self._lock:
                    self._counts['failures'] += 1
            finally:
                self._queue.task_done()

    def snapshot(self):
        with self._lock:
            return {'enabled': self.enabled, 'queued': self._queue.qsize(), **self._counts}

    def close(self):
        self._closed.set()
        if self._thread:
            self._thread.join(timeout=3)
