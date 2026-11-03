import copy
import itertools
import json
import re
import sys
import tempfile
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BUNDLE / 'app'), str(BUNDLE)]
import agent  # noqa: E402
import authority as auth  # noqa: E402
import common  # noqa: E402
import contract  # noqa: E402
import facade  # noqa: E402
import golden  # noqa: E402
import render  # noqa: E402
import payload  # noqa: E402

NS, GNS = 'secure-kro-standalone', 'secure-byo-gateway-system'
IMAGE = 'registry.example.invalid/python-helper@sha256:' + 'a' * 64
ISSUER = 'https://kubernetes.default.svc.cluster.local'
JWKS = {'keys': [{'kty': 'RSA', 'kid': 'fixture-key', 'use': 'sig', 'alg': 'RS256', 'n': 'fixture' * 8, 'e': 'AQAB'}]}
UPSTREAM = 'http://flow-gateway.agent-flow-demo.svc.cluster.local:8081/v1/chat/completions'
CONTENT = BUNDLE / 'content'
EXPR = re.compile(r'\$\{([^}]*)\}')


def settings(**overrides):
    value = {
        'schema': render.SETTINGS_SCHEMA, 'standaloneNamespace': NS, 'image': IMAGE, 'imagePullSecrets': [],
        'gateway': {'create': True, 'name': 'standalone-secure', 'namespace': GNS, 'className': 'agentgateway',
                    'controllerName': 'agentgateway.dev/agentgateway', 'listenerName': 'agents', 'port': 8080,
                    'serviceHost': 'standalone-secure.' + GNS + '.svc.cluster.local',
                    'podLabels': {'gateway.networking.k8s.io/gateway-name': 'standalone-secure'}},
        'jwt': {'issuer': ISSUER, 'jwks': copy.deepcopy(JWKS)},
        'model': {'upstreamURL': UPSTREAM, 'name': 'flow-model', 'podLabels': {'app': 'flow-gateway'}},
        'apiServer': {'cidrs': ['192.0.2.10/32'], 'ports': [6443]},
        'dns': {'namespace': 'kube-system', 'podLabels': {'k8s-app': 'kube-dns'}},
        'approval': {'verifyingSeconds': 900, 'activeSeconds': 14400},
        'limits': {k: v.default for k, v in contract.LIMITS.items()},
        'revokers': {'users': [], 'groups': ['standalone-secure:revokers']},
        'submitters': {'users': [], 'groups': ['standalone-secure:submitters']}}
    value.update(overrides)
    return value


def rendered(value=None):
    files = render.render(json.dumps(value or settings()).encode())
    docs = {k: json.loads(v) for k, v in files.items() if k.endswith('.json')}
    cm = next(o for o in docs['platform.json']['items'] if o['kind'] == 'ConfigMap')
    return files, docs, json.loads(cm['data']['platform.json'])


def materialize(rgd, name, uid, spec):
    out = {}

    def value(expression):
        fixed = {'schema.metadata.name': name, 'schema.metadata.uid': uid, 'schema.spec.instructions': spec['instructions']}
        if expression in fixed:
            return fixed[expression]
        node, field = expression.split('.', 1)
        assert field == 'metadata.name', expression
        return out[node]['metadata']['name']

    def walk(item):
        if isinstance(item, dict):
            return {k: walk(v) for k, v in item.items()}
        if isinstance(item, list):
            return [walk(v) for v in item]
        return EXPR.sub(lambda m: value(m.group(1)), item) if isinstance(item, str) else item
    for resource in rgd['spec']['resources']:
        out[resource['id']] = walk(resource['template'])
    return out


def api_path(obj):
    kind, meta = obj['kind'], obj['metadata']
    plural = {'ServiceAccount': 'serviceaccounts', 'ConfigMap': 'configmaps', 'Service': 'services',
              'Deployment': 'deployments', 'ReferenceGrant': 'referencegrants', 'HTTPRoute': 'httproutes',
              'AgentgatewayPolicy': 'agentgatewaypolicies', 'Job': 'jobs', 'StandaloneSecureAgent': 'standalonesecureagents'}[kind]
    api = obj['apiVersion']
    prefix = '/api/v1' if api == 'v1' else '/apis/' + api
    return prefix + ('/namespaces/' + meta['namespace'] if meta.get('namespace') else '') + '/' + plural + '/' + meta['name']


class PatchFailed(Exception):
    pass


