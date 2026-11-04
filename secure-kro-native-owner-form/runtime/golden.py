"""One-shot native kagent Golden verifier. Python standard library only.

No agent, skill loader, provider credential, or model runtime lives here. The
frontdoor invokes the native kagent CLI; this Job validates its structured task.
"""
import argparse
import base64
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

SCHEMA = 'native-golden/v1'
SCOPE = 'native-kagent-reviewed-skills-and-fixed-mcp'
API = 'api.kagent.dev/v1alpha3'
CONDITIONS = ('Accepted', 'ResolvedRefs', 'Compatible', 'EgressPoliciesApplied', 'Ready')
MAX_BODY = 1048576


class Failed(Exception):
    """A safe, fixed diagnostic code; never include an HTTP body or credentials."""


class Superseded(Failed):
    pass


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(value):
    return value.isoformat().replace('+00:00', 'Z')


def ready(agent):
    generation, status = agent['metadata']['generation'], agent.get('status', {})
    return (bool(status.get('desiredRevision'))
            and status['desiredRevision'] == status.get('latestSuccessfulRevision')
            and all(any(c.get('type') == kind and c.get('status') == 'True'
                        and c.get('observedGeneration') == generation
                        for c in status.get('conditions', [])) for kind in CONDITIONS))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


class Kubernetes:
    def __init__(self, token_file='/var/run/secrets/kubernetes.io/serviceaccount/token',
                 ca_file='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'):
        self.url = 'https://' + os.environ['KUBERNETES_SERVICE_HOST'] + ':' + os.environ.get('KUBERNETES_SERVICE_PORT', '443')
        self.token_file = token_file
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(
            context=ssl.create_default_context(cafile=ca_file)))

    def call(self, path, value=None, method=None, headers=None):
        values = {'Authorization': 'Bearer ' + Path(self.token_file).read_text().strip(),
                  'Content-Type': 'application/json'}
        values.update(headers or {})
        request = urllib.request.Request(self.url + path, None if value is None else json.dumps(value).encode(),
                                         values, method=method)
        try:
            with self.opener.open(request, timeout=5) as response:
                data = response.read(MAX_BODY + 1)
            if len(data) > MAX_BODY:
                raise Failed('KubernetesResponseTooLarge')
            return json.loads(data)
        except urllib.error.HTTPError as error:
            raise Failed('KubernetesHTTP' + str(error.code)) from None
        except (OSError, ValueError):
            raise Failed('KubernetesUnavailable') from None


class Approval:
    """Each mutation tests resourceVersion AND the complete old approval string.

    approval.json is a ConfigMap string, so a JSON Patch test of that string
    atomically tests the embedded attempt ID, state, request UID, and Job UID.
    Conflicts are terminal for this Job; no mutation is silently retried.
    """
    def __init__(self, kube, namespace, name, request_uid, attempt, job_uid, pod_uid, allow_empty_request=False):
        self.kube = kube
        self.path = f'/api/v1/namespaces/{namespace}/configmaps/{name}'
        self.request_uid, self.attempt, self.job_uid, self.pod_uid = request_uid, attempt, job_uid, pod_uid
        self.allow_empty_request = allow_empty_request

    def read(self):
        cm = self.kube.call(self.path)
        if cm['metadata'].get('deletionTimestamp'):
            raise Superseded('ApprovalDeleting')
        raw = cm['data']['approval.json']
        record = json.loads(raw)
        if not isinstance(record, dict):
            raise Failed('InvalidApprovalShell')
        return cm, raw, record

    def patch(self, cm, raw, record):
        patch = [{'op': 'test', 'path': '/metadata/resourceVersion', 'value': cm['metadata']['resourceVersion']},
                 {'op': 'test', 'path': '/data/approval.json', 'value': raw},
                 {'op': 'replace', 'path': '/data/approval.json', 'value': json.dumps(record, sort_keys=True)}]
        self.kube.call(self.path, patch, method='PATCH', headers={'Content-Type': 'application/json-patch+json'})
        return record

    def claim(self, record):
        cm, raw, old = self.read()
        request_matches = old.get('requestUID') == self.request_uid or (self.allow_empty_request and old.get('requestUID') in (None, ''))
        if (not request_matches or old.get('state') not in (None, '', 'Pending')
                or old.get('attemptID')):
            raise Superseded('ApprovalNotFreshPending')
        return self.patch(cm, raw, record)

    def owned(self, state='Verifying'):
        cm, raw, record = self.read()
        if (record.get('requestUID') != self.request_uid or record.get('attemptID') != self.attempt
                or record.get('jobUID') != self.job_uid or record.get('podUID') != self.pod_uid
                or record.get('state') != state):
            raise Superseded('ApprovalSuperseded')
        if dt.datetime.fromisoformat(record['expiresAt'].replace('Z', '+00:00')) <= now():
            raise Failed('VerificationLeaseExpired')
        return cm, raw, record

    def transition(self, expected, state, **fields):
        if (expected, state) not in (('Verifying', 'Active'), ('Verifying', 'Failed'), ('Active', 'Failed')):
            raise Failed('InvalidApprovalTransition')
        cm, raw, record = self.owned(expected)
        record.update(fields, state=state)
        return self.patch(cm, raw, record)

    def fail_owned(self, phase, receipt):
        # Expired attempts may still be made terminal; expiry never grants access.
        cm, raw, record = self.read()
        if (record.get('state') not in ('Verifying', 'Active') or record.get('attemptID') != self.attempt
                or record.get('requestUID') != self.request_uid or record.get('jobUID') != self.job_uid
                or record.get('podUID') != self.pod_uid):
            raise Superseded('ApprovalSuperseded')
        record.update(state='Failed', failure=phase, goldenFailure=receipt)
        return self.patch(cm, raw, record)


