"""Bounded, call-time authorization front door for the secure BYO rehearsal."""
import argparse
import contextlib
import datetime as dt
import hashlib
import http.server
import http.client
import json
import os
import selectors
import signal
import socket
import subprocess
import tempfile
from pathlib import Path
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BODY_TIMEOUT = 5
REQUEST_TIMEOUT = 105
MAX_REQUEST = 16384
MAX_RESPONSE = 1048576
GOLDEN_SCHEMA = 'native-golden/v1'
GOLDEN_SCOPE = 'native-kagent-reviewed-skills-and-fixed-mcp'
TOOL = {'name': 'get_demo_status', 'description': 'Read a bounded synthetic status for this agent only.',
        'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}}


class Denied(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp required')
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result.timestamp()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def before_deadline(deadline):
    if time.monotonic() >= deadline:
        raise Denied(504, 'RequestDeadlineExceeded')


def post_json(url, payload, headers, deadline, ca_file=None, before_dispatch=None):
    done, cancelled = threading.Event(), threading.Event()
    result, sockets = {}, []
    def abort():
        for sock in list(sockets):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
    def request():
        connection = None
        try:
            target = urllib.parse.urlsplit(url)
            remaining = max(0.001, deadline - time.monotonic())
            if target.scheme == 'https':
                connection = http.client.HTTPSConnection(target.hostname, target.port,
                    timeout=remaining, context=ssl.create_default_context(cafile=ca_file))
            elif target.scheme == 'http':
                connection = http.client.HTTPConnection(target.hostname, target.port, timeout=remaining)
            else:
                raise Denied(503, 'InvalidUpstream')
            connection.connect()
            sockets.append(connection.sock)
            before_deadline(deadline)
            if cancelled.is_set():
                raise Denied(504, 'RequestDeadlineExceeded')
            if before_dispatch:
                before_dispatch()
            before_deadline(deadline)
            if cancelled.is_set():
                raise Denied(504, 'RequestDeadlineExceeded')
            connection.sock.settimeout(max(0.001, deadline - time.monotonic()))
            connection.request('POST', target.path or '/', json.dumps(payload).encode(), headers)
            response = connection.getresponse()
            if response.status != 200:
                raise Denied(502, 'UpstreamRejected')
            data = bytearray()
            while not response.isclosed():
                before_deadline(deadline)
                sockets[0].settimeout(max(0.001, deadline - time.monotonic()))
                chunk = response.read1(min(8192, MAX_RESPONSE + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_RESPONSE:
                    raise Denied(502, 'UpstreamResponseTooLarge')
            before_deadline(deadline)
            result['value'] = json.loads(data)
        except Exception as error:
            result['error'] = error if isinstance(error, Denied) else Denied(502, 'UpstreamUnavailable')
        finally:
            if connection:
                connection.close()
            done.set()
    worker = threading.Thread(target=request, daemon=True)
    worker.start()
    if not done.wait(max(0, deadline - time.monotonic())):
        cancelled.set()
        abort()
        raise Denied(504, 'RequestDeadlineExceeded')
    if 'error' in result:
        raise result['error']
    before_deadline(deadline)
    return result['value']


class Kubernetes:
    def __init__(self, token_file='/var/run/secrets/kubernetes.io/serviceaccount/token',
                 ca_file='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'):
        self.url = 'https://' + os.environ['KUBERNETES_SERVICE_HOST'] + ':' + os.environ.get('KUBERNETES_SERVICE_PORT', '443')
        self.token_file = token_file
        self.context = ssl.create_default_context(cafile=ca_file)

    def call(self, path, value=None):
        headers = {'Authorization': 'Bearer ' + Path(self.token_file).read_text().strip(), 'Content-Type': 'application/json'}
        req = urllib.request.Request(self.url + path, None if value is None else json.dumps(value).encode(), headers)
        with urllib.request.urlopen(req, context=self.context, timeout=3) as response:
            body = response.read(262145)
        if len(body) > 262144:
            raise ValueError('authority response too large')
        return json.loads(body)


class Authority:
    def __init__(self, kube, config, clock=time.time):
        self.kube, self.config, self.clock = kube, config, clock
        self.started_at = clock()
        for key in ('namespace', 'agentName', 'approvalName'):
            if not isinstance(config.get(key), str) or not config[key] or '/' in config[key]:
                raise ValueError('invalid ' + key)
        self.require_golden = config.get('requireGoldenProof', False)
        if type(self.require_golden) is not bool:
            raise ValueError('invalid Golden profile')
        if self.require_golden:
            if (config.get('verifierSubject') != 'system:serviceaccount:secure-byo-kro:approved-verifier'
                    or config['namespace'] != 'secure-byo-kro' or config['agentName'] != 'demo'
                    or config['request'] != {'apiVersion': 'kro.run/v1alpha1', 'plural': 'secureagents', 'name': 'demo'}
                    or set(config.get('dependencyNames', {})) != {'agenttemplates', 'harnesses', 'modelconfigs', 'remotemcpservers'}):
                raise ValueError('invalid bounded native Golden profile')
            for key, expected in {'agenttemplates': 'demo-template', 'harnesses': 'approved-harness',
                                  'remotemcpservers': 'approved-mcp'}.items():
                if config['dependencyNames'][key] != expected:
                    raise ValueError('invalid bounded native dependency')
            if any(not isinstance(name, str) or not name or '/' in name
                   for name in config['dependencyNames'].values()):
                raise ValueError('invalid native dependency name')
            for key, default, ceiling in [('modelCalls', 24, 64), ('mcpCalls', 4, 16), ('invocations', 1, 1)]:
                value = config.get('verificationBudgets', {}).get(key, default)
                if type(value) is not int or not 1 <= value <= ceiling:
                    raise ValueError('invalid verification budget')
        elif config.get('verifierSubject'):
            raise ValueError('verifier requires Golden proof')
        request = config['request']
        if (not isinstance(request['apiVersion'], str) or request['apiVersion'].count('/') != 1
                or any('/' in request[k] or not request[k] for k in ('plural', 'name'))):
            raise ValueError('invalid request reference')
        for field in ('upstreamURL', 'upstreamModelURL'):
            if config.get(field):
                url = urllib.parse.urlsplit(config[field])
                if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
                    raise ValueError('invalid fixed upstream')
        if config.get('upstreamModelKeyFile') and not Path(config['upstreamModelKeyFile']).is_absolute():
            raise ValueError('absolute model key path required')

    def authorize(self, header, lane, details=False):
        if not header or not header.startswith('Bearer ') or not header[7:] or len(header) > 16384:
            raise Denied(401, 'BearerRequired')
        try:
            review = self.kube.call('/apis/authentication.k8s.io/v1/tokenreviews', {
                'apiVersion': 'authentication.k8s.io/v1', 'kind': 'TokenReview',
                'spec': {'token': header[7:], 'audiences': ['secure-byo']}})['status']
            username = review.get('user', {}).get('username', '')
            if (review.get('authenticated') is not True or review.get('error')
                    or 'secure-byo' not in review.get('audiences', [])
                    or not username.startswith('system:serviceaccount:')):
                raise Denied(401, 'TokenRejected')
            ns = self.config['namespace']
            cm = self.kube.call(f'/api/v1/namespaces/{ns}/configmaps/{self.config["approvalName"]}')
            if cm['metadata'].get('deletionTimestamp'):
                raise Denied(403, 'ApprovalDeleting')
            record = json.loads(cm['data']['approval.json'])
            state = record['state']
            if state not in (('Verifying', 'Active') if self.require_golden else ('Active',)) or self.clock() >= timestamp(record['expiresAt']):
                raise Denied(403, 'ApprovalInactive')
            if self.require_golden:
                # Budgets are local to this process. An in-flight verification
                # cannot resume after restart with a fresh allowance.
                if state == 'Verifying' and timestamp(record['startedAt']) < self.started_at:
                    raise Denied(403, 'VerificationRuntimeRestarted')
                prefix = 'system:serviceaccount:' + ns + ':'
                verifier, worker, caller = self.config['verifierSubject'], prefix + 'approved-worker', prefix + 'approved-caller'
                if state == 'Verifying':
                    expected = verifier if lane in ('invoke', 'witness') else worker
                else:
                    expected = caller if lane in ('invoke', 'witness') else worker
                if username != expected:
                    raise Denied(403, 'CallerNotApproved')
                if any(not isinstance(record.get(key), str) or not record[key] for key in ('attemptID', 'jobUID', 'podUID')):
                    raise Denied(403, 'AttemptBindingMissing')
                sa = self.kube.call(f'/api/v1/namespaces/{ns}/serviceaccounts/{username.rsplit(":", 1)[1]}')
                if (sa['metadata'].get('deletionTimestamp')
                        or sa['metadata']['uid'] != review.get('user', {}).get('uid')):
                    raise Denied(403, 'CallerIdentityChanged')
            elif lane == 'witness':
                lane = 'invoke'
            approved_lane = 'invoke' if lane == 'witness' else lane
            # A verifier receives only its narrowly scoped bootstrap lane. Active
            # approvals continue to use the pinned ordinary caller/worker lists.
            if ((not (self.require_golden and state == 'Verifying' and username == self.config['verifierSubject'])
                    and username not in record['callers'][approved_lane])
                    or record['callerUIDs'].get(username) != review.get('user', {}).get('uid')
                    or not review.get('user', {}).get('uid')):
                raise Denied(403, 'CallerNotApproved')
            ref = self.config['request']
            request = self.kube.call(f'/apis/{ref["apiVersion"]}/namespaces/{ns}/{ref["plural"]}/{ref["name"]}')
            agent = self.kube.call(f'/apis/api.kagent.dev/v1alpha3/namespaces/{ns}/agents/{self.config["agentName"]}')
            if (request['metadata'].get('deletionTimestamp') or agent['metadata'].get('deletionTimestamp')
                    or request['metadata']['uid'] != record['requestUID']
                    or agent['metadata']['uid'] != record['agentUID']
                    or canonical(agent['spec']) != record['agentSpecSha256']):
                raise Denied(403, 'BindingChanged')
            expected_dependencies = self.config.get('dependencyNames')
            if expected_dependencies is not None:
                required = {'agenttemplates', 'harnesses', 'modelconfigs', 'remotemcpservers'}
                if set(expected_dependencies) != required:
                    raise Denied(503, 'InvalidDependencyProfile')
                pins = record['dependencies']
                if not isinstance(pins, list) or len(pins) != 4:
                    raise Denied(403, 'DependencyPinsMissing')
                objects = {}
                for pin in pins:
                    plural = pin['plural']
                    if (plural not in required or plural in objects or pin['apiVersion'] != 'api.kagent.dev/v1alpha3'
                            or pin['name'] != expected_dependencies[plural] or '/' in pin['name']):
                        raise Denied(403, 'DependencyPinRejected')
                    obj = self.kube.call(f'/apis/api.kagent.dev/v1alpha3/namespaces/{ns}/{plural}/{pin["name"]}')
                    if (obj['metadata'].get('deletionTimestamp') or obj['metadata']['uid'] != pin['uid']
                            or canonical(obj['spec']) != pin['specSha256']):
                        raise Denied(403, 'DependencyChanged')
                    objects[plural] = obj
                template = objects['agenttemplates']['spec']
                if (agent['spec']['template']['ref']['name'] != expected_dependencies['agenttemplates']
                        or agent['spec']['harnessRef']['name'] != expected_dependencies['harnesses']
                        or template['modelConfig']['name'] != expected_dependencies['modelconfigs']
                        or not template.get('tools')
                        or any(t.get('mcp', {}).get('server', {}).get('name') != expected_dependencies['remotemcpservers']
                               for t in template['tools'])):
                    raise Denied(403, 'DependencyBindingChanged')
            if self.require_golden and state == 'Active':
                self.validate_golden(record, agent, objects['agenttemplates']['spec'].get('skills', []))
            if lane == 'invoke':
                generation = agent['metadata']['generation']
                status = agent.get('status', {})
                required = ('Accepted', 'ResolvedRefs', 'Compatible', 'EgressPoliciesApplied', 'Ready')
                if (not status.get('desiredRevision') or status.get('desiredRevision') != status.get('latestSuccessfulRevision')
                        or not all(any(c.get('type') == kind and c.get('status') == 'True'
                                       and c.get('observedGeneration') == generation
                                       for c in status.get('conditions', [])) for kind in required)):
                    raise Denied(403, 'NativeAgentNotReady')
            if self.clock() >= timestamp(record['expiresAt']):
                raise Denied(403, 'ApprovalExpired')
            return (username, record) if details else username
        except Denied:
            raise
        except (KeyError, ValueError, TypeError, AttributeError, OSError):
            raise Denied(503, 'AuthorityUnavailable') from None


    def validate_golden(self, record, agent, skills):
        proof = record.get('goldenProof', {})
        if not isinstance(proof, dict) or not isinstance(proof.get('receipt'), dict):
            raise Denied(403, 'GoldenProofRejected')
        receipt = proof['receipt']
        required_checks = {'NativeInvocationHTTP', 'StructuredNativeEvidence', 'PositiveModelAndMcpWitnesses',
                           'NativeCurrentReadyAndPins', 'OrdinaryCallerDeniedWhileVerifying', 'MissingTokenDenied',
                           'WrongAudienceDenied', 'WorkerCannotInvoke', 'VerifierCannotUseWorkerLane',
                           'CallerCannotUseWorkerLane', 'ForbiddenMcpOperationDenied', 'NegativeControlsNoBackendDispatch'}
        checks = receipt.get('checks')
        if (not isinstance(checks, list) or any(not isinstance(c, dict) for c in checks)
                or not required_checks <= {c.get('name') for c in checks}
                or not all(c.get('passed') is True for c in checks)
                or sorted(receipt.get('skills', [])) != sorted(s['name'] for s in skills)
                or any(type(receipt.get('evidence', {}).get('toolCallCounts', {}).get(tool)) is not int
                       or receipt['evidence']['toolCallCounts'][tool] <= 0
                       for tool in ('load_skill', 'load_skill_resource', 'get_demo_status'))):
            raise Denied(403, 'GoldenProofRejected')
        if (proof.get('sha256') != canonical(receipt) or receipt.get('schemaVersion') != GOLDEN_SCHEMA
                or receipt.get('proofScope') != GOLDEN_SCOPE or receipt.get('passed') is not True
                or any(receipt.get(key) != record.get(key) for key in
                       ('attemptID', 'jobUID', 'podUID', 'requestUID', 'agentUID', 'agentSpecSha256', 'expiresAt'))
                or canonical(receipt.get('dependencies')) != canonical(record.get('dependencies'))
                or receipt.get('nativeRevision') != agent.get('status', {}).get('desiredRevision')
                or receipt.get('nativeRevision') != agent.get('status', {}).get('latestSuccessfulRevision')
                or not all(isinstance(receipt.get(key), str) and receipt[key] for key in ('taskID', 'contextID'))
                or not receipt.get('checks') or not all(c.get('passed') is True for c in receipt['checks'])
                or any(type(receipt.get('witnessDeltas', {}).get(key)) is not int
                       or receipt['witnessDeltas'][key] <= 0 for key in ('modelCalls', 'mcpCalls'))):
            raise Denied(403, 'GoldenProofRejected')


class Frontdoor(http.server.ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, authority, upstream=None):
        super().__init__(address, Handler)
        self.authority = authority
        self.upstream = upstream
        self.lock = threading.Lock()
        self.invocation_lock = threading.Lock()
        self.verification_usage = {}
        self.counters = {'authorizedMcpCalls': 0, 'authorizedInvocations': 0, 'authorizedModelCalls': 0, 'deniedRequests': 0}

    def count(self, key):
        with self.lock:
            self.counters[key] += 1

    def reserve_verification(self, record, kind):
        if not self.authority.require_golden or record.get('state') != 'Verifying':
            return
        defaults = {'modelCalls': 24, 'mcpCalls': 4, 'invocations': 1}
        limit = self.authority.config.get('verificationBudgets', {}).get(kind, defaults[kind])
        with self.lock:
            # Retain one attempt only. The runtime is scoped to one request; a
            # fresh request requires a fresh frontdoor deployment for new budgets.
            if self.verification_usage and record['attemptID'] not in self.verification_usage:
                raise Denied(403, 'VerificationAttemptChanged')
            usage = self.verification_usage.setdefault(record['attemptID'], {})
            if usage.get(kind, 0) >= limit:
                raise Denied(429, 'VerificationBudgetExceeded')
            usage[kind] = usage.get(kind, 0) + 1

    @contextlib.contextmanager
    def invocation_slot(self, record):
        locked = False
        try:
            if self.authority.require_golden:
                locked = self.invocation_lock.acquire(blocking=False)
                if not locked:
                    raise Denied(429, 'InvocationAlreadyRunning')
                self.reserve_verification(record, 'invocations')
            yield
        finally:
            if locked:
                self.invocation_lock.release()

    def invoke(self, prompt, deadline=None, reauthorize=None):
        deadline = deadline or time.monotonic() + 100
        if self.authority.config.get('kagentBinary'):
            return self.invoke_cli(prompt, deadline, reauthorize)
        url = self.authority.config.get('upstreamURL')
        if not url:
            raise Denied(503, 'NativeInvocationNotConfigured')
        payload = {'jsonrpc': '2.0', 'id': str(uuid.uuid4()), 'method': 'SendMessage', 'params': {
            'message': {'messageId': str(uuid.uuid4()), 'contextId': str(uuid.uuid4()),
                        'role': 'ROLE_USER', 'parts': [{'text': prompt}]},
            'configuration': {'returnImmediately': False}}}
        return post_json(url, payload, {'Content-Type': 'application/json'},
                         min(deadline, time.monotonic() + 45), before_dispatch=reauthorize)



    def model(self, value, deadline=None, reauthorize=None, reserve=None):
        deadline = min(deadline or time.monotonic() + 45, time.monotonic() + 45)
        config = self.authority.config
        if not config.get('upstreamModelURL') or not config.get('modelName'):
            raise Denied(503, 'ModelNotConfigured')
        allowed = {'model', 'messages', 'tools', 'tool_choice', 'parallel_tool_calls', 'temperature', 'top_p',
                   'response_format', 'max_tokens', 'max_completion_tokens', 'stop', 'frequency_penalty',
                   'presence_penalty', 'seed', 'reasoning_effort', 'user', 'stream', 'n'}
        if (set(value) - allowed or value.get('model') != config['modelName']
                or not isinstance(value.get('messages'), list) or not value['messages']
                or value.get('stream', False) is not False or value.get('n', 1) != 1):
            raise Denied(400, 'ModelRequestRejected')
        limit = config.get('modelMaxTokens', 1200)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 4096:
            raise Denied(503, 'InvalidModelProfile')
        if 'max_tokens' in value and 'max_completion_tokens' in value:
            raise Denied(400, 'AmbiguousTokenLimit')
        token_field = 'max_completion_tokens' if 'max_completion_tokens' in value else 'max_tokens'
        requested = value.get(token_field, limit)
        if not isinstance(requested, int) or isinstance(requested, bool) or not 1 <= requested <= limit:
            raise Denied(400, 'ModelTokenLimitExceeded')
        payload = dict(value, stream=False)
        payload[token_field] = requested
        if not config.get('upstreamModelKeyFile'):
            raise Denied(503, 'ModelCredentialUnavailable')
        key = Path(config['upstreamModelKeyFile']).read_text().strip()
        if not key or '\n' in key or '\r' in key:
            raise Denied(503, 'ModelCredentialUnavailable')
        def authorize_dispatch():
            if reauthorize:
                reauthorize()
            before_deadline(deadline)
            if reserve:
                reserve()
            self.count('authorizedModelCalls')
        return post_json(config['upstreamModelURL'], payload,
            {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}, deadline,
            ca_file=config.get('upstreamModelCAFile'), before_dispatch=authorize_dispatch)

    def invoke_cli(self, prompt, deadline=None, reauthorize=None):
        config = self.authority.config
        prefix = [config['kagentBinary'], '--api-url', config['apiURL'],
                  '--gateway-url', config['gatewayURL'], '--namespace', config['namespace'],
                  '--user-id', config['nativeUserID'], '--timeout', '90s', '-o', 'json']
        deadline = min(deadline or time.monotonic() + 100, time.monotonic() + 100)
        if reauthorize:
            reauthorize()
        before_deadline(deadline)
        session = run_cli(prefix + ['agent', 'session', 'create', '--agent', config['agentName']], deadline)
        current = session['session']
        if (current['agent'] != {'namespace': config['namespace'], 'name': config['agentName']}
                or not isinstance(current['id'], str) or not current['id'] or current['id'].startswith('-')):
            raise Denied(502, 'NativeSessionBindingMismatch')
        with tempfile.TemporaryDirectory(prefix='secure-byo-', dir='/tmp') as directory:
            path = Path(directory) / 'prompt.txt'
            path.write_text(prompt)
            os.chmod(path, 0o600)
            if reauthorize:
                reauthorize()
            before_deadline(deadline)
            result = run_cli(prefix + ['agent', 'invoke', '--session', current['id'], '--file', str(path)], deadline)
        if result.get('task', {}).get('contextId') != current['id']:
            raise Denied(502, 'NativeTaskBindingMismatch')
        return result


def run_cli(argv, deadline):
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    output = bytearray()
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Denied(504, 'NativeDeadlineExceeded')
            for key, _ in selector.select(min(remaining, 1)):
                data = os.read(key.fileobj.fileno(), 8192)
                if not data:
                    selector.unregister(key.fileobj)
                else:
                    output.extend(data)
                    if len(output) > MAX_RESPONSE:
                        raise Denied(502, 'NativeResponseTooLarge')
        if process.wait(timeout=max(0.001, deadline - time.monotonic())) != 0:
            raise Denied(502, 'NativeCommandFailed')
        return json.loads(output)
    except subprocess.TimeoutExpired:
        raise Denied(504, 'NativeDeadlineExceeded') from None
    finally:
        selector.close()
        process.stdout.close()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'SecureBYO/1'
    def log_message(self, *_):
        pass

    def setup(self):
        self.started = time.monotonic()
        super().setup()
        self.connection.settimeout(10)

    def reply(self, code, value):
        body = json.dumps(value, separators=(',', ':')).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_GET(self):
        if self.path == '/healthz':
            self.reply(200, {'status': 'alive'})
        else:
            self.reply(404, {'error': 'UnsupportedPath'})

    def do_POST(self):
        self.deadline = self.started + REQUEST_TIMEOUT
        try:
            before_deadline(self.deadline)
            if self.path not in ('/mcp', '/invoke', '/witness', '/v1/chat/completions'):
                raise Denied(404, 'UnsupportedPath')
            lane = 'mcp' if self.path in ('/mcp', '/v1/chat/completions') else ('witness' if self.path == '/witness' else 'invoke')
            _, self.approval_record = self.server.authority.authorize(self.headers.get('Authorization'), lane, details=True)
            if self.headers.get('Transfer-Encoding'):
                raise Denied(400, 'TransferEncodingUnsupported')
            try:
                size = int(self.headers['Content-Length'])
            except (KeyError, TypeError, ValueError):
                raise Denied(411, 'ContentLengthRequired') from None
            if size < 0 or size > (262144 if self.path == '/v1/chat/completions' else MAX_REQUEST):
                raise Denied(413, 'RequestTooLarge')
            value = json.loads(self.read_body(size))
            if not isinstance(value, dict):
                raise Denied(400, 'ObjectRequired')
            def reauthorize():
                before_deadline(self.deadline)
                _, current = self.server.authority.authorize(self.headers.get('Authorization'), lane, details=True)
                if self.server.authority.require_golden and current['attemptID'] != self.approval_record['attemptID']:
                    raise Denied(403, 'VerificationAttemptChanged')
                before_deadline(self.deadline)
            reauthorize()
            if self.path == '/v1/chat/completions':
                result = self.server.model(value, self.deadline, reauthorize,
                    lambda: self.server.reserve_verification(self.approval_record, 'modelCalls'))
                reauthorize()
                if len(json.dumps(result).encode()) > MAX_RESPONSE:
                    raise Denied(502, 'ModelResponseTooLarge')
                self.reply(200, result)
            elif self.path == '/witness':
                if value:
                    raise Denied(400, 'EmptyObjectRequired')
                self.reply(200, dict(self.server.counters))
            elif self.path == '/invoke':
                if set(value) != {'prompt'} or not isinstance(value['prompt'], str) or not 1 <= len(value['prompt']) <= 8192:
                    raise Denied(400, 'PromptOnly')
                with self.server.invocation_slot(self.approval_record):
                    reauthorize()
                    self.server.count('authorizedInvocations')
                    if self.server.upstream is None:
                        result = self.server.invoke(value['prompt'], self.deadline, reauthorize)
                    else:
                        result = self.server.upstream(value['prompt'])
                    reauthorize()
                if len(json.dumps(result).encode()) > MAX_RESPONSE:
                    raise Denied(502, 'NativeResponseTooLarge')
                self.reply(200, result)
            else:
                self.mcp(value)
        except Denied as error:
            print(json.dumps({'denied': error.reason, 'status': error.status}), flush=True)
            self.server.count('deniedRequests')
            self.reply(error.status, {'error': error.reason})
        except (ValueError, TypeError, UnicodeError):
            self.reply(400, {'error': 'InvalidJSON'})
        except (OSError, urllib.error.URLError):
            self.reply(502, {'error': 'UpstreamUnavailable'})

    def read_body(self, size):
        deadline = min(self.deadline, time.monotonic() + BODY_TIMEOUT)
        body = bytearray()
        while len(body) < size:
            before_deadline(deadline)
            self.connection.settimeout(max(0.001, deadline - time.monotonic()))
            try:
                chunk = self.rfile.read1(min(8192, size - len(body)))
            except TimeoutError:
                raise Denied(408, 'BodyDeadlineExceeded') from None
            if not chunk:
                raise Denied(400, 'IncompleteBody')
            body.extend(chunk)
        before_deadline(deadline)
        return body

    def mcp(self, value):
        if value.get('jsonrpc') != '2.0' or set(value) - {'jsonrpc', 'id', 'method', 'params'}:
            raise Denied(400, 'InvalidRPC')
        method = value.get('method')
        params = value.get('params', {})
        if method == 'notifications/initialized' and 'id' not in value:
            self.reply(202, {})
            return
        ident = value.get('id')
        if not isinstance(ident, (str, int)) or isinstance(ident, bool):
            raise Denied(400, 'RPCIdRequired')
        if method == 'initialize':
            result = {'protocolVersion': '2025-03-26', 'capabilities': {'tools': {}},
                      'serverInfo': {'name': 'secure-byo-status', 'version': '1'}}
        elif method == 'tools/list' and params == {}:
            result = {'tools': [TOOL]}
        elif (method == 'tools/call' and isinstance(params, dict)
              and set(params) <= {'name', 'arguments'} and params.get('name') == TOOL['name']
              and params.get('arguments', {}) == {}):
            self.server.reserve_verification(self.approval_record, 'mcpCalls')
            self.server.count('authorizedMcpCalls')
            content = {'agent': self.server.authority.config['agentName'], 'status': 'synthetic-ready',
                       'scope': 'fixed-demo-only'}
            result = {'content': [{'type': 'text', 'text': json.dumps(content)}], 'isError': False}
        else:
            self.reply(200, {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'OperationDenied'}})
            return
        self.reply(200, {'jsonrpc': '2.0', 'id': ident, 'result': result})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    authority = Authority(Kubernetes(), json.loads(Path(args.config).read_text()))
    Frontdoor(('0.0.0.0', args.port), authority).serve_forever()


if __name__ == '__main__':
    main()