def json_patch(document, ops):
    doc = copy.deepcopy(document)
    for op in ops:
        parts = [p.replace('~1', '/').replace('~0', '~') for p in op['path'].split('/')[1:]]
        parent = doc
        for part in parts[:-1]:
            if part not in parent:
                raise PatchFailed(op['path'])
            parent = parent[part]
        key = parts[-1]
        if op['op'] == 'test':
            if key not in parent or parent[key] != op['value']:
                raise PatchFailed(op['path'])
        elif op['op'] in ('add', 'replace'):
            if op['op'] == 'replace' and key not in parent:
                raise PatchFailed(op['path'])
            parent[key] = copy.deepcopy(op['value'])
        else:
            raise PatchFailed(op['op'])
    return doc


class FakeKube:

    def __init__(self, cfg):
        self.cfg, self.objects, self.tokens, self.calls, self.fail = cfg, {}, {}, [], set()
        self.counter = itertools.count(1)
        self.on_patch = None

    def put(self, obj, uid=None):
        obj = copy.deepcopy(obj)
        meta = obj['metadata']
        meta.setdefault('uid', uid or 'uid-%s-%d' % (meta['name'], next(self.counter)))
        meta['resourceVersion'] = str(next(self.counter))
        meta.setdefault('generation', 1)
        self.objects[api_path(obj)] = obj
        return obj

    def call(self, method, path, value=None, content_type='application/json'):
        self.calls.append((method, path))
        if path in self.fail or 'all' in self.fail:
            raise common.Denied(503, 'AuthorityUnavailable')
        if method == 'GET':
            obj = self.objects.get(path)
            return (200, copy.deepcopy(obj)) if obj else (404, {'kind': 'Status', 'code': 404})
        if method == 'POST' and path == '/apis/authentication.k8s.io/v1/tokenreviews':
            claims = self.tokens.get(value['spec']['token'])
            audience = value['spec']['audiences'][0]
            if not claims or audience not in claims['audiences']:
                return 201, {'status': {'authenticated': False, 'error': 'invalid token'}}
            return 201, {'status': {'authenticated': True, 'audiences': [audience],
                                    'user': {'username': claims['username'], 'uid': claims['uid']}}}
        if method == 'POST' and path.endswith('/token'):
            account = path.split('/')[-2]
            if account != self.cfg['accounts']['negative']:
                return 403, {'kind': 'Status', 'code': 403}
            token = 'negative-token-%d-%s' % (next(self.counter), value['spec']['audiences'][0])
            sa = self.objects[path.rsplit('/', 1)[0]]
            self.tokens[token] = {'username': 'system:serviceaccount:%s:%s' % (NS, account),
                                  'uid': sa['metadata']['uid'], 'audiences': value['spec']['audiences']}
            return 201, {'status': {'token': token}}
        if method == 'PATCH':
            assert content_type == 'application/json-patch+json'
            if self.on_patch:
                self.on_patch(path, value)
            obj = self.objects.get(path)
            if obj is None:
                return 404, {'code': 404}
            try:
                patched = json_patch(obj, value)
            except PatchFailed:
                return 422, {'kind': 'Status', 'code': 422}
            patched['metadata']['resourceVersion'] = str(next(self.counter))
            self.objects[path] = patched
            return 200, copy.deepcopy(patched)
        raise AssertionError((method, path))

    def get(self, path):
        status, value = self.call('GET', path)
        if status == 404:
            return None
        return value


def ready_status(obj, cfg):
    gw = cfg['gateway']
    generation = obj['metadata']['generation']
    if obj['kind'] == 'Deployment':
        obj['status'] = {'observedGeneration': generation, 'replicas': 1, 'updatedReplicas': 1, 'readyReplicas': 1,
                         'availableReplicas': 1, 'conditions': [{'type': 'Available', 'status': 'True'}]}
    elif obj['kind'] == 'HTTPRoute':
        obj['status'] = {'parents': [{'controllerName': gw['controllerName'],
                                      'parentRef': {'name': gw['name'], 'namespace': gw['namespace'],
                                                    'sectionName': gw['listenerName']},
                                      'conditions': [{'type': t, 'status': 'True', 'reason': t,
                                                      'observedGeneration': generation}
                                                     for t in ('Accepted', 'ResolvedRefs')]}]}
    elif obj['kind'] == 'AgentgatewayPolicy':
        obj['status'] = {'ancestors': [{'controllerName': gw['controllerName'], 'ancestorRef': {'name': gw['name']},
                                        'conditions': [{'type': 'Accepted', 'status': 'True', 'reason': 'Valid',
                                                        'observedGeneration': generation},
                                                       {'type': 'Attached', 'status': 'True', 'reason': 'Attached',
                                                        'observedGeneration': generation}]}]}
    return obj


