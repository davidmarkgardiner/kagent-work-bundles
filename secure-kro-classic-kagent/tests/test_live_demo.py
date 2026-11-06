import copy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import threading
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live_demo


def backend():
    return live_demo.Backend(SimpleNamespace(context='fixture-only', namespace='classic-agents', name='demo',
        kubectl='kubectl', gateway='classic-demo', audience='secure-agent-classic', read_namespace='classic-agents',
        allow_tool=[], allow_skill=[], kagent_namespace='kagent', kagent_deployment='kagent-controller',
        kro_namespace='kro-system', kro_deployment='kro'))


def fixture():
    def obj(kind, name, uid, parent=None, spec=None):
        metadata = dict(name=name, uid=uid, generation=1)
        if parent:
            metadata['ownerReferences'] = [dict(uid=parent)]
        return dict(kind=kind, metadata=metadata, spec=spec or {})
    ready = dict(conditions=[dict(type='Ready', status='True', observedGeneration=1)])
    objects = [obj('ClassicSecureAgent', 'demo', 'owner-1'),
               obj('Agent', 'demo', 'agent-1', 'owner-1', dict(declarative=dict(modelConfig='approved-model', tools=[]))),
               obj('Deployment', 'demo', 'deployment-1', 'agent-1'), obj('Service', 'demo', 'service-1', 'agent-1'),
               obj('Job', 'demo-golden', 'golden-1', 'owner-1'), obj('HTTPRoute', 'demo-invoke', 'route-1', 'owner-1'),
               obj('AgentgatewayPolicy', 'demo-invoke', 'policy-1', 'owner-1')]
    for entry in objects[:2]:
        entry['status'] = copy.deepcopy(ready)
    objects[2]['status'] = dict(observedGeneration=1, availableReplicas=1, updatedReplicas=1)
    objects[4]['status'] = dict(succeeded=1)
    objects[4]['metadata']['labels'] = {'kro.run/instance-id': 'owner-1'}
    objects[5]['spec'] = dict(parentRefs=[dict(group='gateway.networking.k8s.io', kind='Gateway', name='classic-demo', namespace='classic-agents', sectionName='caller')],
        rules=[dict(matches=[dict(path=dict(type='Exact', value='/classic/classic-agents/demo/invoke'))],
            backendRefs=[dict(group='', kind='Service', name='demo', namespace='classic-agents', port=8080, weight=1)])])
    objects[5]['status'] = dict(parents=[dict(conditions=[dict(type=kind, status='True', observedGeneration=1) for kind in ['Accepted','ResolvedRefs']])])
    objects[6]['spec'] = dict(targetRefs=[dict(group='gateway.networking.k8s.io', kind='HTTPRoute', name='demo-invoke')],
        traffic=dict(jwtAuthentication=dict(mode='Strict', providers=[dict(issuer='https://issuer.example.com', audiences=['secure-agent-classic'])]),
                     authorization=dict(action='Require', policy=dict(matchExpressions=['jwt.sub == "system:serviceaccount:classic-agents:demo-caller"']))))
    for kind,suffix in [('ServiceAccount','-runtime'),('ServiceAccount','-verifier'),('ServiceAccount','-caller'),
                        ('NetworkPolicy','-boundary'),('NetworkPolicy','-verifier'),('AgentgatewayPolicy','-verify'),
                        ('AgentgatewayPolicy','-card'),('HTTPRoute','-verify'),('HTTPRoute','-card'),('ConfigMap','-golden')]:
        objects.append(obj(kind,'demo'+suffix,kind+suffix+'-1','owner-1'))
    for entry in objects:
        if entry['kind'] not in ('ClassicSecureAgent', 'Deployment', 'Service'):
            entry['metadata'].pop('ownerReferences', None)
            entry['metadata']['labels'] = {'kro.run/instance-id':'owner-1','kro.run/owned':'true'}
    receipt = dict(schemaVersion='classic-golden/v1', passed=True, requestUID='owner-1', taskID='golden-task', contextID='golden-context')
    return objects, receipt


