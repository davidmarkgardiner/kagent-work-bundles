import re
from pathlib import Path

import common
import contract
import payload

PLATFORM_FILE = '/etc/standalone/platform/platform.json'
API_TOKEN_FILE = '/var/run/secrets/standalone/api/token'
API_CA_FILE = '/var/run/secrets/standalone/api/ca.crt'
GATEWAY_TOKEN_FILE = '/var/run/secrets/standalone/gateway/token'
GATEWAY_AUDIENCE = 'secure-byo'
NEGATIVE_AUDIENCE = 'standalone-negative-audience'
NEGATIVE_AUDIENCE_TOKEN_FILE = '/var/run/secrets/standalone/negative-audience/token'
PLATFORM_SCHEMA = 'secure-kro-standalone-platform/v1'
DNS = re.compile(r'[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?')
LABEL_AGENT = 'standalone-secure.platform/agent'
LABEL_ROLE = 'standalone-secure.platform/role'
EXPECTED_UID = 'standalone-secure.platform/expected-request-uid'
KRO_INSTANCE = 'kro.run/instance-id'
APPROVAL_SCHEMA = 'standalone-approval/v1'
ROUTE_PREFIX = 'kro-standalone-'
DATA_KEYS = {'state', 'requestUID', 'expiresAt', 'approval.json'}
PIN_FIELDS = ('spec', 'data', 'binaryData', 'immutable', 'automountServiceAccountToken', 'imagePullSecrets', 'secrets')
LANES = {'invoke': {'caller': ('Active',), 'verifier': ('Verifying',)},
         'witness': {'verifier': ('Verifying', 'Active')},
         'model': {'worker': ('Verifying', 'Active')},
         'mcp': {'worker': ('Verifying', 'Active')}}


def platform_ok(cfg):
    def keys(value, expected):
        return isinstance(value, dict) and set(value) == set(expected)
    try:
        return (keys(cfg, ('schema', 'profile', 'standaloneNamespace', 'audience', 'image', 'request', 'accounts',
                           'gateway', 'jwt', 'model', 'limits', 'approval', 'bindings'))
                and cfg['schema'] == PLATFORM_SCHEMA and cfg['profile'] == contract.PROFILE
                and DNS.fullmatch(cfg['standaloneNamespace']) is not None and cfg['audience'] == GATEWAY_AUDIENCE
                and re.fullmatch(r'[a-z0-9][a-z0-9._:/-]{0,254}@sha256:[0-9a-f]{64}', cfg['image']) is not None
                and cfg['request'] == {'group': 'kro.run', 'version': 'v1alpha1', 'plural': 'standalonesecureagents',
                                       'kind': 'StandaloneSecureAgent'}
                and keys(cfg['accounts'], ('facade', 'verifier', 'negative'))
                and all(DNS.fullmatch(v) for v in cfg['accounts'].values())
                and keys(cfg['gateway'], ('name', 'namespace', 'listenerName', 'controllerName', 'baseURL', 'port'))
                and all(DNS.fullmatch(cfg['gateway'][k]) for k in ('name', 'namespace', 'listenerName'))
                and contract.base_url_ok(cfg['gateway']['baseURL'])
                and keys(cfg['jwt'], ('issuer', 'jwksSha256')) and re.fullmatch(r'[0-9a-f]{64}', cfg['jwt']['jwksSha256'])
                and keys(cfg['model'], ('name', 'upstreamURL')) and contract.limits_ok(cfg['limits'])
                and keys(cfg['approval'], ('verifyingSeconds', 'activeSeconds'))
                and keys(cfg['bindings'], ('modelSha256', 'contentSha256', *payload.HASH_FIELDS))
                and all(isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v) for v in cfg['bindings'].values()))
    except (TypeError, KeyError):
        return False


def load_platform(path):
    cfg = common.loads(Path(path).read_bytes(), 65536)
    if not platform_ok(cfg):
        raise ValueError('InvalidPlatformConfig')
    return cfg


