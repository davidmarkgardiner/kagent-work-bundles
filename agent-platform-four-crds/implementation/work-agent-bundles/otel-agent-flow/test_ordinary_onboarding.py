import copy
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from onboarding import canonical,publish
from onboarding_ordinary import ROLES,CAPABILITY,ReviewedPlan,pin,capability_projection,observe,read_view

NOW=1792668000


def fixture():
    objects={role:{'apiVersion':api,'kind':kind,'metadata':{'name':role.lower(),'namespace':'demo','uid':role+'-uid','generation':1},'spec':{},'status':{'conditions':[{'type':name,'status':'True','observedGeneration':1} for name in ('Ready','Accepted')]}} for role,(api,kind,_) in ROLES.items()}
    profile={'runtimeProfile':'ordinary-v1','modelProfile':'approved-v1','modelConfig':{'name':'model','specSha256':canonical({})}}
    hosted=objects['hosted'];hosted['spec']={'runtimeProfile':'ordinary-v1','modelProfile':'approved-v1','toolGrantRefs':[]};hosted['status']['bindings']=[]
    for role,field in [('skill','skillRefs'),('knowledge','knowledgeBaseRefs')]:
        release,source,cm=(objects[k] for k in (role,role+'Source',role+'ConfigMap'))
        source['spec']={'ref':{'commit':'a'*40}};source['status']['artifact']={'revision':'sha1:'+'a'*40}
        release['spec']={'sourceRef':{'name':source['metadata']['name']},'sourceCommit':'a'*40,'contentSha256':'b'*64}
        release['status'].update(observedSourceRevision='sha1:'+'a'*40,contentSha256='b'*64,configMapRef={'name':cm['metadata']['name']})
        cm.update(immutable=True,data={'file00':'NEVER-EXPORT-DOCUMENT-BODY'});cm['metadata']['ownerReferences']=[{'uid':release['metadata']['uid']}]
        hosted['spec'][field]=[{'name':release['metadata']['name'],'sourceCommit':'a'*40,'contentSha256':'b'*64}]
        hosted['status']['bindings'].append({'kind':release['kind'],'configMapUID':cm['metadata']['uid'],'sourceUID':source['metadata']['uid'],'contentSha256':'b'*64,'sourceSpecSha256':canonical(source['spec'])})
    for role in ('mcpCode','mcpData','telemetry'):
        objects[role].update(data={'fixture':'DO-NOT-EXPORT'},immutable=True)
    objects['mcpRole']['rules']=[{'verbs':['get'],'resources':['configmaps'],'resourceNames':['mcpdata']}]
    objects['mcpBinding'].update(roleRef={'kind':'Role','name':'mcprole'},subjects=[{'kind':'ServiceAccount','name':'mcpaccount'}])
    objects['mcpAccount']['automountServiceAccountToken']=True
    objects['mcpServer']['status']['discoveredTools']=[{'name':'get_demo_status'}]
    objects['mcpBackend']['status'].update(observedGeneration=1,availableReplicas=1,updatedReplicas=1)
    pins=[{'role':role,'name':objects[target]['metadata']['name'],'kind':objects[target]['kind'],'uid':objects[target]['metadata']['uid'],'sha256':canonical(capability_projection(objects[target]))} for role,target in CAPABILITY.items()]
    profile['approvedMcp']={'toolName':'get_demo_status','pins':pins}
    hosted['status'].update(mcpProfileSha256=canonical(profile),mcpDependencyPinsSha256=canonical(pins),agentRef={'name':'agent'})
    objects['agent']['metadata']['ownerReferences']=[{'uid':hosted['metadata']['uid'],'controller':True}]
    objects['account']['automountServiceAccountToken']=False
    objects['agent']['spec']={'declarative':{'modelConfig':'model','deployment':{'serviceAccountName':'account'}}}
    hosted['status']['agentSpecSha256']=canonical(objects['agent']['spec'])
    objects['profile']['data']={'profile.json':json.dumps(profile)}
    objects['declarations']['spec']={'ref':{'commit':'c'*40}};objects['declarations']['status']['artifact']={'revision':'sha1:'+'c'*40};objects['flux']['status']['lastAppliedRevision']='sha1:'+'c'*40
    refs=[{'role':role,'apiVersion':obj['apiVersion'],'kind':obj['kind'],'namespace':'demo','name':obj['metadata']['name'],'uid':obj['metadata']['uid'],'bodySha256':pin(obj)['bodySha256']} for role,obj in objects.items()]
    plan=ReviewedPlan.parse({'schemaVersion':2,'namespace':'demo','agentName':'agent','hostedName':'hosted','profileSha256':canonical(profile),'objects':refs})
    return plan,objects


