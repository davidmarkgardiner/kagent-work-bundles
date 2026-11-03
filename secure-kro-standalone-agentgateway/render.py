#!/usr/bin/env python3
"""Render platform prerequisites, the KRO graph and an owner example. Writes new private files; applies nothing."""
import argparse
import ipaddress
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'app'))
import authority as auth  # noqa: E402
import common  # noqa: E402
import contract  # noqa: E402
import payload  # noqa: E402

SETTINGS_SCHEMA = 'secure-kro-standalone-settings/v1'
DNS_LABEL = re.compile(r'[a-z]([a-z0-9-]{0,61}[a-z0-9])?')
LABEL_KEY = re.compile(r'([a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?/)?[A-Za-z0-9]([A-Za-z0-9._-]{0,61}[A-Za-z0-9])?')
LABEL_VALUE = re.compile(r'[A-Za-z0-9]([A-Za-z0-9._-]{0,61}[A-Za-z0-9])?')
IMAGE = re.compile(r'[a-z0-9][a-z0-9._:/-]{0,254}@sha256:[0-9a-f]{64}')
SUBJECT = re.compile(r'[A-Za-z0-9:._@-]{1,253}')
SERVICE_HOST = re.compile(r'([a-z]([a-z0-9-]{0,61}[a-z0-9])?)\.([a-z]([a-z0-9-]{0,61}[a-z0-9])?)\.svc\.cluster\.local')
RGD_NAME = 'standalone-secure-agent-v1'
# Exact KRO/CEL reserved-ID union from KRO v0.9.4 pkg/graph/validation.go.
KRO_RESERVED_IDS = frozenset('''
    true false null in as break const continue else for function if import let loop package namespace return var void while
    apiVersion context dependency dependencies each externalRef externalReference externalRefs externalReferences graph
    instance item items kind kro metadata object resource resourcegraphdefinition resourceGraphDefinition resources root
    runtime schema self serviceAccountName spec status this variables vars version
'''.split())
PLATFORM_CM = 'standalone-platform'
PLATFORM_CODE = 'standalone-platform-code'
ACCOUNTS = {'facade': 'standalone-facade', 'verifier': 'standalone-verifier', 'negative': 'standalone-negative'}
PART_OF = {'app.kubernetes.io/part-of': 'secure-kro-standalone'}
POD_SECURITY = {'runAsNonRoot': True, 'runAsUser': 65532, 'runAsGroup': 65532, 'seccompProfile': {'type': 'RuntimeDefault'}}
CONTAINER_SECURITY = {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'runAsNonRoot': True,
                      'capabilities': {'drop': ['ALL']}}