class Names:

    def __init__(self, cfg, agent):
        common.require(isinstance(agent, str) and common.NAME.fullmatch(agent) is not None, 404, 'UnknownAgent')
        ns, gns = cfg['standaloneNamespace'], cfg['gateway']['namespace']
        self.agent, self.ns, self.gateway_ns = agent, ns, gns
        self.worker, self.caller = agent + '-worker', agent + '-caller'
        self.model, self.content = agent + '-model', agent + '-content'
        self.runtime_code = agent + '-runtime-code'
        self.runtime, self.front = agent + '-runtime', agent + '-front'
        self.approval, self.golden = agent + '-approval', agent + '-golden'
        self.route = ROUTE_PREFIX + agent
        self.verifier = cfg['accounts']['verifier']
        self.subjects = {role: 'system:serviceaccount:' + ns + ':' + sa
                         for role, sa in (('caller', self.caller), ('worker', self.worker), ('verifier', self.verifier))}
        request = cfg['request']
        self.request_path = '/apis/' + request['group'] + '/' + request['version'] + '/' + request['plural'] + '/' + agent
        self.approval_path = '/api/v1/namespaces/' + ns + '/configmaps/' + self.approval
        self.verifier_path = '/api/v1/namespaces/' + ns + '/serviceaccounts/' + self.verifier
        self.job_path = '/apis/batch/v1/namespaces/' + ns + '/jobs/' + self.golden
        core, gw = '/api/v1/namespaces/' + ns, '/apis/gateway.networking.k8s.io/'
        self.children = (
            ('workerAccount', 'v1', 'ServiceAccount', ns, self.worker, core + '/serviceaccounts/' + self.worker),
            ('callerAccount', 'v1', 'ServiceAccount', ns, self.caller, core + '/serviceaccounts/' + self.caller),
            ('modelBinding', 'v1', 'ConfigMap', ns, self.model, core + '/configmaps/' + self.model),
            ('contentBinding', 'v1', 'ConfigMap', ns, self.content, core + '/configmaps/' + self.content),
            ('runtime', 'apps/v1', 'Deployment', ns, self.runtime,
             '/apis/apps/v1/namespaces/' + ns + '/deployments/' + self.runtime),
            ('runtimeService', 'v1', 'Service', ns, self.runtime, core + '/services/' + self.runtime),
            ('frontService', 'v1', 'Service', ns, self.front, core + '/services/' + self.front),
            ('frontGrant', 'gateway.networking.k8s.io/v1beta1', 'ReferenceGrant', ns, self.front,
             gw + 'v1beta1/namespaces/' + ns + '/referencegrants/' + self.front),
            ('route', 'gateway.networking.k8s.io/v1', 'HTTPRoute', gns, self.route,
             gw + 'v1/namespaces/' + gns + '/httproutes/' + self.route),
            ('routePolicy', 'agentgateway.dev/v1alpha1', 'AgentgatewayPolicy', gns, self.route,
             '/apis/agentgateway.dev/v1alpha1/namespaces/' + gns + '/agentgatewaypolicies/' + self.route),
            ('runtimeCode', 'v1', 'ConfigMap', ns, self.runtime_code, core + '/configmaps/' + self.runtime_code))


def pin(child, obj):
    meta = obj['metadata']
    return {'id': child[0], 'apiVersion': child[1], 'kind': child[2], 'namespace': child[3], 'name': child[4],
            'uid': meta['uid'], 'generation': meta.get('generation'),
            'sha256': common.canonical({k: obj[k] for k in PIN_FIELDS if k in obj})}


class Snapshot:
    def __init__(self, names, request, approval, state, record=None):
        self.names, self.request, self.approval, self.state, self.record = names, request, approval, state, record
        self.role = None

    @property
    def request_uid(self):
        return self.request['metadata']['uid']

    def binding(self):
        return (self.request_uid, self.approval['metadata']['uid'], self.record['epoch'], self.state,
                self.record['accounts']['worker']['uid'], common.canonical(self.record['pins']))


