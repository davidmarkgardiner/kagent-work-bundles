"""Platform verifier Job: inventory, Verifying lease, live Gateway probes, golden run, CAS to Active (no retry)."""
import argparse
import base64
import json
import os
import re
import secrets
import time
from pathlib import Path

import authority as auth
import common
import contract
import payload

HERE = Path(__file__).resolve().parent
SHA = re.compile(r'[0-9a-f]{64}')
DEPENDENCY_ENV = (('RUNTIME_DEPLOYMENT', 'runtime'), ('ROUTE_NAME', 'route'), ('POLICY_NAME', 'route'))


class Failure(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason if common.REASON.fullmatch(reason) else 'VerificationFailed'


def check(ok, reason):
    if not ok:
        raise Failure(reason)


def condition(entry, kind, generation, reason=None):
    return any(c.get('type') == kind and c.get('status') == 'True' and c.get('observedGeneration') == generation
               and (reason is None or c.get('reason') == reason) for c in entry.get('conditions') or [])


def policy_expression(names):
    return 'jwt.sub in ' + json.dumps([names.subjects[r] for r in ('caller', 'worker', 'verifier')])


def approval_data(record):
    return {'state': record['state'], 'requestUID': record['requestUID'], 'expiresAt': record['expiresAt'],
            'approval.json': json.dumps(record, sort_keys=True, separators=(',', ':'))}


class Verifier:
    def __init__(self, cfg, kube, gateway_token_file, content_root, transport=common.http_call, clock=common.now,
                 sleep=time.sleep, env=None, wait_seconds=120,
                 negative_audience_token_file=auth.NEGATIVE_AUDIENCE_TOKEN_FILE, code_root=HERE):
        self.cfg, self.kube, self.transport, self.clock, self.sleep = cfg, kube, transport, clock, sleep
        self.authority = auth.Authority(kube, cfg, clock)
        self.token_file, self.wait_seconds = gateway_token_file, wait_seconds
        self.negative_audience_token_file = negative_audience_token_file
        self.env = os.environ if env is None else env
        self.binding = contract.content_binding(content_root)
        self.payload = payload.collect(code_root, content_root)
        self.texts = contract.load_packages(self.binding, content_root)
        self.proofs = contract.proofs(self.texts)
        self.epoch, self.probes, self.uid = secrets.token_hex(16), {}, None

    def gateway(self, names, lane, body, token=None):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if token is not None:
            headers['Authorization'] = 'Bearer ' + token
        path = {'invoke': '/invoke', 'model': '/model/v1/chat/completions', 'mcp': '/mcp', 'witness': '/witness'}[lane]
        try:
            status, raw = self.transport('POST', self.cfg['gateway']['baseURL'] + '/agents/' + names.agent + path,
                                         headers, common.encoded(body), max_bytes=262144,
                                         deadline=time.monotonic() + self.cfg['limits']['deadlineSeconds'] + 30)
        except common.Denied:
            raise Failure('GatewayUnavailable') from None
        try:
            return status, common.loads(raw, 262144) if raw else None
        except common.Denied:
            return status, None

    def own_token(self, token_file=None):
        try:
            return common.read_token(self.token_file if token_file is None else token_file)
        except common.Denied:
            raise Failure('VerifierCredentialUnavailable') from None

    def witness(self, names, run_id=None):
        status, payload = self.gateway(names, 'witness', {'runId': run_id} if run_id else {}, self.own_token())
        check(status == 200 and isinstance(payload, dict) and payload.get('agent') == names.agent
              and payload.get('requestUID') == self.uid and isinstance(payload.get('counters'), dict),
              'WitnessUnavailable')
        return payload

    def expect_facade(self, names, label, lane, body, reason):
        status, payload = self.gateway(names, lane, body, self.own_token())
        check(status == 403 and payload == {'error': reason}, 'Probe' + label[0].upper() + label[1:] + 'NotDenied')
        self.probes[label] = status

    def expect_gateway(self, names, label, token):
        status, _ = self.gateway(names, 'invoke', {'prompt': 'gateway denial probe'}, token)
        check(status in (401, 403), 'Probe' + label[0].upper() + label[1:] + 'NotDenied')
        self.probes[label] = status

    def negative_token(self, names):
        path = ('/api/v1/namespaces/' + names.ns + '/serviceaccounts/' + self.cfg['accounts']['negative'] + '/token')
        status, value = self.kube.call('POST', path, {'apiVersion': 'authentication.k8s.io/v1', 'kind': 'TokenRequest',
                                                      'spec': {'audiences': [self.cfg['audience']], 'expirationSeconds': 600}})
        token = (value or {}).get('status', {}).get('token') if isinstance(value, dict) else None
        check(status in (200, 201) and isinstance(token, str) and common.TOKEN.fullmatch(token), 'NegativeTokenUnavailable')
        return token

    def forged_token(self, names, inventory):
        def b64(raw):
            return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()
        try:
            keys = json.loads(inventory['routePolicy']['spec']['traffic']['jwtAuthentication']['providers'][0]
                              ['jwks']['inline'])['keys']
            kid = str(keys[0].get('kid', 'forged'))
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            kid = 'forged'
        moment = int(self.clock())
        claims = {'iss': self.cfg['jwt']['issuer'], 'aud': [self.cfg['audience']], 'sub': names.subjects['caller'],
                  'iat': moment, 'nbf': moment, 'exp': moment + 300}
        return '.'.join((b64(json.dumps({'alg': 'RS256', 'typ': 'JWT', 'kid': kid}).encode()),
                         b64(json.dumps(claims).encode()), b64(secrets.token_bytes(256))))

    def check_shapes(self, names, request, inv):
        cfg, agent, gw = self.cfg, names.agent, self.cfg['gateway']
        check(payload.matches(self.payload.hashes, cfg['bindings']), 'MountedPayloadMismatch')
        api_payload = self.payload.from_config_map(inv['runtimeCode'])
        check(api_payload == self.payload and payload.matches(api_payload.hashes, cfg['bindings']), 'RuntimeCodeMismatch')
        for key in ('workerAccount', 'callerAccount'):
            check(inv[key].get('automountServiceAccountToken') is False, 'AccountShape')
        for key, field, digest in (('modelBinding', 'model.json', cfg['bindings']['modelSha256']),
                                   ('contentBinding', 'content.json', cfg['bindings']['contentSha256'])):
            cm = inv[key]
            check(cm.get('immutable') is True and set(cm.get('data') or {}) == {field} and not cm.get('binaryData'),
                  'BindingShape')
            try:
                parsed = common.loads(cm['data'][field].encode(), 262144)
            except common.Denied:
                raise Failure('BindingShape') from None
            check(common.canonical(parsed) == digest, 'BindingContentMismatch')
            check(key != 'contentBinding' or parsed == self.binding, 'PackagedContentMismatch')
            check(key != 'modelBinding' or (parsed['model'] == cfg['model']['name'] and parsed['limits'] == cfg['limits']
                                            and parsed['gatewayBaseURL'] == gw['baseURL']), 'ModelBindingMismatch')
        runtime_labels = {auth.LABEL_AGENT: agent, auth.LABEL_ROLE: 'runtime'}
        deployment = inv['runtime']
        spec = deployment.get('spec') or {}
        pod = (spec.get('template') or {}).get('spec') or {}
        containers = pod.get('containers') or [{}]
        container = containers[0]
        check(spec.get('replicas') == 1 and spec.get('selector') == {'matchLabels': runtime_labels}
              and ((spec.get('template') or {}).get('metadata') or {}).get('labels') == runtime_labels
              and pod.get('serviceAccountName') == names.worker and pod.get('automountServiceAccountToken') is False
              and len(containers) == 1 and not pod.get('initContainers') and not pod.get('ephemeralContainers')
              and container.get('image') == cfg['image'] and container.get('name') == 'agent'
              and container.get('args') == ['agent'] and container.get('command') == list(payload.COMMAND), 'RuntimeShape')
        check(container.get('env') == [{'name': 'AGENT_NAME', 'value': agent},
                                       {'name': 'OWNER_INSTRUCTIONS', 'value': request['spec']['instructions']}],
              'RuntimeEnvMismatch')
        check(not any(container.get(k) for k in ('envFrom', 'workingDir', 'lifecycle', 'livenessProbe', 'startupProbe'))
              and not any('exec' in (container.get(k) or {}) for k in ('readinessProbe', 'livenessProbe', 'startupProbe')),
              'RuntimeExecutionShape')
        volumes = {v.get('name'): v for v in pod.get('volumes') or []}
        check(len(pod.get('volumes') or []) == 4 and set(volumes) == {'gateway-token', 'model', 'content', 'code'}
              and volumes['code'] == self.payload.volume(names.runtime_code)
              and volumes['model'].get('configMap', {}).get('name') == names.model
              and volumes['content'].get('configMap', {}).get('name') == names.content
              and volumes['gateway-token'].get('projected', {}).get('sources') == [{'serviceAccountToken': {
                  'audience': cfg['audience'], 'expirationSeconds': 3600, 'path': 'token'}}], 'RuntimeVolumeShape')
        check(container.get('volumeMounts') == [
            {'name': 'gateway-token', 'mountPath': str(Path(auth.GATEWAY_TOKEN_FILE).parent), 'readOnly': True},
            {'name': 'model', 'mountPath': '/etc/standalone/model', 'readOnly': True},
            {'name': 'content', 'mountPath': '/etc/standalone/content', 'readOnly': True}, dict(payload.CODE_MOUNT)],
            'RuntimeMountShape')
        status = deployment.get('status') or {}
        check(status.get('observedGeneration') == deployment['metadata'].get('generation')
              and all(status.get(k) == 1 for k in ('replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas'))
              and any(c.get('type') == 'Available' and c.get('status') == 'True' for c in status.get('conditions') or []),
              'RuntimeNotRolledOut')
        for key, selector in (('runtimeService', runtime_labels), ('frontService', {auth.LABEL_ROLE: 'facade'})):
            svc = inv[key].get('spec') or {}
            check(svc.get('selector') == selector and svc.get('type', 'ClusterIP') == 'ClusterIP'
                  and [(p.get('port'), p.get('targetPort')) for p in svc.get('ports') or []] == [(8080, 8080)],
                  'ServiceShape')
        check(inv['frontGrant'].get('spec') == {
            'from': [{'group': 'gateway.networking.k8s.io', 'kind': 'HTTPRoute', 'namespace': names.gateway_ns}],
            'to': [{'group': '', 'kind': 'Service', 'name': names.front}]}, 'ReferenceGrantNotExact')
        route = inv['route']
        rules = (route.get('spec') or {}).get('rules') or []
        check(route['spec'].get('parentRefs') == [{'group': 'gateway.networking.k8s.io', 'kind': 'Gateway',
                                                   'name': gw['name'], 'namespace': gw['namespace'],
                                                   'sectionName': gw['listenerName']}]
              and not route['spec'].get('hostnames') and len(rules) == 1
              and set(rules[0]) <= {'matches', 'backendRefs', 'timeouts'}
              and rules[0].get('matches') == [{'path': {'type': 'PathPrefix', 'value': '/agents/' + agent + '/'}}]
              and rules[0].get('backendRefs') == [{'group': '', 'kind': 'Service', 'name': names.front,
                                                   'namespace': names.ns, 'port': 8080, 'weight': 1}], 'RouteShape')
        generation = route['metadata'].get('generation')
        parents = [p for p in (route.get('status') or {}).get('parents') or []
                   if p.get('controllerName') == gw['controllerName'] and (p.get('parentRef') or {}).get('name') == gw['name']]
        check(parents and all(condition(p, 'Accepted', generation) and condition(p, 'ResolvedRefs', generation)
                              for p in parents), 'RouteNotAccepted')
        policy = inv['routePolicy']
        traffic = (policy.get('spec') or {}).get('traffic') or {}
        jwt = traffic.get('jwtAuthentication') or {}
        providers = jwt.get('providers') or [{}]
        inline = (providers[0].get('jwks') or {}).get('inline')
        check(policy['spec'].get('targetRefs') == [{'group': 'gateway.networking.k8s.io', 'kind': 'HTTPRoute',
                                                     'name': names.route}]
              and set(traffic) == {'jwtAuthentication', 'authorization'} and jwt.get('mode') == 'Strict'
              and jwt.get('preserveToken') is True and len(providers) == 1
              and providers[0].get('issuer') == cfg['jwt']['issuer'] and providers[0].get('audiences') == [cfg['audience']]
              and set(providers[0].get('jwks') or {}) == {'inline'} and isinstance(inline, str)
              and common.sha256(inline.encode()) == cfg['jwt']['jwksSha256']
              and traffic.get('authorization') == {'action': 'Require',
                                                   'policy': {'matchExpressions': [policy_expression(names)]}},
              'PolicyShape')
        generation = policy['metadata'].get('generation')
        ancestors = [a for a in (policy.get('status') or {}).get('ancestors') or []
                     if a.get('controllerName') == gw['controllerName']]
        check(ancestors and all(condition(a, 'Accepted', generation, 'Valid') and condition(a, 'Attached', generation)
                                for a in ancestors), 'PolicyNotAttached')

    def shapes(self, names, request, inventory):
        try:
            self.check_shapes(names, request, inventory)
        except (KeyError, TypeError, AttributeError, IndexError, ValueError):
            raise Failure('InventoryShapeRejected') from None

    def ready_inventory(self, names, request):
        give_up = time.monotonic() + self.wait_seconds
        while True:
            try:
                inventory = self.authority.inventory(names, request['metadata']['uid'])
                self.shapes(names, request, inventory)
                return inventory
            except (Failure, common.Denied):
                if time.monotonic() >= give_up:
                    raise
                self.sleep(5)

    def own_job(self, names, uid):
        job = self.kube.get(names.job_path)
        check(job is not None and (job['metadata'].get('labels') or {}).get(auth.KRO_INSTANCE) == uid, 'VerifierJobMissing')
        spec = job.get('spec') or {}
        pod = (spec.get('template') or {}).get('spec') or {}
        containers = pod.get('containers') or [{}]
        check(spec.get('backoffLimit') == 0 and 'ttlSecondsAfterFinished' not in spec
              and pod.get('serviceAccountName') == names.verifier and len(containers) == 1
              and not pod.get('initContainers') and not pod.get('ephemeralContainers')
              and containers[0].get('image') == self.cfg['image']
              and containers[0].get('command') == list(payload.COMMAND)
              and containers[0].get('args') == ['golden', '--request', names.agent], 'VerifierJobShape')
        code_volumes = [v for v in pod.get('volumes') or [] if v.get('name') == 'code']
        check(code_volumes == [self.payload.volume(names.runtime_code)]
              and [m for m in containers[0].get('volumeMounts') or [] if m.get('mountPath') == '/agent'
                   or m.get('name') == 'code'] == [payload.CODE_MOUNT], 'VerifierCodeShape')
        return job

    def accounts(self, names, inventory):
        verifier = self.kube.get(names.verifier_path)
        check(verifier is not None, 'VerifierAccountMissing')
        return {'caller': {'subject': names.subjects['caller'], 'uid': inventory['callerAccount']['metadata']['uid']},
                'worker': {'subject': names.subjects['worker'], 'uid': inventory['workerAccount']['metadata']['uid']},
                'verifier': {'subject': names.subjects['verifier'], 'uid': verifier['metadata']['uid']}}

    def cas(self, names, cm, data, previous=None):
        ops = [{'op': 'test', 'path': '/metadata/uid', 'value': cm['metadata']['uid']},
               {'op': 'test', 'path': '/metadata/resourceVersion', 'value': cm['metadata']['resourceVersion']}]
        if previous is None:
            ops.append({'op': 'add', 'path': '/data', 'value': data})
        else:
            ops += [{'op': 'test', 'path': '/data/state', 'value': previous['state']},
                    {'op': 'test', 'path': '/data/approval.json', 'value': previous['approval.json']},
                    {'op': 'replace', 'path': '/data', 'value': data}]
        status, value = self.kube.call('PATCH', names.approval_path, ops, 'application/json-patch+json')
        check(status == 200 and isinstance(value, dict) and value.get('data') == data, 'ApprovalCASConflict')
        return value

    def record(self, names, request, cm, accounts, pins, job):
        return {'schema': auth.APPROVAL_SCHEMA, 'state': 'Verifying', 'epoch': self.epoch, 'requestName': names.agent,
                'requestUID': self.uid, 'requestGeneration': request['metadata'].get('generation'),
                'requestSpecSha256': common.canonical(request['spec']), 'approvalUID': cm['metadata']['uid'],
                'platformConfigSha256': common.canonical(self.cfg),
                'expiresAt': common.stamp(self.clock() + self.cfg['approval']['verifyingSeconds']),
                'accounts': accounts, 'pins': pins, 'verifierJob': {'name': names.golden, 'uid': job['metadata']['uid']}}

    def golden(self, names, before):
        status, result = self.gateway(names, 'invoke', {'prompt': contract.GOLDEN_PROMPT}, self.own_token())
        if status != 200:
            self.probes['goldenHTTPStatus'] = status
            reason = result.get('reason') if isinstance(result, dict) else None
            if isinstance(reason, str) and common.REASON.fullmatch(reason):
                self.probes['goldenRuntimeReason'] = reason
            raise Failure('GoldenInvokeRejected')
        check(isinstance(result, dict) and set(result) == {'agent', 'runId', 'answer', 'receipt', 'facade'}
              and result['agent'] == names.agent and isinstance(result['answer'], str)
              and isinstance(result['receipt'], dict), 'GoldenResponseRejected')
        answer, receipt, run_id = result['answer'], result['receipt'], result['runId']
        check(receipt.get('result') == 'Passed' and receipt.get('runId') == run_id and receipt.get('agent') == names.agent
              and receipt.get('answerSha256') == common.sha256(answer.encode()), 'GoldenReceiptRejected')
        check(payload.matches(receipt, self.cfg['bindings']), 'GoldenCodeReceiptMismatch')
        check(all(p in answer for p in self.proofs), 'ReleaseProofMissing')
        check(all(c in answer for c in contract.CITATIONS), 'CitationMissing')
        check(all(re.search(r'(?<!\w)' + re.escape(t) + r'(?!\w)', answer, re.I) for t in contract.ANSWER_TERMS),
              'AnswerTermMissing')
        evidence = receipt.get('toolEvidence') or []

        def used(name, arguments, result_sha=None):
            return any(e.get('name') == name and e.get('argumentsSha256') == contract.arguments_sha256(arguments)
                       and (result_sha is None or e.get('resultSha256') == result_sha) for e in evidence)
        check(all(used('load_skill', {'name': p}) for p in contract.PACKAGES), 'SkillNotLoaded')
        check(all(used('load_skill_resource', {'skill_name': s, 'resource_path': p},
                       contract.resource_result_sha256(s, p, self.texts[s][p])) for s, p in contract.REQUIRED),
              'RequiredContentNotRead')
        check(used('get_demo_status', {}), 'SyntheticToolNotCalled')
        after = self.witness(names, run_id)
        run = after.get('run') or {}
        model, mcp = run.get('modelDispatches') or [], run.get('mcpDispatches') or []
        check(run.get('result') == 'Passed' and run.get('role') == 'verifier'
              and run.get('answerSha256') == common.sha256(answer.encode()), 'FacadeRunEvidenceMismatch')
        check(len(model) == receipt.get('modelCalls') and len(model) >= 2
              and all(SHA.fullmatch(str(m.get('responseSha256'))) for m in model), 'ModelDispatchNotWitnessed')
        check(len(mcp) == receipt.get('mcpCalls') == 1
              and all(isinstance(m.get('proof'), str) and m['proof'] in answer for m in mcp), 'McpProofNotWitnessed')
        check(sorted(common.sha256(m['proof'].encode()) for m in mcp) == sorted(receipt.get('mcpProofSha256') or []),
              'McpProofMismatch')
        check(result['facade'] == {'modelDispatches': len(model), 'mcpDispatches': len(mcp)}, 'FacadeSummaryMismatch')
        delta = {k: after['counters'].get(k, 0) - before.get(k, 0) for k in before}
        check(delta == {'received': 1 + len(model) + len(mcp), 'denied': 0, 'invocations': 1, 'handlesMinted': 1,
                        'modelDispatches': len(model), 'mcpDispatches': len(mcp)}, 'FacadeCountersMismatch')
        return {'scenario': contract.GOLDEN_SCENARIO, 'runId': run_id, 'modelCalls': len(model),
                'toolCalls': receipt.get('toolCalls'), 'mcpCalls': len(mcp), 'answerSha256': common.sha256(answer.encode()),
                'toolEvidenceSha256': common.canonical(evidence), 'facadeEvidenceSha256': common.canonical(run),
                **{k: receipt[k] for k in payload.HASH_FIELDS}}

    def run(self, agent):
        names = auth.Names(self.cfg, agent)
        receipt = {'scenario': contract.GOLDEN_SCENARIO, 'agent': agent, 'result': 'Failed', 'reason': 'VerificationFailed',
                   'proofScope': contract.PROOF_SCOPE, 'imageDigest': self.cfg['image'].split('@', 1)[1],
                   'probes': self.probes, 'podUID': self.env.get('POD_UID')}
        cm = verifying = None
        try:
            check(payload.matches(self.payload.hashes, self.cfg['bindings']), 'MountedPayloadMismatch')
            check(all(self.env.get(var) == getattr(names, attr) for var, attr in DEPENDENCY_ENV), 'DependencyEnvMismatch')
            request = self.authority.request(names)
            self.uid = receipt['requestUID'] = request['metadata']['uid']
            fresh = self.authority.approval(names, self.uid)
            check(not fresh.get('data') and not fresh.get('binaryData'), 'ApprovalAlreadyInitialized')
            cm = fresh
            inventory = self.ready_inventory(names, request)
            job = self.own_job(names, self.uid)
            accounts = self.accounts(names, inventory)
            pins = [auth.pin(c, inventory[c[0]]) for c in names.children]
            receipt['verifierJobUID'] = job['metadata']['uid']
            self.expect_facade(names, 'verifierBeforeVerifying', 'invoke', {'prompt': 'pre-lease probe'},
                               'ApprovalNotVerifying')
            record = self.record(names, request, cm, accounts, pins, job)
            cm = self.cas(names, cm, approval_data(record))
            verifying = approval_data(record)
            base = self.witness(names)['counters']
            check(all(base.get(k) == 0 for k in ('invocations', 'handlesMinted', 'modelDispatches', 'mcpDispatches'))
                  and base.get('received', 0) >= 1 and base.get('denied', 0) >= 1, 'FacadeCountersNotFresh')
            self.expect_gateway(names, 'missingToken', None)
            self.expect_gateway(names, 'forgedToken', self.forged_token(names, inventory))
            self.expect_gateway(names, 'wrongAudience', self.own_token(self.negative_audience_token_file))
            self.expect_gateway(names, 'wrongSubject', self.negative_token(names))
            self.expect_facade(names, 'wrongLaneModel', 'model', {'model': self.cfg['model']['name']}, 'LaneNotPermitted')
            self.expect_facade(names, 'wrongLaneMcp', 'mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
                               'LaneNotPermitted')
            middle = self.witness(names)['counters']
            check({k: middle.get(k, 0) - base.get(k, 0) for k in base}
                  == dict(dict.fromkeys(base, 0), received=2, denied=2), 'ForbiddenFacadeActivity')
            summary = self.golden(names, middle)
            latest = self.authority.request(names)
            check(latest['metadata']['uid'] == self.uid and latest['metadata'].get('generation') == record['requestGeneration']
                  and common.canonical(latest['spec']) == record['requestSpecSha256'], 'RequestChanged')
            again = self.authority.inventory(names, self.uid)
            self.shapes(names, latest, again)
            check([auth.pin(c, again[c[0]]) for c in names.children] == pins, 'BindingChanged')
            check(self.accounts(names, again) == accounts, 'AccountChanged')
            current = self.authority.approval(names, self.uid)
            check(current['metadata']['uid'] == cm['metadata']['uid'] and current.get('data') == verifying,
                  'ApprovalChanged')
            active = dict(record, state='Active', receipt=dict(summary, probes=dict(self.probes)),
                          expiresAt=common.stamp(self.clock() + self.cfg['approval']['activeSeconds']))
            self.cas(names, current, approval_data(active), verifying)
            receipt.update(result='Passed', reason='GoldenScenarioVerified', state='Active',
                           expiresAt=active['expiresAt'], golden=summary)
            return 0, receipt
        except Exception as error:
            reason = error.reason if isinstance(error, (Failure, common.Denied)) else 'VerifierInputRejected'
            receipt['reason'] = reason
            receipt['state'] = self.record_failure(names, cm, verifying, reason)
            return 1, receipt

    def record_failure(self, names, cm, verifying, reason):
        if cm is None:
            return None
        try:
            latest = self.authority.approval(names, self.uid)
            check(latest['metadata']['uid'] == cm['metadata']['uid'], 'ApprovalChanged')
            check((latest.get('data') or None) == verifying, 'ApprovalChanged')
            base = json.loads(verifying['approval.json']) if verifying else {
                'schema': auth.APPROVAL_SCHEMA, 'epoch': self.epoch, 'requestName': names.agent,
                'requestUID': self.uid, 'approvalUID': latest['metadata']['uid']}
            failed = dict(base, state='Failed', reason=reason, expiresAt=common.stamp(self.clock()),
                          receipt={'scenario': contract.GOLDEN_SCENARIO, 'probes': dict(self.probes)})
            self.cas(names, latest, approval_data(failed), verifying)
            return 'Failed'
        except (Failure, common.Denied):
            return None


def main(argv):
    parser = argparse.ArgumentParser(prog='golden', description=__doc__)
    parser.add_argument('--request', required=True)
    args = parser.parse_args(argv)
    cfg = auth.load_platform(auth.PLATFORM_FILE)
    kube = common.Kube(auth.API_TOKEN_FILE, auth.API_CA_FILE)
    code, receipt = Verifier(cfg, kube, auth.GATEWAY_TOKEN_FILE, HERE / 'content').run(args.request)
    print(json.dumps(dict(receipt, event='golden-receipt'), sort_keys=True), flush=True)
    return code
