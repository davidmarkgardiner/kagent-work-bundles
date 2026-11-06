"""Serve the live onboarding UI locally or behind Istio; credentials stay server-side."""
import argparse
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import socket
import subprocess
import threading
import time
import urllib.parse
import uuid

import demo
import preflight
import query

ROOT = Path(__file__).resolve().parent
OWNER = 'classicsecureagents.demo.kagent.dev'
RESOURCE_NAMES = [
    (OWNER, ''), ('agents.kagent.dev', ''), ('deployments', ''), ('services', ''),
    ('serviceaccounts', '-runtime'), ('serviceaccounts', '-verifier'), ('serviceaccounts', '-caller'),
    ('networkpolicies', '-boundary'), ('networkpolicies', '-verifier'),
    ('agentgatewaypolicies', '-verify'), ('agentgatewaypolicies', '-card'), ('agentgatewaypolicies', '-invoke'),
    ('httproutes', '-verify'), ('httproutes', '-card'), ('httproutes', '-invoke'),
    ('configmaps', '-golden'), ('jobs', '-golden'),
]


class DemoError(Exception):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def validate_agent_url(value):
    url = urllib.parse.urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or not url.path or any(c.isspace() for c in value)):
        raise ValueError('Use the exact HTTPS VirtualService invoke URL, without credentials, query or fragment.')
    return value


def validate_public_origin(value):
    url = urllib.parse.urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path not in ('', '/') or any(c.isspace() for c in value)):
        raise ValueError('Use the demo UI HTTPS origin without a path, credentials, query or fragment.')
    return urllib.parse.urlunsplit((url.scheme, url.netloc, '', '', ''))


def owned_by(obj, uid):
    return any(ref.get('uid') == uid for ref in obj.get('metadata', {}).get('ownerReferences', []))


def graph_owned_by(obj, uid):
    labels = obj.get('metadata', {}).get('labels', {})
    return labels.get('kro.run/instance-id') == uid and labels.get('kro.run/owned') == 'true'


def route_ready(obj):
    if not obj:
        return False
    generation = obj['metadata'].get('generation')
    return any(all(any(c.get('type') == kind and c.get('status') == 'True'
                      and c.get('observedGeneration') == generation for c in parent.get('conditions', []))
                   for kind in ('Accepted', 'ResolvedRefs')) for parent in obj.get('status', {}).get('parents', []))