class OrdinaryObserverTests(unittest.TestCase):
    def setUp(self):self.plan,self.objects=fixture()
    def reader(self,ref):return copy.deepcopy(self.objects[ref['role']])
    def test_two_pass_named_reads_publish_only_metadata(self):
        calls=[]
        def reader(ref):calls.append(ref['role']);return self.reader(ref)
        value=observe(self.plan,reader,NOW)
        self.assertEqual(len(calls),48)
        self.assertTrue(all(s['state']=='ready' for s in value['stages']))
        self.assertNotIn('NEVER-EXPORT',json.dumps(value));self.assertNotIn('DO-NOT-EXPORT',json.dumps(value))
    def test_permission_read_failure_immediately_replaces_ready_state(self):
        first=observe(self.plan,self.reader,NOW)
        def denied(ref):
            if ref['role']=='mcpRole':raise urllib.error.HTTPError('fixed',403,'Denied',{},None)
            return self.reader(ref)
        value=observe(self.plan,denied,NOW+1,first)
        self.assertEqual(value['sampleErrors']['mcpRole'],'ReadDenied')
        self.assertNotEqual(next(x for x in value['stages'] if x['key']=='tools')['state'],'ready')
    def test_role_authority_and_replacement_are_pinned(self):
        self.objects['mcpRole']['rules'][0]['verbs'].append('delete')
        value=observe(self.plan,self.reader,NOW)
        self.assertEqual(value['sampleErrors']['mcpRole'],'PinMismatch')
        self.objects['mcpRole']['metadata']['uid']='replacement'
        self.assertEqual(observe(self.plan,self.reader,NOW)['sampleErrors']['mcpRole'],'UIDChanged')
    def test_expiry_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json';publish(path,observe(self.plan,self.reader,NOW))
            self.assertEqual(read_view(path,NOW+1)['freshness'],'current')
            expired=read_view(path,NOW+16)
            self.assertEqual(expired['freshness'],'expired');self.assertTrue(all(s['state']=='unknown' for s in expired['stages']))
    def test_secret_and_cross_namespace_references_cannot_enter_the_plan(self):
        for field,value in [('kind','Secret'),('namespace','other')]:
            changed=copy.deepcopy(self.plan.value);changed['objects'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):ReviewedPlan.parse(changed)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        from onboarding_ordinary import validate_receipt
        self.validate=validate_receipt
        plan,objects=fixture()
        self.record={'schemaVersion':2,'source':'operator-supplied-runner-receipt','recordedAt':NOW,
            'scenarioName':'combined','agentName':'agent','namespace':'demo',
            'agentSpecSha256':canonical(objects['agent']['spec']),'sessionId':'session','taskId':'task',
            'result':'passed','profileSha256':plan.value['profileSha256'],
            'pins':{k:pin(v) for k,v in objects.items()},'observations':[
                {'callId':str(i),'toolName':name,'category':category,'resultSha256':'a'*64,
                 **({'executionId':'e'*32} if category=='mcp' else {})}
                for i,(name,category) in enumerate([('skills','skill'),('read_file','skill'),
                    ('read_file','knowledge'),('get_demo_status','mcp')])]}

    def test_missing_or_mislabelled_proof_is_rejected(self):
        self.validate(self.record)
        variants=[]
        for index in range(4):
            changed=copy.deepcopy(self.record);changed['observations'].pop(index);variants.append(changed)
        changed=copy.deepcopy(self.record);changed['observations'][-1].pop('executionId');variants.append(changed)
        changed=copy.deepcopy(self.record);changed['observations'][0]['executionId']='e'*32;variants.append(changed)
        changed=copy.deepcopy(self.record);changed['observations'][-1]['toolName']='delete_configmap';variants.append(changed)
        for changed in variants:
            with self.subTest(observations=changed['observations']),self.assertRaises(ValueError):self.validate(changed)

class OrdinaryUiTests(unittest.TestCase):
    def test_independent_backend_is_joined_only_by_an_applicable_receipt_and_exact_execution(self):
        import time
        from test_ui import UiBehaviorTests,ui_span,ui_trace,TRACE,BACKGROUND
        plan,objects=fixture();proof=ReceiptTests();proof.setUp();record=proof.record
        now=time.time();record['recordedAt']=now-1
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'view.json';publish(path,observe(plan,lambda ref:copy.deepcopy(objects[ref['role']]),now,receipt=record));view=read_view(path,now)
        spans=[]
        for n,(name,category) in enumerate([('skills','skill'),('read_file','skill'),('read_file','skill'),('get_demo_status','mcp')]):
            span=ui_span(n+1,name,category,'native-skill' if category=='skill' else '',service='agent')
            span['attributes'].update({'service.name':'agent','service.namespace':'demo','gen_ai.conversation.id':'session','gen_ai.task.id':'task','gen_ai.tool.call.id':str(n)})
            spans.append(span)
        native=ui_trace(spans=spans);native['nativeRuntimeIdentity']={'runtime':'adk-python','agentName':'agent','agentId':'demo/agent'};native['executionMode']='ordinary'
        backend=ui_span(99,'get_demo_status','mcp','server','onboarding-status-mcp')
        backend.update(traceId=BACKGROUND,kind='server',component='mcp',otelStatus='ok')
        backend['attributes'].update({'flow.evidence.source':'mcp-handler','flow.execution.id':'e'*32,'mcp.tool.name':'get_demo_status'})
        root=ui_trace(BACKGROUND,False,[backend]);root.update(components=['mcp'],edges=[])
        state={'revision':1,'traces':[root,native],'onboarding':view,'invocation':{'status':'idle'},'sessionActivity':None,'nativeActivities':{},'runtime':{'readOnlyViewer':True,'ordinaryObservationOnly':True,'executionTargets':[],'substrateInstalled':False,'demoMode':'connected','label':'Ordinary viewer'}}
        UiBehaviorTests().run_ui(state,r'''
          setView('onboarding');render();
          assert.equal(receiptBackendSpans().length,1);
          assert.match($('observed-skills').textContent,/Knowledge read · runner-correlated/);
          assert.match($('mcp-servers').textContent,/Backend-observed completion · independent trace/);
          assert.match($('graph-scope').textContent,/receipt-correlated backend/);
          state.traces[0].spans[0].attributes['flow.execution.id']='0'.repeat(32);render();
          assert.equal(receiptBackendSpans().length,0);assert.equal($('mcp-servers').children.length,0);
          state.traces[0].spans[0].attributes['flow.execution.id']='e'.repeat(32);
          state.onboarding.golden.appliesToCurrent=false;render();assert.equal(receiptBackendSpans().length,0);
        ''')