def validate_config(config):
    expected = {'apiVersion': 'kro.run/v1alpha1', 'plural': 'secureagents', 'name': 'demo'}
    if (config.get('namespace') != 'secure-byo-kro' or config.get('agentName') != 'demo'
            or config.get('approvalName') != 'demo-approval' or config.get('request') != expected
            or not isinstance(config.get('requestUID'), str) or not config['requestUID']):
        raise Failed('InvalidBoundedTarget')
    names = config.get('dependencyNames', {})
    if (set(names) != {'agenttemplates', 'harnesses', 'modelconfigs', 'remotemcpservers'}
            or names['agenttemplates'] != 'demo-template' or names['harnesses'] != 'approved-harness'
            or names['remotemcpservers'] != 'approved-mcp'
            or any(not isinstance(name, str) or not name or '/' in name for name in names.values())):
        raise Failed('InvalidNativeNames')
    url = urllib.parse.urlsplit(config.get('gatewayURL', ''))
    if (url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password
            or url.query or url.fragment):
        raise Failed('InvalidGatewayURL')
    ttl = config.get('maxTTLSeconds', 600)
    if type(ttl) is not int or not 120 <= ttl <= 600:
        raise Failed('InvalidLease')
    active_ttl = config.get('activeTTLSeconds', 600)
    if type(active_ttl) is not int or not 120 <= active_ttl <= 14400:
        raise Failed('InvalidActiveLease')
    skills = config.get('skills', [])
    if not isinstance(skills, list) or not 1 <= len(skills) <= 2:
        raise Failed('InvalidReviewedSkills')
    if len({s['name'] for s in skills}) != len(skills):
        raise Failed('DuplicateSkill')
    allowed = {'aks-known-issues': 'references/error-code-map.md',
               'kb-aks-bootstrap': 'references/oras-pull-unauthorized.md'}
    for skill in skills:
        if (skill.get('name') not in allowed or not isinstance(skill.get('source'), dict)
                or not isinstance(skill['source'].get('oci'), str)
                or not re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}', skill['source']['oci'])
                or set(skill['source']) - {'oci', 'path'} or skill['source'].get('path', 'skill') != 'skill'
                or not skill.get('proofTerms')
                or not isinstance(skill.get('references'), list) or len(skill['references']) != 1
                or skill['references'][0].get('path') != allowed[skill['name']]):
            raise Failed('UnreviewedSkillOrReference')
        for terms in [skill['proofTerms'], skill['references'][0].get('proofTerms')]:
            if (not isinstance(terms, list) or not terms
                    or any(not isinstance(term, str) or not 1 <= len(term) <= 200 for term in terms)):
                raise Failed('InvalidProofTerms')
    return config