RESOURCES = {'requests': {'cpu': '50m', 'memory': '64Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}
NAME_PATTERN = '^[a-z][a-z0-9-]{1,28}[a-z0-9]$'
N = '${schema.metadata.name}'


class Rejected(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise Rejected(reason)


def keys(value, required, optional=()):
    return isinstance(value, dict) and set(required) <= set(value) <= set(required) | set(optional)


def labels_ok(value):
    return (isinstance(value, dict) and 1 <= len(value) <= 4
            and all(isinstance(k, str) and LABEL_KEY.fullmatch(k) and isinstance(v, str) and LABEL_VALUE.fullmatch(v)
                    for k, v in value.items()))


def port_ok(value):
    return type(value) is int and 1 <= value <= 65535


def subjects_ok(value):
    return (keys(value, ('users', 'groups')) and all(isinstance(value[k], list) and len(value[k]) <= 8
            and all(isinstance(s, str) and SUBJECT.fullmatch(s) for s in value[k]) for k in ('users', 'groups')))


def upstream(url):
    need(isinstance(url, str) and len(url) <= 512 and not re.search(r'[\s%\x00-\x1f]', url), 'InvalidModelURL')
    p = urllib.parse.urlsplit(url)
    host = SERVICE_HOST.fullmatch(p.hostname or '')
    need(p.scheme in ('http', 'https') and host and p.port and p.username is None and p.password is None
         and not p.query and not p.fragment and p.path.endswith('/chat/completions')
         and '..' not in p.path.split('/'), 'InvalidModelURL')
    return host.group(3), p.port


def jwks_ok(value):
    private = {'d', 'p', 'q', 'dp', 'dq', 'qi', 'oth', 'k'}
    return (keys(value, ('keys',)) and isinstance(value['keys'], list) and 1 <= len(value['keys']) <= 8
            and all(isinstance(k, dict) and k.get('kty') in ('RSA', 'EC') and not private & set(k)
                    and k.get('use', 'sig') == 'sig' for k in value['keys']))


def strings(value):
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in [k] + strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return [value] if isinstance(value, str) else []


def validate(raw):
    s = common.loads(raw, 262144)
    need(not any('{{' in v or '}}' in v for v in strings(s)), 'UnresolvedPlaceholder')
    need(keys(s, ('schema', 'standaloneNamespace', 'image', 'gateway', 'jwt', 'model', 'apiServer', 'dns', 'approval'),
              ('imagePullSecrets', 'limits', 'revokers', 'submitters')) and s['schema'] == SETTINGS_SCHEMA,
         'InvalidSettingsFields')
    need(isinstance(s['standaloneNamespace'], str) and DNS_LABEL.fullmatch(s['standaloneNamespace']), 'InvalidNamespace')
    need(isinstance(s['image'], str) and IMAGE.fullmatch(s['image']), 'ImageMustBeDigestPinned')
    pulls = s.setdefault('imagePullSecrets', [])
    need(isinstance(pulls, list) and len(pulls) <= 4 and all(isinstance(p, str) and DNS_LABEL.fullmatch(p) for p in pulls),
         'InvalidImagePullSecrets')
    g = s['gateway']
    need(keys(g, ('create', 'name', 'namespace', 'className', 'controllerName', 'listenerName', 'port', 'serviceHost',
                  'podLabels'), ('podPort',)) and type(g['create']) is bool
         and all(isinstance(g[k], str) and DNS_LABEL.fullmatch(g[k]) for k in ('name', 'namespace', 'className', 'listenerName'))
         and isinstance(g['controllerName'], str) and re.fullmatch(r'[a-z0-9.-]{1,253}/[A-Za-z0-9._-]{1,63}', g['controllerName'])
         and port_ok(g['port']) and port_ok(g.setdefault('podPort', g['port'])) and labels_ok(g['podLabels']),
         'InvalidGatewaySettings')
    host = SERVICE_HOST.fullmatch(g['serviceHost']) if isinstance(g['serviceHost'], str) else None
    need(host and host.group(3) == g['namespace'], 'GatewayServiceMustBeInGatewayNamespace')
    need(g['namespace'] != s['standaloneNamespace'], 'GatewayNamespaceMustDiffer')
    j = s['jwt']
    need(keys(j, ('issuer', 'jwks')) and isinstance(j['issuer'], str) and 1 <= len(j['issuer']) <= 256
         and not re.search(r'[\s\x00-\x1f]', j['issuer']) and jwks_ok(j['jwks']), 'InvalidJWTSettings')
    need(len(inline_jwks(s)) <= 65536, 'JWKSTooLarge')
    m = s['model']
    need(keys(m, ('upstreamURL', 'name', 'podLabels'), ('podPort',)) and isinstance(m['name'], str)
         and re.fullmatch(r'[A-Za-z0-9._:/-]{1,128}', m['name']) and labels_ok(m['podLabels']), 'InvalidModelSettings')
    m['namespace'], port = upstream(m['upstreamURL'])
    need(port_ok(m.setdefault('podPort', port)), 'InvalidModelSettings')
    need(m['namespace'] not in (s['standaloneNamespace'], g['namespace']), 'ModelNamespaceMustDiffer')
    a = s['apiServer']
    need(keys(a, ('cidrs', 'ports')) and isinstance(a['cidrs'], list) and 1 <= len(a['cidrs']) <= 4
         and isinstance(a['ports'], list) and 1 <= len(a['ports']) <= 2 and all(port_ok(p) for p in a['ports']),
         'InvalidAPIServerSettings')
    for cidr in a['cidrs']:
        try:
            net = ipaddress.ip_network(cidr, strict=True)
        except (TypeError, ValueError):
            raise Rejected('InvalidAPIServerCIDR') from None
        need(net.prefixlen == net.max_prefixlen and not (net.network_address.is_unspecified or net.network_address.is_loopback
                                                          or net.network_address.is_multicast), 'APIServerCIDRMustBeOneHost')
    d = s['dns']
    need(keys(d, ('namespace', 'podLabels')) and isinstance(d['namespace'], str) and DNS_LABEL.fullmatch(d['namespace'])
         and labels_ok(d['podLabels']), 'InvalidDNSSettings')
    limits = s.setdefault('limits', {k: v.default for k, v in contract.LIMITS.items()})
    need(contract.limits_ok(limits), 'InvalidLimits')
    ap = s['approval']
    need(keys(ap, ('verifyingSeconds', 'activeSeconds')) and type(ap['verifyingSeconds']) is int
         and limits['deadlineSeconds'] + 120 <= ap['verifyingSeconds'] <= 3600 and type(ap['activeSeconds']) is int
         and 600 <= ap['activeSeconds'] <= 86400, 'InvalidApprovalWindows')
    for field in ('revokers', 'submitters'):
        need(subjects_ok(s.setdefault(field, {'users': [], 'groups': []})), 'InvalidSubjects')
    verifier = 'system:serviceaccount:' + s['standaloneNamespace'] + ':' + ACCOUNTS['verifier']
    need(verifier not in s['revokers']['users'], 'VerifierCannotRevoke')
    return s


def inline_jwks(s):
    return json.dumps(s['jwt']['jwks'], sort_keys=True, separators=(',', ':'))


def base_url(s):
    return 'http://' + s['gateway']['serviceHost'] + ':' + str(s['gateway']['port'])


def meta(name, namespace=None, labels=None, annotations=None):
    out = {'name': name}
    if namespace:
        out['namespace'] = namespace
    out['labels'] = dict(PART_OF, **(labels or {}))
    if annotations:
        out['annotations'] = annotations
    return out


def peer(namespace, labels):
    return {'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': namespace}},
            'podSelector': {'matchLabels': dict(labels)}}


def role(name):
    return {'matchLabels': {auth.LABEL_ROLE: name}}


def tcp(*ports):
    return [{'protocol': 'TCP', 'port': p} for p in ports]


def api_volume():
    return {'name': 'api', 'projected': {'sources': [
        {'serviceAccountToken': {'expirationSeconds': 3600, 'path': 'token'}},
        {'configMap': {'name': 'kube-root-ca.crt', 'items': [{'key': 'ca.crt', 'path': 'ca.crt'}]}}]}}


def gateway_volume():
    return {'name': 'gateway-token', 'projected': {'sources': [
        {'serviceAccountToken': {'audience': auth.GATEWAY_AUDIENCE, 'expirationSeconds': 3600, 'path': 'token'}}]}}


def negative_audience_volume():
    return {'name': 'negative-audience-token', 'projected': {'sources': [
        {'serviceAccountToken': {'audience': auth.NEGATIVE_AUDIENCE, 'expirationSeconds': 3600,
                                 'path': Path(auth.NEGATIVE_AUDIENCE_TOKEN_FILE).name}}]}}


def mount(name, path):
    return {'name': name, 'mountPath': path, 'readOnly': True}


def container(s, name, args, mounts, env=None):
    out = {'name': name, 'image': s['image'], 'imagePullPolicy': 'IfNotPresent', 'command': list(payload.COMMAND), 'args': args,
           'resources': RESOURCES, 'securityContext': CONTAINER_SECURITY, 'volumeMounts': mounts}
    if env:
        out['env'] = env
    return out


def pod_spec(s, account, containers, volumes, **extra):
    out = {'serviceAccountName': account, 'automountServiceAccountToken': False, 'enableServiceLinks': False,
           'securityContext': POD_SECURITY, 'containers': containers, 'volumes': volumes, **extra}
    if s['imagePullSecrets']:
        out['imagePullSecrets'] = [{'name': n} for n in s['imagePullSecrets']]
    return out


def platform_config(s, model_binding, content_binding, code):
    g = s['gateway']
    cfg = {'schema': auth.PLATFORM_SCHEMA, 'profile': contract.PROFILE, 'standaloneNamespace': s['standaloneNamespace'],
           'audience': auth.GATEWAY_AUDIENCE, 'image': s['image'],
           'request': {'group': 'kro.run', 'version': 'v1alpha1', 'plural': 'standalonesecureagents',
                       'kind': 'StandaloneSecureAgent'},
           'accounts': dict(ACCOUNTS),
           'gateway': {'name': g['name'], 'namespace': g['namespace'], 'listenerName': g['listenerName'],
                       'controllerName': g['controllerName'], 'baseURL': base_url(s), 'port': g['port']},
           'jwt': {'issuer': s['jwt']['issuer'], 'jwksSha256': common.sha256(inline_jwks(s).encode())},
           'model': {'name': s['model']['name'], 'upstreamURL': s['model']['upstreamURL']},
           'limits': s['limits'], 'approval': dict(s['approval']),
           'bindings': {'modelSha256': common.canonical(model_binding), 'contentSha256': common.canonical(content_binding),
                        **code.hashes}}
    need(auth.platform_ok(cfg), 'InvalidPlatformConfig')
    return cfg


def rbac(s):
    ns, gns = s['standaloneNamespace'], s['gateway']['namespace']
    sa = {k: {'kind': 'ServiceAccount', 'name': v, 'namespace': ns} for k, v in ACCOUNTS.items()}

    def rule(group, resources, verbs, names=None):
        out = {'apiGroups': [group], 'resources': resources, 'verbs': verbs}
        if names:
            out['resourceNames'] = names
        return out

    def bind(kind, name, namespace, subjects):
        ref = {'apiGroup': 'rbac.authorization.k8s.io', 'kind': kind.replace('Binding', ''), 'name': name}
        return {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': kind, 'metadata': meta(name, namespace),
                'roleRef': ref, 'subjects': subjects}

    def humans(field):
        return ([{'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'User', 'name': u} for u in s[field]['users']]
                + [{'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Group', 'name': g} for g in s[field]['groups']])
    read_children = [rule('', ['configmaps', 'serviceaccounts', 'services'], ['get']),
                     rule('apps', ['deployments'], ['get']),
                     rule('gateway.networking.k8s.io', ['referencegrants'], ['get'])]
    roles = [
        ('ClusterRole', 'standalone-secure-tokenreview', None, [rule('authentication.k8s.io', ['tokenreviews'], ['create'])],
         [sa['facade']]),
        ('ClusterRole', 'standalone-secure-request-reader', None, [rule('kro.run', ['standalonesecureagents'], ['get'])],
         [sa['facade'], sa['verifier']]),
        ('Role', 'standalone-secure-facade', ns, read_children, [sa['facade']]),
        ('Role', 'standalone-secure-route-reader', gns,
         [rule('gateway.networking.k8s.io', ['httproutes'], ['get']),
          rule('agentgateway.dev', ['agentgatewaypolicies'], ['get'])], [sa['facade'], sa['verifier']]),
        ('Role', 'standalone-secure-verifier', ns,
         read_children + [rule('batch', ['jobs'], ['get']), rule('', ['configmaps'], ['patch']),
                          rule('', ['serviceaccounts/token'], ['create'], [ACCOUNTS['negative']])], [sa['verifier']]),
        ('ClusterRole', 'standalone-secure-submitter', None,
         [rule('kro.run', ['standalonesecureagents'], ['get', 'list', 'watch', 'create', 'delete'])], humans('submitters')),
        ('Role', 'standalone-secure-revoker', ns, [rule('', ['configmaps'], ['get', 'patch'])], humans('revokers'))]
    items = []
    for kind, name, namespace, rules, subjects in roles:
        items.append({'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': kind, 'metadata': meta(name, namespace),
                      'rules': rules})
        if subjects:
            items.append(bind(kind + 'Binding', name, namespace, subjects))
    return items


def network_policies(s):
    ns, g, m, d = s['standaloneNamespace'], s['gateway'], s['model'], s['dns']
    gateway = [{'to': [peer(g['namespace'], g['podLabels'])], 'ports': tcp(g['podPort'])}]
    dns = [{'to': [peer(d['namespace'], d['podLabels'])],
            'ports': [{'protocol': 'UDP', 'port': 53}, {'protocol': 'TCP', 'port': 53}]}]
    api = [{'to': [{'ipBlock': {'cidr': c}} for c in s['apiServer']['cidrs']], 'ports': tcp(*s['apiServer']['ports'])}]

    def policy(name, selector, ingress, egress):
        return {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': meta(name, ns),
                'spec': {'podSelector': selector, 'policyTypes': ['Ingress', 'Egress'], 'ingress': ingress,
                         'egress': egress}}
    return [
        policy('standalone-default-deny', {}, [], []),
        policy('standalone-runtime', role('runtime'),
               [{'from': [{'podSelector': role('facade')}], 'ports': tcp(8080)}], gateway + dns),
        policy('standalone-facade', role('facade'),
               [{'from': [peer(g['namespace'], g['podLabels'])], 'ports': tcp(8080)}],
               api + [{'to': [peer(m['namespace'], m['podLabels'])], 'ports': tcp(m['podPort'])},
                      {'to': [{'podSelector': role('runtime')}], 'ports': tcp(8080)}] + dns),
        policy('standalone-verifier', role('verifier'), [], api + gateway + dns)]


def approval_admission(s):
    ns = s['standaloneNamespace']
    verifier = 'system:serviceaccount:' + ns + ':' + ACCOUNTS['verifier']
    key = auth.EXPECTED_UID
    revoker = ('request.userInfo.username in ' + json.dumps(s['revokers']['users'])
               + ' || (has(request.userInfo.groups) && request.userInfo.groups.exists(g, g in '
               + json.dumps(s['revokers']['groups']) + '))')

    def annotation(obj):
        return "has(%s.metadata.annotations) && '%s' in %s.metadata.annotations ? %s.metadata.annotations['%s'] : ''" % (
            obj, key, obj, obj, key)
    variables = [
        ('verifier', "request.userInfo.username == '%s'" % verifier),
        ('revoker', revoker),
        ('newData', 'has(object.data) ? object.data : {}'),
        ('oldData', "request.operation == 'UPDATE' && has(oldObject.data) ? oldObject.data : {}"),
        ('newState', "'state' in variables.newData ? variables.newData['state'] : ''"),
        ('oldState', "'state' in variables.oldData ? variables.oldData['state'] : ''"),
        ('newAnnotation', annotation('object')),
        ('oldAnnotation', "request.operation == 'UPDATE' ? (%s) : ''" % annotation('oldObject')),
        ('changed', "request.operation == 'UPDATE' && variables.newData != variables.oldData")]
    verifier_rule = (
        "variables.newAnnotation != '' && variables.newAnnotation == variables.oldAnnotation"
        " && size(variables.newData) == 4"
        " && variables.newData.all(k, k in ['state', 'requestUID', 'expiresAt', 'approval.json'])"
        " && variables.newData['requestUID'] == variables.newAnnotation"
        " && ((size(variables.oldData) == 0 && variables.newState in ['Verifying', 'Failed'])"
        " || (variables.oldState == 'Verifying' && variables.newState in ['Active', 'Failed']"
        " && variables.oldData['requestUID'] == variables.newData['requestUID']))"
        " && (has(object.metadata.labels) ? object.metadata.labels : {})"
        " == (has(oldObject.metadata.labels) ? oldObject.metadata.labels : {})")
    revoke_rule = (
        "variables.oldState in ['Verifying', 'Active'] && variables.newState == 'Revoked'"
        " && size(variables.newData) == size(variables.oldData)"
        " && variables.oldData.all(k, k in variables.newData && (k == 'state' || variables.newData[k] == variables.oldData[k]))")
    validations = [
        ('!has(object.binaryData)', 'approval ConfigMaps never carry binaryData'),
        ("request.operation != 'CREATE' || size(variables.newData) == 0",
         'approval ConfigMaps are created metadata-only; the composer cannot create approval data'),
        ("request.operation != 'UPDATE' || variables.oldAnnotation == '' || variables.newAnnotation == variables.oldAnnotation",
         'expected-request-uid is immutable'),
        ('!variables.changed || variables.verifier || variables.revoker',
         'only the shared verifier may change approval data (composer self-approval denied)'),
        ('!variables.changed || !variables.verifier || (%s)' % verifier_rule,
         'verifier writes must follow Verifying then Active/Failed for the expected request UID'),
        ('!variables.changed || variables.verifier || !variables.revoker || (%s)' % revoke_rule,
         'revokers may only change state to Revoked, preserving all other approval data')]
    name = 'standalone-secure-approval-data'
    return [
        {'apiVersion': 'admissionregistration.k8s.io/v1', 'kind': 'ValidatingAdmissionPolicy', 'metadata': meta(name),
         'spec': {'failurePolicy': 'Fail',
                  'matchConstraints': {'resourceRules': [{'apiGroups': [''], 'apiVersions': ['v1'],
                                                          'operations': ['CREATE', 'UPDATE'], 'resources': ['configmaps']}]},
                  'matchConditions': [{'name': 'standalone-approval-configmaps',
                                       'expression': "request.namespace == '%s' && object.metadata.name.endsWith('-approval')" % ns}],
                  'variables': [{'name': n, 'expression': e} for n, e in variables],
                  'validations': [{'expression': e, 'message': msg} for e, msg in validations]}},
        {'apiVersion': 'admissionregistration.k8s.io/v1', 'kind': 'ValidatingAdmissionPolicyBinding',
         'metadata': meta(name),
         'spec': {'policyName': name, 'validationActions': ['Deny'],
                  'matchResources': {'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': ns}}}}}]


def kyverno(name, rules, autogen=False):
    annotations = None if autogen else {'pod-policies.kyverno.io/autogen-controllers': 'none'}
    return {'apiVersion': 'kyverno.io/v1', 'kind': 'ClusterPolicy', 'metadata': meta(name, annotations=annotations),
            'spec': {'background': False, 'rules': rules}}


def cel_rule(name, kinds, namespaces, expressions, variables=()):
    match = {'kinds': kinds, 'operations': ['CREATE', 'UPDATE']}
    if namespaces:
        match['namespaces'] = namespaces
    return {'name': name, 'match': {'any': [{'resources': match}]},
            'validate': {'failureAction': 'Enforce', 'cel': {
                'variables': [{'name': n, 'expression': e} for n, e in variables],
                'expressions': [{'expression': e, 'message': m} for e, m in expressions]}}}


class CEL(str):
    """A renderer-owned CEL operand; never used for owner-provided strings."""


def cel_equal(path, value):
    return path + ' == ' + (str(value) if isinstance(value, CEL) else json.dumps(value))


def cel_fields(path, expected):
    """Match known typed fields explicitly. Kubernetes structs are not iterable maps in CEL."""
    if isinstance(expected, dict):
        return ' && '.join('has(%s.%s) && (%s)' % (path, k, cel_fields(path + '.' + k, v))
                           for k, v in expected.items())
    if isinstance(expected, list):
        return 'size(%s) == %d%s' % (path, len(expected), ''.join(
            ' && (' + cel_fields(path + '[%d]' % i, v) + ')' for i, v in enumerate(expected)))
    return cel_equal(path, expected)


def absent(path, *fields):
    return ' && '.join('!has(%s.%s)' % (path, f) for f in fields)


def optional_default(path, field, value):
    return '(!has(%s.%s) || %s)' % (path, field, cel_equal(path + '.' + field, value))


def volume_contract(path, expected):
    out = [cel_equal(path + '.name', expected['name'])]
    if 'configMap' in expected:
        cm = path + '.configMap'
        wanted = expected['configMap']
        out += ['has(' + cm + ')', cel_equal(cm + '.name', wanted['name']),
                optional_default(cm, 'optional', False),
                optional_default(cm, 'defaultMode', wanted.get('defaultMode', 0o644))]
        if 'items' in wanted:
            out += ['has(' + cm + '.items)', cel_fields(cm + '.items', wanted['items']),
                    cm + '.items.all(i, !has(i.mode))']
        else:
            out.append('(!has(%s.items) || size(%s.items) == 0)' % (cm, cm))
    else:
        projection = path + '.projected'
        sources = expected['projected']['sources']
        out += ['has(' + projection + ')', optional_default(projection, 'defaultMode', 0o644),
                'size(%s.sources) == %d' % (projection, len(sources))]
        for i, source in enumerate(sources):
            field = next(iter(source))
            base = projection + '.sources[%d].' % i + field
            out += ['has(' + base + ')', cel_fields(base, source[field])]
            if field == 'serviceAccountToken' and 'audience' not in source[field]:
                out.append('!has(' + base + '.audience)')
            if field == 'configMap':
                out += [optional_default(base, 'optional', False), base + '.items.all(i, !has(i.mode))']
    return ' && '.join(out)


def role_volumes(code, role_name):
    agent = "string(variables.agent)"
    code_name = PLATFORM_CODE if role_name == 'facade' else CEL(agent + " + '-runtime-code'")
    if role_name == 'runtime':
        volumes = [gateway_volume(), {'name': 'model', 'configMap': {'name': CEL(agent + " + '-model'")}},
                   {'name': 'content', 'configMap': {'name': CEL(agent + " + '-content'")}}]
        mounts = [mount('gateway-token', str(Path(auth.GATEWAY_TOKEN_FILE).parent)),
                  mount('model', '/etc/standalone/model'), mount('content', '/etc/standalone/content')]
    elif role_name == 'facade':
        volumes = [api_volume(), {'name': 'platform', 'configMap': {'name': PLATFORM_CM}}]
        mounts = [mount('api', '/var/run/secrets/standalone/api'), mount('platform', '/etc/standalone/platform')]
    else:
        volumes = [api_volume(), gateway_volume(), negative_audience_volume(),
                   {'name': 'platform', 'configMap': {'name': PLATFORM_CM}}]
        mounts = [mount('api', '/var/run/secrets/standalone/api'),
                  mount('gateway-token', str(Path(auth.GATEWAY_TOKEN_FILE).parent)),
                  mount('negative-audience-token', str(Path(auth.NEGATIVE_AUDIENCE_TOKEN_FILE).parent)),
                  mount('platform', '/etc/standalone/platform')]
    return volumes + [code.volume(code_name)], mounts + [dict(payload.CODE_MOUNT)]


def role_contract(pod, code, role_name):
    c = pod + '.containers[0]'
    volumes, mounts = role_volumes(code, role_name)
    out = ['has(%s.volumes) && size(%s.volumes) == %d' % (pod, pod, len(volumes))]
    out += [volume_contract(pod + '.volumes[%d]' % i, v) for i, v in enumerate(volumes)]
    out += ['has(%s.volumeMounts)' % c, cel_fields(c + '.volumeMounts', mounts),
            c + '.volumeMounts.all(m, ' + absent('m', 'subPath', 'subPathExpr', 'mountPropagation', 'recursiveReadOnly') + ')',
            cel_equal(c + '.name', {'runtime': 'agent', 'facade': 'facade', 'verifier': 'golden'}[role_name])]
    if role_name == 'facade':
        out.append('(!has(%s.env) || size(%s.env) == 0)' % (c, c))
    elif role_name == 'runtime':
        env = c + '.env'
        out += ['has(%s) && size(%s) == 2' % (env, env),
                cel_fields(env + '[0]', {'name': 'AGENT_NAME', 'value': CEL('string(variables.agent)')}),
                cel_fields(env + '[1]', {'name': 'OWNER_INSTRUCTIONS'}),
                'has(%s[1].value) && size(%s[1].value) >= 1 && size(%s[1].value) <= %d'
                % (env, env, env, contract.MAX_INSTRUCTIONS),
                "!%s[1].value.matches('[\\\\x00-\\\\x1f\\\\x7f-\\\\x9f]')" % env,
                env + '.all(e, !has(e.valueFrom))']
    else:
        env = c + '.env'
        values = ('RUNTIME_DEPLOYMENT', 'ROUTE_NAME', 'POLICY_NAME')
        out += ['has(%s) && size(%s) == 4' % (env, env)]
        for i, name in enumerate(values):
            value = (CEL("string(variables.agent) + '-runtime'") if i == 0
                     else CEL(json.dumps(auth.ROUTE_PREFIX) + ' + string(variables.agent)'))
            out += [cel_fields(env + '[%d]' % i, {'name': name, 'value': value}),
                    '!has(%s[%d].valueFrom)' % (env, i)]
        field_ref = env + '[3].valueFrom.fieldRef'
        out += [cel_fields(env + '[3]', {'name': 'POD_UID', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.uid'}}}),
                '!has(%s[3].value)' % env, optional_default(field_ref, 'apiVersion', 'v1')]
    if role_name == 'verifier':
        out.append('!has(%s.readinessProbe)' % c)
    else:
        probe = c + '.readinessProbe'
        out += ['has(' + probe + ')', cel_fields(probe, {'httpGet': {'path': '/healthz', 'port': 8080}, 'periodSeconds': 10}),
                absent(probe, 'exec', 'tcpSocket', 'grpc', 'terminationGracePeriodSeconds'),
                optional_default(probe, 'initialDelaySeconds', 0), optional_default(probe, 'timeoutSeconds', 1),
                optional_default(probe, 'successThreshold', 1), optional_default(probe, 'failureThreshold', 3),
                optional_default(probe + '.httpGet', 'host', ''), optional_default(probe + '.httpGet', 'scheme', 'HTTP'),
                '(!has(%s.httpGet.httpHeaders) || size(%s.httpGet.httpHeaders) == 0)' % (probe, probe)]
    return ' && '.join('(' + v + ')' for v in out)


def execution_contract(pod, s):
    c = pod + '.containers[0]'
    return ' && '.join([
        'size(%s.containers) == 1' % pod,
        '(!has(%s.initContainers) || size(%s.initContainers) == 0)' % (pod, pod),
        '(!has(%s.ephemeralContainers) || size(%s.ephemeralContainers) == 0)' % (pod, pod),
        cel_fields(c, {'image': s['image'], 'imagePullPolicy': 'IfNotPresent', 'command': list(payload.COMMAND),
                       'securityContext': CONTAINER_SECURITY}),
        absent(c, 'envFrom', 'workingDir', 'lifecycle', 'livenessProbe', 'startupProbe'),
        optional_default(c, 'stdin', False), optional_default(c, 'tty', False),
        optional_default(c + '.securityContext', 'privileged', False),
        '(!has(%s.securityContext.capabilities.add) || size(%s.securityContext.capabilities.add) == 0)' % (c, c),
        absent(c + '.securityContext', 'runAsUser', 'runAsGroup', 'procMount', 'seLinuxOptions', 'windowsOptions'),
        cel_fields(pod, {'automountServiceAccountToken': False, 'enableServiceLinks': False, 'securityContext': POD_SECURITY}),
        optional_default(pod, 'hostNetwork', False), optional_default(pod, 'hostPID', False),
        optional_default(pod, 'hostIPC', False), optional_default(pod, 'shareProcessNamespace', False),
        '(!has(%s.hostAliases) || size(%s.hostAliases) == 0)' % (pod, pod),
        '!has(%s.dnsConfig)' % pod, optional_default(pod, 'dnsPolicy', 'ClusterFirst')])


def workload_guard(s, code):
    ns = s['standaloneNamespace']
    one = "size(object.spec.containers) == 1 && has(object.spec.containers[0].args)"
    pod = cel_rule('standalone-pods', ['Pod'], [ns], [
        (execution_contract('object.spec', s), 'only the approved helper, Python command and restricted execution shape'),
        ("(variables.role == 'facade' && object.spec.serviceAccountName == '%s' && %s"
         " && object.spec.containers[0].args == ['facade'])"
         " || (variables.role == 'runtime' && variables.agent.matches('%s')"
         " && object.spec.serviceAccountName == variables.agent + '-worker' && %s"
         " && object.spec.containers[0].args == ['agent'])"
         " || (variables.role == 'verifier' && variables.agent.matches('%s')"
         " && object.spec.serviceAccountName == '%s' && %s"
         " && object.spec.containers[0].args == ['golden', '--request', string(variables.agent)]"
         " && ((has(object.metadata.ownerReferences)"
         " && object.metadata.ownerReferences.exists(o, o.kind == 'Job' && o.name == variables.agent + '-golden'))"
         " || (request.operation == 'UPDATE'"
         " && has(oldObject.status) && has(oldObject.status.phase)"
         " && oldObject.status.phase in ['Succeeded', 'Failed']"
         " && has(oldObject.metadata.ownerReferences)"
         " && oldObject.metadata.ownerReferences.exists(o, o.kind == 'Job' && o.name == variables.agent + '-golden')"
         " && (!has(object.metadata.ownerReferences) || size(object.metadata.ownerReferences) == 0))))"
         % (ACCOUNTS['facade'], one, NAME_PATTERN, one, NAME_PATTERN, ACCOUNTS['verifier'], one),
         'role label, service account, args and owner must match one approved standalone workload'),
        (' || '.join("(variables.role == '%s' && (%s))" % (r, role_contract('object.spec', code, r))
                     for r in ('facade', 'runtime', 'verifier')),
         'exact role code source, projection items, read-only mounts, environment and probes are required'),
        ("variables.volumes.all(v, !has(v.projected) || v.projected.sources.all(p, !has(p.serviceAccountToken)"
         " || (variables.role == 'runtime' && has(p.serviceAccountToken.audience) && p.serviceAccountToken.audience == '%s')"
         " || (variables.role == 'facade' && !has(p.serviceAccountToken.audience))"
         " || (variables.role == 'verifier' && (!has(p.serviceAccountToken.audience)"
         " || p.serviceAccountToken.audience in %s))))"
         % (auth.GATEWAY_AUDIENCE, json.dumps([auth.GATEWAY_AUDIENCE, auth.NEGATIVE_AUDIENCE])),
         'runtime gets only the Gateway audience; facade only the API audience; verifier also gets the denial-probe audience')],
        [('labels', 'has(object.metadata.labels) ? object.metadata.labels : {}'),
         ('role', "'%s' in variables.labels ? variables.labels['%s'] : ''" % (auth.LABEL_ROLE, auth.LABEL_ROLE)),
         ('agent', "'%s' in variables.labels ? variables.labels['%s'] : ''" % (auth.LABEL_AGENT, auth.LABEL_AGENT)),
         ('volumes', 'has(object.spec.volumes) ? object.spec.volumes : []')])
    job = cel_rule('standalone-golden-jobs', ['Job'], [ns], [
        ("object.metadata.name == variables.agent + '-golden' && variables.agent.matches('%s')"
         " && has(object.spec.backoffLimit) && object.spec.backoffLimit == 0 && !has(object.spec.ttlSecondsAfterFinished)"
         % NAME_PATTERN, 'only <agent>-golden verifier Jobs, no retries and no TTL re-run'),
        ("variables.pod.serviceAccountName == '%s' && has(variables.pod.containers[0].args)"
         " && variables.pod.containers[0].args == ['golden', '--request', string(variables.agent)]"
         " && variables.pod.restartPolicy == 'Never'" % ACCOUNTS['verifier'],
         'verifier Jobs run the fixed golden args as the shared verifier only'),
        (execution_contract('variables.pod', s), 'verifier templates must have the exact restricted Python execution shape'),
        (role_contract('variables.pod', code, 'verifier'), 'verifier templates must have exact code, mounts and environment')],
        [('labels', 'has(object.spec.template.metadata.labels) ? object.spec.template.metadata.labels : {}'),
         ('agent', "'%s' in variables.labels && variables.labels['%s'] == 'verifier' && '%s' in variables.labels"
                   " ? variables.labels['%s'] : ''" % (auth.LABEL_ROLE, auth.LABEL_ROLE, auth.LABEL_AGENT, auth.LABEL_AGENT)),
         ('pod', 'object.spec.template.spec')])
    return kyverno('standalone-secure-workloads', [pod, job])


def code_guard(s, code):
    match = {'any': [{'resources': {'kinds': ['ConfigMap'], 'operations': ['CREATE', 'UPDATE'],
                                   'namespaces': [s['standaloneNamespace']],
                                   'names': [PLATFORM_CODE, '*-runtime-code']}}]}
    exact = {'name': 'standalone-code-bytes', 'match': match,
             'validate': {'failureAction': 'Enforce', 'message': 'only the reviewed immutable code bytes',
                          'pattern': {'immutable': True, 'binaryData': code.binary_data}}}
    keys = cel_rule('standalone-code-keyset', ['ConfigMap'], [s['standaloneNamespace']], [
        ('!has(object.data) && has(object.immutable) && object.immutable == true && has(object.binaryData)'
         ' && size(object.binaryData) == %d && object.binaryData.all(k, k in %s)' % (len(code.files), json.dumps(list(code.binary_data))),
         'code ConfigMaps have exactly the approved binaryData keys, immutable true and no alternate data')])
    keys['match'] = match
    return kyverno('standalone-secure-code', [exact, keys])


def request_guard():
    rule = cel_rule('standalone-requests', ['kro.run/v1alpha1/StandaloneSecureAgent'], None, [
        ("object.metadata.name.matches('%s')" % NAME_PATTERN, 'request names are 3-30 lowercase DNS characters'),
        ("has(object.spec.profileRef) && object.spec.profileRef == '%s'" % contract.PROFILE, 'only the approved profile'),
        ("has(object.spec.instructions) && size(object.spec.instructions) >= 1 && size(object.spec.instructions) <= %d"
         " && !object.spec.instructions.matches('[\\\\x00-\\\\x1f\\\\x7f-\\\\x9f]')" % contract.MAX_INSTRUCTIONS,
         'instructions are bounded single-paragraph text'),
        ("request.operation != 'UPDATE' || object.spec == oldObject.spec",
         'requests are immutable: create a new name for any change')])
    return kyverno('standalone-secure-requests', [rule], autogen=True)


def facade_deployment(s, code):
    labels = {auth.LABEL_ROLE: 'facade'}
    pod = pod_spec(s, ACCOUNTS['facade'], [dict(
        container(s, 'facade', ['facade'], [mount('api', '/var/run/secrets/standalone/api'),
                                            mount('platform', '/etc/standalone/platform'), dict(payload.CODE_MOUNT)]),
        ports=[{'name': 'http', 'containerPort': 8080}],
        readinessProbe={'httpGet': {'path': '/healthz', 'port': 8080}, 'periodSeconds': 10})],
        [api_volume(), {'name': 'platform', 'configMap': {'name': PLATFORM_CM}}, code.volume(PLATFORM_CODE)])
    return {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': meta(ACCOUNTS['facade'], s['standaloneNamespace'], labels),
            'spec': {'replicas': 1, 'revisionHistoryLimit': 1, 'strategy': {'type': 'Recreate'},
                     'selector': {'matchLabels': labels},
                     'template': {'metadata': {'labels': labels}, 'spec': pod}}}


def platform(s, cfg, code):
    ns, g = s['standaloneNamespace'], s['gateway']
    psa = {'pod-security.kubernetes.io/' + k: v for k, v in (('enforce', 'restricted'), ('enforce-version', 'latest'),
                                                              ('audit', 'restricted'), ('warn', 'restricted'))}
    items = [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': meta(ns, labels=psa)}]
    items += [{'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': meta(v, ns), 'automountServiceAccountToken': False}
              for v in ACCOUNTS.values()]
    items.append({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': meta(PLATFORM_CM, ns), 'immutable': True,
                  'data': {'platform.json': json.dumps(cfg, sort_keys=True, indent=1)}})
    items.append(code.config_map(meta(PLATFORM_CODE, ns)))
    items += rbac(s) + network_policies(s) + approval_admission(s) + [workload_guard(s, code), code_guard(s, code)]
    if g['create']:
        items.append({'apiVersion': 'gateway.networking.k8s.io/v1', 'kind': 'Gateway', 'metadata': meta(g['name'], g['namespace']),
                      'spec': {'gatewayClassName': g['className'], 'listeners': [{
                          'name': g['listenerName'], 'port': g['port'], 'protocol': 'HTTP',
                          'allowedRoutes': {'namespaces': {'from': 'Same'},
                                            'kinds': [{'group': 'gateway.networking.k8s.io', 'kind': 'HTTPRoute'}]}}]}})
    items.append(facade_deployment(s, code))
    return {'apiVersion': 'v1', 'kind': 'List', 'items': items}


def graph(s, model_binding, content_binding, code):
    ns, g = s['standaloneNamespace'], s['gateway']
    gns, controller = g['namespace'], g['controllerName']

    def labels(role_name):
        return {auth.LABEL_AGENT: N, auth.LABEL_ROLE: role_name}

    def subject(account):
        return 'system:serviceaccount:' + ns + ':' + account
    runtime_labels = labels('runtime')
    expression = 'jwt.sub in ' + json.dumps([subject(N + '-caller'), subject(N + '-worker'), subject(ACCOUNTS['verifier'])])
    current = lambda node: "c.observedGeneration == %s.metadata.generation" % node  # noqa: E731
    resources = [
        {'id': 'workerAccount', 'template': {'apiVersion': 'v1', 'kind': 'ServiceAccount',
                                             'metadata': meta(N + '-worker', ns, labels('worker')),
                                             'automountServiceAccountToken': False}},
        {'id': 'callerAccount', 'template': {'apiVersion': 'v1', 'kind': 'ServiceAccount',
                                             'metadata': meta(N + '-caller', ns, labels('caller')),
                                             'automountServiceAccountToken': False}},
        {'id': 'modelBinding', 'template': {'apiVersion': 'v1', 'kind': 'ConfigMap',
                                            'metadata': meta(N + '-model', ns, labels('binding')), 'immutable': True,
                                            'data': {'model.json': json.dumps(model_binding, sort_keys=True)}}},
        {'id': 'contentBinding', 'template': {'apiVersion': 'v1', 'kind': 'ConfigMap',
                                              'metadata': meta(N + '-content', ns, labels('binding')), 'immutable': True,
                                              'data': {'content.json': json.dumps(content_binding, sort_keys=True)}}},
        {'id': 'runtimeCode', 'template': code.config_map(meta(N + '-runtime-code', ns, labels('code')))},
        {'id': 'agentDeployment', 'template': {'apiVersion': 'apps/v1', 'kind': 'Deployment',
                                       'metadata': meta(N + '-runtime', ns, runtime_labels),
                                       'spec': {'replicas': 1, 'revisionHistoryLimit': 1, 'strategy': {'type': 'Recreate'},
                                                'selector': {'matchLabels': runtime_labels},
                                                'template': {'metadata': {'labels': runtime_labels}, 'spec': pod_spec(
                                                    s, '${workerAccount.metadata.name}', [dict(container(
                                                        s, 'agent', ['agent'],
                                                        [mount('gateway-token', str(Path(auth.GATEWAY_TOKEN_FILE).parent)),
                                                         mount('model', '/etc/standalone/model'),
                                                         mount('content', '/etc/standalone/content'), dict(payload.CODE_MOUNT)],
                                                        [{'name': 'AGENT_NAME', 'value': N},
                                                         {'name': 'OWNER_INSTRUCTIONS', 'value': '${schema.spec.instructions}'}]),
                                                        ports=[{'name': 'http', 'containerPort': 8080}],
                                                        readinessProbe={'httpGet': {'path': '/healthz', 'port': 8080},
                                                                        'periodSeconds': 10})],
                                                    [gateway_volume(),
                                                     {'name': 'model', 'configMap': {'name': '${modelBinding.metadata.name}'}},
                                                     {'name': 'content', 'configMap': {'name': '${contentBinding.metadata.name}'}},
                                                     code.volume('${runtimeCode.metadata.name}')])}}},
         'readyWhen': ['${agentDeployment.status.observedGeneration == agentDeployment.metadata.generation}',
                       '${agentDeployment.status.replicas == 1}', '${agentDeployment.status.updatedReplicas == 1}',
                       '${agentDeployment.status.availableReplicas == 1}']},
        {'id': 'runtimeService', 'template': {'apiVersion': 'v1', 'kind': 'Service',
                                              'metadata': meta(N + '-runtime', ns, runtime_labels),
                                              'spec': {'type': 'ClusterIP', 'selector': runtime_labels,
                                                       'ports': [{'name': 'http', 'port': 8080, 'targetPort': 8080,
                                                                  'protocol': 'TCP'}]}}},
        {'id': 'frontService', 'template': {'apiVersion': 'v1', 'kind': 'Service',
                                            'metadata': meta(N + '-front', ns, labels('front')),
                                            'spec': {'type': 'ClusterIP', 'selector': {auth.LABEL_ROLE: 'facade'},
                                                     'ports': [{'name': 'http', 'port': 8080, 'targetPort': 8080,
                                                                'protocol': 'TCP'}]}}},
        {'id': 'frontGrant', 'template': {'apiVersion': 'gateway.networking.k8s.io/v1beta1', 'kind': 'ReferenceGrant',
                                          'metadata': meta(N + '-front', ns, labels('front')),
                                          'spec': {'from': [{'group': 'gateway.networking.k8s.io', 'kind': 'HTTPRoute',
                                                             'namespace': gns}],
                                                   'to': [{'group': '', 'kind': 'Service',
                                                           'name': '${frontService.metadata.name}'}]}}},
        {'id': 'route', 'template': {'apiVersion': 'gateway.networking.k8s.io/v1', 'kind': 'HTTPRoute',
                                     'metadata': meta(auth.ROUTE_PREFIX + N, gns, labels('route'),
                                                      {'standalone-secure.platform/reference-grant': '${frontGrant.metadata.name}'}),
                                     'spec': {'parentRefs': [{'group': 'gateway.networking.k8s.io', 'kind': 'Gateway',
                                                              'name': g['name'], 'namespace': gns,
                                                              'sectionName': g['listenerName']}],
                                              'rules': [{'matches': [{'path': {'type': 'PathPrefix',
                                                                               'value': '/agents/' + N + '/'}}],
                                                         'backendRefs': [{'group': '', 'kind': 'Service',
                                                                          'name': '${frontService.metadata.name}',
                                                                          'namespace': ns, 'port': 8080, 'weight': 1}],
                                                         'timeouts': {'request': str(s['limits']['deadlineSeconds'] + 30) + 's'}}]}},
         'readyWhen': ["${route.status.parents.exists(p, p.controllerName == '%s' && p.parentRef.name == '%s'"
                       " && p.conditions.exists(c, c.type == 'Accepted' && c.status == 'True' && %s)"
                       " && p.conditions.exists(c, c.type == 'ResolvedRefs' && c.status == 'True' && %s))}"
                       % (controller, g['name'], current('route'), current('route'))]},
        {'id': 'routePolicy', 'template': {'apiVersion': 'agentgateway.dev/v1alpha1', 'kind': 'AgentgatewayPolicy',
                                           'metadata': meta(auth.ROUTE_PREFIX + N, gns, labels('policy')),
                                           'spec': {'targetRefs': [{'group': 'gateway.networking.k8s.io', 'kind': 'HTTPRoute',
                                                                    'name': '${route.metadata.name}'}],
                                                    'traffic': {'jwtAuthentication': {
                                                        'mode': 'Strict', 'preserveToken': True,
                                                        'providers': [{'issuer': s['jwt']['issuer'], 'audiences': [auth.GATEWAY_AUDIENCE],
                                                                       'jwks': {'inline': inline_jwks(s)}}]},
                                                        'authorization': {'action': 'Require',
                                                                          'policy': {'matchExpressions': [expression]}}}}},
         'readyWhen': ["${routePolicy.status.ancestors.exists(a, a.controllerName == '%s'"
                       " && a.conditions.exists(c, c.type == 'Accepted' && c.status == 'True' && c.reason == 'Valid' && %s)"
                       " && a.conditions.exists(c, c.type == 'Attached' && c.status == 'True' && %s))}"
                       % (controller, current('routePolicy'), current('routePolicy'))]},
        {'id': 'approval', 'template': {'apiVersion': 'v1', 'kind': 'ConfigMap',
                                        'metadata': meta(N + '-approval', ns, labels('approval'),
                                                         {auth.EXPECTED_UID: '${schema.metadata.uid}'})},
         'readyWhen': ["${approval.data.state == 'Active'}",
                       "${approval.data.requestUID == approval.metadata.annotations['%s']}" % auth.EXPECTED_UID]},
        {'id': 'golden', 'template': {'apiVersion': 'batch/v1', 'kind': 'Job',
                                      'metadata': meta(N + '-golden', ns, labels('verifier')),
                                      'spec': {'backoffLimit': 0,
                                               'activeDeadlineSeconds': s['approval']['verifyingSeconds'] + 300,
                                               'template': {'metadata': {'labels': labels('verifier')}, 'spec': pod_spec(
                                                   s, ACCOUNTS['verifier'], [container(
                                                       s, 'golden', ['golden', '--request', N],
                                                       [mount('api', '/var/run/secrets/standalone/api'),
                                                        mount('gateway-token', str(Path(auth.GATEWAY_TOKEN_FILE).parent)),
                                                        mount('negative-audience-token',
                                                              str(Path(auth.NEGATIVE_AUDIENCE_TOKEN_FILE).parent)),
                                                        mount('platform', '/etc/standalone/platform'), dict(payload.CODE_MOUNT)],
                                                       [{'name': 'RUNTIME_DEPLOYMENT', 'value': '${agentDeployment.metadata.name}'},
                                                        {'name': 'ROUTE_NAME', 'value': '${route.metadata.name}'},
                                                        {'name': 'POLICY_NAME', 'value': '${routePolicy.metadata.name}'},
                                                        {'name': 'POD_UID', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.uid'}}}])],
                                                   [api_volume(), gateway_volume(), negative_audience_volume(),
                                                    {'name': 'platform', 'configMap': {'name': PLATFORM_CM}},
                                                    code.volume('${runtimeCode.metadata.name}')],
                                                   restartPolicy='Never')}}},
         'readyWhen': ['${golden.status.succeeded == 1}']}]
    rgd = {'apiVersion': 'kro.run/v1alpha1', 'kind': 'ResourceGraphDefinition', 'metadata': meta(RGD_NAME),
           'spec': {'schema': {'apiVersion': 'v1alpha1', 'kind': 'StandaloneSecureAgent', 'group': 'kro.run',
                               'scope': 'Cluster',
                               'spec': {'profileRef': 'string | required=true enum=%s immutable=true' % contract.PROFILE,
                                        'instructions': 'string | required=true minLength=1 maxLength=%d immutable=true'
                                                        % contract.MAX_INSTRUCTIONS},
                               'status': {'approvalState': '${approval.data.state}',
                                          'approvalExpiresAt': '${approval.data.expiresAt}',
                                          'goldenSucceeded': '${golden.status.succeeded}'}},
                    'resources': resources}}
    audit(rgd)
    return rgd


def expressions(value):
    if isinstance(value, dict):
        return [e for v in value.values() for e in expressions(v)]
    if isinstance(value, list):
        return [e for v in value for e in expressions(v)]
    return re.findall(r'\$\{([^}]*)\}', value) if isinstance(value, str) else []


def dependencies(resource, ids):
    return sorted({i for e in expressions(resource['template']) for i in ids if re.search(r'\b' + i + r'\.', e)})


def audit(rgd):
    resources = rgd['spec']['resources']
    ids = [r['id'] for r in resources]
    for rid in ids:
        need(rid not in KRO_RESERVED_IDS, 'ReservedResourceID:' + rid)
    allowed = {'schema.metadata.name', 'schema.metadata.uid', 'schema.spec.instructions'} | {i + '.metadata.name' for i in ids}
    for r in resources:
        need(set(expressions(r['template'])) <= allowed, 'UnexpectedTemplateExpression:' + r['id'])
        need('ownerReferences' not in json.dumps(r), 'OwnerReferencesForbidden')
        for ready in r.get('readyWhen', []):
            need(ready.startswith('${') and ready.endswith('}') and not any(
                re.search(r'\b' + other + r'\.', ready) for other in ids if other != r['id']), 'ReadyWhenMustBeSelfOnly')
    by_id = {r['id']: r for r in resources}
    need(not {'data', 'binaryData'} & set(by_id['approval']['template']), 'ApprovalTemplateMustBeMetadataOnly')
    need('approval' not in dependencies(by_id['golden'], ids), 'GoldenMustNotDependOnApproval')
    need({'agentDeployment', 'route', 'routePolicy', 'runtimeCode'} <= set(dependencies(by_id['golden'], ids)), 'GoldenDependencies')
    need(json.dumps(resources).count('${') == len(expressions(resources)), 'UnexpectedLiteralExpressionMarker')


def owner_example(name='docs-demo'):
    return ('apiVersion: kro.run/v1alpha1\nkind: StandaloneSecureAgent\nmetadata:\n  name: %s\nspec:\n  profileRef: %s\n'
            '  instructions: %s\n' % (name, contract.PROFILE, json.dumps(contract.EXAMPLE_INSTRUCTIONS)))


def inventory(s, cfg, files, platform_doc, rgd):
    ids = [r['id'] for r in rgd['spec']['resources']]
    return {
        'schema': 'secure-kro-standalone-inventory/v1',
        'rendererSha256': common.sha256(Path(__file__).read_bytes()),
        'settingsSha256': common.canonical(s), 'platformConfigSha256': common.canonical(cfg),
        'image': s['image'], 'standaloneNamespace': s['standaloneNamespace'],
        'pythonCommand': list(payload.COMMAND),
        'gateway': {k: s['gateway'][k] for k in ('create', 'name', 'namespace', 'listenerName', 'port', 'className')},
        'files': {name: common.sha256(text.encode()) for name, text in sorted(files.items())},
        'platformObjects': [[o['kind'], o['metadata'].get('namespace', ''), o['metadata']['name']] for o in platform_doc['items']],
        'graph': {'name': RGD_NAME, 'kind': 'StandaloneSecureAgent', 'scope': 'Cluster',
                  'resources': [{'id': r['id'], 'kind': r['template']['kind'],
                                 'namespace': r['template']['metadata'].get('namespace'),
                                 'name': r['template']['metadata']['name'], 'dependsOn': dependencies(r, ids),
                                 'readyWhen': len(r.get('readyWhen', []))} for r in rgd['spec']['resources']]},
        'bindings': cfg['bindings'],
        'applyOrder': ['platform.json', 'graph.json (wait for RGD Active and CRD Established)', 'request-guard.json',
                       'example-owner.yaml (after renaming as needed)'],
        'trustRoots': ['KRO controller identity and RGD/profile/request writers (platform-only)',
                       'approved Python helper digest, immutable reviewed code bytes and exact command/projection admission',
                       'shared facade and verifier RBAC', 'Gateway controller and issuer JWKS'],
        'notProven': ['approved existing helper image provides /usr/local/bin/python3 and compatible standard library',
                      'live KRO reconciliation, SSA data preservation and admission decisions (parent lab)',
                      'Gateway JWT enforcement and route/grant behaviour on the target cluster',
                      'NetworkPolicy enforcement by the target CNI including API server egress',
                      'approved-caller denial before Active through the live Gateway (verifier cannot mint caller tokens)',
                      'OpenTelemetry tracing; office TLS; cold registry import']}


def write_outputs(output, files):
    output = Path(os.path.abspath(output))
    need(output != HERE and HERE not in output.parents, 'OutputInsideSourceTree')
    need(output.parent.is_dir(), 'OutputParentMissing')
    try:
        output.mkdir(mode=0o700)
    except FileExistsError:
        raise Rejected('OutputExists') from None
    for name, text in files.items():
        descriptor = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(text)


def render(settings_raw):
    s = validate(settings_raw)
    content_binding = contract.content_binding(HERE / 'content')
    model_binding = contract.model_binding(s['model']['name'], base_url(s), s['limits'])
    need(contract.model_binding_ok(model_binding), 'InvalidModelBinding')
    code = payload.collect(HERE / 'app', HERE / 'content')
    cfg = platform_config(s, model_binding, content_binding, code)
    platform_doc, rgd = platform(s, cfg, code), graph(s, model_binding, content_binding, code)
    need(all(len(common.encoded(o)) < payload.MAX_OBJECT_BYTES for o in platform_doc['items'] + [rgd]),
         'RenderedObjectTooLarge')
    files = {'platform.json': json.dumps(platform_doc, indent=2) + '\n', 'graph.json': json.dumps(rgd, indent=2) + '\n',
             'request-guard.json': json.dumps(request_guard(), indent=2) + '\n', 'example-owner.yaml': owner_example()}
    files['inventory.json'] = json.dumps(inventory(s, cfg, files, platform_doc, rgd), indent=2, sort_keys=True) + '\n'
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, required=True, help='private settings JSON (never committed)')
    parser.add_argument('--output', type=Path, required=True, help='new private directory outside the source tree')
    args = parser.parse_args(argv)
    try:
        settings = Path(os.path.abspath(args.settings))
        need(HERE not in settings.parents, 'SettingsInsideSourceTree')
        need(settings.stat().st_size <= 262144, 'SettingsTooLarge')
        files = render(settings.read_bytes())
        write_outputs(args.output, files)
    except (Rejected, common.Denied, OSError, ValueError, KeyError, TypeError) as error:
        reason = (str(error) if isinstance(error, Rejected) else error.reason if isinstance(error, common.Denied)
                  else type(error).__name__)
        print(json.dumps({'result': 'Rejected', 'reason': reason}), file=sys.stderr)
        return 1
    print(json.dumps({'result': 'Rendered', 'files': sorted(files),
                      'inventorySha256': common.sha256(files['inventory.json'].encode())}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
