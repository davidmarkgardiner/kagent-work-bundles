import base64
import copy
import json
import io
import sys
from types import SimpleNamespace, ModuleType
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest

from lab_adapter import LabAdapter, Blocked, Uncertain, digest, POD_CODE


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.policy={'apiVersion':'kyverno.io/v1','kind':'Policy','metadata':{'name':'policy','namespace':'demo'},'spec':{'rules':[{'validate':{'pattern':{'spec':{'containers':[{'image':'docker.io/library/*'}]}}}}]}}
        faulty=copy.deepcopy(self.policy); faulty['spec']['rules'][0]['validate']['pattern']['spec']['containers'][0]['image']='docker.io/libary/*'
        self.base={'run_id':'ready','incident_id':'ready-incident','profile_revision':'0'*64,'namespace':'demo','project_id':'123','target_branch':'dashboard','fix_branch':'unused','investigator_id':'kagent/specialist','reviewer_id':'kagent/reviewer','policy_file':'deploy/policy.json','application':'application','policy_name':'policy','rule_name':'rule','gitlab_api':'https://example.invalid/api/v4','healthy_policy_sha256':digest(self.policy),'faulty_policy_sha256':digest(faulty),'healthy_policy_spec_sha256':digest(self.policy['spec']),'faulty_policy_spec_sha256':digest(faulty['spec']),'expected_body_sha256':'f'*64}
        (self.root/'base.json').write_text(json.dumps(self.base))
        (self.root/'ssh.json').write_text(json.dumps(['ssh','fixed-host']))
        (self.root/'token').write_text('secret-never-output')
        self.settings={'base_config_file':str(self.root/'base.json'),'ssh_argv_file':str(self.root/'ssh.json'),'gitlab_token_file':str(self.root/'token'),'project_id':'123','namespace':'demo','target_branch':'dashboard','kubeconfig':'/private/kubeconfig','native_cli':'/private/native','grpcurl':'/private/grpcurl','proto_dir':'/private/proto','native_address':'127.0.0.1:9999','human_merger_ids':[7],'specialist_agent':'specialist','reviewer_agent':'reviewer'}
        self.adapter=LabAdapter(self.settings,sleep=lambda _:None)
        self.run={'runId':'run-1','workspace':str(self.root/'run-1'),'_call':{'intentId':'intent-1','mode':'execute'}}

    def native_continuation_fixture(self):
        self.run['data']={'adapter':{'rollout_sha':'a'*40}}
        self.adapter._once(self.run,'triage-session',lambda:{'session':{'id':'original-session'}})
        self.adapter._once(self.run,'native-dispatch',lambda:{'state':'accepted','task_id':'original-task'})
        status={'new':'TASK_STATE_WORKING','proposal':False,'ci':False,'credential':True,'get_failure':False}
        calls=[]
        def rpc(agent,method,body,**kwargs):
            calls.append((method,body,kwargs))
            if method=='SendMessage':
                return {'task':{'id':'continued-task','contextId':'original-session','status':{'state':'TASK_STATE_WORKING'}}}
            if body['id']=='continued-task' and status['get_failure']:
                status['get_failure']=False;raise Uncertain('Readback unavailable')
            return {'id':body['id'],'contextId':'original-session','status':{'state':'TASK_STATE_COMPLETED' if body['id']=='original-task' else status['new']}}
        def pod(run,action,value=None):
            if action=='repository':
                if not status['credential']:raise Blocked('Repository unauthorized')
                return {'project_id':'123','target_branch':'dashboard','head_sha':'a'*40,'known_faulty_file':True}
            if action=='read':return {'state':{'proposal':{'url':'https://gitlab.com/p/-/merge_requests/1'} if status['proposal'] else None}}
            if action=='inspect':return {'binding':{'head_sha':'b'*40},'diff_valid':True,'ci_pass':status['ci']}
            raise AssertionError(action)
        self.adapter._rpc=rpc;self.adapter._pod=pod
        return status,calls

    def test_native_office_origin_and_partition_reach_rpc_session_and_pod_dispatch(self):
        settings=dict(self.settings,native_controller_origin='https://native.office.example.invalid',native_user='office-agent@example.invalid')
        adapter=LabAdapter(settings);calls=[]
        adapter._remote=lambda args,body=None,timeout=120:calls.append((args,body)) or {'session':{'id':'actual-session'}}
        adapter._session(self.run,'triage',False)
        adapter._rpc('specialist','GetTask',{'id':'task'})
        self.assertIn('office-agent@example.invalid',calls[0][0])
        self.assertIn('x-user-id: office-agent@example.invalid',calls[1][0])
        payloads=[];adapter._kubectl=lambda args,body=None,timeout=120:payloads.append(body) or {'ok':True}
        adapter._pod(self.run,'dispatch',{'session_id':'actual-session','native_user':'untrusted-value'})
        self.assertEqual(payloads[0]['native_controller_origin'],'https://native.office.example.invalid')
        self.assertEqual(payloads[0]['native_user'],'office-agent@example.invalid')
        for bad in ['line\nbreak','wrong/partition','']:
            with self.subTest(user=bad),self.assertRaises(ValueError):
                LabAdapter(dict(settings,native_user=bad))

    def test_remote_initial_dispatch_uses_operator_origin_and_user(self):
        from runtime import ready, observed_generation, policy_read_metadata
        cfg=SimpleNamespace(identity='config',run_id='run');captured={}
        class Ledger:
            def __init__(self,*args):pass
            def close(self):pass
        class Admission:
            def __init__(self,*args):pass
            def dispatch(self,callback):return {'state':'accepted'}
        modules={name:ModuleType(name) for name in ('core','runtime','admission','gitlab_lifecycle','native_dispatch')}
        modules['core'].Config=SimpleNamespace(from_dict=lambda _:cfg);modules['core'].Ledger=Ledger
        modules['core'].digest=digest;modules['core'].POLICY_OBSERVATION_METHOD='method'
        modules['runtime'].Runtime=lambda *a,**kw:None;modules['runtime'].ready=ready
        modules['runtime'].observed_generation=observed_generation;modules['runtime'].policy_read_metadata=policy_read_metadata
        modules['admission'].Admission=Admission;modules['gitlab_lifecycle'].Lifecycle=lambda *a:None
        modules['native_dispatch'].DEFAULT_ORIGIN='https://wrong-default.invalid'
        modules['native_dispatch'].DEFAULT_USER='wrong-default'
        def native(*args,**kwargs):captured.update(kwargs);return object()
        modules['native_dispatch'].NativeDispatch=native
        payload={'action':'dispatch','config_identity':'config','human_merger_ids':[7],
                 'native_controller_origin':'https://native.office.example.invalid','native_user':'office@example.invalid',
                 'value':{'session_id':'actual-session','native_user':'attacker','origin':'https://attacker.invalid'}}
        output=io.StringIO()
        with patch.dict(sys.modules,modules),patch.object(sys,'stdin',io.StringIO(json.dumps(payload))),patch.object(sys,'stdout',output),patch.object(sys,'path',list(sys.path)),patch.object(Path,'read_text',return_value='{}'):
            exec(POD_CODE,{})
        self.assertEqual(json.loads(output.getvalue()),{'state':'accepted'})
        self.assertEqual(captured['origin'],'https://native.office.example.invalid')
        self.assertEqual(captured['user'],'office@example.invalid')

    def test_native_continuation_sends_once_preserves_original_and_waits_for_ci(self):
        status,calls=self.native_continuation_fixture()
        original=(self.root/'run-1/native-dispatch.json').read_bytes()
        self.run['_traceparent']='00-'+'a'*32+'-'+'b'*16+'-01'
        first=self.adapter.advance(self.run,'triage_continuation')
        self.assertEqual(first['status'],'pending');self.assertEqual(first['patch']['native']['taskId'],'continued-task')
        self.assertEqual(first['patch']['adapter']['task_id'],'continued-task')
        self.run['_call']['mode']='observe';status.update(proposal=True,new='TASK_STATE_COMPLETED')
        self.assertEqual(self.adapter.advance(self.run,'triage_continuation')['phase'],'waiting_ci')
        status['ci']=True
        result=self.adapter.advance(self.run,'triage_continuation')
        self.assertEqual(result['status'],'completed');self.assertEqual(result['events'][0]['stage'],'triage_continuation')
        sends=[c for c in calls if c[0]=='SendMessage'];self.assertEqual(len(sends),1)
        self.assertEqual(sends[0][1]['message']['contextId'],'original-session')
        self.assertIn('propose_policy_fix once',sends[0][1]['message']['parts'][0]['text'])
        self.assertEqual(sends[0][2]['traceparent'],self.run['_traceparent'])
        self.assertTrue(all(not c[2] for c in calls if c[0]=='GetTask'))
        self.assertEqual((self.root/'run-1/native-dispatch.json').read_bytes(),original)
        receipt=json.loads((self.root/'run-1/operator-triage-continuation.json').read_text())
        self.assertEqual(receipt['original_task_id'],'original-task')
        self.assertEqual(receipt['task_id'],'continued-task')

    def test_native_continuation_rejects_unrepaired_credentials_before_send(self):
        status,calls=self.native_continuation_fixture();status['credential']=False
        self.assertEqual(self.adapter.advance(self.run,'triage_continuation')['status'],'blocked')
        self.assertFalse(any(c[0]=='SendMessage' for c in calls))
        self.assertFalse((self.root/'run-1/triage-continuation-send.json').exists())

    def test_native_continuation_unknown_send_is_spent_and_never_resent(self):
        _,calls=self.native_continuation_fixture();old=self.adapter._rpc
        def rpc(agent,method,body,**kwargs):
            if method=='SendMessage':calls.append((method,body,kwargs));raise Uncertain('Uncertain send')
            return old(agent,method,body,**kwargs)
        self.adapter._rpc=rpc
        self.assertEqual(self.adapter.advance(self.run,'triage_continuation')['status'],'unknown')
        self.run['_call']['mode']='observe'
        self.assertEqual(self.adapter.advance(self.run,'triage_continuation')['status'],'unknown')
        self.assertEqual(len([c for c in calls if c[0]=='SendMessage']),1)

    def test_accepted_continuation_readback_failure_uses_same_task_without_resend(self):
        status,calls=self.native_continuation_fixture();status['get_failure']=True
        self.assertEqual(self.adapter.advance(self.run,'triage_continuation')['status'],'pending')
        self.run['_call']['mode']='observe'
        result=self.adapter.advance(self.run,'triage_continuation')
        self.assertEqual(result['status'],'pending');self.assertEqual(result['patch']['native']['taskId'],'continued-task')
        self.assertEqual(len([c for c in calls if c[0]=='SendMessage']),1)

    def test_completed_continuation_without_proposal_preserves_actual_completed_state(self):
        status,_=self.native_continuation_fixture();status['new']='TASK_STATE_COMPLETED'
        result=self.adapter.advance(self.run,'triage_continuation')
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['patch']['native']['state'],'TASK_STATE_COMPLETED')

    def test_dynamic_configuration_persists_only_reviewed_identity_changes(self):
        config=self.adapter._config(self.run)
        changed={k for k in self.base if config[k]!=self.base[k]}
        self.assertEqual(changed,{'run_id','incident_id','fix_branch','profile_revision'})
        self.assertEqual(config['fix_branch'],'repair/run-1')
        self.assertEqual(json.loads((self.root/'run-1/runtime-config.json').read_text()),config)
        second=dict(self.run,runId='run-2',workspace=str(self.root/'run-2'))
        self.assertNotEqual(config['profile_revision'],self.adapter._config(second)['profile_revision'])
        self.assertEqual(self.adapter._config(self.run),config)

    def test_execution_capacity_keeps_merge_and_verification_minimums_read_only(self):
        state={'enabled':True,'available':True,'requestsRemaining':2,'inputBytesRemaining':4000,'boundRunId':'current-run'}
        self.adapter.budget_state=lambda:dict(state)
        merge=self.adapter.execution_budget('merge')
        self.assertFalse(merge['ready']);self.assertEqual(merge['required'],4)
        self.assertEqual(merge['remaining'],2);self.assertEqual(merge['boundRunId'],'current-run')
        self.assertTrue(self.adapter.execution_budget('verify')['ready'])
        state['requestsRemaining']=4;self.assertTrue(self.adapter.execution_budget('merge')['ready'])
        for patch in ({'available':False},{'requestsRemaining':None},{'inputBytesRemaining':0},{'enabled':False}):
            saved=dict(state);state.update(patch)
            self.assertFalse(self.adapter.execution_budget('merge')['ready'])
            state.clear();state.update(saved)
        self.assertEqual(state['requestsRemaining'],4)

    def test_budget_health_is_cached_read_only_and_bounded(self):
        now = [100]
        self.adapter.clock = lambda: now[0]
        calls = []
        def kubectl(args, body=None, timeout=120):
            calls.append((args, body, timeout))
            return {'requests_remaining': 4, 'input_bytes_remaining': 10000, 'private': 'secret'}
        self.adapter._kubectl = kubectl
        first = self.adapter.budget_state()
        self.assertTrue(first['available'])
        self.assertEqual(first['requestsRemaining'], 4)
        first['requestsRemaining'] = 99
        self.assertEqual(self.adapter.budget_state()['requestsRemaining'], 4)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0][:4], ['exec', '-i', 'deploy/kyverno-runtime', '--'])
        self.assertIsNone(calls[0][1])
        self.assertIn("health_origin.rstrip('/')+'/healthz'", calls[0][0][-1])
        self.assertNotIn('token', calls[0][0][-1])
        now[0] += 5
        self.adapter.budget_state()
        self.assertEqual(len(calls), 2)
        self.adapter.budget_state(force=True)
        self.assertEqual(len(calls), 3)

    def test_exhausted_or_unavailable_budget_prevents_configuration_issue_and_fault(self):
        for health in ({'requests_remaining': 0, 'input_bytes_remaining': 100},
                       {'requests_remaining': 2, 'input_bytes_remaining': 0},
                       {'requests_remaining': '2', 'input_bytes_remaining': 100},
                       {'requests_remaining': 33, 'input_bytes_remaining': 100}, None):
            with self.subTest(health=health):
                calls = []
                def kubectl(args, body=None, timeout=120):
                    calls.append(args)
                    if health is None:
                        raise TimeoutError('private endpoint')
                    return health
                self.adapter._kubectl = kubectl
                self.adapter._pod = lambda *a, **k: self.fail('No runtime/issue mutation')
                self.adapter._gl = lambda *a, **k: self.fail('No repository/fault mutation')
                result = self.adapter.advance(self.run, 'prepare')
                self.assertEqual(result['status'], 'blocked')
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][0], 'exec')
                self.assertFalse((self.root/'run-1/runtime-configuration.json').exists())
                self.assertFalse((self.root/'run-1/runtime-config.json').exists())

    def test_classifier_and_triage_dispatch_receive_actual_caller_context(self):
        carrier = '00-' + 'a'*32 + '-' + 'b'*16 + '-01'
        self.run['_traceparent'] = carrier
        calls = []
        def pod(run, action, value=None):
            calls.append((action, value))
            if action == 'read':
                return {'state': {'candidate_id': 'actual-candidate'}, 'admission': {'classifications': []}}
            if action == 'classify':
                return {'state': 'accepted', 'classification': {'result': {'choice': 'investigate', 'severity': 'critical', 'confidence': .98}}}
            return {'state': 'accepted', 'task_id': 'actual-task'}
        self.adapter._pod = pod
        self.assertEqual(self.adapter.advance(self.run, 'classify')['status'], 'completed')
        self.assertEqual(calls[-1][1]['traceparent'], carrier)
        self.adapter._session = lambda *a: 'actual-session'
        self.adapter._rpc = lambda *a: {'id': 'actual-task', 'contextId': 'actual-session', 'status': {'state': 'TASK_STATE_WORKING'}}
        self.assertEqual(self.adapter.advance(self.run, 'dispatch')['status'], 'completed')
        self.assertEqual(calls[-1], ('dispatch', {'session_id': 'actual-session', 'traceparent': carrier}))

    def test_native_roles_propagate_on_original_send_only_never_task_polls(self):
        carrier = '00-' + 'a'*32 + '-' + 'b'*16 + '-01'
        self.run['_traceparent'] = carrier
        self.adapter._session = lambda *a: 'actual-session'
        for role in ('review', 'merge', 'verify'):
            calls = []
            def rpc(agent, method, body, **kwargs):
                calls.append((method, kwargs))
                task = {'id': role+'-task', 'contextId': 'actual-session', 'status': {'state': 'TASK_STATE_WORKING'}}
                return {'task': task} if method == 'SendMessage' else task
            self.adapter._rpc = rpc
            self.adapter._task(self.run, role, False, 'private prompt')
            self.adapter._task(self.run, role, True, 'private prompt')
            self.assertEqual(calls, [('SendMessage', {'traceparent': carrier}), ('GetTask', {}), ('GetTask', {})])

    def test_rpc_only_adds_traceparent_header_to_send_message(self):
        carrier = '00-' + 'a'*32 + '-' + 'b'*16 + '-01'
        calls = []
        self.adapter._remote = lambda args, *a: calls.append(args)
        self.adapter._rpc('reviewer', 'SendMessage', {}, traceparent=carrier)
        self.assertIn('traceparent: '+carrier, calls[-1])
        self.adapter._rpc('reviewer', 'GetTask', {}, traceparent=carrier)
        self.assertNotIn('traceparent: '+carrier, calls[-1])
        with self.assertRaises(Blocked):
            self.adapter._rpc('reviewer', 'SendMessage', {}, traceparent='invalid')

    def test_trusted_scope_cannot_be_overridden_by_request(self):
        self.run['namespace']='victim';self.run['project_id']='999';self.run['config']={'target_branch':'main'}
        self.assertEqual(self.adapter._config(self.run)['namespace'],'demo')
        settings=dict(self.settings,namespace='victim')
        with self.assertRaises(ValueError):LabAdapter(settings)

    def test_uncertain_write_is_never_repeated(self):
        calls=[]
        def failed(): calls.append('post');raise TimeoutError()
        with self.assertRaises(TimeoutError):self.adapter._once(self.run,'write',failed)
        for observe in (True,False):
            with self.assertRaises(Uncertain):self.adapter._once(self.run,'write',failed,observe)
        self.assertEqual(calls,['post'])

    def test_completed_write_reuses_receipt_and_observe_never_starts_write(self):
        calls=[]
        with self.assertRaises(Uncertain):self.adapter._once(self.run,'new',lambda:calls.append(1),True)
        self.adapter._once(self.run,'done',lambda:{'id':'actual'})
        self.assertEqual(self.adapter._once(self.run,'done',lambda:calls.append(2),True),{'id':'actual'})
        self.assertEqual(calls,[])

    def test_observe_native_missing_session_never_creates_or_sends(self):
        calls=[];self.adapter._remote=lambda *a,**k:calls.append(a)
        self.run['_call']['mode']='observe'
        result=self.adapter.advance(self.run,'dispatch')
        self.assertEqual(result['status'],'unknown');self.assertEqual(calls,[])

    def test_observe_merge_reads_actual_dashboard_approved_agent_receipt(self):
        calls=[]
        def pod(run,action,value=None):
            calls.append(action)
            return {'state':'reconciling','merge_sha':'a'*40,'actor_id':7,'approval_id':'approved'}
        self.adapter._pod=pod;self.run['_call']['mode']='observe'
        result=self.adapter.advance(self.run,'observe_merge')
        self.assertEqual(calls,['dashboard_merge']);self.assertEqual(result['patch']['merge'],{'sha':'a'*40,'mergedBy':7,'status':'merged','approvalId':'approved'})

    def test_waiting_human_is_pending_not_unknown(self):
        self.adapter._pod=lambda *a,**k:{'state':{}}
        self.run['_call']['mode']='observe'
        result=self.adapter.advance(self.run,'await_approval')
        self.assertEqual(result['status'],'pending');self.assertEqual(result['phase'],'waiting_human')

    def test_native_merge_never_starts_without_dashboard_approval(self):
        self.adapter._pod=lambda *a,**k:{'state':{}}
        self.adapter._task=lambda *a,**k:self.fail('No native send without human approval')
        self.assertEqual(self.adapter.advance(self.run,'merge')['status'],'blocked')

    def test_approved_native_merge_requires_actual_completed_tool_response(self):
        self.adapter._pod=lambda *a,**k:{'state':{'flow_dashboard_approval':{'approval_id':'approved'},'proposal':{'binding':{'head_sha':'b'*40}}}}
        task={'id':'merge-task','contextId':'merge-session','status':{'state':'TASK_STATE_COMPLETED'},
              'artifacts':[{'parts':[{'text':'Merged successfully'}]}]}
        self.adapter._task=lambda *a,**k:task
        self.assertEqual(self.adapter.advance(self.run,'merge')['status'],'blocked')
        task['artifacts'][0]['parts'].append({'metadata':{'kagent.dev/a2a/part-type':'function_response'},
            'data':{'id':'actual-call','name':'merge_dashboard_approved_fix','response':{'output':json.dumps({'state':'reconciling','merge_sha':'a'*40,'approval_id':'approved','binding':{'head_sha':'b'*40}})}}})
        result=self.adapter.advance(self.run,'merge')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['patch']['merge']['taskId'],'merge-task')

    def test_approval_binds_displayed_head_and_uses_only_trusted_principal(self):
        self.adapter.clock=lambda:1000
        binding={'head_sha':'a'*40};calls=[]
        def pod(run,action,value=None):
            calls.append((action,value))
            return {'state':{'proposal':{'binding':binding}}} if action=='read' else value
        self.adapter._pod=pod
        value=self.adapter.approve(self.run,'approval-request','a'*40)
        self.assertEqual(value['approvedBy'],7)
        self.assertEqual(value['headSha'],'a'*40)
        self.assertEqual(calls[-1][1],{'approval_id':'approval-request','binding':binding,'principal_id':7,'approved_at':1000,'expires_at':1900})

    def test_approval_observation_never_records_missing_grant(self):
        from flow_controller import ApprovalUnknown
        calls=[]
        def pod(run,action,value=None):
            calls.append(action);return {'state':{}}
        self.adapter._pod=pod
        with self.assertRaises(ApprovalUnknown):self.adapter.approve(self.run,'request','a'*40,observe=True)
        self.assertEqual(calls,['read'])

    def test_uncertain_completed_native_merge_moves_to_original_intent_readback(self):
        calls=[]
        def pod(run,action,value=None):
            calls.append(action)
            return {'state':{'flow_dashboard_approval':{'approval_id':'approved'}}} if action=='read' else {'state':'unknown','operation':'flow-dashboard-merge'}
        self.adapter._pod=pod
        self.adapter._task=lambda *a,**k:{'id':'actual-task','contextId':'actual-session','status':{'state':'TASK_STATE_COMPLETED'},
            'artifacts':[{'parts':[{'metadata':{'kagent.dev/a2a/part-type':'function_response'},'data':{
                'id':'actual-tool-call','name':'merge_dashboard_approved_fix','response':{'output':json.dumps({'state':'unknown','operation':'flow-dashboard-merge'})}}}]}]}
        result=self.adapter.advance(self.run,'merge')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['patch']['merge']['status'],'readback_pending')
        self.assertEqual(calls,['read','dashboard_merge'])

    def test_terminal_triage_without_proposal_stops(self):
        self.adapter._task=lambda *a,**k:{'id':'task','status':{'state':'TASK_STATE_COMPLETED'}}
        self.adapter._pod=lambda *a,**k:{'state':{}}
        self.assertEqual(self.adapter.advance(self.run,'triage')['status'],'blocked')

    def test_fault_measurement_waits_for_current_rollout_and_accepted_denial(self):
        from admission import Admission
        from core import Ledger
        from test_runtime import config, observation
        cfg=config(); now=[1700000200]; expected='a'*40
        ledger=Ledger(self.root/'admission.sqlite',cfg.identity)
        self.addCleanup(ledger.close)
        admission=Admission(cfg,ledger,now=lambda:now[0])
        self.run['data']={'adapter':{'rollout_sha':expected}}
        sleeps=[];collected=[]
        def sleep(seconds):
            sleeps.append(seconds);now[0]+=seconds
        def collect(run,kind):
            index=len(collected)
            packet=observation(cfg,index,when=now[0],native=False)
            if index==0:
                packet['policy']['policy_revision']='d'*40
            if index<2:
                packet['rollout'].update(available_replicas=1,updated_replicas=1)
            value={'policy_revision':packet['policy']['policy_revision'],'packet':packet}
            collected.append(value)
            return value
        def pod(run,action,value=None):
            self.assertEqual(action,'observe')
            return [admission.observe(item['packet']) for item in value]
        self.adapter.sleep=sleep;self.adapter._collect=collect;self.adapter._pod=pod
        result=self.adapter.advance(self.run,'observe_fault')
        self.assertEqual(result['status'],'completed')
        candidate=admission.candidate(result['patch']['adapter']['candidate_id']).packet
        observations=candidate['observations']
        self.assertEqual([p['probe']['probe_id'] for p in observations],['probe-2','probe-3','probe-4'])
        self.assertEqual(observations[-1]['probe']['observed_at']-observations[0]['probe']['observed_at'],62)
        self.assertEqual(sleeps,[3,3,31,31])
        self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM observations').fetchone()[0],3)
        self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM classifications').fetchone()[0],0)
        self.assertIsNone(admission.state()['outbox'])
        self.assertEqual(json.loads((self.root/'run-1/fault-readiness-0.json').read_text()),collected[0])
        self.assertEqual(json.loads((self.root/'run-1/fault-probe-0.json').read_text()),collected[2])

    def recheck_fixture(self):
        from admission import Admission
        from core import Config,Ledger
        from test_runtime import config,observation
        from dataclasses import asdict,replace
        cfg=replace(config(),run_id=self.run['runId']);now=[1700000200]
        self.adapter._config=lambda run:asdict(cfg)
        ledger=Ledger(self.root/'recheck.sqlite',cfg.identity);self.addCleanup(ledger.close)
        admission=Admission(cfg,ledger,now=lambda:now[0]);self.run['data']={'adapter':{'rollout_sha':'a'*40}}
        self.adapter.clock=lambda:now[0]
        self.adapter.sleep=lambda seconds:now.__setitem__(0,now[0]+seconds)
        collected=[]
        def collect(run,kind):
            packet=observation(cfg,len(collected),when=now[0],native=False)
            value={'policy_revision':'a'*40,'packet':packet};collected.append(value);return value
        def pod(run,action,value=None):
            if action=='observe':return [admission.observe(v['packet']) for v in value]
            if action=='candidate':return admission.candidate(value['candidate_id']).packet
            self.fail('No unrelated runtime action '+action)
        self.adapter._collect=collect;self.adapter._pod=pod
        return cfg,now,ledger,admission,collected

    def test_same_incident_recheck_measures_own_window_preserving_failed_window(self):
        from test_runtime import observation
        cfg,now,ledger,admission,collected=self.recheck_fixture()
        self.adapter._once(self.run,'fault-window',lambda:{'receipts':[],'admission':{'state':'observing'}})
        original=(self.root/'run-1/fault-window.json').read_bytes()
        for index,seconds in [(90,62),(91,31)]:admission.observe(observation(cfg,index,when=now[0]-seconds,native=False))
        result=self.adapter.advance(self.run,'recheck_fault')
        self.assertEqual(result['status'],'completed',result)
        candidate=admission.candidate(result['patch']['adapter']['candidate_id']).packet
        self.assertEqual([p['probe']['probe_id'] for p in candidate['observations']],['probe-0','probe-1','probe-2'])
        self.assertEqual(candidate['observations'][-1]['probe']['observed_at']-candidate['observations'][0]['probe']['observed_at'],62)
        self.assertEqual((self.root/'run-1/fault-window.json').read_bytes(),original)
        self.assertEqual(len(collected),3)
        self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM classifications').fetchone()[0],0)
        self.assertIsNone(admission.state()['outbox'])
        self.adapter._collect=lambda *args:self.fail('Readback cannot open another physical window')
        self.run['_call']['mode']='observe'
        self.assertEqual(self.adapter.advance(self.run,'recheck_fault')['status'],'completed')

    def test_interrupted_recheck_cannot_use_latest_mixed_candidate_or_remeasure(self):
        cfg,now,ledger,admission,collected=self.recheck_fixture()
        from test_runtime import observation
        for index,seconds in [(90,62),(91,31)]:admission.observe(observation(cfg,index,when=now[0]-seconds,native=False))
        admission.observe(observation(cfg,0,when=now[0],native=False))
        self.assertIsNotNone(admission.state()['state'].get('candidate_id'))
        self.adapter._workspace(self.run)
        path=self.root/'run-1/fault-recheck-window.json'
        path.write_text(json.dumps({'state':'unknown','intentId':'recorded'}))
        before=path.read_bytes();self.run['_call']['mode']='observe'
        self.adapter._collect=lambda *args:self.fail('Interrupted observation cannot be remeasured')
        self.adapter._pod=lambda *args:self.fail('Latest candidate is not completed recheck proof')
        self.assertEqual(self.adapter.advance(self.run,'recheck_fault')['status'],'unknown')
        self.assertEqual(path.read_bytes(),before)

    def test_completed_recheck_rejects_candidate_without_its_three_receipts(self):
        cfg,now,ledger,admission,collected=self.recheck_fixture()
        result=self.adapter.advance(self.run,'recheck_fault');self.assertEqual(result['status'],'completed',result)
        path=self.root/'run-1/fault-recheck-window.json';saved=json.loads(path.read_text())
        saved['result']['receipts'][0]['packet']['probe']['probe_id']='other-fresh-probe'
        path.write_text(json.dumps(saved));self.run['_call']['mode']='observe'
        self.adapter._collect=lambda *args:self.fail('Mismatched receipt cannot be resampled')
        self.assertEqual(self.adapter.advance(self.run,'recheck_fault')['status'],'unknown')

    def classification_followup_fixture(self,confidence=.97):
        cfg,now,ledger,admission,collected=self.recheck_fixture()
        from test_runtime import observation,classification
        for index,offset in [(90,132),(91,101),(92,70)]:admission.observe(observation(cfg,index,when=now[0]-offset,native=False))
        original=admission.state()['state']['candidate_id']
        first=admission.classify(original,lambda packet,limits:classification(packet,limits,confidence=.93,request_id='original-request'))
        self.run['data']['adapter']['candidate_id']=original
        self.adapter._once(self.run,'classification',lambda:first)
        original_pod=self.adapter._pod;calls=[]
        def pod(run,action,value=None):
            if action=='read':
                return {'state':ledger.state(),'admission':admission.state(),
                    'classification_envelopes':{r['candidate_id']:json.loads(r['value']) for r in ledger.db.execute('SELECT candidate_id,value FROM classifications WHERE value IS NOT NULL')}}
            if action=='classify':
                calls.append(value)
                return admission.classify(value['candidate_id'],lambda packet,limits:classification(packet,limits,confidence=confidence,request_id='fresh-request'))
            return original_pod(run,action,value)
        self.adapter._pod=pod
        return now,ledger,admission,collected,calls,original

    def test_followup_collects_new_actual_candidate_preserving_original_call_and_own_receipts(self):
        now,ledger,admission,collected,calls,original=self.classification_followup_fixture()
        path=self.root/'run-1/classification.json';before=path.read_bytes()
        self.run['_traceparent']='00-'+'d'*32+'-'+'e'*16+'-01'
        result=self.adapter.advance(self.run,'classification_followup')
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(result['patch']['classifier']['attempts'],2)
        candidate=result['patch']['adapter']['candidate_id'];self.assertNotEqual(candidate,original)
        self.assertEqual(calls[0]['candidate_id'],candidate)
        self.assertEqual(calls[0]['traceparent'],self.run['_traceparent'])
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(len(collected),3);self.assertEqual(admission.state()['classifier_requests_reserved'],2)
        self.assertIsNone(admission.state()['outbox'])
        self.adapter._collect=lambda *args:self.fail('Completed followup cannot sample another window')
        self.run['_call']['mode']='observe'
        self.assertEqual(self.adapter.advance(self.run,'classification_followup')['status'],'completed')
        self.assertEqual(len(calls),1)

    def test_followup_below_threshold_remains_suppressed_without_native_dispatch(self):
        now,ledger,admission,collected,calls,original=self.classification_followup_fixture(.93)
        result=self.adapter.advance(self.run,'classification_followup')
        self.assertEqual(result['status'],'suppressed',result)
        self.assertEqual(result['patch']['classifier']['confidence'],.93)
        self.assertEqual(result['patch']['classifier']['threshold'],.95)
        self.assertIsNone(admission.state()['outbox']);self.assertEqual(len(calls),1)

    def test_interrupted_followup_window_or_paid_receipt_never_resamples_or_resends(self):
        now,ledger,admission,collected,calls,original=self.classification_followup_fixture()
        self.adapter._workspace(self.run)
        path=self.root/'run-1/classification-followup-window.json'
        path.write_text(json.dumps({'state':'unknown','intentId':'original'}))
        self.run['_call']['mode']='observe';self.adapter._collect=lambda *args:self.fail('No fresh physical window')
        self.assertEqual(self.adapter.advance(self.run,'classification_followup')['status'],'unknown')
        self.assertEqual(calls,[])

    def test_unknown_followup_paid_receipt_stays_unknown_even_if_runtime_has_result(self):
        now,ledger,admission,collected,calls,original=self.classification_followup_fixture()
        self.assertEqual(self.adapter.advance(self.run,'classification_followup')['status'],'completed')
        path=self.root/'run-1/classification-followup.json'
        path.write_text(json.dumps({'state':'unknown','intentId':'paid-original'}));before=path.read_bytes()
        self.run['_call']['mode']='observe';self.adapter._collect=lambda *args:self.fail('No remeasurement')
        result=self.adapter.advance(self.run,'classification_followup')
        self.assertEqual(result['status'],'unknown');self.assertEqual(len(calls),1)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(admission.state()['classifications'][-1]['status'],'accepted')

    def test_trusted_model_origin_controls_health_and_classifier_only(self):
        target='http://approved-budget.demo.svc.cluster.local:8082'
        adapter=LabAdapter(dict(self.settings,model_origin=target))
        calls=[]
        adapter._kubectl=lambda args,**kwargs:calls.append(args) or {'requests_remaining':16,'input_bytes_remaining':524288}
        self.assertTrue(adapter.budget_state(force=True)['available'])
        self.assertEqual(calls[0][-1],target)
        pods=[]
        def pod(run,action,value=None):
            pods.append((action,value))
            if action=='read':return {'state':{'candidate_id':'candidate'},'admission':{'classifications':[]}}
            return {'state':'accepted','classification':{'result':{'choice':'investigate','severity':'critical','confidence':.97}}}
        adapter._pod=pod
        self.assertEqual(adapter.advance(self.run,'classify')['status'],'completed')
        self.assertEqual(pods[-1][1]['model_origin'],target)
        with self.assertRaises(ValueError):LabAdapter(dict(self.settings,model_origin='https://evil.invalid/private'))

    def test_run_bound_allowance_rejects_other_prepare_before_any_mutation(self):
        bound='demo-'+'a'*32
        adapter=LabAdapter(dict(self.settings,model_allowance_run_id=bound))
        calls=[]
        adapter._kubectl=lambda args,**kwargs:calls.append(args) or {'requests_remaining':16,'input_bytes_remaining':10000}
        self.assertEqual(adapter.budget_state(force=True)['boundRunId'],bound)
        calls.clear()
        adapter._pod=lambda *args:self.fail('Another incident cannot create an issue')
        adapter._gl=lambda *args:self.fail('Another incident cannot inject a fault')
        result=adapter.advance(self.run,'prepare')
        self.assertEqual(result['status'],'blocked');self.assertEqual(calls,[])
        self.assertIn('reserved for the existing incident',result['events'][0]['message'])
        self.assertFalse((self.root/'run-1/runtime-configuration.json').exists())
        with self.assertRaises(ValueError):LabAdapter(dict(self.settings,model_allowance_run_id='run-arbitrary'))

    def test_fault_window_requires_exact_revision_and_never_counts_suppressed_probe(self):
        self.run['data']={'adapter':{'rollout_sha':'a'*40}}
        self.adapter._collect=lambda *a,**k: {'policy_revision':'b'*40,'packet':{'policy':{'policy_revision':'b'*40}}}
        self.adapter._pod=lambda *a,**k: self.fail('Wrong revision cannot be admitted')
        result=self.adapter.advance(self.run,'observe_fault')
        self.assertEqual(result['status'],'blocked')
        self.assertFalse((self.root/'run-1/fault-probe-0.json').exists())
        self.assertTrue((self.root/'run-1/fault-readiness-29.json').exists())
        self.adapter._collect=lambda *a,**k: self.fail('Completed or uncertain physical window is not automatically replayed')
        self.assertEqual(self.adapter.advance(self.run,'observe_fault')['status'],'unknown')
        self.assertEqual(json.loads((self.root/'run-1/fault-window.json').read_text())['state'],'unknown')

    def test_completed_failed_fault_window_remains_stopped_after_upgrade(self):
        original={'receipts':[{'actual':'old-receipt'}],'admission':{'state':'observing'}}
        self.adapter._once(self.run,'fault-window',lambda:original)
        before=(self.root/'run-1/fault-window.json').read_bytes()
        self.adapter._collect=lambda *a,**k: self.fail('No automatic replacement window')
        self.adapter._pod=lambda *a,**k: self.fail('No implicit classification/readback')
        self.assertEqual(self.adapter.advance(self.run,'observe_fault')['status'],'blocked')
        self.assertEqual((self.root/'run-1/fault-window.json').read_bytes(),before)

    def test_interrupted_fault_window_stops_without_an_automatic_replay(self):
        self.run['_call']['mode']='observe'
        self.adapter._pod=lambda *a,**k:{'state':{}}
        self.adapter._collect=lambda *a,**k:self.fail('No probe replay')
        self.assertEqual(self.adapter.advance(self.run,'observe_fault')['status'],'unknown')

    def test_transient_triage_read_failure_keeps_observing_original_task(self):
        self.adapter._task=lambda *a,**k:(_ for _ in ()).throw(Uncertain('read failed'))
        self.assertEqual(self.adapter.advance(self.run,'triage')['status'],'pending')

    def test_closed_ticket_proof_uses_independent_actual_issue(self):
        self.adapter._task=lambda *a,**k:{'id':'task','status':{'state':'TASK_STATE_COMPLETED'}}
        self.adapter._pod=lambda *a,**k:{'verified':True,'task_id':'task','task_state':'TASK_STATE_COMPLETED','evidence_digest':'a'*64}
        self.run['data']={'ticket':{'iid':7,'state':'closed'}}
        self.adapter._gl=lambda path:{'iid':7,'state':'opened'}
        self.assertFalse(self.adapter.closure_verifier(self.run)['issue_closed'])
        self.adapter._gl=lambda path:{'iid':7,'state':'closed'}
        proof=self.adapter.closure_verifier(self.run)
        self.assertTrue(proof['issue_closed']);self.assertEqual(proof['issue_iid'],7)

    def test_actual_task_identity_fields_are_used(self):
        sid='actual-session';tid='actual-native-task'
        self.adapter._once(self.run,'triage-session',lambda:{'session':{'id':sid}})
        self.adapter._once(self.run,'native-dispatch',lambda:{'state':'accepted','task_id':tid})
        calls=[]
        def rpc(agent,method,body):
            calls.append((agent,method,body));return {'id':tid,'contextId':sid,'status':{'state':'TASK_STATE_WORKING'}}
        self.adapter._rpc=rpc
        self.run['_call']['mode']='observe'
        result=self.adapter.advance(self.run,'dispatch')
        self.assertEqual(result['patch']['native']['taskId'],tid)
        self.assertEqual(calls[0][1],'GetTask')
        self.assertEqual(calls[0][2]['id'],tid)

    def test_explicit_continuation_preserves_original_and_reads_actual_followup(self):
        self.adapter._once(self.run,'triage-session',lambda:{'session':{'id':'session'}})
        self.adapter._once(self.run,'native-dispatch',lambda:{'state':'accepted','task_id':'original'})
        path=self.root/'run-1/operator-triage-continuation.json'
        path.write_text(json.dumps({'original_task_id':'original','task_id':'followup','session_id':'session','send_receipt_sha256':'a'*64}))
        calls=[]
        def rpc(agent,method,body):
            calls.append((method,body))
            return {'id':'followup','contextId':'session','status':{'state':'TASK_STATE_COMPLETED'}}
        self.adapter._rpc=rpc
        self.assertEqual(self.adapter._task(self.run,'triage',True)['id'],'followup')
        self.assertEqual(calls,[('GetTask',{'id':'followup','historyLength':40})])
        self.assertEqual(json.loads((self.root/'run-1/native-dispatch.json').read_text())['result']['task_id'],'original')
        path.write_text(json.dumps({'original_task_id':'different','task_id':'followup','session_id':'session','send_receipt_sha256':'a'*64}))
        with self.assertRaises(Blocked):
            self.adapter._task(self.run,'triage',True)

    def test_changed_native_identity_blocks(self):
        self.adapter._once(self.run,'triage-session',lambda:{'session':{'id':'actual-session'}})
        self.adapter._once(self.run,'native-dispatch',lambda:{'state':'accepted','task_id':'original-task'})
        self.adapter._rpc=lambda *a,**k:{'id':'other-task','contextId':'actual-session','status':{'state':'TASK_STATE_COMPLETED'}}
        self.assertEqual(self.adapter.advance(self.run,'dispatch')['status'],'blocked')

    def test_real_classifier_fields_are_preserved_on_observe(self):
        snapshot={'state':{'candidate_id':'candidate'},'admission':{'classifications':[{'candidate_id':'candidate','status':'accepted'}]},'classification_envelopes':{'candidate':{'request_id':'actual-request','result':{'choice':'investigate','severity':'critical','confidence':0.97}}}}
        calls=[]
        def pod(run,action,value=None): calls.append(action);return snapshot
        self.adapter._pod=pod;self.run['_call']['mode']='observe'
        result=self.adapter.advance(self.run,'classify')
        self.assertEqual(result['status'],'completed');self.assertEqual(result['patch']['classifier']['confidence'],0.97)
        self.assertEqual(calls,['read'])

    def test_review_requires_structured_exact_head_binding(self):
        binding={'iid':2,'head_sha':'a'*40}
        value={'verdict':'PASS','binding':binding,'ci':{'pipeline_sha':'a'*40,'pipeline_status':'success'}}
        task={'artifacts':[{'parts':[{'text':json.dumps(value)}]}]}
        self.assertEqual(LabAdapter._review_verdict(task,binding),value)
        task['artifacts'][0]['parts'][0]['text']='PASS looks fine'
        with self.assertRaises(Blocked):LabAdapter._review_verdict(task,binding)

    def test_native_verification_cannot_start_before_recovery_window(self):
        self.adapter._pod=lambda *a,**k:{'state':{'merged':{'merge_sha':'a'*40}}}
        self.adapter._task=lambda *a,**k:self.fail('Native model must not start')
        self.assertEqual(self.adapter.advance(self.run,'verify')['status'],'blocked')

    def test_recovery_receipt_maps_real_probe_fields_into_both_contracts(self):
        now=[1000];counter=[0];recorded=[]
        self.adapter.clock=lambda:now[0]
        self.adapter.sleep=lambda duration:now.__setitem__(0,now[0]+duration)
        policy=copy.deepcopy(self.policy);policy['metadata'].update(uid='policy-uid',generation=2)
        metadata={'uid':'policy-uid','generation':2,'policy_spec_sha256':self.base['healthy_policy_spec_sha256'],'ready':True,'deleting':False,'enforcement':'Enforce','observed_at':1000}
        state={'merged':{'merge_sha':'a'*40,'observed_at':999},'flow_baseline':{'policy_uid':'policy-uid','deployment_uid':'deployment-uid'}}
        def pod(run,action,value=None):
            if action=='window':recorded.append(value);return {'state':'recorded'}
            if action=='recovery_window':return {'recorded':False}
            self.assertEqual(action,'http');counter[0]+=1
            return {'policy':policy,'state':state,'deployment':{'uid':'deployment-uid','available_replicas':1},'http':{'probe_id':'http-'+str(counter[0]),'observed_at':now[0],'status_code':200,'body_sha256':'f'*64}}
        def collect(run,kind):
            counter[0]+=1
            before=dict(metadata,observed_at=now[0])
            return {'probe_id':kind+'-'+str(counter[0]),'observed_at':now[0],'kind':kind,'result':'admitted' if kind=='valid' else 'denied','policy_revision':'a'*40,'policy_read_before':before,'policy_read_after':before,'native_observed_generation':None}
        self.adapter._pod=pod;self.adapter._collect=collect
        result=self.adapter.advance(self.run,'measure_recovery')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(len(recorded),1)
        receipt=recorded[0]['receipt'];window=recorded[0]['window']
        self.assertEqual(receipt['observation_method'],'stable-read-and-admission-probes')
        self.assertEqual(len(receipt['observations']),6)
        self.assertTrue(all(p['policy_name']=='policy' and p['rule_name']=='rule' for p in receipt['observations']))
        self.assertEqual(window['ended_at']-window['started_at'],62)
        self.assertEqual(len(window['observations']),3)
        self.assertEqual(window['deployment_uid'],'deployment-uid')

    def test_observe_recovery_does_not_issue_server_dry_run_or_http_window(self):
        self.adapter._pod=lambda run,action,value=None:{'state':{}}
        self.adapter._collect=lambda *a,**k:self.fail('Observe must not issue server-dry-run POST')
        self.run['_call']['mode']='observe'
        self.assertEqual(self.adapter.advance(self.run,'measure_recovery')['status'],'unknown')

    def test_validated_existing_window_is_reused_in_execute_and_observe_modes(self):
        calls=[]
        def pod(run,action,value=None):
            calls.append(action);self.assertEqual(action,'recovery_window');return {'recorded':True}
        self.adapter._pod=pod
        self.adapter._collect=lambda *a,**k:self.fail('No resampling an immutable window')
        self.adapter._task=lambda *a,**k:self.fail('No native task in measurement')
        for mode in ('execute','observe'):
            self.run['_call']['mode']=mode
            self.assertEqual(self.adapter.advance(self.run,'measure_recovery')['status'],'completed')
        self.assertEqual(calls,['recovery_window','recovery_window'])
        self.assertFalse((self.root/'run-1/measured-recovery-window.json').exists())

    def test_seven_minute_readiness_delay_does_not_reserve_or_replay_measurement(self):
        now=[1000];ready=[False];calls=[]
        self.adapter.clock=lambda:now[0]
        def pod(run,action,value=None):
            calls.append(action);self.assertEqual(action,'recovery_ready')
            return {'ready':ready[0],'reasons':[] if ready[0] else ['GitOps is reconciling']}
        self.adapter._pod=pod
        self.adapter._collect=lambda *a,**k:self.fail('No admission probes before readiness')
        self.adapter._task=lambda *a,**k:self.fail('No native task before readiness')
        for i in range(15):
            self.run['_call']['mode']='execute' if i==0 else 'observe'
            result=self.adapter.advance(self.run,'await_recovery')
            self.assertEqual((result['status'],result['phase']),('pending','reconciling'))
            now[0]+=30
        self.assertGreaterEqual(now[0]-1000,420)
        self.assertFalse((self.root/'run-1/measured-recovery-window.json').exists())
        self.assertFalse((self.root/'run-1/recovery-window.json').exists())
        ready[0]=True
        self.assertEqual(self.adapter.advance(self.run,'await_recovery')['status'],'completed')
        self.assertEqual(calls,['recovery_ready']*16)

    def test_remote_readiness_checks_actual_revisions_uids_rollout_and_http(self):
        from runtime import ready, observed_generation, policy_read_metadata
        cfg=SimpleNamespace(identity='config',run_id='run',target_branch='dashboard',flux_namespace='flux',
            flux_source='source',flux_kustomization='kust',healthy_policy_spec_sha256=digest(self.policy['spec']),
            expected_http_status=200,expected_body_sha256='f'*64)
        state={'merged':{'merge_sha':'a'*40},'flow_baseline':{'policy_uid':'policy-uid','deployment_uid':'deployment-uid'}}
        source={'metadata':{'generation':2},'status':{'observedGeneration':2,'artifact':{'revision':'dashboard@sha1:'+'a'*40},'conditions':[{'type':'Ready','status':'True'}]}}
        flux={'metadata':{'generation':3},'status':{'observedGeneration':3,'lastAppliedRevision':'dashboard@sha1:'+'a'*40,'conditions':[{'type':'Ready','status':'True'}]}}
        policy=copy.deepcopy(self.policy);policy['metadata']['uid']='policy-uid';policy['status']={'conditions':[{'type':'Ready','status':'True'}]}
        deployment={'uid':'deployment-uid','generation':4,'observed_generation':4,'desired_replicas':1,'actual_replicas':1,
            'updated_replicas':1,'ready_replicas':1,'available_replicas':1,'unavailable_replicas':0,'deleting':False}
        http={'status_code':200,'body_sha256':'f'*64}
        class Ledger:
            def __init__(self,*args):pass
            def state(self):return state
            def close(self):pass
        class Runtime:
            def __init__(self,*args,**kwargs):pass
            def _kube(self,path):return source if '/gitrepositories/' in path else flux
            def _policy(self):return policy
            def _deployment(self):return deployment
            def _http_probe(self):return http
        modules={}
        for name in ('core','runtime','admission','gitlab_lifecycle'):modules[name]=ModuleType(name)
        modules['core'].Config=SimpleNamespace(from_dict=lambda _:cfg);modules['core'].Ledger=Ledger
        modules['core'].digest=digest;modules['core'].POLICY_OBSERVATION_METHOD='method'
        modules['runtime'].Runtime=Runtime;modules['runtime'].ready=ready
        modules['runtime'].observed_generation=observed_generation;modules['runtime'].policy_read_metadata=policy_read_metadata
        modules['admission'].Admission=lambda *args:None;modules['gitlab_lifecycle'].Lifecycle=lambda *args:None
        def execute():
            output=io.StringIO();payload={'action':'recovery_ready','config_identity':'config','human_merger_ids':[7]}
            with patch.dict(sys.modules,modules),patch.object(sys,'stdin',io.StringIO(json.dumps(payload))),patch.object(sys,'stdout',output),patch.object(sys,'path',list(sys.path)),patch.object(Path,'read_text',return_value='{}'):
                exec(POD_CODE,{})
            return json.loads(output.getvalue())
        self.assertEqual(execute(),{'ready':True,'reasons':[]})
        source['status']['artifact']['revision']='dashboard@sha1:'+'b'*40
        self.assertFalse(execute()['ready'])
        source['status']['artifact']['revision']='dashboard@sha1:'+'a'*40
        deployment['available_replicas']=0
        self.assertFalse(execute()['ready'])
        deployment['available_replicas']=1;http['status_code']=503
        self.assertFalse(execute()['ready'])
        http['status_code']=200;policy['metadata']['uid']='different'
        self.assertFalse(execute()['ready'])

    def test_closure_requires_actual_terminal_native_task(self):
        self.adapter._task=lambda *a,**k:{'id':'actual','status':{'state':'TASK_STATE_WORKING'}}
        self.adapter._pod=lambda *a,**k:self.fail('Unfinished task must not verify')
        self.assertFalse(self.adapter.closure_verifier(self.run)['verified'])

    def test_fault_policy_precedes_active_readback_then_rollout_commit(self):
        events=[];head=['a'*40];files={'deploy/policy.json':copy.deepcopy(self.policy),'deploy/application.json':{'kind':'Deployment','metadata':{'namespace':'demo','name':'application'},'spec':{'template':{}}}}
        def gl(path,method='GET',body=None):
            if method=='POST':
                actions=body['actions'];events.append(('commit',actions[0]['file_path']))
                self.assertEqual(len(actions),1)
                old=head[0];head[0]=('b' if len([x for x in events if x[0]=='commit'])==1 else 'c')*40
                for action in actions:files[action['file_path']]=json.loads(action['content'])
                return {'id':head[0],'parent_ids':[old]}
            if '/repository/branches/' in path:return {'commit':{'id':head[0]}}
            if '/repository/files/' in path:
                name='deploy/policy.json' if 'policy.json' in path else 'deploy/application.json'
                return {'content':base64.b64encode(json.dumps(files[name]).encode()).decode(),'last_commit_id':head[0]}
            self.fail(path)
        def pod(run,action,value=None):
            events.append(('read','policy-active'))
            self.assertEqual(head[0],'b'*40)
            return {'policy':files['deploy/policy.json']}
        self.adapter._gl=gl;self.adapter._pod=pod
        result=self.adapter.advance(self.run,'inject_fault')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(events,[('commit','deploy/policy.json'),('read','policy-active'),('commit','deploy/application.json')])
        self.assertEqual(result['patch']['adapter']['rollout_sha'],'c'*40)

    def test_fault_rollout_is_not_sent_when_policy_not_active(self):
        self.adapter._once(self.run,'fault-commit',lambda:{'id':'b'*40})
        self.adapter._pod=lambda *a,**k:{'policy':self.policy}
        calls=[];self.adapter._gl=lambda *a,**k:calls.append(a)
        self.run['_call']['mode']='observe'
        result=self.adapter.advance(self.run,'inject_fault')
        self.assertEqual(result['status'],'pending');self.assertEqual(calls,[])

    def test_transport_errors_do_not_leak_secrets(self):
        def pod(*a,**k):raise RuntimeError('secret-never-output')
        self.adapter._pod=pod
        result=self.adapter.advance(self.run,'classify')
        self.assertNotIn('secret-never-output',json.dumps(result))
        self.assertEqual(result['status'],'unknown')


if __name__=='__main__':unittest.main()