def argument(data):
    value = data.get('arguments', data.get('args', {}))
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise Failed('MalformedToolArguments') from None
    if not isinstance(value, dict):
        raise Failed('MalformedToolArguments')
    return value


def call_id(data):
    return data.get('id', data.get('callId', data.get('tool_call_id')))


def tool_name(data):
    name = data.get('name', '')
    return next((kind for kind in ('load_skill_resource', 'load_skill', 'get_demo_status')
                 if isinstance(name, str) and name.endswith(kind)), None)


def native_evidence(result, skills):
    task = result.get('task', {})
    if (task.get('status', {}).get('state') != 'TASK_STATE_COMPLETED'
            or not all(isinstance(task.get(k), str) and task[k] for k in ('id', 'contextId'))):
        raise Failed('NativeTaskNotCompleted')
    pending, paired = [], []
    for message in [*task.get('history', []), *task.get('artifacts', [])]:
        for part in message.get('parts', []):
            tag = part.get('metadata', {}).get('kagent.dev/a2a/part-type')
            data = part.get('data', {})
            if tag not in ('function_call', 'function_response'):
                continue
            if not isinstance(data, dict) or not tool_name(data):
                raise Failed('UnexpectedNativeTool')
            if tag == 'function_call':
                pending.append(data)
            elif tag == 'function_response':
                ident = call_id(data)
                candidates = [c for c in pending if tool_name(c) == tool_name(data)
                              and (call_id(c) == ident if ident is not None else call_id(c) is None)]
                if not candidates:
                    raise Failed('UnpairedNativeToolResponse')
                called = candidates[0]
                pending.remove(called)
                paired.append((called, data))
    if pending:
        raise Failed('MissingNativeToolResponse')
    approved = {skill['name']: {ref['path'] for ref in skill['references']} for skill in skills}
    for called, _ in paired:
        kind, args = tool_name(called), argument(called)
        selected = args.get('skill_name', args.get('skillName', args.get('name')))
        resource = args.get('resource_path', args.get('resourcePath', args.get('path', args.get('resource'))))
        if ((kind == 'get_demo_status' and args != {})
                or (kind != 'get_demo_status' and selected not in approved)
                or (kind == 'load_skill_resource' and resource not in approved[selected])):
            raise Failed('UnexpectedNativeSkillOrReference')
    proofs = []
    def match(kind, predicate, terms):
        matches = [(c, r) for c, r in paired if tool_name(c) == kind and predicate(argument(c))]
        # Terms must occur in the paired returned body, never the echoed name or arguments.
        for called, response in matches:
            returned = {k: v for k, v in response.items()
                        if k not in ('name', 'arguments', 'args', 'id', 'callId', 'tool_call_id')}
            text = json.dumps(returned, sort_keys=True)
            if all(term in text for term in terms):
                return {'tool': kind, 'argumentsSha256': canonical(argument(called)),
                        'responseSha256': canonical(returned), 'proofTerms': terms}
        raise Failed('NativeEvidenceMissing_' + kind)
    for skill in skills:
        name = skill['name']
        skill_name = lambda args: args.get('skill_name', args.get('skillName', args.get('name')))
        proofs.append(match('load_skill', lambda a: skill_name(a) == name, skill['proofTerms']))
        for ref in skill['references']:
            resource = lambda args: args.get('resource_path', args.get('resourcePath', args.get('path', args.get('resource'))))
            proofs.append(match('load_skill_resource', lambda a: skill_name(a) == name and resource(a) == ref['path'], ref['proofTerms']))
    proofs.append(match('get_demo_status', lambda a: a == {}, ['synthetic-ready']))
    if {s['name'] for s in skills} == {'aks-known-issues', 'kb-aks-bootstrap'}:
        if not any('AKS-KB-ORAS-212-R1' in json.dumps(r) for c, r in paired if tool_name(c) == 'load_skill_resource'):
            raise Failed('ReviewedDocumentMarkerMissing')
    return {'taskID': task['id'], 'contextID': task['contextId'], 'proofs': proofs,
            'toolCallCounts': {kind: sum(tool_name(c) == kind for c, _ in paired)
                               for kind in ('load_skill', 'load_skill_resource', 'get_demo_status')},
            'responseSha256': canonical(result)}