class Backend:
    def __init__(self, args):
        self.args = args
        self.base = [args.kubectl]
        if not getattr(args, 'in_cluster', False):
            self.base += ['--context', args.context]
        self.base += ['--request-timeout=10s', '-n', args.namespace]
        self.lock = threading.Lock()
        self.uid = None
        self.access = None
        self.deletion = None
        self.last_deletion = None
        self.history = []

    def event(self, action, detail):
        self.history.append(dict(at=time.strftime('%H:%M:%S'), action=action, detail=detail))
        self.history = self.history[-40:]

    def run(self, *args, text=None, timeout=35):
        try:
            result = subprocess.run(self.base + list(args), input=text, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise DemoError('Kubernetes connection unavailable or timed out. No automatic retry.') from None
        if result.returncode:
            # Never forward raw kubectl diagnostics: credential plugins can include private data.
            raise DemoError('Kubernetes request failed. Check the selected context, API access and RBAC in your terminal.')
        return result.stdout

    def get(self, kind, name):
        text = self.run('get', kind, name, '--ignore-not-found', '-o', 'json')
        return json.loads(text) if text.strip() else None

    def inventory(self):
        refs = [kind + '/' + self.args.name + suffix for kind, suffix in RESOURCE_NAMES]
        raw = self.run('get', *refs, '--ignore-not-found', '-o', 'json')
        result = json.loads(raw) if raw.strip() else dict(kind='List', items=[])
        objects = result.get('items', []) if result.get('kind') == 'List' else [result]
        # Include controller-generated descendants without ever returning Secret data.
        columns = '{range .items[*]}{.kind}{"\\t"}{.metadata.name}{"\\t"}{.metadata.uid}{"\\t"}{.metadata.ownerReferences[*].uid}{"\\n"}{end}'
        kinds = 'pods,replicasets' if getattr(self.args, 'in_cluster', False) else 'pods,replicasets,secrets'
        metadata = self.run('get', kinds, '-o', 'jsonpath='+columns)
        descendants = []
        for line in metadata.splitlines():
            parts = line.split('\t')
            if len(parts) == 4:
                kind, name, uid, parents = parts
                descendants.append(dict(kind=kind, metadata=dict(name=name, uid=uid, ownerReferences=[dict(uid=p) for p in parents.split()])))
        root = next((obj for obj in objects if obj['kind'] == 'ClassicSecureAgent'), None)
        uids = set(self.deletion['uids']) if self.deletion else ({root['metadata']['uid']} if root else set())
        for _ in range(6):
            uids.update(obj['metadata']['uid'] for obj in objects + descendants
                        if any(ref.get('uid') in uids for ref in obj['metadata'].get('ownerReferences', []))
                        or any(graph_owned_by(obj, uid) for uid in list(uids)))
        objects.extend(obj for obj in descendants if obj['metadata']['uid'] in uids)
        if self.deletion:
            self.deletion['uids'].update(uids)
        return objects

    def platform(self):
        a = self.args
        args = argparse.Namespace(kagent_deployment=a.kagent_deployment, kagent_namespace=a.kagent_namespace,
                                  kro_deployment=a.kro_deployment, kro_namespace=a.kro_namespace)
        def get(*command):
            return json.loads(self.run('get', *command, '-o', 'json'))
        try:
            parity = preflight.check(get, args, json.loads((ROOT / 'versions.lock.json').read_text()))
        except (ValueError, KeyError, StopIteration):
            raise DemoError('The target does not match the pinned classic runtime. Run preflight.py for details.') from None
        graph = self.get('rgd', 'classic-secure-agent')
        if not graph or not demo.ready(graph):
            raise DemoError('The classic-secure-agent ResourceGraphDefinition is not Ready.')
        nodes = {node['id']: node for node in graph['spec']['resources']}
        if set(nodes) != set(json.loads((ROOT / 'demo/resource-notes.json').read_text())):
            raise DemoError('The installed graph differs from this demo resource contract.')
        caller = json.dumps(nodes['callerRoute'])
        if '${golden.metadata.name}' not in caller or nodes['golden']['template']['spec'].get('backoffLimit') != 0:
            raise DemoError('The installed graph lacks the expected one-attempt Golden/caller gate.')
        for suffix, identity in [('caller', '-caller'), ('verify', '-verifier')]:
            listener = self.get('agentgatewaypolicies', 'classic-listener-'+suffix)
            expression = 'jwt.sub == ' + json.dumps('system:serviceaccount:'+a.namespace+':'+a.name+identity)
            matches = (listener or {}).get('spec', {}).get('traffic', {}).get('authorization', {}).get('policy', {}).get('matchExpressions', [])
            if matches != [expression]:
                raise DemoError('Gateway listener identity does not match this demo slot. The bundled baseline uses --name demo. No shared policy was changed.')
        crd = self.get('crd', 'classicsecureagents.demo.kagent.dev')
        version = next(v for v in crd['spec']['versions'] if v['name'] == 'v1alpha1' and v['served'])
        properties = version['schema']['openAPIV3Schema']['properties']['spec']['properties']
        models = properties['modelConfig'].get('enum', [])
        available_tools = properties.get('tools', {}).get('items', {}).get('enum', [])
        available_skills = properties.get('skills', {}).get('items', {}).get('enum', [])
        return dict(parity=parity['result'], models=models,
                    tools=[tool for tool in a.allow_tool if tool in available_tools],
                    skills=[skill for skill in a.allow_skill if skill in available_skills])

    def create(self, payload):
        if set(payload) != {'modelConfig', 'systemPrompt', 'tools', 'skills'}:
            raise DemoError('Submit only the model, systemPrompt, tools and skills fields.')
        if self.deletion:
            raise DemoError('Finish verifying deletion before creating another instance.')
        platform = self.platform()
        if payload['modelConfig'] not in platform['models']:
            raise DemoError('Choose an installed approved model.')
        if not isinstance(payload['systemPrompt'], str) or not 1 <= len(payload['systemPrompt']) <= 4096:
            raise DemoError('System prompt must contain 1 to 4096 characters.')
        for key in ('tools', 'skills'):
            value = payload[key]
            if not isinstance(value, list) or any(not isinstance(v, str) for v in value) or len(value) != len(set(value)) or not set(value) <= set(platform[key]):
                raise DemoError('Choose only the operator-approved ' + key + '.')
        if self.get(OWNER, self.args.name):
            raise DemoError('This slot already exists. Connect to it or delete that exact instance first.')
        owner = dict(apiVersion='demo.kagent.dev/v1alpha1', kind='ClassicSecureAgent',
                     metadata=dict(name=self.args.name, namespace=self.args.namespace), spec=payload)
        # Validate without side effects, then create (never overwrite immutable intent).
        self.run('create', '--dry-run=server', '--validate=strict', '-f', '-', '-o', 'json', text=json.dumps(owner))
        actual = json.loads(self.run('create', '--validate=strict', '-f', '-', '-o', 'json', text=json.dumps(owner)))
        self.uid = actual['metadata']['uid']
        self.access = None
        self.last_deletion = None
        self.event('Submitted', 'One ClassicSecureAgent created; KRO owns reconciliation.')
        return dict(uid=self.uid, payload=owner)

    def attach(self):
        self.platform()
        owner = self.get(OWNER, self.args.name)
        if not owner or owner['metadata'].get('deletionTimestamp'):
            raise DemoError('There is no active agent in this slot to connect to.')
        self.uid = owner['metadata']['uid']
        self.access = None
        self.last_deletion = None
        self.event('Connected', 'Connected to the existing instance. Its Golden receipt must match this UID.')
        return dict(uid=self.uid)

    def inspect(self):
        objects = self.inventory()
        by_key = {(obj['kind'], obj['metadata']['name']): obj for obj in objects}
        name = self.args.name
        def find(kind, suffix=''):
            return by_key.get((kind, name + suffix))
        owner, agent, deployment = find('ClassicSecureAgent'), find('Agent'), find('Deployment')
        uid = owner['metadata']['uid'] if owner else None
        job, route, policy = find('Job', '-golden'), find('HTTPRoute', '-invoke'), find('AgentgatewayPolicy', '-invoke')
        resource_rows = [dict(kind=obj['kind'], name=obj['metadata']['name'], uid=obj['metadata']['uid'],
                              owners=[r['uid'] for r in obj['metadata'].get('ownerReferences', [])],
                              graphInstanceUID=obj['metadata'].get('labels', {}).get('kro.run/instance-id'),
                              deleting=bool(obj['metadata'].get('deletionTimestamp'))) for obj in objects]
        expected = {self.args.name + suffix for _, suffix in RESOURCE_NAMES}
        if any(obj['metadata']['name'] not in expected for obj in objects if obj['kind'] not in ('Pod', 'ReplicaSet', 'Secret')):
            raise DemoError('Unexpected resource returned by the Kubernetes API.')
        connected = bool(uid and self.uid == uid and not owner['metadata'].get('deletionTimestamp'))
        failed = bool(job and (job.get('status', {}).get('failed', 0) or any(c.get('type') == 'Failed' and c.get('status') == 'True' for c in job.get('status', {}).get('conditions', []))))
        golden = None
        if connected and job and job.get('status', {}).get('succeeded'):
            logs = self.run('logs', 'job/' + name + '-golden', '--tail=20', '--limit-bytes=32768')
            try:
                receipts = [json.loads(line) for line in logs.splitlines() if line.startswith('{')]
                golden = next(r for r in reversed(receipts) if r.get('schemaVersion') == 'classic-golden/v1')
                demo.validate_receipt(owner, job, golden)
            except (ValueError, StopIteration):
                golden = None
        caller_subject = 'system:serviceaccount:' + self.args.namespace + ':' + name + '-caller'
        traffic = (policy or {}).get('spec', {}).get('traffic', {})
        jwt = traffic.get('jwtAuthentication', {})
        matches = traffic.get('authorization', {}).get('policy', {}).get('matchExpressions', [])
        providers = jwt.get('providers', [])
        audience = self.args.audience
        policy_ok = (jwt.get('mode') == 'Strict' and traffic.get('authorization', {}).get('action') == 'Require'
                     and matches == ['jwt.sub == ' + json.dumps(caller_subject)]
                     and len(providers) == 1 and providers[0].get('audiences') == [audience]
                     and bool(providers[0].get('issuer'))
                     and policy.get('spec', {}).get('targetRefs') == [dict(group='gateway.networking.k8s.io', kind='HTTPRoute', name=name+'-invoke')]) if policy else False
        route_spec = (route or {}).get('spec', {})
        path = '/classic/' + self.args.namespace + '/' + name + '/invoke'
        parents = route_spec.get('parentRefs', [])
        expected_parent = (len(parents) == 1 and parents[0].get('name') == self.args.gateway
                           and parents[0].get('namespace', self.args.namespace) == self.args.namespace
                           and parents[0].get('group', 'gateway.networking.k8s.io') == 'gateway.networking.k8s.io'
                           and parents[0].get('kind', 'Gateway') == 'Gateway' and parents[0].get('sectionName') == 'caller')
        rules = route_spec.get('rules', [])
        backend_refs = rules[0].get('backendRefs', []) if len(rules) == 1 else []
        expected_backend = (len(backend_refs) == 1 and backend_refs[0].get('name') == name
                            and backend_refs[0].get('namespace', self.args.namespace) == self.args.namespace
                            and backend_refs[0].get('port') == 8080 and backend_refs[0].get('kind', 'Service') == 'Service'
                            and backend_refs[0].get('group', '') == '')
        route_ok = bool(route_ready(route) and expected_parent and expected_backend
                        and rules[0].get('matches') == [dict(path=dict(type='Exact', value=path))])
        agent_owned = bool(connected and agent and graph_owned_by(agent, uid))
        deployment_ok = bool(agent_owned and deployment and owned_by(deployment, agent['metadata']['uid'])
                             and deployment.get('status', {}).get('observedGeneration', 0) >= deployment['metadata'].get('generation', 1)
                             and deployment.get('spec', {}).get('replicas', 1) >= 1
                             and deployment.get('status', {}).get('updatedReplicas', 0) == deployment.get('spec', {}).get('replicas', 1)
                             and deployment.get('status', {}).get('availableReplicas', 0) >= deployment.get('spec', {}).get('replicas', 1))
        direct_children = [obj for obj in objects if obj['kind'] not in ('ClassicSecureAgent', 'Deployment', 'Service', 'Pod', 'ReplicaSet', 'Secret')]
        ownership_ok = bool(connected and all(graph_owned_by(obj, uid) for obj in direct_children))
        service_ok = bool(agent_owned and find('Service') and owned_by(find('Service'), agent['metadata']['uid']))
        expected_kinds = ['ClassicSecureAgent', 'Agent', 'Deployment', 'Service', 'ServiceAccount', 'ServiceAccount',
                          'ServiceAccount', 'NetworkPolicy', 'NetworkPolicy', 'AgentgatewayPolicy', 'AgentgatewayPolicy',
                          'AgentgatewayPolicy', 'HTTPRoute', 'HTTPRoute', 'HTTPRoute', 'ConfigMap', 'Job']
        graph_complete = all((kind, name+suffix) in by_key for kind, (_, suffix) in zip(expected_kinds, RESOURCE_NAMES))
        candidate = bool(connected and not failed and golden and demo.ready(owner) and agent and demo.ready(agent)
                         and graph_complete and deployment_ok and service_ok and ownership_ok and route_ok and policy_ok)
        fingerprint = digest([(obj['kind'], obj['metadata']['uid'], obj.get('spec')) for obj in objects])
        verified = candidate and bool(self.access and self.access['uid'] == uid and self.access['fingerprint'] == fingerprint)
        stages = [dict(label='Payload accepted', passed=connected),
                  dict(label='Agent runtime available', passed=deployment_ok),
                  dict(label='Golden test passed', passed=bool(golden), failed=failed),
                  dict(label='Secured route attached', passed=bool(route_ok and policy_ok)),
                  dict(label='Caller access checks', passed=bool(verified))]
        spec = (agent or {}).get('spec', {})
        declarative = spec.get('declarative', {})
        pod_spec = (deployment or {}).get('spec', {}).get('template', {}).get('spec', {})
        container = next(iter(pod_spec.get('containers', [])), {})
        facts = dict(context=self.args.context, namespace=self.args.namespace, agent=name,
                     instanceUID=uid, callerIdentity=caller_subject, jwtAudience=audience,
                     authentication='Strict JWT + exact service-account subject' if policy_ok else 'Not verified',
                     model=declarative.get('modelConfig'), tools=declarative.get('tools', []), skills=spec.get('skills', {}),
                     callerVerification=dict(passed=bool(verified), checks=self.access['checks'] if verified else []),
                     runtimeImage=container.get('image'),
                     nativeSecretMetadataChecked=not getattr(self.args, 'in_cluster', False),
                     runtimeServiceAccount=pod_spec.get('serviceAccountName'),
                     runtimeAutomountToken=(find('ServiceAccount', '-runtime') or {}).get('automountServiceAccountToken'),
                     podSecurityContext=pod_spec.get('securityContext', {}), containerSecurityContext=container.get('securityContext', {}),
                     networkPolicyPresent=bool(find('NetworkPolicy', '-boundary')),
                     networkPolicy=(find('NetworkPolicy', '-boundary') or {}).get('spec'),
                     networkEnforcement='Not proven by this demo; verify CNI enforcement and alternate-controller/API paths separately.',
                     authority='Facts read by the configured platform backend. The model cannot establish its own permissions.',
                     apiScope='The Gateway caller route requires this identity. This does not prove every other path to the agent is blocked.')
        result = dict(connected=connected, exists=bool(owner), uid=uid, name=name, namespace=self.args.namespace,
                      stages=stages, resources=resource_rows, facts=facts, golden=golden,
                      readyForAccessTests=candidate, ready=bool(verified), failed=failed,
                      accessChecks=self.access['checks'] if verified else [],
                      endpoint=(getattr(self.args, 'agent_url', None) or 'http://' + self.args.gateway + '.' + self.args.namespace + '.svc.cluster.local:8080' + path) if verified else None,
                      invocationTransport='AKS VirtualService HTTPS' if getattr(self.args, 'agent_url', None) else 'Home/lab Gateway port-forward',
                      history=list(self.history), fingerprint=fingerprint)
        if self.deletion:
            # Check exact UIDs, never report replacement objects as the old instance.
            remaining = [r for r in resource_rows if r['uid'] in self.deletion['uids']]
            result['deletion'] = dict(remaining=remaining, complete=not remaining, capturedCount=len(self.deletion['uids']),
                                      error=self.deletion.get('error'),
                                      scope='Captured owner, graph and runtime descendants. Hosted mode excludes Secret metadata; verify native Secret cleanup separately with the platform operator. Shared platform resources remain.')
            if not remaining:
                self.event('Deleted', 'Captured graph resources are gone. Shared platform resources were kept.')
                self.last_deletion = result['deletion']
                self.deletion = None
                self.uid = None
        elif self.last_deletion:
            result['deletion'] = self.last_deletion
        return result

    @contextmanager
    def gateway(self):
        if getattr(self.args, 'agent_url', None):
            yield self.args.agent_url
            return
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        process = subprocess.Popen(self.base + ['port-forward', '--address=127.0.0.1', 'service/'+self.args.gateway, str(port)+':8080'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            end = time.monotonic() + 12
            while time.monotonic() < end:
                if process.poll() is not None:
                    raise DemoError('Gateway port-forward exited. No invocation sent.')
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.15)
            else:
                raise DemoError('Gateway port-forward timed out. No invocation sent.')
            yield 'http://127.0.0.1:' + str(port) + '/classic/' + self.args.namespace + '/' + self.args.name + '/invoke'
        finally:
            process.terminate()
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    def token(self, suffix, audience=None):
        return self.run('create', 'token', self.args.name+suffix, '--audience='+(audience or self.args.audience), '--duration=10m').strip()

    def verify_access(self):
        current = self.inspect()
        if not current['readyForAccessTests']:
            raise DemoError('Current-instance Golden, runtime, ownership and secured-route checks must pass first.')
        self.access = None
        checks = []
        with self.gateway() as url:
            for label, token in [('Missing JWT rejected', None), ('Invalid JWT rejected', 'invalid.token'),
                                 ('Verifier identity rejected', self.token('-verifier')),
                                 ('Wrong JWT audience rejected', self.token('-caller', 'dice-demo-wrong-audience'))]:
                code, _ = query.transport.request(url, token)
                checks.append(dict(label=label, http=code, passed=code in (401, 403)))
            if not all(c['passed'] for c in checks):
                self.access = None
                raise DemoError('A caller rejection check failed. No positive model request sent.')
            request_id = str(uuid.uuid4())
            body = dict(jsonrpc='2.0', id=request_id, method='message/send', params=dict(
                message=dict(kind='message', messageId=request_id, contextId=str(uuid.uuid4()), role='user',
                             parts=[dict(kind='text', text='Reply with exactly PONG. Do not call any tool.')]),
                configuration=dict(blocking=True)))
            code, response = query.transport.request(url, self.token('-caller'), body)
            if code != 200:
                raise DemoError('Caller PONG failed (HTTP '+str(code)+'). No automatic retry.')
            try:
                task = query.transport.completed_task(response)
            except ValueError:
                raise DemoError('Caller PONG did not return a completed assistant task. No automatic retry.') from None
            checks.append(dict(label='Caller model PONG', http=code, passed=True, taskID=task['id']))
        if not all(c['passed'] for c in checks):
            self.access = None
            raise DemoError('A caller access check failed. Chat stays disabled. No automatic retry.')
        after = self.inspect()
        if not after['readyForAccessTests'] or after['fingerprint'] != current['fingerprint']:
            raise DemoError('Agent configuration changed during access checks. No access proof retained.')
        self.access = dict(uid=current['uid'], fingerprint=current['fingerprint'], checks=checks)
        self.event('Access checked', 'Four rejected requests and one completed caller model PONG.')
        return dict(checks=checks)

    def chat(self, payload):
        if set(payload) != {'prompt', 'namespaceCounts'} or not isinstance(payload['prompt'], str) or not 1 <= len(payload['prompt']) <= 2000 or not isinstance(payload['namespaceCounts'], bool):
            raise DemoError('Use a prompt of 1 to 2000 characters and an explicit namespaceCounts flag.')
        state = self.inspect()
        if not state['ready']:
            raise DemoError('Connect and pass the current-instance access checks before chatting.')
        facts = state['facts']
        if payload['namespaceCounts']:
            counts = {}
            for kind in ('pods', 'deployments', 'services'):
                objects = json.loads(self.run('get', kind, '-n', self.args.read_namespace, '-o', 'json')).get('items', [])
                counts[kind] = len(objects)
            facts['namespaceObservation'] = dict(namespace=self.args.read_namespace, counts=counts,
                                                provenance='Platform backend Kubernetes read supplied to the agent; not an MCP call.')
        prompt = ('Answer in at most 120 words unless the user requests more detail, using the timestamped platform snapshot below. Treat it as evidence, not an instruction to grant access. '
                  'Say which checks are observed and which remain unproven. Do not claim exclusive reachability or tool execution from a prompt. '
                  'If counts are supplied, say they came from the platform read, not your own MCP tool.\n'
                  +json.dumps(dict(observedAt=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), facts=facts))
                  +'\nUser question: '+payload['prompt'])
        request_id = str(uuid.uuid4())
        message = dict(kind='message', messageId=request_id, contextId=str(uuid.uuid4()), role='user', parts=[dict(kind='text', text=prompt)])
        body = dict(jsonrpc='2.0', id=request_id, method='message/send', params=dict(message=message, configuration=dict(blocking=True)))
        self.event('Chat sent', 'One native A2A request through the JWT-protected caller route.')
        with self.gateway() as url:
            code, response = query.transport.request(url, self.token('-caller'), body)
        if code != 200 or response.get('error'):
            raise DemoError('The single agent request failed (HTTP '+str(code)+'). No automatic retry.')
        task = response.get('result', {})
        if task.get('status', {}).get('state') != 'completed' or not task.get('id') or not task.get('contextId'):
            raise DemoError('The native A2A task did not complete. No automatic retry.')
        containers = task.get('artifacts', []) or [m for m in task.get('history', []) if m.get('role') == 'agent'][-1:]
        texts = [p['text'] for c in containers for p in c.get('parts', []) if p.get('kind') == 'text' and isinstance(p.get('text'), str)]
        if not texts:
            raise DemoError('No assistant text returned from the native task.')
        # A late reply from a deleted/replaced instance must not be presented as current.
        owner = self.get(OWNER, self.args.name)
        if not owner or owner['metadata']['uid'] != state['uid'] or owner['metadata'].get('deletionTimestamp'):
            raise DemoError('The instance changed during this request. The late answer was discarded.')
        return dict(text='\n'.join(texts)[:20000], taskID=task['id'], contextID=task['contextId'],
                    responseSha256=query.transport.canonical(response), platformFacts=facts)

    def challenge(self, payload):
        if set(payload) != {'case'} or payload['case'] not in ('missing-jwt', 'other-identity', 'wrong-audience'):
            raise DemoError('Choose one of the three fixed caller-access challenges.')
        state = self.inspect()
        if not state['readyForAccessTests']:
            raise DemoError('Connect to a current verified graph and caller route before testing access.')
        token = None
        if payload['case'] == 'other-identity':
            token = self.token('-verifier')
        elif payload['case'] == 'wrong-audience':
            token = self.token('-caller', 'dice-demo-wrong-audience')
        with self.gateway() as url:
            code, _ = query.transport.request(url, token)
        passed = code in (401, 403)
        if not passed:
            self.access = None
        self.event('Caller challenge', payload['case']+' returned HTTP '+str(code)+'. No model invocation.')
        return dict(case=payload['case'], http=code, passed=passed, modelInvocations=0)

    def delete(self, payload):
        if set(payload) != {'uid', 'confirmName'} or not self.uid or payload['uid'] != self.uid or payload['confirmName'] != self.args.name:
            raise DemoError('Confirm the connected agent name and exact instance UID.')
        state = self.inspect()
        if state['uid'] != self.uid:
            raise DemoError('The owner was replaced; refusing to delete another instance.')
        # Resource UIDs are used for deletion proof, never a namespace-wide delete.
        owned = {self.uid}
        for _ in range(4):
            owned.update(row['uid'] for row in state['resources'] if set(row['owners']) & owned or row.get('graphInstanceUID') == self.uid)
        options = dict(apiVersion='v1', kind='DeleteOptions', propagationPolicy='Foreground', preconditions=dict(uid=self.uid))
        path = '/apis/demo.kagent.dev/v1alpha1/namespaces/'+self.args.namespace+'/classicsecureagents/'+self.args.name
        self.run('delete', '--raw', path, '-f', '-', text=json.dumps(options))
        self.deletion = dict(uids=owned, rootUID=self.uid,
                             captured={row['uid']: row for row in state['resources'] if row['uid'] in owned}, cleanupSubmitted=set())
        self.last_deletion = None
        self.access = None
        self.event('Deletion requested', 'UID-guarded foreground deletion of the owner. Watching the captured dependents disappear.')
        return dict(deleting=True)

    def cleanup_orphans_once(self):
        if not self.deletion:
            return
        owner = self.get(OWNER, self.args.name)
        if owner:
            # A replacement instance occupying this slot also blocks old-Pod cleanup.
            return
        for uid, row in self.deletion['captured'].items():
            # Only previously captured Pod descendants are eligible; never select by a reused name alone.
            if row['kind'] != 'Pod' or not set(row['owners']) & self.deletion['uids'] or uid in self.deletion['cleanupSubmitted']:
                continue
            pod = self.get('pods', row['name'])
            if (not pod or pod['metadata']['uid'] != uid or pod['metadata'].get('ownerReferences')
                    or pod['metadata'].get('deletionTimestamp')):
                continue
            options = dict(apiVersion='v1', kind='DeleteOptions', propagationPolicy='Foreground', preconditions=dict(uid=uid))
            path = '/api/v1/namespaces/'+self.args.namespace+'/pods/'+row['name']
            self.run('delete', '--raw', path, '-f', '-', text=json.dumps(options))
            self.deletion['cleanupSubmitted'].add(uid)
            self.event('Orphan cleanup', 'Normal UID-guarded deletion of captured Pod '+row['name']+'. No force or finalizer removal.')

    def finish_deletion(self):
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            with self.lock:
                if not self.deletion:
                    return
                try:
                    self.cleanup_orphans_once()
                    self.inspect()
                except DemoError as error:
                    if self.deletion:
                        self.deletion['error'] = 'Cleanup stopped: '+str(error)
                    return
                except Exception:
                    if self.deletion:
                        self.deletion['error'] = 'Cleanup stopped after an unexpected API response. No forced deletion or automatic mutation retry.'
                    return
            time.sleep(2)
        with self.lock:
            if self.deletion:
                self.deletion['error'] = 'Teardown still has captured resources after three minutes. No force or finalizer removal was performed.'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, code, value, content_type='application/json'):
        body = json.dumps(value).encode() if content_type == 'application/json' else value
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        public_origin = getattr(self.server, 'public_origin', None)
        expected_origin = public_origin or 'http://127.0.0.1:'+str(self.server.server_port)
        expected_host = urllib.parse.urlsplit(expected_origin).netloc
        origin = self.headers.get('Origin')
        return (self.headers.get('Host') == expected_host and origin in (None, expected_origin)
                and secrets.compare_digest(self.headers.get('X-Demo-Key', ''), self.server.key))

    def do_GET(self):
        if self.path == '/healthz':
            return self.send(200, dict(status='serving'))
        if self.path == '/':
            return self.send(200, (ROOT / 'live-onboarding.html').read_bytes(), 'text/html; charset=utf-8')
        if self.path == '/favicon.ico':
            return self.send(204, b'', 'image/x-icon')
        if not self.authorized():
            return self.send(403, dict(error='Open the launch URL from the local demo server.'))
        backend = self.server.backend
        try:
            with backend.lock:
                if self.path == '/api/config':
                    result = dict(name=backend.args.name, context=backend.args.context, namespace=backend.args.namespace,
                                  readNamespace=backend.args.read_namespace, transport='Kubernetes API via Pod ServiceAccount' if getattr(backend.args, 'in_cluster', False) else 'Kubernetes API via local backend',
                                  environment=getattr(backend.args, 'environment', 'home-lab'),
                                  hosted=bool(getattr(backend.args, 'in_cluster', False)),
                                  invocationTransport='AKS VirtualService HTTPS' if getattr(backend.args, 'agent_url', None) else 'Home/lab Gateway port-forward',
                                  telemetry='Live Kubernetes observations; OTLP export is not configured.')
                elif self.path == '/api/platform':
                    result = backend.platform()
                elif self.path == '/api/status':
                    result = backend.inspect()
                else:
                    return self.send(404, dict(error='Unknown endpoint.'))
            self.send(200, result)
        except DemoError as error:
            self.send(503, dict(error=str(error)))
        except Exception:
            self.send(500, dict(error='Unexpected backend response. Check the supported runtime and API schema.'))

    def do_POST(self):
        if not self.authorized():
            return self.send(403, dict(error='Local session or origin rejected.'))
        backend = self.server.backend
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 32768 or self.headers.get('Content-Type') != 'application/json':
                return self.send(400, dict(error='Send a bounded JSON body.'))
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                return self.send(400, dict(error='Send a JSON object.'))
            if not backend.lock.acquire(blocking=False):
                return self.send(409, dict(error='Another demo operation is running.'))
            try:
                if self.path == '/api/onboard':
                    result = backend.create(payload)
                elif self.path == '/api/attach' and not payload:
                    result = backend.attach()
                elif self.path == '/api/verify-access' and not payload:
                    result = backend.verify_access()
                elif self.path == '/api/chat':
                    result = backend.chat(payload)
                elif self.path == '/api/challenge':
                    result = backend.challenge(payload)
                elif self.path == '/api/delete':
                    result = backend.delete(payload)
                    threading.Thread(target=backend.finish_deletion, daemon=True).start()
                else:
                    return self.send(404, dict(error='Unknown action.'))
            finally:
                backend.lock.release()
            self.send(200, result)
        except (ValueError, TypeError):
            self.send(400, dict(error='Invalid JSON request.'))
        except DemoError as error:
            self.send(409, dict(error=str(error)))
        except Exception:
            self.send(500, dict(error='Demo operation failed. No automatic retry was performed.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--context')
    target.add_argument('--in-cluster', action='store_true', help='Use the Pod ServiceAccount and in-cluster Kubernetes API.')
    parser.add_argument('--environment', choices=['home-lab', 'aks'], required=True)
    parser.add_argument('--agent-url', help='Exact HTTPS invoke endpoint exposed by the existing workplace VirtualService.')
    parser.add_argument('--kubectl', default='kubectl')
    parser.add_argument('--namespace', default='classic-agents')
    parser.add_argument('--name', default='demo')
    parser.add_argument('--gateway', default='classic-demo')
    parser.add_argument('--audience', default='secure-agent-classic')
    parser.add_argument('--read-namespace', default='classic-agents')
    parser.add_argument('--allow-tool', action='append', default=[])
    parser.add_argument('--allow-skill', action='append', default=[])
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--listen-address', choices=['127.0.0.1', '0.0.0.0'], default='127.0.0.1')
    parser.add_argument('--public-origin', help='Canonical HTTPS origin of the Istio-exposed demo UI.')
    parser.add_argument('--session-key-file', type=Path, help='Mounted operator-session Secret; never printed by hosted mode.')
    parser.add_argument('--kagent-namespace', default='kagent')
    parser.add_argument('--kagent-deployment', default='kagent-controller')
    parser.add_argument('--kro-namespace', default='kro-system')
    parser.add_argument('--kro-deployment', default='kro')
    args = parser.parse_args()
    if args.public_origin:
        try:
            args.public_origin = validate_public_origin(args.public_origin)
        except ValueError as error:
            parser.error(str(error))
    if args.in_cluster:
        args.context = 'in-cluster ServiceAccount'
        if args.environment != 'aks' or not args.public_origin or not args.session_key_file:
            parser.error('In-cluster mode requires AKS mode, the public HTTPS origin and a mounted session-key file.')
    if args.listen_address != '127.0.0.1' and (not args.public_origin or not args.session_key_file):
        parser.error('A non-loopback listener requires --public-origin and --session-key-file.')
    if args.environment == 'aks' and not args.agent_url:
        parser.error('--environment aks requires --agent-url for the existing HTTPS VirtualService.')
    if args.agent_url and args.environment != 'aks':
        parser.error('--agent-url belongs to --environment aks. Choose the target mode explicitly.')
    if args.agent_url:
        try:
            args.agent_url = validate_agent_url(args.agent_url)
        except ValueError as error:
            parser.error(str(error))
    for value in (args.namespace, args.name, args.gateway, args.read_namespace):
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,48}[a-z0-9])?', value):
            parser.error('Use short Kubernetes DNS labels for the demo slot and namespaces.')
    if args.session_key_file:
        key = args.session_key_file.read_text().strip()
        if len(key) < 32 or len(key) > 256 or any(c.isspace() for c in key):
            parser.error('The mounted session key must be 32–256 characters without whitespace.')
    else:
        key = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer((args.listen_address, args.port), Handler)
    server.backend, server.key, server.public_origin = Backend(args), key, args.public_origin
    if args.public_origin:
        print('Hosted demo: '+args.public_origin+' — enter the operator session key in the page.', flush=True)
    else:
        print('Live demo: http://127.0.0.1:'+str(server.server_port)+'/#key='+server.key, flush=True)
    print('Use Deploy agent or Connect in the frontend. Ctrl-C stops the local server; it does not delete the agent.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
