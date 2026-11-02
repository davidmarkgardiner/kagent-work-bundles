import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid
from http.server import ThreadingHTTPServer

from flow_server import make_handler
from flow_controller import ApprovalConflict, ApprovalUnknown, ResumeConflict


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.starts, self.approvals, self.approval_failure = [], [], None
        test = self
        class Controller:
            def public_state(self):
                return {'enabled': True, 'phase': 'ready'}
            def start(self, request):
                test.starts.append(request)
                return self.public_state()
            def approve(self, request, run_id, head_sha):
                if test.approval_failure:
                    raise test.approval_failure
                test.approvals.append((request, run_id, head_sha))
                return self.public_state()
            def trace_context(self):
                return None
        self.temp = tempfile.TemporaryDirectory()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(
            Controller(), Path(self.temp.name), 'http://127.0.0.1:1', 'placeholder', 'nonce'))
        self.port = self.server.server_port
        self.authority = '127.0.0.1:' + str(self.port)
        self.controller = Controller()
        self.server.RequestHandlerClass = make_handler(self.controller, Path(self.temp.name),
            'http://127.0.0.1:1', self.authority, 'nonce')
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path='/api/demo/start', headers=None, body=None, method='POST'):
        default = {'Host': self.authority, 'Origin': 'http://' + self.authority,
                   'Content-Type': 'application/json', 'X-Demo-CSRF': 'nonce'}
        default.update(headers or {})
        connection = http.client.HTTPConnection('127.0.0.1', self.port)
        connection.request(method, path, body or '{"requestId":"' + str(uuid.uuid4()) + '"}', default)
        response = connection.getresponse()
        status, raw = response.status, response.read()
        connection.close()
        return status, raw

    def test_start_and_no_merge_endpoint(self):
        self.assertEqual(self.request()[0], 202)
        self.assertEqual(self.request('/api/demo/merge')[0], 404)
        self.assertEqual(len(self.starts), 1)

    def test_cross_origin_and_rebinding_never_start(self):
        for headers in ({'Origin': 'https://other.invalid'}, {'Host': 'other.invalid'}, {'X-Demo-CSRF': ''}):
            self.assertEqual(self.request(headers=headers)[0], 403)
        self.assertEqual(self.starts, [])

    def test_only_canonical_uuid_and_bounded_json(self):
        for body in ('{}', '[]', '{"requestId":"bad"}', 'x' * 1025):
            self.assertEqual(self.request(body=body)[0], 400)
        self.assertEqual(self.starts, [])

    def test_state_keeps_controller_visible_when_receiver_disconnects(self):
        status, raw = self.request('/api/state', method='GET')
        self.assertEqual(status, 200)
        self.assertIn(b'"csrf": "nonce"', raw)
        self.assertIn(b'"receiverConnected": false', raw)

    def test_gitlab_link_origin_is_pinned_to_operator_configuration(self):
        class Adapter:
            base = {'gitlab_api':'https://gitlab.office.example.invalid:8443/api/v4'}
        self.controller.adapter = Adapter()
        self.controller.public_state = lambda: {'enabled':True,'phase':'ready','gitlabOrigin':'https://unrelated.invalid'}
        self.server.RequestHandlerClass = make_handler(self.controller, Path(self.temp.name),
            'http://127.0.0.1:1', self.authority, 'nonce')
        self.controller.adapter.base = {'gitlab_api':'https://later-change.invalid/api/v4'}
        status, raw = self.request('/api/state',method='GET')
        self.assertEqual(status,200)
        self.assertEqual(json.loads(raw)['demo']['gitlabOrigin'],'https://gitlab.office.example.invalid:8443')
        self.assertEqual(self.starts,[])

    def test_invalid_operator_gitlab_authorities_are_rejected(self):
        class Adapter:
            base = {}
        self.controller.adapter = Adapter()
        for api in ['http://gitlab.office.invalid/api/v4','https://user:secret@gitlab.office.invalid/api/v4',
                    'https://gitlab.office.invalid:invalid/api/v4','https://gitlab.office.invalid:0/api/v4',
                    'https://gitlab.office.invalid\\path/api/v4','https://gitlab.office.invalid/\x01api/v4',
                    'https://@gitlab.office.invalid/api/v4']:
            with self.subTest(api=api),self.assertRaises(ValueError):
                self.controller.adapter.base = {'gitlab_api':api}
                make_handler(self.controller, Path(self.temp.name),'http://127.0.0.1:1',self.authority,'nonce')

    def approval_body(self, **patch):
        return json.dumps({'requestId':str(uuid.uuid4()), 'runId':'demo-owned', 'headSha':'a'*40, **patch})

    def test_exact_approval_payload_is_forwarded_without_a_merge_endpoint(self):
        body = self.approval_body()
        self.assertEqual(self.request('/api/demo/approve', body=body)[0], 202)
        parsed = json.loads(body)
        self.assertEqual(self.approvals, [(parsed['requestId'], parsed['runId'], parsed['headSha'])])
        self.assertEqual(self.starts, [])
        self.assertEqual(self.request('/api/demo/merge')[0], 404)

    def test_approval_requires_same_origin_host_and_csrf(self):
        for headers in ({'Origin':'https://other.invalid'}, {'Host':'other.invalid'}, {'X-Demo-CSRF':''}):
            self.assertEqual(self.request('/api/demo/approve', headers=headers, body=self.approval_body())[0], 403)
        self.assertEqual(self.approvals, [])

    def test_approval_rejects_caller_principal_extra_fields_and_bad_uuid(self):
        invalid = [self.approval_body(principalId=9), self.approval_body(expiresAt=9999999999),
                   self.approval_body(requestId='bad'), json.dumps({'requestId':str(uuid.uuid4())}), '[]', 'x'*1025]
        for body in invalid:
            self.assertEqual(self.request('/api/demo/approve', body=body)[0], 400)
        self.assertEqual(self.approvals, [])

    def test_approval_conflict_and_uncertain_outcome_are_distinct(self):
        self.approval_failure = ApprovalConflict('private checks')
        status, raw = self.request('/api/demo/approve', body=self.approval_body())
        self.assertEqual(status, 409)
        self.assertNotIn(b'private checks', raw)
        self.approval_failure = ApprovalUnknown('private response')
        status, raw = self.request('/api/demo/approve', body=self.approval_body())
        self.assertEqual(status, 502)
        self.assertNotIn(b'private response', raw)

    def test_exhausted_budget_blocks_start_before_controller(self):
        class Adapter:
            def budget_state(self):
                return {'enabled':True,'available':True,'requestsRemaining':0,'inputBytesRemaining':100,'reason':'Existing budget exhausted.'}
        self.controller.adapter = Adapter()
        self.assertEqual(self.request()[0],409)
        self.assertEqual(self.starts,[])
        self.controller.public_state = lambda: {'phase':'closed','actions':{'start':{'enabled':True}}}
        status, raw = self.request('/api/state',method='GET')
        state = json.loads(raw)
        self.assertFalse(state['demo']['actions']['start']['enabled'])
        self.assertEqual(state['demo']['budget']['requestsRemaining'],0)

    def test_unavailable_budget_blocks_start_but_not_human_approval(self):
        class Adapter:
            def budget_state(self):
                raise OSError('private health response')
        self.controller.adapter = Adapter()
        status, raw = self.request()
        self.assertEqual(status,409)
        self.assertNotIn(b'private health',raw)
        self.assertEqual(self.request('/api/demo/approve',body=self.approval_body())[0],202)

    def test_state_strict_task_join_and_bounded_cached_log_arrival(self):
        trace = 'a'*32
        span = {'traceId':trace,'spanId':'b'*16,'startNs':'1','endNs':'2','receivedAt':1,
                'component':'kagent','attributes':{'a2a.task.id':'wrong-task','gen_ai.conversation.id':'session'}}
        state = {'revision':1,'traces':[{'traceId':trace,'spans':[span],'components':['kagent'],'edges':[]}],
                 'nativeActivities':{'native':{'actorName':'session-session','requestTraceId':trace}}}
        self.controller.public_state = lambda: {'runId':'demo-1','phase':'triaging','native':{'taskId':'task'},
                                                'actions':{'start':{'enabled':False}}}
        self.controller.evidence_context = lambda: {'runId':'demo-1','tasks':{'triage':{'taskId':'task','sessionId':'session'}}}
        calls = []
        def upstream(handler,path):
            calls.append(path)
            if path == '/api/state':
                return json.loads(json.dumps(state))
            return {'logs':[{'id':'log-id','timestampNs':'2','attributes':{},'service':'kagent'}]}
        self.server.RequestHandlerClass.upstream_json = upstream
        status, raw = self.request('/api/state',method='GET')
        value = json.loads(raw)
        self.assertEqual(status,200)
        self.assertIsNone(value['demo']['native']['traceId'])
        self.assertEqual(value['demo']['flow']['scope']['traceIds'],[])
        span['attributes']['a2a.task.id'] = 'task'
        state['revision'] = 2
        status, raw = self.request('/api/state',method='GET')
        self.assertEqual(json.loads(raw)['demo']['native']['traceId'],trace)
        self.request('/api/state',method='GET')
        self.assertEqual(calls.count('/api/logs'),2)

    def test_legacy_log_first_viewer_arrival_survives_cache_refresh(self):
        state = {'revision':1,'traces':[]}
        log = {'id':'owned-log','timestampNs':str(1000*10**9),'traceId':'','spanId':'',
               'service':'kyverno-demo-controller','attributes':{'flow.run.id':'demo-1',
               'flow.workflow':'kyverno-demo.observe_fault','flow.result':'pending'}}
        self.controller.public_state = lambda: {'runId':'demo-1','phase':'observing'}
        def upstream(handler,path):
            return dict(state) if path == '/api/state' else {'logs':[dict(log)]}
        self.server.RequestHandlerClass.upstream_json = upstream
        with patch('flow_server.time.time',return_value=1000):
            _, raw = self.request('/api/state',method='GET')
        first = json.loads(raw)['demo']['flow']['observations'][0]
        self.assertEqual(first['viewerReceivedAt'],1000)
        self.assertIsNone(first['receivedAt'])
        self.assertTrue(first['recent'])
        state['revision'] = 2
        with patch('flow_server.time.time',return_value=1001):
            _, raw = self.request('/api/state',method='GET')
        second = json.loads(raw)['demo']['flow']['observations'][0]
        self.assertEqual(second['viewerReceivedAt'],first['viewerReceivedAt'])
        self.assertEqual(second['receiptSource'],'viewer')

    def configure_resume(self):
        from types import SimpleNamespace
        calls=[];health=[];remaining=[16]
        def budget_state(force=False):
            health.append(force)
            return {'enabled':True,'available':remaining[0]>0,'requestsRemaining':remaining[0],'inputBytesRemaining':10000,'reason':'Original allowance exhausted.' if not remaining[0] else None}
        self.controller.adapter=SimpleNamespace(budget_state=budget_state)
        self.controller.public_state=lambda:{'runId':'demo-'+'a'*32,'phase':'blocked','running':False,
             'actions':{'start':{'enabled':False,'reason':'This incident is stopped.'},'resume':{'enabled':True}}}
        self.controller.resume_readback=lambda request,run:None
        self.controller.resume_fault=lambda request,run:calls.append((request,run)) or self.controller.public_state()
        return calls,health,remaining

    def test_resume_exact_payload_and_existing_origin_guards(self):
        calls,health,remaining=self.configure_resume()
        request=str(uuid.uuid4());run='demo-'+'a'*32;body=json.dumps({'requestId':request,'runId':run})
        status,raw=self.request('/api/demo/resume',body=body)
        self.assertEqual(status,202);self.assertEqual(calls,[(request,run)]);self.assertEqual(health,[True])
        for bad in ({'requestId':request},{'requestId':request,'runId':run,'command':'reset'},
                    {'requestId':request.upper(),'runId':run}):
            self.assertEqual(self.request('/api/demo/resume',body=json.dumps(bad))[0],400)
        for headers in ({'Origin':'https://other.invalid'},{'Host':'other.invalid'},{'X-Demo-CSRF':''}):
            self.assertEqual(self.request('/api/demo/resume',headers=headers,body=body)[0],403)
        self.assertEqual(len(calls),1)
        self.controller.resume_fault=lambda *args:(_ for _ in ()).throw(ResumeConflict('Incident state changed'))
        self.assertEqual(self.request('/api/demo/resume',body=body)[0],409)

    def test_stopped_budget_is_visible_and_blocks_fresh_resume_without_mutation(self):
        calls,health,remaining=self.configure_resume();remaining[0]=0
        body=json.dumps({'requestId':str(uuid.uuid4()),'runId':'demo-'+'a'*32})
        status,raw=self.request('/api/demo/resume',body=body)
        self.assertEqual(status,409);self.assertEqual(calls,[]);self.assertEqual(health,[True])
        self.server.RequestHandlerClass.upstream_json=lambda handler,path:{'logs':[]} if path=='/api/logs' else {'revision':1,'traces':[]}
        status,raw=self.request('/api/state',method='GET');demo=json.loads(raw)['demo']
        self.assertEqual(demo['budget']['requestsRemaining'],0)
        self.assertFalse(demo['actions']['resume']['enabled'])
        self.assertIn('exhausted',demo['actions']['start']['reason'])
        self.assertIn('exhausted',demo['actions']['resume']['reason'])
        self.assertFalse(demo['running'])

    def test_remaining_bound_allowance_cannot_start_another_demo(self):
        calls,health,remaining=self.configure_resume();read=self.controller.adapter.budget_state
        bound='demo-'+'a'*32
        self.controller.adapter.budget_state=lambda force=False:dict(read(force),boundRunId=bound)
        self.controller.public_state=lambda:{'runId':bound,'phase':'closed','running':False,
            'actions':{'start':{'enabled':True},'resume':{'enabled':False}}}
        self.server.RequestHandlerClass.upstream_json=lambda handler,path:{'logs':[]} if path=='/api/logs' else {'revision':1,'traces':[]}
        status,raw=self.request('/api/state',method='GET');demo=json.loads(raw)['demo']
        self.assertEqual(demo['budget']['requestsRemaining'],16)
        self.assertFalse(demo['actions']['start']['enabled'])
        self.assertIn('reserved for the existing incident',demo['actions']['start']['reason'])
        self.assertEqual(self.request('/api/demo/start')[0],409);self.assertEqual(self.starts,[])
        wrong=json.dumps({'requestId':str(uuid.uuid4()),'runId':'demo-'+'e'*32})
        self.assertEqual(self.request('/api/demo/resume',body=wrong)[0],409);self.assertEqual(calls,[])
        matching=json.dumps({'requestId':str(uuid.uuid4()),'runId':bound})
        self.assertEqual(self.request('/api/demo/resume',body=matching)[0],202)
        self.assertEqual(len(calls),1)

    def test_accepted_resume_reads_back_even_after_allowance_is_spent(self):
        calls,health,remaining=self.configure_resume();remaining[0]=0
        self.controller.resume_readback=lambda request,run:{'runId':run,'phase':'classifying','running':True}
        body=json.dumps({'requestId':str(uuid.uuid4()),'runId':'demo-'+'a'*32})
        status,raw=self.request('/api/demo/resume',body=body)
        self.assertEqual(status,202);self.assertEqual(json.loads(raw)['demo']['phase'],'classifying')
        self.assertEqual(calls,[]);self.assertEqual(health,[])

    def test_no_generic_api_proxy(self):
        self.assertEqual(self.request('/api/invoke')[0], 404)
        self.assertEqual(self.request('/api/admin', method='GET')[0], 404)
        self.assertEqual(self.starts, [])


if __name__ == '__main__':
    unittest.main()