class Golden:
    def __init__(self, kube, config, environ=None, transport=None):
        self.kube, self.config = kube, validate_config(config)
        env = os.environ if environ is None else environ
        self.pod_uid = env.get('POD_UID')
        self.job_name, self.pod_name = env.get('JOB_NAME', 'demo-golden'), env.get('POD_NAME')
        if (self.job_name != 'demo-golden' or not isinstance(self.pod_name, str) or not self.pod_name
                or '/' in self.pod_name or not isinstance(self.pod_uid, str) or not self.pod_uid):
            raise Failed('JobNameAndPodIdentityRequired')
        pod = kube.call(f'/api/v1/namespaces/{config["namespace"]}/pods/{self.pod_name}')
        job = kube.call(f'/apis/batch/v1/namespaces/{config["namespace"]}/jobs/{self.job_name}')
        self.job_uid = job['metadata']['uid']
        label = 'secure-byo.platform/request-uid'
        if (pod['metadata']['uid'] != self.pod_uid or pod['spec'].get('serviceAccountName') != 'approved-verifier'
                or pod['metadata'].get('deletionTimestamp') or job['metadata'].get('deletionTimestamp')
                or any(obj['metadata'].get('labels', {}).get(label) != config['requestUID'] for obj in (pod, job))
                or not any(owner.get('kind') == 'Job' and owner.get('name') == self.job_name
                           and owner.get('uid') == self.job_uid and owner.get('controller') is True
                           for owner in pod['metadata'].get('ownerReferences', []))
                or job['spec'].get('backoffLimit') != 0 or pod['spec'].get('restartPolicy') != 'Never'
                or (env.get('JOB_UID') and env['JOB_UID'] != self.job_uid)):
            raise Failed('VerifierJobBindingRejected')
        self.attempt = env.get('ATTEMPT_ID') or str(uuid.uuid4())
        self.store = Approval(kube, config['namespace'], config['approvalName'], config['requestUID'],
                              self.attempt, self.job_uid, self.pod_uid, allow_empty_request=True)
        self.skills = None
        self.transport = transport or self.http
        self.deadline = time.monotonic() + config.get('maxTTLSeconds', 600)
        self.checks, self.record, self.phase = [], None, 'CollectingPins'
        self.observations = {}

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise Failed('VerificationLeaseExpired')
        return remaining

    def native(self, plural, name):
        return self.kube.call(f'/apis/{API}/namespaces/{self.config["namespace"]}/{plural}/{name}')

    def request_object(self):
        ref = self.config['request']
        obj = self.kube.call(f'/apis/{ref["apiVersion"]}/namespaces/{self.config["namespace"]}/{ref["plural"]}/{ref["name"]}')
        if obj['metadata'].get('deletionTimestamp') or obj['metadata']['uid'] != self.config['requestUID']:
            raise Failed('RequestBindingChanged')
        return obj

    def collect(self):
        self.request_object()
        agent = self.native('agents', self.config['agentName'])
        if agent['metadata'].get('deletionTimestamp'):
            raise Failed('AgentDeleting')
        pins = []
        for plural, name in sorted(self.config['dependencyNames'].items()):
            obj = self.native(plural, name)
            if obj['metadata'].get('deletionTimestamp'):
                raise Failed('DependencyDeleting')
            if plural == 'agenttemplates':
                selected = obj['spec'].get('skills', [])
                catalog = {skill['name']: skill for skill in self.config['skills']}
                if (not selected or len({skill.get('name') for skill in selected}) != len(selected)
                        or any(skill.get('name') not in catalog or skill.get('source') != catalog[skill['name']]['source'] for skill in selected)):
                    raise Failed('SelectedSkillOutsideReviewedCatalog')
                self.skills = [catalog[skill['name']] for skill in selected]
            pins.append({'apiVersion': API, 'plural': plural, 'name': name,
                         'uid': obj['metadata']['uid'], 'specSha256': canonical(obj['spec'])})
        return agent, pins

    def token(self, sa, audience='secure-byo'):
        lifetime = 600 if sa == 'approved-verifier' else self.config.get('activeTTLSeconds', 600) + self.config.get('maxTTLSeconds', 600)
        result = self.kube.call(f'/api/v1/namespaces/{self.config["namespace"]}/serviceaccounts/{sa}/token',
            {'apiVersion': 'authentication.k8s.io/v1', 'kind': 'TokenRequest',
             'spec': {'audiences': [audience], 'expirationSeconds': lifetime}})
        token = result['status']['token']
        if not isinstance(token, str) or not token or '\n' in token or '\r' in token:
            raise Failed('InvalidTokenRequestResult')
        expiry = dt.datetime.fromisoformat(result['status']['expirationTimestamp'].replace('Z', '+00:00'))
        if expiry <= now():
            raise Failed('TokenRequestExpired')
        return token

    def rotate_worker(self, token):
        path = f'/api/v1/namespaces/{self.config["namespace"]}/secrets/secure-byo-mcp-token'
        metadata = self.kube.call(path, headers={'Accept': 'application/json;as=PartialObjectMetadata;g=meta.k8s.io;v=v1,application/json;q=0.9'})
        if metadata['metadata'].get('deletionTimestamp'):
            raise Failed('WorkerSecretDeleting')
        patch = [{'op': 'test', 'path': '/metadata/resourceVersion', 'value': metadata['metadata']['resourceVersion']},
                 {'op': 'add', 'path': '/data/token', 'value': base64.b64encode(token.encode()).decode()},
                 {'op': 'add', 'path': '/data/Authorization', 'value': base64.b64encode(('Bearer ' + token).encode()).decode()}]
        self.kube.call(path, patch, method='PATCH', headers={'Content-Type': 'application/json-patch+json',
            'Accept': 'application/json;as=PartialObjectMetadata;g=meta.k8s.io;v=v1,application/json;q=0.9'})

    def http(self, path, value, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(self.config['gatewayURL'].rstrip('/') + path,
                                         json.dumps(value).encode(), headers)
        opener = urllib.request.build_opener(NoRedirect())
        try:
            response = opener.open(request, timeout=min(115, self.remaining()))
        except urllib.error.HTTPError as error:
            response = error
        except OSError:
            raise Failed('FrontdoorUnavailable') from None
        with response:
            data = response.read(MAX_BODY + 1)
            if len(data) > MAX_BODY:
                raise Failed('FrontdoorResponseTooLarge')
            try:
                return response.status, json.loads(data)
            except ValueError:
                if response.status in (401, 403):
                    return response.status, {'error': 'GatewayRejected'}
                raise Failed('FrontdoorInvalidJSON') from None

    def check(self, name, passed, details=None):
        self.checks.append({'name': name, 'passed': bool(passed), 'details': details})
        if not passed:
            raise Failed(name)

    def witness(self, token):
        code, result = self.transport('/witness', {}, token)
        self.check('AuthenticatedWitness', code == 200 and all(type(result.get(k)) is int for k in
                   ('authorizedModelCalls', 'authorizedMcpCalls')), {'http': code})
        return result

    def wait_ready(self):
        while True:
            self.remaining()
            self.store.owned()
            agent, pins = self.collect()
            if (agent['metadata']['uid'] != self.record['agentUID'] or canonical(agent['spec']) != self.record['agentSpecSha256']
                    or pins != self.record['dependencies']):
                raise Failed('NativeBindingChanged')
            if ready(agent):
                return agent['status']['desiredRevision']
            time.sleep(min(1, self.remaining()))

    def observe(self, name, status, result):
        task = result.get('task', {}) if isinstance(result, dict) else {}
        observation = {'http': status, 'responseSha256': canonical(result)}
        for source, target in (('id', 'taskID'), ('contextId', 'contextID')):
            value = task.get(source)
            if isinstance(value, str) and 1 <= len(value) <= 256:
                observation[target] = value
        state = task.get('status', {}).get('state')
        if isinstance(state, str) and state.startswith('TASK_STATE_') and len(state) <= 80:
            observation['nativeTaskState'] = state
        self.observations[name] = observation

    def prompt(self):
        instructions = ['Synthetic documentation case only. Use the native load_skill and load_skill_resource tools.']
        for skill in self.skills:
            instructions.append('Load skill ' + skill['name'] + ' and read ' + ', '.join(r['path'] for r in skill['references']) + ' from that skill.')
        instructions.append('Call get_demo_status. Explain OrasPullUnauthorizedVMExtensionError exit 212 using those documents, cite sources and report the returned MCP status. No Azure actions.')
        return ' '.join(instructions)

    def run(self):
        try:
            agent, pins = self.collect()  # Deliberately no Ready prerequisite.
            caller_uids = {}
            for name in ('approved-caller', 'approved-worker', 'approved-verifier'):
                sa = self.kube.call(f'/api/v1/namespaces/{self.config["namespace"]}/serviceaccounts/{name}')
                if sa['metadata'].get('deletionTimestamp'):
                    raise Failed('ServiceAccountDeleting')
                caller_uids['system:serviceaccount:' + self.config['namespace'] + ':' + name] = sa['metadata']['uid']
            prefix = 'system:serviceaccount:' + self.config['namespace'] + ':'
            candidate = {'state': 'Verifying', 'attemptID': self.attempt, 'jobUID': self.job_uid, 'podUID': self.pod_uid,
                'requestUID': self.config['requestUID'], 'agentUID': agent['metadata']['uid'],
                'agentSpecSha256': canonical(agent['spec']), 'dependencies': pins,
                'startedAt': iso(now()), 'expiresAt': iso(now() + dt.timedelta(seconds=self.config.get('maxTTLSeconds', 600))),
                'callers': {'invoke': [prefix + 'approved-caller'], 'mcp': [prefix + 'approved-worker']}, 'callerUIDs': caller_uids}
            self.phase = 'ClaimingVerifying'
            self.record = self.store.claim(candidate)
            self.phase = 'BootstrappingNative'
            verifier, caller, worker = (self.token(sa) for sa in ('approved-verifier', 'approved-caller', 'approved-worker'))
            wrong = self.token('approved-verifier', 'wrong-audience')
            self.store.owned()
            self.rotate_worker(worker)
            revision = self.wait_ready()
            self.phase = 'NegativeControls'
            before = self.witness(verifier)
            rpc = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}
            for name, path, value, auth, expected in [
                ('OrdinaryCallerDeniedWhileVerifying', '/invoke', {'prompt': 'denied'}, caller, 403),
                ('MissingTokenDenied', '/invoke', {'prompt': 'denied'}, None, 401),
                ('WrongAudienceDenied', '/invoke', {'prompt': 'denied'}, wrong, 401),
                ('WorkerCannotInvoke', '/invoke', {'prompt': 'denied'}, worker, 403),
                ('VerifierCannotUseWorkerLane', '/mcp', rpc, verifier, 403),
                ('CallerCannotUseWorkerLane', '/mcp', rpc, caller, 403)]:
                status, _ = self.transport(path, value, auth)
                self.check(name, status == expected, {'http': status})
            denied_tool = dict(rpc, method='tools/call', params={'name': 'delete_pod', 'arguments': {}})
            status, body = self.transport('/mcp', denied_tool, worker)
            self.check('ForbiddenMcpOperationDenied', status == 200 and body.get('error', {}).get('code') == -32601, {'http': status})
            after = self.witness(verifier)
            self.check('NegativeControlsNoBackendDispatch', all(before[k] == after[k] for k in ('authorizedModelCalls', 'authorizedMcpCalls')))
            self.phase = 'NativeScenario'
            self.store.owned()
            status, result = self.transport('/invoke', {'prompt': self.prompt()}, verifier)
            self.observe('nativeScenario', status, result)
            self.check('NativeInvocationHTTP', status == 200, {'http': status})
            evidence = native_evidence(result, self.skills)
            self.check('StructuredNativeEvidence', True, {'toolCallCounts': evidence['toolCallCounts']})
            after = self.witness(verifier)
            deltas = {'modelCalls': after['authorizedModelCalls'] - before['authorizedModelCalls'],
                      'mcpCalls': after['authorizedMcpCalls'] - before['authorizedMcpCalls']}
            self.check('PositiveModelAndMcpWitnesses', all(type(v) is int and v > 0 for v in deltas.values()), deltas)
            self.store.owned()
            current, current_pins = self.collect()
            self.check('NativeCurrentReadyAndPins', ready(current) and current['status']['desiredRevision'] == revision
                       and current['metadata']['uid'] == self.record['agentUID'] and canonical(current['spec']) == self.record['agentSpecSha256']
                       and current_pins == pins)
            receipt = {k: copy.deepcopy(self.record[k]) for k in ('attemptID', 'jobUID', 'podUID', 'requestUID',
                        'agentUID', 'agentSpecSha256', 'dependencies', 'expiresAt')}
            receipt.update(schemaVersion=SCHEMA, proofScope=SCOPE, passed=True, nativeRevision=revision,
                           taskID=evidence['taskID'], contextID=evidence['contextID'], evidence=evidence,
                           skills=[s['name'] for s in self.skills], witnessDeltas=deltas,
                           checks=copy.deepcopy(self.checks), completedAt=iso(now()))
            active_expiry = iso(now() + dt.timedelta(seconds=self.config.get('activeTTLSeconds', 600)))
            receipt['expiresAt'] = active_expiry
            self.phase = 'PromotingActive'
            self.store.transition('Verifying', 'Active', expiresAt=active_expiry,
                                  goldenProof={'receipt': receipt, 'sha256': canonical(receipt)})
            self.phase = 'OrdinaryCallerSmoke'
            status, result = self.transport('/invoke', {'prompt': 'Reply with exactly PONG. Do not call any tool.'}, caller)
            self.observe('callerSmoke', status, result)
            task = result.get('task', {})
            outputs = [*task.get('artifacts', []), *[message for message in task.get('history', [])
                       if message.get('role') in ('ROLE_AGENT', 'ROLE_ASSISTANT')]]
            pong = any(isinstance(part.get('text'), str) and part['text'].strip() == 'PONG'
                       for container in outputs for part in container.get('parts', []))
            self.check('OrdinaryCallerNativeSmoke', status == 200 and task.get('status', {}).get('state') == 'TASK_STATE_COMPLETED'
                       and pong and bool(task.get('id')) and bool(task.get('contextId')), {'http': status})
            self.store.owned('Active')
            # The pre-promotion proof is immutable. Record the real caller result separately.
            cm, raw, record = self.store.owned('Active')
            record['callerSmoke'] = {'passed': True, 'taskID': task['id'], 'contextID': task['contextId'],
                                     'responseSha256': canonical(result), 'completedAt': iso(now())}
            self.store.patch(cm, raw, record)
            return {'schemaVersion': SCHEMA, 'passed': True, 'state': 'Active', 'receipt': receipt,
                    'receiptSha256': canonical(receipt), 'callerSmoke': record['callerSmoke']}
        except Exception as error:
            # Exception bodies, raw native responses, HTTP bodies and tokens never reach stdout.
            reason = str(error) if isinstance(error, Failed) else type(error).__name__
            failure = {'schemaVersion': SCHEMA, 'passed': False, 'attemptID': self.attempt,
                       'jobUID': self.job_uid, 'podUID': self.pod_uid, 'requestUID': self.config['requestUID'],
                       'phase': self.phase, 'reason': reason, 'checks': self.checks,
                       'observations': self.observations, 'completedAt': iso(now())}
            if self.record is not None:
                failure['bindings'] = {key: copy.deepcopy(self.record[key]) for key in
                    ('agentUID', 'agentSpecSha256', 'dependencies', 'expiresAt')}
            try:
                if self.record is None:
                    raise Superseded('ApprovalNotClaimed')
                self.store.fail_owned(self.phase, failure)
                failure['state'] = 'Failed'
            except Exception:
                failure['state'] = 'UnchangedOrSuperseded'
            return failure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    try:
        report = Golden(Kubernetes(), json.loads(Path(args.config).read_text())).run()
    except Exception as error:
        report = {'schemaVersion': SCHEMA, 'passed': False, 'phase': 'Initialization',
                  'reason': str(error) if isinstance(error, Failed) else type(error).__name__}
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