class FakeModel:

    def __init__(self, mode='success'):
        self.mode, self.requests, self.on_request = mode, [], None

    def __call__(self, method, url, headers, body=None, *, deadline, max_bytes, ca_file=None, before_send=None):
        assert url == UPSTREAM and all(k.lower() != 'authorization' for k in headers), 'credentials must not reach provider'
        assert all(k.lower() != facade.HANDLE_HEADER.lower() for k in headers), 'handle must not reach provider'
        if before_send:
            before_send()
        request = json.loads(body)
        self.requests.append(request)
        if self.on_request:
            self.on_request(request)
        if self.mode == 'http-500':
            return 500, b'{"error":"fixture"}'
        return 200, json.dumps(self.respond(request)).encode()

    def respond(self, request):
        results = [json.loads(m['content']) for m in request['messages'] if m['role'] == 'tool']
        if not results or self.mode == 'loop':
            calls = [('load_skill', {'name': p}) for p in contract.PACKAGES]
            calls += [('load_skill_resource', {'skill_name': s, 'resource_path': p}) for s, p in contract.REQUIRED]
            if self.mode != 'omit-mcp':
                calls.append(('get_demo_status', {} if self.mode != 'bad-demo-args' else {'component': 'x'}))
            if self.mode == 'duplicate-mcp':
                calls.append(('get_demo_status', {}))
            if self.mode == 'unknown-tool':
                calls[0] = ('run_shell', {'command': 'id'})
            if self.mode == 'loop':
                calls = [('load_skill', {'name': contract.PACKAGES[0]})]
            offset = len(request['messages'])
            message = {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'call_%d_%d' % (offset, i), 'type': 'function',
                 'function': {'name': n, 'arguments': json.dumps(a)}} for i, (n, a) in enumerate(calls)]}
            return {'choices': [{'message': message, 'finish_reason': 'tool_calls'}]}
        proofs = [r['content'] for r in results if r.get('path') == contract.PROOF_FILE]
        status = [r['runProof'] for r in results if 'runProof' in r]
        answer = ('Synthetic documentation analysis only; no operational investigation or changes were performed. '
                  'Evidence code AKS-KB-ORAS-212-R1. Source: %s\n%s\nSynthetic status runProof: %s'
                  % (contract.CITATIONS[0], '\n'.join(proofs), ' '.join(status)))
        if self.mode == 'missing-proof':
            answer = 'AKS-KB-ORAS-212-R1 ' + contract.CITATIONS[0] + ' ' + ' '.join(status)
        if self.mode == 'skip-mcp-proof':
            answer = answer.split('Synthetic status runProof')[0]
        return {'choices': [{'message': {'role': 'assistant', 'content': answer}, 'finish_reason': 'stop'}]}


class FakeGateway:

    def __init__(self, world, enforce_audience=True):
        self.world, self.forwarded, self.enforce_subjects = world, 0, True
        self.enforce_audience = enforce_audience

    def __call__(self, method, url, headers, body=None, *, deadline, max_bytes, ca_file=None, before_send=None):
        base = self.world.cfg['gateway']['baseURL']
        assert url.startswith(base + '/agents/'), url
        path = url[len(base):]
        name = path.split('/')[2]
        policy = self.world.kube.objects.get(auth.Names(self.world.cfg, name).children[9][5]) if common.NAME.fullmatch(name) else None
        if policy is None:
            return 404, b'route not found'
        authorization = next((v for k, v in headers.items() if k.lower() == 'authorization'), None)
        claims = self.world.kube.tokens.get(authorization[7:]) if authorization and authorization.startswith('Bearer ') else None
        if claims is None or (self.enforce_audience and self.world.cfg['audience'] not in claims['audiences']):
            return 401, b'jwt rejected'
        expression = policy['spec']['traffic']['authorization']['policy']['matchExpressions'][0]
        allowed = json.loads(expression[len('jwt.sub in '):])
        if self.enforce_subjects and claims['username'] not in allowed:
            return 403, b'authorization failed'
        self.forwarded += 1
        try:
            status, payload = self.world.facade.handle(method, path, list(headers.items()), body)
        except common.Denied as error:
            status, payload = error.status, {'error': error.reason}
        return status, json.dumps(payload).encode()


class Clock:
    def __init__(self, start=1_800_000_000.0):
        self.now = start

    def __call__(self):
        return self.now