class LiveDemoTests(unittest.TestCase):
    def test_real_kubectl_empty_output_is_an_empty_slot_not_a_json_error(self):
        b=backend();b.run=lambda *args,**kwargs:''
        state=b.inspect()
        self.assertFalse(state['exists'])
        self.assertFalse(state['ready'])
        self.assertEqual(state['resources'],[])

    def test_workplace_endpoint_requires_https_and_cannot_embed_credentials(self):
        accepted='https://agents.example.com/classic/classic-agents/demo/invoke'
        self.assertEqual(live_demo.validate_agent_url(accepted),accepted)
        for url in ['http://agents.example.com/invoke','https://user:password@agents.example.com/invoke',
                    'https://agents.example.com/invoke?token=secret','https://agents.example.com/invoke#fragment']:
            with self.assertRaises(ValueError):live_demo.validate_agent_url(url)

    def test_virtualservice_mode_never_opens_a_lab_port_forward(self):
        b=backend();b.args.agent_url='https://agents.example.com/invoke'
        with patch.object(live_demo.subprocess,'Popen',side_effect=AssertionError('No port-forward in VirtualService mode')):
            with b.gateway() as url:self.assertEqual(url,b.args.agent_url)

    def connected(self):
        b = backend()
        objects, receipt = fixture()
        b.uid = 'owner-1'
        b.inventory = lambda: copy.deepcopy(objects)
        b.run = lambda *args, **kw: json.dumps(receipt)
        return b, objects, receipt

    def test_defaulted_gateway_fields_and_current_golden_allow_access_tests_only(self):
        b, _, _ = self.connected()
        state = b.inspect()
        self.assertTrue(state['readyForAccessTests'])
        self.assertFalse(state['ready'])
        self.assertIsNone(state['endpoint'])

    def test_stale_golden_does_not_open_a_replacement_instance(self):
        b, _, receipt = self.connected()
        receipt['requestUID'] = 'previous-owner'
        self.assertFalse(b.inspect()['readyForAccessTests'])

    def test_missing_boundary_resource_keeps_api_locked(self):
        b, objects, _ = self.connected()
        objects[:] = [o for o in objects if o['kind'] != 'NetworkPolicy']
        self.assertFalse(b.inspect()['readyForAccessTests'])

    def test_foreign_route_and_wrong_subject_cannot_open_chat(self):
        b, objects, _ = self.connected()
        for change in ['backend', 'subject', 'ownership', 'audience']:
            candidate = copy.deepcopy(objects)
            if change == 'backend':
                candidate[5]['spec']['rules'][0]['backendRefs'][0]['name'] = 'other-agent'
            elif change == 'subject':
                candidate[6]['spec']['traffic']['authorization']['policy']['matchExpressions'] = ['true']
            elif change == 'ownership':
                candidate[5]['metadata']['labels']['kro.run/instance-id'] = 'other-owner'
            else:
                candidate[6]['spec']['traffic']['jwtAuthentication']['providers'][0]['audiences'] = ['other']
            b.inventory = lambda: copy.deepcopy(candidate)
            self.assertFalse(b.inspect()['readyForAccessTests'], change)

    def test_changed_configuration_invalidates_prior_access_proof(self):
        b, objects, _ = self.connected()
        initial = b.inspect()
        b.access = dict(uid=b.uid, fingerprint=initial['fingerprint'], checks=[])
        self.assertTrue(b.inspect()['ready'])
        objects[1]['spec']['declarative']['tools'] = [dict(type='McpServer')]
        self.assertFalse(b.inspect()['ready'])

    def test_failed_rejection_sends_no_model_request(self):
        b, _, _ = self.connected()
        @contextmanager
        def gateway():
            yield 'http://127.0.0.1/invoke'
        b.gateway = gateway
        b.token = lambda *args: 'fixture-token'
        with patch.object(live_demo.query.transport, 'request', return_value=(200, {})) as call:
            with self.assertRaises(live_demo.DemoError):
                b.verify_access()
            self.assertEqual(call.call_count, 4)
            self.assertTrue(all(len(c.args) == 2 for c in call.call_args_list))
            self.assertIsNone(b.access)

    def test_caller_model_failure_is_not_retried_or_retained(self):
        b, _, _ = self.connected()
        @contextmanager
        def gateway():
            yield 'http://127.0.0.1/invoke'
        b.gateway = gateway
        b.token = lambda *args: 'fixture-token'
        with patch.object(live_demo.query.transport, 'request', side_effect=[(401,{})]*4+[(502,{})]) as call:
            with self.assertRaisesRegex(live_demo.DemoError, 'No automatic retry'):
                b.verify_access()
            self.assertEqual(call.call_count, 5)
            self.assertIsNone(b.access)

    def test_live_challenge_sends_one_bodyless_request_and_reports_actual_denial(self):
        b, _, _ = self.connected()
        @contextmanager
        def gateway():yield 'http://127.0.0.1/invoke'
        b.gateway=gateway;b.token=lambda *args:'different-identity'
        with patch.object(live_demo.query.transport,'request',return_value=(403,{})) as call:
            result=b.challenge(dict(case='other-identity'))
        self.assertTrue(result['passed'])
        self.assertEqual(result['modelInvocations'],0)
        self.assertEqual(call.call_args.args,('http://127.0.0.1/invoke','different-identity'))

    def test_unexpected_challenge_result_revokes_chat_proof(self):
        b, _, _ = self.connected()
        @contextmanager
        def gateway():yield 'http://127.0.0.1/invoke'
        b.gateway=gateway;b.access=dict(uid=b.uid,fingerprint=b.inspect()['fingerprint'],checks=[])
        with patch.object(live_demo.query.transport,'request',return_value=(200,{})):
            self.assertFalse(b.challenge(dict(case='missing-jwt'))['passed'])
        self.assertIsNone(b.access)

    def test_payload_cannot_choose_a_namespace_command_or_unapproved_tool(self):
        b = backend()
        b.platform = lambda: dict(models=['approved-model'], tools=[], skills=[])
        b.run = lambda *args, **kw: self.fail('No Kubernetes write expected')
        base = dict(modelConfig='approved-model', systemPrompt='Read only.', tools=[], skills=[])
        for value in [dict(base, namespace='other'), dict(base, command='shell'), dict(base, tools=['write-tool'])]:
            with self.assertRaises(live_demo.DemoError):
                b.create(value)

    def test_create_never_overwrites_an_existing_owner(self):
        b = backend()
        b.platform = lambda: dict(models=['approved-model'], tools=[], skills=[])
        b.get = lambda *args: fixture()[0][0]
        b.run = lambda *args, **kw: self.fail('No mutation of existing owner expected')
        with self.assertRaisesRegex(live_demo.DemoError, 'already exists'):
            b.create(dict(modelConfig='approved-model', systemPrompt='Read only.', tools=[], skills=[]))

    def test_connect_existing_records_its_uid_without_creating_resources(self):
        b = backend()
        b.platform = lambda: dict(models=['approved-model'], tools=[], skills=[])
        b.get = lambda *args: fixture()[0][0]
        b.run = lambda *args, **kw: self.fail('Connect must not create or modify resources')
        self.assertEqual(b.attach(), dict(uid='owner-1'))
        self.assertEqual(b.uid, 'owner-1')
        self.assertIsNone(b.access)

    def test_delete_requires_connected_uid_and_uses_a_server_uid_precondition(self):
        b, _, _ = self.connected()
        writes = []
        b.run = lambda *args, **kw: writes.append((args,kw)) or '{}'
        b.inspect = lambda: dict(uid='owner-1', resources=[dict(uid='owner-1', owners=[]),dict(uid='child-1',owners=['owner-1']),dict(uid='foreign',owners=[])])
        with self.assertRaises(live_demo.DemoError):
            b.delete(dict(uid='old-uid',confirmName='demo'))
        b.delete(dict(uid='owner-1',confirmName='demo'))
        self.assertEqual(len(writes), 1)
        args,kw = writes[0]
        self.assertEqual(args[:2], ('delete','--raw'))
        body = json.loads(kw['text'])
        self.assertEqual(body['preconditions'], dict(uid='owner-1'))
        self.assertEqual(body['propagationPolicy'], 'Foreground')
        self.assertEqual(b.deletion['uids'], {'owner-1','child-1'})

    def test_deletion_tracks_late_old_descendants_without_adopting_a_replacement(self):
        b = backend()
        replacement = fixture()[0][0]
        replacement['metadata']['uid'] = 'replacement-owner'
        b.uid = 'previous-owner'
        b.deletion = dict(uids={'previous-owner','previous-deployment'})
        metadata = ['Pod\tdemo-previous\tprevious-pod\tprevious-deployment\n']
        def run(*args, **kw):
            if args[-1].startswith('jsonpath='):
                return metadata[0]
            return json.dumps(dict(kind='List',items=[replacement]))
        b.run = run
        state = b.inspect()
        self.assertEqual([r['uid'] for r in state['deletion']['remaining']], ['previous-pod'])
        self.assertNotIn('replacement-owner', b.deletion['uids'])
        metadata[0] = ''
        state = b.inspect()
        self.assertTrue(state['deletion']['complete'])
        self.assertTrue(state['exists'])
        self.assertFalse(state['connected'])

    def orphan_case(self):
        b=backend();b.uid='owner-1'
        b.deletion=dict(rootUID='owner-1',uids={'owner-1','job-1','pod-1'},cleanupSubmitted=set(),
                        captured={'pod-1':dict(kind='Pod',name='demo-golden-pod',owners=['job-1'])})
        pod=dict(metadata=dict(uid='pod-1'))
        b.get=lambda kind,name: None if kind==live_demo.OWNER else pod
        writes=[];b.run=lambda *args,**kw:writes.append((args,kw)) or '{}'
        return b,pod,writes

    def test_captured_orphan_pod_cleanup_is_uid_guarded_and_submitted_once(self):
        b,_,writes=self.orphan_case();b.cleanup_orphans_once();b.cleanup_orphans_once()
        self.assertEqual(len(writes),1)
        self.assertEqual(writes[0][0][2],'/api/v1/namespaces/classic-agents/pods/demo-golden-pod')
        options=json.loads(writes[0][1]['text'])
        self.assertEqual(options['preconditions'],dict(uid='pod-1'))
        self.assertNotIn('gracePeriodSeconds',options)

    def test_orphan_cleanup_preserves_replacement_pods(self):
        b,pod,writes=self.orphan_case();pod['metadata']['uid']='new-pod'
        b.cleanup_orphans_once();self.assertEqual(writes,[])

    def test_orphan_cleanup_leaves_managed_pods_and_existing_owner_alone(self):
        b,pod,writes=self.orphan_case();pod['metadata']['ownerReferences']=[dict(uid='job-1')]
        b.cleanup_orphans_once();self.assertEqual(writes,[])
        pod['metadata'].pop('ownerReferences');b.get=lambda *args:dict(metadata=dict(uid='owner-1'))
        b.cleanup_orphans_once();self.assertEqual(writes,[])
        b.get=lambda *args:dict(metadata=dict(uid='replacement-owner'))
        b.cleanup_orphans_once();self.assertEqual(writes,[])


class HTTPBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.server = live_demo.ThreadingHTTPServer(('127.0.0.1',0), live_demo.Handler)
        self.server.key = 'fixture-session-key'
        self.server.backend = backend()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def status(self, path, key=None, origin=None):
        headers = {}
        if key: headers['X-Demo-Key']=key
        if origin: headers['Origin']=origin
        request = urllib.request.Request(self.url+path,headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as response:
            with response:
                return response.code,response.read()

    def test_api_requires_local_session_and_rejects_cross_origin(self):
        self.assertEqual(self.status('/api/config')[0],403)
        self.assertEqual(self.status('/api/config','fixture-session-key','https://other.example.com')[0],403)
        status, body = self.status('/api/config','fixture-session-key',self.url)
        self.assertEqual(status,200)
        self.assertNotIn(b'fixture-session-key',body)

    def test_server_does_not_serve_repository_files(self):
        self.assertEqual(self.status('/live_demo.py','fixture-session-key')[0],404)
        self.assertEqual(self.status('/../examples/platform-profile.json','fixture-session-key')[0],404)


class RawDeleteTransportTests(unittest.TestCase):
    def test_real_kubectl_sends_delete_options_and_uid_to_the_exact_endpoint(self):
        seen=[]
        class API(live_demo.BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_DELETE(self):
                if self.headers.get('Transfer-Encoding') == 'chunked':
                    chunks=[]
                    while True:
                        size=int(self.rfile.readline().strip(),16)
                        if not size:
                            self.rfile.readline();break
                        chunks.append(self.rfile.read(size));self.rfile.read(2)
                    raw=b''.join(chunks)
                else:
                    raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
                seen.append((self.path,json.loads(raw)))
                body=json.dumps(dict(apiVersion='v1',kind='Status',status='Success')).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        server=live_demo.ThreadingHTTPServer(('127.0.0.1',0),API)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                config=Path(directory)/'config'
                config.write_text(json.dumps(dict(apiVersion='v1',kind='Config',clusters=[dict(name='fixture',cluster=dict(server='http://127.0.0.1:'+str(server.server_port)))],
                    contexts=[dict(name='fixture-only',context=dict(cluster='fixture',user='fixture'))],users=[dict(name='fixture',user={})])))
                b=backend();b.uid='owner-1';b.inspect=lambda:dict(uid='owner-1',resources=[dict(uid='owner-1',owners=[])])
                with patch.dict(os.environ,{'KUBECONFIG':str(config)}):
                    b.delete(dict(uid='owner-1',confirmName='demo'))
            self.assertEqual(len(seen),1)
            self.assertEqual(urllib.parse.urlsplit(seen[0][0]).path,'/apis/demo.kagent.dev/v1alpha1/namespaces/classic-agents/classicsecureagents/demo')
            self.assertEqual(seen[0][1]['preconditions'],dict(uid='owner-1'))
            self.assertEqual(seen[0][1]['propagationPolicy'],'Foreground')
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__ == '__main__':
    unittest.main()