class Authority:
    def __init__(self, kube, cfg, clock=common.now):
        self.kube, self.cfg, self.clock = kube, cfg, clock

    def request(self, names):
        obj = self.kube.get(names.request_path)
        common.require(obj is not None, 403, 'RequestMissing')
        meta, spec = obj.get('metadata') or {}, obj.get('spec')
        common.require(not meta.get('deletionTimestamp'), 403, 'RequestDeleting')
        common.require(meta.get('name') == names.agent and isinstance(meta.get('uid'), str) and meta['uid'],
                       503, 'AuthorityUnavailable')
        common.require(isinstance(spec, dict) and set(spec) == {'profileRef', 'instructions'}
                       and spec['profileRef'] == self.cfg['profile'], 403, 'RequestProfileRejected')
        return obj

    def inventory(self, names, request_uid):
        found = {}
        for child in names.children:
            obj = self.kube.get(child[5])
            common.require(obj is not None, 403, 'BindingMissing')
            meta = obj.get('metadata') or {}
            common.require(not meta.get('deletionTimestamp') and meta.get('name') == child[4]
                           and (meta.get('labels') or {}).get(KRO_INSTANCE) == request_uid, 403, 'BindingChanged')
            found[child[0]] = obj
        return found

    def approval(self, names, request_uid):
        cm = self.kube.get(names.approval_path)
        common.require(cm is not None, 403, 'ApprovalMissing')
        meta = cm.get('metadata') or {}
        common.require(not meta.get('deletionTimestamp')
                       and (meta.get('annotations') or {}).get(EXPECTED_UID) == request_uid
                       and (meta.get('labels') or {}).get(KRO_INSTANCE) == request_uid, 403, 'ApprovalNotForRequest')
        return cm

    def snapshot(self, agent):
        names = Names(self.cfg, agent)
        request = self.request(names)
        uid = request['metadata']['uid']
        cm = self.approval(names, uid)
        data = cm.get('data') or {}
        state = data.get('state')
        if state not in ('Verifying', 'Active'):
            return Snapshot(names, request, cm, state)
        common.require(set(data) == DATA_KEYS and data['requestUID'] == uid, 403, 'ApprovalRejected')
        try:
            record = common.loads(data['approval.json'].encode(), 65536)
        except common.Denied:
            raise common.Denied(403, 'ApprovalRejected') from None
        self.check_record(names, request, cm, data, record)
        common.require(self.clock() < common.parse_stamp(data['expiresAt']), 403, 'ApprovalExpired')
        inventory = self.inventory(names, uid)
        common.require([pin(c, inventory[c[0]]) for c in names.children] == record['pins'], 403, 'BindingChanged')
        accounts = record['accounts']
        verifier = self.kube.get(names.verifier_path)
        common.require(verifier is not None and verifier['metadata'].get('uid') == accounts['verifier']['uid']
                       and inventory['callerAccount']['metadata']['uid'] == accounts['caller']['uid']
                       and inventory['workerAccount']['metadata']['uid'] == accounts['worker']['uid'],
                       403, 'AccountChanged')
        return Snapshot(names, request, cm, state, record)

    def check_record(self, names, request, cm, data, record):
        uid = request['metadata']['uid']
        accounts = record.get('accounts') if isinstance(record, dict) else None
        pins = record.get('pins') if isinstance(record, dict) else None
        common.require(
            isinstance(record, dict) and record.get('schema') == APPROVAL_SCHEMA and record.get('state') == data['state']
            and record.get('requestName') == names.agent and record.get('requestUID') == uid
            and record.get('approvalUID') == cm['metadata'].get('uid')
            and record.get('requestGeneration') == request['metadata'].get('generation')
            and record.get('requestSpecSha256') == common.canonical(request['spec'])
            and record.get('platformConfigSha256') == common.canonical(self.cfg)
            and record.get('expiresAt') == data['expiresAt'] and isinstance(record.get('epoch'), str)
            and isinstance(accounts, dict) and set(accounts) == set(names.subjects)
            and all(isinstance(accounts[r], dict) and accounts[r].get('subject') == names.subjects[r]
                    and isinstance(accounts[r].get('uid'), str) and accounts[r]['uid'] for r in names.subjects)
            and isinstance(pins, list) and [p.get('id') if isinstance(p, dict) else None for p in pins]
            == [c[0] for c in names.children], 403, 'ApprovalRejected')

    def review(self, authorization):
        """Kubernetes TokenReview for the shared Gateway audience; returns (username, uid)."""
        common.require(isinstance(authorization, str) and authorization.startswith('Bearer ')
                       and common.TOKEN.fullmatch(authorization[7:]) is not None, 401, 'BearerRequired')
        status, value = self.kube.call('POST', '/apis/authentication.k8s.io/v1/tokenreviews', {
            'apiVersion': 'authentication.k8s.io/v1', 'kind': 'TokenReview',
            'spec': {'token': authorization[7:], 'audiences': [self.cfg['audience']]}})
        common.require(status in (200, 201) and isinstance(value, dict), 503, 'AuthorityUnavailable')
        result = value.get('status') or {}
        user = result.get('user') or {}
        common.require(result.get('authenticated') is True and not result.get('error')
                       and self.cfg['audience'] in (result.get('audiences') or [])
                       and isinstance(user.get('username'), str) and isinstance(user.get('uid'), str) and user['uid'],
                       401, 'TokenRejected')
        return user['username'], user['uid']

    def authorize(self, agent, lane, authorization):
        names = Names(self.cfg, agent)
        username, uid = self.review(authorization)
        role = next((r for r, subject in names.subjects.items() if subject == username), None)
        common.require(role is not None, 403, 'SubjectNotPermitted')
        common.require(role in LANES[lane], 403, 'LaneNotPermitted')
        snap = self.snapshot(agent)
        if snap.state not in LANES[lane][role]:
            reason = {'Revoked': 'ApprovalRevoked', 'Failed': 'ApprovalFailed'}.get(snap.state)
            raise common.Denied(403, reason or ('ApprovalNotActive' if role == 'caller' else
                                                'ApprovalNotVerifying' if lane == 'invoke' else 'ApprovalInactive'))
        common.require(snap.record['accounts'][role]['uid'] == uid, 403, 'AccountUIDMismatch')
        snap.role = role
        return snap