class World:

    def __init__(self, model_mode='success', enforce_audience=True):
        self.files, self.docs, self.cfg = rendered()
        self.rgd = self.docs['graph.json']
        self.kube, self.clock, self.model = FakeKube(self.cfg), Clock(), FakeModel(model_mode)
        self.tmp = tempfile.TemporaryDirectory(prefix='kro-standalone-test-')
        for obj in self.docs['platform.json']['items']:
            if obj['kind'] == 'ServiceAccount':
                self.kube.put(obj)
        self.authority = auth.Authority(self.kube, self.cfg, self.clock)
        self.facade = facade.Facade(self.cfg, self.authority, transport=self.facade_transport, log=lambda *_: None,
                                    content_root=CONTENT)
        self.gateway = FakeGateway(self, enforce_audience=enforce_audience)
        self.runtimes, self.token_files = {}, {}
        verifier = self.kube.objects['/api/v1/namespaces/%s/serviceaccounts/standalone-verifier' % NS]
        self.verifier_token = self.token('verifier', 'system:serviceaccount:%s:standalone-verifier' % NS,
                                         verifier['metadata']['uid'])
        self.verifier_negative_audience_token = self.token(
            'verifier-negative-audience', 'system:serviceaccount:%s:standalone-verifier' % NS,
            verifier['metadata']['uid'], audiences=(auth.NEGATIVE_AUDIENCE,))

    def close(self):
        self.tmp.cleanup()

    def token(self, label, username, uid, audiences=(auth.GATEWAY_AUDIENCE,)):
        value = 'fixture-%s-token-%d' % (label, next(self.kube.counter))
        self.kube.tokens[value] = {'username': username, 'uid': uid, 'audiences': list(audiences)}
        path = Path(self.tmp.name) / (label + '.token')
        path.write_text(value)
        self.token_files[label] = path
        return value

    def create(self, name='docs-demo', instructions=contract.EXAMPLE_INSTRUCTIONS, uid=None):
        request = self.kube.put({'apiVersion': 'kro.run/v1alpha1', 'kind': 'StandaloneSecureAgent',
                                 'metadata': {'name': name},
                                 'spec': {'profileRef': contract.PROFILE, 'instructions': instructions}}, uid)
        rid = request['metadata']['uid']
        for node, obj in materialize(self.rgd, name, rid, request['spec']).items():
            obj['metadata'].setdefault('labels', {})[auth.KRO_INSTANCE] = rid
            obj['metadata']['generation'] = 1
            self.kube.put(ready_status(obj, self.cfg) if node != 'golden' else obj)
        names = auth.Names(self.cfg, name)
        worker = self.get(names.children[0][5])
        caller = self.get(names.children[1][5])
        self.worker_token = self.token(name + '-worker', names.subjects['worker'], worker['metadata']['uid'])
        self.caller_token = self.token(name + '-caller', names.subjects['caller'], caller['metadata']['uid'])
        model = json.loads(self.get(names.children[2][5])['data']['model.json'])
        content = json.loads(self.get(names.children[3][5])['data']['content.json'])
        self.runtimes[name] = agent.Runtime(name, instructions, model, content, CONTENT, self.token_files[name + '-worker'],
                                            transport=self.gateway, log=lambda *_: None)
        return names

    def get(self, path):
        return self.kube.objects.get(path)

    def facade_transport(self, method, url, headers, body=None, *, deadline, max_bytes, ca_file=None, before_send=None):
        if url == UPSTREAM:
            return self.model(method, url, headers, body, deadline=deadline, max_bytes=max_bytes, before_send=before_send)
        match = re.fullmatch(r'http://([a-z0-9-]+)-runtime\.%s\.svc\.cluster\.local:8080/invoke' % NS, url)
        assert match, url
        if before_send:
            before_send()
        try:
            status, payload = self.runtimes[match.group(1)].handle(method, '/invoke', list(headers.items()), body)
        except common.Denied as error:
            status, payload = error.status, {'error': error.reason}
        return status, json.dumps(payload).encode()

    def verifier(self, name='docs-demo', env=None):
        names = auth.Names(self.cfg, name)
        values = {'RUNTIME_DEPLOYMENT': names.runtime, 'ROUTE_NAME': names.route, 'POLICY_NAME': names.route,
                  'POD_UID': 'fixture-pod'}
        values.update(env or {})
        return golden.Verifier(self.cfg, self.kube, self.token_files['verifier'], CONTENT, transport=self.gateway,
                               clock=self.clock, sleep=lambda _: None, env=values, wait_seconds=0,
                               negative_audience_token_file=self.token_files['verifier-negative-audience'])

    def call(self, name, lane, body, token=None, headers=None):
        hdrs = {'Content-Type': 'application/json'}
        if token:
            hdrs['Authorization'] = 'Bearer ' + token
        hdrs.update(headers or {})
        path = {'invoke': '/invoke', 'model': '/model/v1/chat/completions', 'mcp': '/mcp', 'witness': '/witness'}[lane]
        status, raw = self.gateway('POST', self.cfg['gateway']['baseURL'] + '/agents/' + name + path, hdrs,
                                   json.dumps(body, ensure_ascii=False).encode(), deadline=0, max_bytes=0)
        try:
            return status, json.loads(raw)
        except ValueError:
            return status, None

    def approval(self, name='docs-demo'):
        return self.get(auth.Names(self.cfg, name).approval_path)
