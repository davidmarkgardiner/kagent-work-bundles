"""Private operator adapter. All external effects have durable one-shot intents."""
import base64
import copy
from dataclasses import MISSING, fields
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import threading
import time
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

from core import Config
from classifier import DEFAULT_ORIGIN, origin
from native_dispatch import controller_origin, DEFAULT_ORIGIN as NATIVE_ORIGIN, DEFAULT_USER as NATIVE_USER


class Blocked(Exception):
    pass


class Uncertain(Exception):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def private_write(path, value):
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


POD_CODE = r'''
import json,sys,pathlib,time
sys.path.insert(0,'/app')
from core import Config,Ledger,digest,POLICY_OBSERVATION_METHOD
from admission import Admission
from runtime import Runtime,policy_read_metadata,observed_generation,ready
from gitlab_lifecycle import Lifecycle
p=json.load(sys.stdin); c=Config.from_dict(json.loads(pathlib.Path('/config/config.json').read_text()))
if c.identity != p['config_identity']: raise ValueError('Runtime scope/configuration changed')
ledger=Ledger(pathlib.Path('/data/runs')/c.run_id/'kyverno.sqlite',c.identity)
r=Runtime(c,ledger,human_merger_ids=tuple(p['human_merger_ids'])); a=Admission(c,ledger); life=Lifecycle(r,tuple(p['human_merger_ids']))
action=p['action']; v=p.get('value'); result=None
if action=='read':
 result={'state':ledger.state(),'admission':a.state(),'classification_envelopes':{x['candidate_id']:json.loads(x['value']) for x in ledger.db.execute('SELECT candidate_id,value FROM classifications WHERE value IS NOT NULL')}}
elif action=='candidate': result=a.candidate(v['candidate_id']).packet
elif action=='prepare':
 before=ledger.state().get('flow_baseline'); current={'deployment_uid':r._deployment()['uid'],'policy_uid':r._policy()['metadata']['uid']}
 if before and before!=current: raise ValueError('Baseline resource identity changed')
 ledger.patch({'flow_baseline':before or current}); result=life.ensure_ticket()
elif action=='prepare_observe':
 result=life.ensure_ticket() if ledger.operation('flow-ticket-create') else {'state':'unknown'}
elif action=='observe': result=[a.observe(item['packet']) for item in v]
elif action=='classify':
 from classifier import Classifier
 result=a.classify(v['candidate_id'],Classifier('/config/model.token',traceparent=v.get('traceparent'),**({'origin_url':v['model_origin']} if v.get('model_origin') else {})))
elif action=='dispatch':
 import native_dispatch
 native_dispatch.PROMPT=('Investigate the admitted incident with native skill and scoped tools. Propose the minimal repository policy fix and inspect exact-head CI. Then complete your task with the actual MR binding and checks. The human approves in the dashboard. A separate Kagent executor performs the guarded merge and later verifies recovery. This triage task must never merge, approve, change Kubernetes, or claim recovery. Immutable identity data: ')
 result=a.dispatch(native_dispatch.NativeDispatch(c,v['session_id'],response_file='/data/runs/'+c.run_id+'/native-dispatch-response.json',origin=p.get('native_controller_origin',native_dispatch.DEFAULT_ORIGIN),user=p.get('native_user',native_dispatch.DEFAULT_USER),traceparent=v.get('traceparent')))
elif action=='repository': result=r.read_policy_repository()
elif action=='inspect': result=r.inspect_policy_fix()
elif action=='review': result=r.control(v)
elif action=='merge': result=life.observe_human_merge()
elif action=='approve_dashboard': result=life.approve_dashboard(v)
elif action=='dashboard_merge': result=life.observe_dashboard_merge()
elif action=='http':
 result={'policy':r._policy(),'deployment':r._deployment(),'http':r._http_probe(),'state':ledger.state()}
elif action=='recovery_ready':
 state=ledger.state(); merged=state.get('merged') or {}; baseline=state.get('flow_baseline') or {}; reasons=[]
 source=r._kube('/apis/source.toolkit.fluxcd.io/v1/namespaces/'+c.flux_namespace+'/gitrepositories/'+c.flux_source)
 flux=r._kube('/apis/kustomize.toolkit.fluxcd.io/v1/namespaces/'+c.flux_namespace+'/kustomizations/'+c.flux_kustomization)
 policy=r._policy(); deployment=r._deployment(); http=r._http_probe()
 revision=c.target_branch+'@sha1:'+merged.get('merge_sha','')
 if (not merged.get('merge_sha') or source.get('status',{}).get('artifact',{}).get('revision')!=revision
     or flux.get('status',{}).get('lastAppliedRevision')!=revision or not ready(source) or not ready(flux)
     or observed_generation(source)!=source['metadata']['generation'] or observed_generation(flux)!=flux['metadata']['generation']):
  reasons.append('Flux has not applied the exact approved merge revision with current Ready generations')
 if (policy['metadata']['uid']!=baseline.get('policy_uid') or digest(policy['spec'])!=c.healthy_policy_spec_sha256
     or not ready(policy) or policy['metadata'].get('deletionTimestamp')):
  reasons.append('The pinned policy has not recovered to its exact healthy specification')
 if (deployment['uid']!=baseline.get('deployment_uid') or deployment['generation']!=deployment['observed_generation']
     or deployment.get('deleting') or any(deployment.get(k)!=1 for k in
        ('desired_replicas','actual_replicas','updated_replicas','ready_replicas','available_replicas'))
     or deployment.get('unavailable_replicas')!=0):
  reasons.append('The pinned application rollout is not ready')
 if (http.get('status_code')!=c.expected_http_status or http.get('body_sha256')!=c.expected_body_sha256 or http.get('error')):
  reasons.append('The application has not returned the expected live HTTP response')
 result={'ready':not reasons,'reasons':reasons}
elif action=='live': result={'policy':r._policy(),'deployment':r._deployment(),'state':ledger.state()}
elif action=='window':
 state=ledger.state()
 if state.get('flow_recovery_window') and state['flow_recovery_window']!=v['window']: raise ValueError('Immutable recovery window changed')
 result=r.control({'action':'record_probe_receipt','receipt':v['receipt']})
 ledger.patch({'flow_recovery_window':v['window']}); life._window(ledger.state())
elif action=='recovery_window':
 state=ledger.state()
 if state.get('flow_recovery_window'):
  life._window(state); result={'recorded':True}
 else: result={'recorded':False}
elif action=='verification_binding':
 old=ledger.state().get('flow_verification_binding')
 if old and old!=v: raise ValueError('Verification binding changed')
 ledger.patch({'flow_verification_binding':v}); result=v
elif action=='closure_check':
 state=ledger.state(); life._native_proof(v,state); life._window(state)
 result=r.verify_recovery(); life._proof(result,ledger.state())
 result={'verified':True,'task_id':v['id'],'task_state':v['status']['state'],'evidence_digest':digest({'task':v,'window':state['flow_recovery_window'],'verification':result})}
elif action=='close': result=life.close_verified_ticket(v)
elif action=='close_observe':
 result=life.close_verified_ticket(v) if ledger.operation('flow-ticket-close') else {'state':'pending'}
else: raise ValueError('Unknown fixed action')
print(json.dumps(result));ledger.close()
'''


COLLECT_CODE = r'''
import json,sys
p=json.load(sys.stdin);sys.path.insert(0,p['collector_dir'])
from core import Config
from collect_probe import Collector
c=Config.from_dict(p['config']); print(json.dumps(Collector(c,p['kubeconfig']).collect(p['kind'])))
'''


BUDGET_HEALTH_CODE = r'''
import json,sys
sys.path.insert(0,'/app')
from classifier import DEFAULT_ORIGIN,origin
from urllib.request import build_opener,HTTPRedirectHandler
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs): return None
health_origin=origin(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_ORIGIN
with build_opener(NoRedirect()).open(health_origin.rstrip('/')+'/healthz',timeout=4) as response:
 raw=response.read(16385)
if len(raw)>16384: raise ValueError('Bounded health response required')
value=json.loads(raw)
print(json.dumps({key:value.get(key) for key in ('requests_remaining','input_bytes_remaining')}))
'''


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class LabAdapter:
    STEPS = ('triage_continuation','classification_followup','recheck_fault','prepare','inject_fault','observe_fault','classify','dispatch','triage','review','await_approval','merge','observe_merge','await_recovery','measure_recovery','verify','close')

    def __init__(self, settings_path, command=None, clock=time.time, sleep=time.sleep):
        self.settings = json.loads(Path(settings_path).read_text()) if not isinstance(settings_path, dict) else copy.deepcopy(settings_path)
        s = self.settings
        required = ('ssh_argv_file','gitlab_token_file','base_config_file','project_id','namespace','target_branch','kubeconfig','native_cli','grpcurl','proto_dir','native_address','human_merger_ids','specialist_agent','reviewer_agent')
        if any(k not in s for k in required):
            raise ValueError('Missing trusted adapter settings')
        for key in ('namespace','specialist_agent','reviewer_agent','executor_agent','runtime_deployment'):
            if key in s and not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,80}', s[key]):
                raise ValueError('Invalid fixed Kubernetes identity')
        if not isinstance(s['human_merger_ids'],list) or not s['human_merger_ids'] or any(type(x) is not int or x<1 for x in s['human_merger_ids']):
            raise ValueError('Explicit human merge allowlist required')
        self.ssh = json.loads(Path(s['ssh_argv_file']).read_text())
        if not isinstance(self.ssh,list) or not self.ssh or not all(isinstance(x,str) and '\x00' not in x for x in self.ssh):
            raise ValueError('SSH argv must be a fixed list')
        self.base = json.loads(Path(s['base_config_file']).read_text())
        for field in fields(Config):
            if field.default is not MISSING:
                self.base.setdefault(field.name,field.default)
        if (str(s['project_id'])!=self.base['project_id'] or s['namespace']!=self.base['namespace'] or s['target_branch']!=self.base['target_branch']
                or self.base['investigator_id']!='kagent/'+s['specialist_agent'] or self.base['reviewer_id']!='kagent/'+s['reviewer_agent']):
            raise ValueError('Base configuration differs from trusted scope')
        bound=s.get('model_allowance_run_id')
        if bound is not None and (not isinstance(bound,str) or not re.fullmatch(r'demo-[a-f0-9]{32}',bound)):
            raise ValueError('Model allowance requires an exact demo run identity')
        self.model_origin = origin(s.get('model_origin', DEFAULT_ORIGIN))
        self.native_controller_origin = controller_origin(s.get('native_controller_origin', NATIVE_ORIGIN))
        self.native_user = s.get('native_user', NATIVE_USER)
        if not isinstance(self.native_user, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.@_+-]{0,127}', self.native_user):
            raise ValueError('Invalid trusted native user partition')
        self.command = command or subprocess.run
        self.clock, self.sleep = clock, sleep
        self.lock = threading.RLock()
        self._budget_cache, self._budget_checked_at = None, None

    def budget_state(self, force=False):
        """Read the existing proxy allowance; never allocate, reserve or reset it."""
        with self.lock:
            now = self.clock()
            if (not force and self._budget_cache is not None and self._budget_checked_at is not None
                    and 0 <= now - self._budget_checked_at < 5):
                return dict(self._budget_cache)
            state = {'enabled': True, 'available': False, 'requestsRemaining': None,
                     'inputBytesRemaining': None, 'reason': 'Existing model budget health is unavailable.'}
            if self.settings.get('model_allowance_run_id'):
                state['boundRunId']=self.settings['model_allowance_run_id']
            try:
                health = self._kubectl(['exec', '-i', 'deploy/' + self.settings.get('runtime_deployment', 'kyverno-runtime'),
                                        '--', 'python', '-c', BUDGET_HEALTH_CODE] + ([self.model_origin] if 'model_origin' in self.settings else []), timeout=12)
                requests, input_bytes = health.get('requests_remaining'), health.get('input_bytes_remaining')
                if (type(requests) is not int or type(input_bytes) is not int
                        or not 0 <= requests <= 32 or not 0 <= input_bytes <= 524288):
                    raise ValueError('Invalid bounded allowance')
                available = requests > 0 and input_bytes > 0
                state.update(available=available, requestsRemaining=requests, inputBytesRemaining=input_bytes,
                             reason=None if available else 'The existing model allowance is exhausted; a new allowance requires operator authorization.')
            except Exception:
                pass
            self._budget_cache, self._budget_checked_at = dict(state), now
            return state

    def execution_budget(self, step):
        required = {'merge': 4, 'verify': 2}[step]
        state = self.budget_state()
        remaining = state.get('requestsRemaining')
        ready = (state.get('enabled') is True and state.get('available') is True
                 and type(remaining) is int and remaining >= required
                 and type(state.get('inputBytesRemaining')) is int and state['inputBytesRemaining'] > 0)
        return {'ready':ready, 'required':required, 'remaining':remaining,
                'boundRunId':state.get('boundRunId'),
                'reason':None if ready else 'Waiting for model allowance to complete merge and verification; no native task was sent.'}

    def _workspace(self, run):
        rid = run.get('runId')
        if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',rid):
            raise Blocked('Invalid run identity')
        path=Path(run['workspace'])
        if not path.is_absolute() or path.is_symlink(): raise Blocked('Private absolute workspace required')
        path.mkdir(parents=True,exist_ok=True,mode=0o700)
        path.chmod(0o700)
        identity=path/'adapter-identity.json'
        expected={'runId':rid,'scope':digest(self.base)}
        if identity.exists() and json.loads(identity.read_text())!=expected: raise Blocked('Workspace identity changed')
        if not identity.exists(): private_write(identity,expected)
        return path

    def _config(self, run):
        path=self._workspace(run)/'runtime-config.json'
        config=copy.deepcopy(self.base)
        config.update(run_id=run['runId'],incident_id='incident-'+run['runId'],fix_branch='repair/'+run['runId'])
        config['profile_revision']=digest({k:v for k,v in config.items() if k!='profile_revision'})
        if path.exists():
            saved=json.loads(path.read_text())
            if saved!=config: raise Blocked('Immutable per-run runtime configuration differs')
            return saved
        private_write(path,config)
        return config

    def _once(self, run, name, callback, observe=False):
        path=self._workspace(run)/(name+'.json')
        if path.exists():
            saved=json.loads(path.read_text())
            if saved['state']=='completed': return saved['result']
            raise Uncertain('Original '+name+' intent has no confirmed response; readback required')
        if observe: raise Uncertain('No original '+name+' receipt is available')
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        except FileExistsError:
            raise Uncertain('Original '+name+' intent was concurrently reserved; no resend') from None
        with os.fdopen(fd,'w') as stream:
            json.dump({'state':'unknown','intentId':run['_call']['intentId'],'reserved_at':int(self.clock())},stream)
            stream.flush();os.fsync(stream.fileno())
        result=callback()
        private_write(path,{'state':'completed','result':result})
        return result

    def _remote(self,args,body=None,timeout=120):
        result=self.command(self.ssh+[shlex.join(args)],input=json.dumps(body) if body is not None else None,text=True,capture_output=True,timeout=timeout)
        if result.returncode: raise Uncertain('Bounded remote operation failed; private intent retained')
        try: return json.loads(result.stdout)
        except ValueError: raise Uncertain('Remote operation returned no valid receipt') from None

    def _kubectl(self,args,body=None,timeout=120):
        return self._remote(['sudo','-n','kubectl','--kubeconfig',self.settings['kubeconfig'],'-n',self.settings['namespace']]+args,body,timeout)

    def _pod(self,run,action,value=None):
        code="import json,sys;sys.path.insert(0,'/app')\nfrom core import Rejected,APIError\ntry:\n exec("+repr(POD_CODE)+")\nexcept APIError:\n print(json.dumps({'adapter_error':'upstream'}))\nexcept Rejected:\n print(json.dumps({'adapter_error':'rejected'}))"
        result=self._kubectl(['exec','-i','deploy/'+self.settings.get('runtime_deployment','kyverno-runtime'),'--','python','-c',code],
                            {'action':action,'value':value,'config_identity':digest(self._config(run)),
                             'human_merger_ids':self.settings['human_merger_ids'],
                             'native_controller_origin':self.native_controller_origin,'native_user':self.native_user})
        if isinstance(result,dict) and result.get('adapter_error')=='rejected':
            raise Blocked('Runtime rejected this scoped operation')
        if isinstance(result,dict) and result.get('adapter_error')=='upstream':
            raise Uncertain('Runtime upstream readback unavailable')
        return result

    def _collect(self,run,kind):
        s=self.settings
        return self._remote(['sudo','-n','python3','-c',COLLECT_CODE],{'collector_dir':s.get('collector_dir',str(Path(s['grpcurl']).parent/'collector')),'config':self._config(run),'kubeconfig':s['kubeconfig'],'kind':kind},60)

    def _gl(self,path,method='GET',body=None):
        token=Path(self.settings['gitlab_token_file']).read_text().strip()
        url=self.base['gitlab_api'].rstrip('/')+'/projects/'+str(self.settings['project_id'])+path
        request=Request(url,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with build_opener(NoRedirect()).open(request,timeout=40) as response:
            raw=response.read(1024*1024+1)
        if len(raw)>1024*1024: raise Blocked('GitLab response exceeds limit')
        return json.loads(raw)

    def _rpc(self,agent,method,body,traceparent=None):
        s=self.settings
        args=[s['grpcurl'],'-plaintext','-max-time','60','-max-msg-sz','1048576','-H','x-user-id: '+self.native_user,'-H','a2a-extensions: https://kagent.dev/extensions/hitl/v1','-import-path',s['proto_dir'],'-proto','a2a.proto','-d','@',s['native_address'],'lf.a2a.v1.A2AService/'+method]
        if method == 'SendMessage' and traceparent is not None:
            match = re.fullmatch(r'00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}', traceparent)
            if not match or not int(match[1],16) or not int(match[2],16):
                raise Blocked('Invalid caller trace context')
            args[1:1] = ['-H', 'traceparent: ' + traceparent]
        return self._remote(args,dict(body,tenant='kagent/'+agent),80)

    def _agent(self,role):
        if role=='review': return self.settings['reviewer_agent']
        return self.settings.get('executor_agent',self.settings['specialist_agent']) if role in ('merge','verify') else self.settings['specialist_agent']

    def _session(self,run,role,observe):
        s=self.settings; agent=self._agent(role)
        args=['sudo','-n',s['native_cli'],'--api-url','http://'+s['native_address'],'--gateway-url','http://'+s['native_address'],'--user-id',self.native_user,'-n','kagent','--timeout','30s','-o','json','agent','session','create','--agent',agent,'--request-id',run['runId']+'-'+role]
        value=self._once(run,role+'-session',lambda:self._remote(args),observe)
        sid=value.get('session',{}).get('id')
        if not sid: raise Uncertain('Native session receipt lacks actual identity')
        return sid

    def _task(self,run,role,observe,message=None):
        s=self.settings; agent=self._agent(role)
        sid=self._session(run,role,observe)
        carrier = {'traceparent': run['_traceparent']} if run.get('_traceparent') else {}
        if role=='triage':
            dispatch=self._once(run,'native-dispatch',lambda:self._pod(run,'dispatch',{'session_id':sid,**carrier}),observe)
            tid=dispatch.get('task_id')
            if dispatch.get('state')!='accepted' or not tid: raise Uncertain('Native original dispatch outcome is unknown')
            continuation=self._workspace(run)/'operator-triage-continuation.json'
            if continuation.exists():
                receipt=json.loads(continuation.read_text())
                if (receipt.get('original_task_id')!=tid or receipt.get('session_id')!=sid
                        or not isinstance(receipt.get('task_id'),str) or receipt['task_id']==tid
                        or not re.fullmatch(r'[0-9a-f]{64}',receipt.get('send_receipt_sha256',''))):
                    raise Blocked('Operator continuation differs from the original native task')
                tid=receipt['task_id']
        else:
            body={'message':{'messageId':run['runId']+'-'+role,'contextId':sid,'role':'ROLE_USER','parts':[{'text':message}]},'configuration':{'returnImmediately':True}}
            receipt=self._once(run,role+'-send',lambda:self._rpc(agent,'SendMessage',body,**carrier),observe)
            task=receipt.get('task',{})
            if task.get('contextId')!=sid or not task.get('id'): raise Uncertain('Native task lacks original session binding')
            tid=task['id']
        result=self._rpc(agent,'GetTask',{'id':tid,'historyLength':40})
        task=result.get('task',result)
        if task.get('id')!=tid or task.get('contextId')!=sid: raise Blocked('Native readback identity changed')
        private_write(self._workspace(run)/(role+'-task-latest.json'),task)
        return task

    def _result(self,step,status,message,patch=None,phase=None):
        result={'status':status,'patch':patch or {},'events':[{'stage':step,'state':status,'message':message}]}
        if phase: result['phase']=phase
        return result

    def advance(self,run,step):
        with self.lock:
            try:
                self._workspace(run)
                call=run.get('_call',{})
                if step not in self.STEPS or call.get('mode') not in ('execute','observe') or not isinstance(call.get('intentId'),str):
                    raise Blocked('Invalid kernel step or intent')
                return getattr(self,'_step_'+step)(run,call['mode']=='observe')
            except Blocked as error:
                return self._result(step,'blocked',str(error),phase='blocked')
            except Uncertain as error:
                if step in ('merge','verify','triage_continuation'):
                    receipt=self._workspace(run)/('triage-continuation-send.json' if step=='triage_continuation' else step+'-send.json')
                    if receipt.exists() and json.loads(receipt.read_text()).get('state')=='completed':
                        phase='merging' if step=='merge' else 'triaging' if step=='triage_continuation' else 'verifying'
                        return self._result(step,'pending','Reading the original accepted native task; no task was resent',phase=phase)
                if step in ('triage','observe_merge','await_approval','await_recovery'):
                    phase={'triage':'triaging','observe_merge':'merging','await_approval':'waiting_human','await_recovery':'reconciling'}[step]
                    return self._result(step,'pending','Readback temporarily unavailable; observing the original recorded operation',phase=phase)
                return self._result(step,'unknown',str(error),phase='unknown')
            except Exception as error:
                return self._result(step,'unknown','Operation lacks corroborated receipt ('+type(error).__name__+'); no automatic resend',phase='unknown')

    def _step_prepare(self,run,observe):
        bound=self.settings.get('model_allowance_run_id')
        if bound is not None and bound!=run['runId']:
            raise Blocked('This allowance is reserved for the existing incident; another demo requires a separate allowance.')
        if not self.budget_state(force=True)['available']:
            raise Blocked('Demo cannot prepare or inject a fault without an available existing model allowance')
        config=self._config(run)
        def configure():
            s=self.settings; name=s.get('runtime_deployment','kyverno-runtime')
            deployment=self._kubectl(['get','deployment',name,'-o','json'])
            container=deployment['spec']['template']['spec']['containers'][0]
            argument_key='args' if 'args' in container else 'command'
            args=list(container[argument_key])
            if '--data' not in args: raise Blocked('Runtime deployment has no reviewed data argument')
            args[args.index('--data')+1]='/data/runs/'+run['runId']
            self._kubectl(['patch','configmap',name+'-config','--type=merge','-p',json.dumps({'data':{'config.json':json.dumps(config)}}),'-o','json'])
            patch={'spec':{'template':{'metadata':{'annotations':{'demo.kagent.dev/dashboard-run':run['runId']}},'spec':{'containers':[{'name':container['name'],argument_key:args}]}}}}
            self._kubectl(['patch','deployment',name,'--type=strategic','-p',json.dumps(patch),'-o','json'])
            code="import subprocess,json,sys;p=json.load(sys.stdin);r=subprocess.run(p,capture_output=True,timeout=100);print(json.dumps({'ready':r.returncode==0}))"
            result=self._remote(['sudo','-n','python3','-c',code],['kubectl','--kubeconfig',s['kubeconfig'],'-n',s['namespace'],'rollout','status','deployment/'+name,'--timeout=90s'],110)
            if not result.get('ready'): raise Uncertain('New runtime pod is not ready; reconcile original rollout')
            return {'configured':True,'config_identity':digest(config)}
        try: self._once(run,'runtime-configuration',configure,observe)
        except Uncertain:
            name=self.settings.get('runtime_deployment','kyverno-runtime')
            actual=self._kubectl(['get','deployment',name,'-o','json'])
            cm=self._kubectl(['get','configmap',name+'-config','-o','json'])
            container=actual['spec']['template']['spec']['containers'][0]
            args=container.get('args',container.get('command',[]))
            if (json.loads(cm['data']['config.json'])!=config or '--data' not in args or args[args.index('--data')+1]!='/data/runs/'+run['runId'] or actual['spec']['template']['metadata'].get('annotations',{}).get('demo.kagent.dev/dashboard-run')!=run['runId'] or actual.get('status',{}).get('observedGeneration')!=actual['metadata']['generation'] or actual.get('status',{}).get('readyReplicas')!=1): raise
            private_write(self._workspace(run)/'runtime-configuration.json',{'state':'completed','result':{'configured':True,'config_identity':digest(config)}})
        if observe:
            ticket=self._pod(run,'prepare_observe')
        else: ticket=self._pod(run,'prepare')
        if ticket.get('state')=='unknown': raise Uncertain('Issue creation requires readback')
        return self._result('prepare','completed','Actual isolated runtime and issue prepared',{'ticket':dict(ticket,closedVerified=False)},'preparing')

    def _step_inject_fault(self,run,observe):
        c=self._config(run); branch=quote(c['target_branch'],safe='')
        def inject():
            head=self._gl('/repository/branches/'+branch)['commit']['id']
            path=c['policy_file']
            f=self._gl('/repository/files/'+quote(path,safe='')+'?'+urlencode({'ref':head}))
            doc=json.loads(base64.b64decode(f['content']))
            if digest(doc)!=c['healthy_policy_sha256']: raise Blocked('Fault injection requires exact reviewed healthy policy')
            doc['spec']['rules'][0]['validate']['pattern']['spec']['containers'][0]['image']='docker.io/libary/*'
            if digest(doc)!=c['faulty_policy_sha256']:
                from_file=self.settings.get('faulty_policy_file')
                if not from_file: raise Blocked('Trusted faulty_policy_file is required for exact fixture')
                doc=json.loads(Path(from_file).read_text())
            if digest(doc)!=c['faulty_policy_sha256'] or doc['metadata']['namespace']!=c['namespace']: raise Blocked('Fault fixture outside exact scope')
            actions=[{'action':'update','file_path':path,'content':json.dumps(doc,indent=2)+'\n','last_commit_id':f['last_commit_id']}]
            body={'branch':c['target_branch'],'commit_message':'Inject isolated policy admission fault ['+run['runId']+']','actions':actions}
            private_write(self._workspace(run)/'fault-commit-request.json',{'parent_sha':head,'body':body})
            receipt=self._gl('/repository/commits','POST',body)
            if receipt.get('parent_ids')!=[head]: raise Blocked('Fault commit parent changed')
            return receipt
        try: receipt=self._once(run,'fault-commit',inject,observe)
        except Uncertain:
            intent=self._workspace(run)/'fault-commit-request.json'
            if not intent.exists(): raise
            intended=json.loads(intent.read_text()); head=self._gl('/repository/branches/'+branch)['commit']['id']; receipt=self._gl('/repository/commits/'+head)
            if receipt.get('parent_ids')!=[intended['parent_sha']] or receipt.get('message','').strip()!=intended['body']['commit_message']: raise
            for action in intended['body']['actions']:
                f=self._gl('/repository/files/'+quote(action['file_path'],safe='')+'?'+urlencode({'ref':head}))
                if base64.b64decode(f['content']).decode()!=action['content']: raise Uncertain('Original commit content readback differs')
            private_write(self._workspace(run)/'fault-commit.json',{'state':'completed','result':receipt})
        # The old application pod must remain available until the bad policy is
        # active. A separate repository commit then triggers Recreate failure.
        for attempt in range(30 if not observe else 1):
            live=self._pod(run,'live')
            if digest(live['policy']['spec'])==c['faulty_policy_spec_sha256']: break
            if observe: return self._result('inject_fault','pending','Waiting for actual faulty policy before any rollout trigger',phase='preparing')
            self.sleep(3)
        else: raise Uncertain('Fault commit exists but exact faulty policy has not reconciled; no rollout write issued')
        def rollout():
            head=self._gl('/repository/branches/'+branch)['commit']['id']
            if head!=receipt['id']: raise Blocked('Target branch changed before scoped rollout fault commit')
            path=self.settings.get('application_file','deploy/application.json')
            f=self._gl('/repository/files/'+quote(path,safe='')+'?'+urlencode({'ref':head}))
            doc=json.loads(base64.b64decode(f['content']))
            if doc.get('kind')!='Deployment' or doc['metadata']['namespace']!=c['namespace'] or doc['metadata']['name']!=c['application']: raise Blocked('Rollout document outside fixed scope')
            doc['spec']['template'].setdefault('metadata',{}).setdefault('annotations',{})['demo.kagent.dev/recovery-run']=run['runId']
            body={'branch':c['target_branch'],'commit_message':'Trigger isolated blocked rollout ['+run['runId']+']','actions':[{'action':'update','file_path':path,'content':json.dumps(doc,indent=2)+'\n','last_commit_id':f['last_commit_id']}]}
            private_write(self._workspace(run)/'rollout-commit-request.json',{'parent_sha':head,'body':body})
            result=self._gl('/repository/commits','POST',body)
            if result.get('parent_ids')!=[head]: raise Blocked('Rollout commit parent changed')
            return result
        try: rollout_receipt=self._once(run,'rollout-commit',rollout,observe)
        except Uncertain:
            intent=self._workspace(run)/'rollout-commit-request.json'
            if not intent.exists(): raise
            intended=json.loads(intent.read_text()); head=self._gl('/repository/branches/'+branch)['commit']['id']; rollout_receipt=self._gl('/repository/commits/'+head)
            if rollout_receipt.get('parent_ids')!=[intended['parent_sha']] or rollout_receipt.get('message','').strip()!=intended['body']['commit_message']: raise
            action=intended['body']['actions'][0]
            f=self._gl('/repository/files/'+quote(action['file_path'],safe='')+'?'+urlencode({'ref':head}))
            if base64.b64decode(f['content']).decode()!=action['content']: raise Uncertain('Original rollout commit content readback differs')
            private_write(self._workspace(run)/'rollout-commit.json',{'state':'completed','result':rollout_receipt})
        return self._result('inject_fault','completed','Separate fault and rollout commits read back after active faulty policy proof',{'adapter':{'fault_sha':receipt['id'],'rollout_sha':rollout_receipt['id']}},'fault_injected')

    def _measure_fault_window(self,run,prefix):
        expected=run.get('data',{}).get('adapter',{}).get('rollout_sha')
        if not isinstance(expected,str) or not re.fullmatch(r'[0-9a-f]{40}',expected):
            raise Blocked('Exact fault rollout revision is required before measuring denials')
        receipts=[]
        for i in range(3):
            if i: self.sleep(31)
            for attempt in range(30 if i==0 else 1):
                value=self._collect(run,'valid')
                packet=value.get('packet') or {}
                if i==0:
                    private_write(self._workspace(run)/(prefix+'-readiness-'+str(attempt)+'.json'),value)
                result=None
                if (value.get('policy_revision')==expected
                        and packet.get('policy',{}).get('policy_revision')==expected):
                    result=self._pod(run,'observe',[value])[-1]
                if result and result.get('state') in ('observing','candidate'):
                    break
                if i==0 and attempt<29: self.sleep(3)
            else:
                raise Blocked('Current fault rollout has not supplied an accepted policy-specific denial')
            receipts.append(value)
            private_write(self._workspace(run)/(prefix+'-probe-'+str(i)+'.json'),value)
        return {'receipts':receipts,'admission':result}

    def _step_observe_fault(self,run,observe):
        if observe:
            snapshot=self._pod(run,'read'); candidate=snapshot['state'].get('candidate_id')
            if not candidate: raise Uncertain('Interrupted fault observation window requires reconciliation of retained physical receipts')
        else:
            value=self._once(run,'fault-window',lambda:self._measure_fault_window(run,'fault')); candidate=value['admission'].get('candidate_id')
            if not candidate: raise Blocked('Actual denial window did not satisfy admission gates')
        return self._result('observe_fault','completed','Three actual denials satisfied the admission window',{'adapter':{'candidate_id':candidate}},'observing')

    def _validated_recheck(self,run,window):
        receipts=window.get('receipts',[])
        if len(receipts)!=3 or type(window.get('started_at')) is not int:
            raise Uncertain('Fresh recheck lacks its complete original three-probe receipt')
        expected=run.get('data',{}).get('adapter',{}).get('rollout_sha')
        packets=[value.get('packet') or {} for value in receipts]
        try:
            times=[packet['probe']['observed_at'] for packet in packets]
            ids=[packet['probe']['probe_id'] for packet in packets]
            if (len(set(ids))!=3 or any(type(t) is not int for t in times)
                    or not 60<=times[-1]-times[0]<=120 or times!=sorted(times)
                    or times[0]<window['started_at']
                    or any(value.get('policy_revision')!=expected or packet['policy']['policy_revision']!=expected
                           for value,packet in zip(receipts,packets))):
                raise ValueError()
        except (KeyError,TypeError,ValueError):
            raise Uncertain('Fresh recheck receipt does not prove its own measured denial window') from None
        candidate=(window.get('admission') or {}).get('candidate_id')
        if not isinstance(candidate,str) or not re.fullmatch(r'[a-f0-9]{64}',candidate):
            raise Uncertain('Fresh recheck lacks its own admitted candidate identity')
        actual=self._pod(run,'candidate',{'candidate_id':candidate})
        config=self._config(run)
        candidate_body=dict(actual);candidate_body.pop('candidate_id',None)
        expected_ids=sorted(set(ids)|{p['rollout']['event_id'] for p in packets})
        if (actual.get('candidate_id')!=candidate or digest(candidate_body)!=candidate
                or actual.get('run_id')!=run['runId'] or actual.get('incident_id')!=config['incident_id']
                or actual.get('profile_revision')!=config['profile_revision']
                or sorted(digest(p) for p in actual.get('observations',[]))!=sorted(digest(p) for p in packets)
                or actual.get('evidence_ids')!=expected_ids
                or any(not self.clock()-config['evidence_max_age_seconds']<=t<=self.clock() for t in times)):
            raise Uncertain('Actual candidate is not bound to the complete current recheck receipt')
        return candidate

    def _step_recheck_fault(self,run,observe):
        def collect_window():
            started=int(self.clock())
            window=dict(self._measure_fault_window(run,'fault-recheck'),started_at=started)
            self._validated_recheck(run,window)
            return window
        window=self._once(run,'fault-recheck-window',collect_window,observe)
        candidate=self._validated_recheck(run,window)
        return self._result('recheck_fault','completed','Three fresh denials for this same incident passed the measured admission window',
                            {'adapter':{'candidate_id':candidate}},'observing')

    def _step_classify(self,run,observe):
        snapshot=self._pod(run,'read'); candidate=snapshot['state'].get('candidate_id')
        if not candidate: raise Blocked('No actual admitted candidate')
        expected=run.get('data',{}).get('adapter',{}).get('candidate_id')
        if expected and candidate!=expected: raise Blocked('Admitted candidate changed after the recorded observation window')
        if observe:
            records=[r for r in snapshot['admission']['classifications'] if r['candidate_id']==candidate]
            if not records: raise Uncertain('No original classifier reservation')
            state=records[-1]['status']; result={'state':state,'classification':snapshot.get('classification_envelopes',{}).get(candidate)}
        else: result=self._once(run,'classification',lambda:self._pod(run,'classify',{'candidate_id':candidate,
            **({'traceparent':run['_traceparent']} if run.get('_traceparent') else {}),
            **({'model_origin':self.model_origin} if 'model_origin' in self.settings else {})}))
        return self._classification_result('classify',result,len(snapshot['admission']['classifications']) or 1)

    def _classification_result(self,step,result,attempts,candidate=None):
        if result['state']=='unknown': raise Uncertain('Classifier original call is uncertain; reservation remains spent')
        classification=result.get('classification') or {}
        choice=classification.get('result') or {}
        patch={'classifier':{'decision':choice.get('choice'),'severity':choice.get('severity'),'confidence':choice.get('confidence'),'threshold':0.95,'attempts':attempts}}
        if candidate: patch['adapter']={'candidate_id':candidate}
        if result['state']=='suppressed': return self._result(step,'suppressed','Actual classifier suppressed this candidate',patch,'suppressed')
        if result['state']!='accepted': raise Blocked('Classifier did not admit this candidate')
        return self._result(step,'completed','Actual classifier admitted the bounded investigation',patch,'classifying')

    def _step_classification_followup(self,run,observe):
        original=run.get('data',{}).get('adapter',{}).get('candidate_id')
        snapshot=self._pod(run,'read')
        prior=[r for r in snapshot['admission']['classifications'] if r['candidate_id']==original]
        if (snapshot['admission'].get('outbox') is not None or len(prior)!=1 or prior[0]['status']!='suppressed'):
            raise Blocked('Fresh followup requires the original suppression and no native dispatch')
        original_decision=(snapshot.get('classification_envelopes',{}).get(original) or {}).get('result',{})
        confidence=original_decision.get('confidence')
        if (original_decision.get('choice')!='investigate' or original_decision.get('severity')!='critical'
                or type(confidence) not in {float,int} or not 0<=confidence<0.95):
            raise Blocked('Original classification does not permit this critical-confidence followup')
        def collect_window():
            if len(snapshot['admission']['classifications'])!=1:
                raise Blocked('Only one fresh classification followup is permitted')
            started=int(self.clock())
            window=dict(self._measure_fault_window(run,'classification-followup'),started_at=started)
            candidate=self._validated_recheck(run,window)
            if candidate==original: raise Blocked('The suppressed candidate cannot be resent')
            return window
        window=self._once(run,'classification-followup-window',collect_window,observe)
        candidate=self._validated_recheck(run,window)
        if candidate==original: raise Blocked('The suppressed candidate cannot be resent')
        result=self._once(run,'classification-followup',lambda:self._pod(run,'classify',{'candidate_id':candidate,
            **({'traceparent':run['_traceparent']} if run.get('_traceparent') else {}),
            **({'model_origin':self.model_origin} if 'model_origin' in self.settings else {})}),observe)
        if result.get('state')=='unknown': raise Uncertain('Fresh classifier reservation remains spent; no resend')
        actual=self._pod(run,'read')
        records=actual['admission']['classifications']
        followup=[r for r in records if r['candidate_id']==candidate]
        envelope=actual.get('classification_envelopes',{}).get(candidate)
        if (len(records)!=2 or len(followup)!=1 or followup[0]['status']!=result.get('state')
                or envelope!=result.get('classification') or actual['state'].get('candidate_id')!=candidate
                or actual['admission'].get('outbox') is not None):
            raise Uncertain('Fresh classifier response lacks its exact retained Admission reservation')
        return self._classification_result('classification_followup',result,len(records),candidate)

    def _step_dispatch(self,run,observe):
        task=self._task(run,'triage',observe)
        return self._result('dispatch','completed','Original native task accepted and read back',{'native':{'agent':self.settings['specialist_agent'],'taskId':task['id'],'state':task['status']['state']},'adapter':{'task_id':task['id'],'session_id':task['contextId']}},'triaging')

    def _step_triage(self,run,observe):
        task=self._task(run,'triage',True); state=task.get('status',{}).get('state')
        patch={'native':{'agent':self.settings['specialist_agent'],'taskId':task['id'],'state':state},'adapter':{'task_id':task['id']}}
        if state in ('TASK_STATE_FAILED','TASK_STATE_CANCELED','TASK_STATE_REJECTED'):
            return self._result('triage','blocked','Native triage ended without a successful proposal',patch,'blocked')
        snapshot=self._pod(run,'read'); proposal=snapshot['state'].get('proposal')
        if not proposal and state=='TASK_STATE_COMPLETED':
            return self._result('triage','blocked','Native triage completed without a repository proposal',patch,'blocked')
        if not proposal: return self._result('triage','pending','Native triage is running; no repository proposal receipt yet',patch,'triaging')
        info=self._pod(run,'inspect'); binding=info['binding']
        patch['remedy']={'summary':'Minimal scoped policy repair','mrUrl':info.get('url') or proposal.get('url'),'headSha':binding['head_sha'],'ci':'passed' if info.get('ci_pass') else 'pending','review':'pending'}
        if not info.get('diff_valid'): raise Blocked('Actual MR diff is outside the permitted repair')
        if not info.get('ci_pass'): return self._result('triage','pending','Exact-head CI is pending',patch,'waiting_ci')
        if state!='TASK_STATE_COMPLETED': return self._result('triage','pending','Waiting for native triage to complete after proposing the MR',patch,'triaging')
        return self._result('triage','completed','Native triage completed with exact-head passing CI',patch,'waiting_review')

    def _original_triage(self,run):
        sid=self._session(run,'triage',True)
        dispatch=self._once(run,'native-dispatch',lambda:None,True)
        tid=dispatch.get('task_id')
        if dispatch.get('state')!='accepted' or not isinstance(tid,str) or not tid:
            raise Blocked('An original accepted native triage identity is required')
        return sid,tid

    def validate_triage_continuation(self,run):
        sid,tid=self._original_triage(run)
        if (self._workspace(run)/'operator-triage-continuation.json').exists():
            raise Blocked('A native continuation is already recorded')
        task=self._rpc(self._agent('triage'),'GetTask',{'id':tid,'historyLength':40})
        task=task.get('task',task)
        if (task.get('id')!=tid or task.get('contextId')!=sid
                or task.get('status',{}).get('state')!='TASK_STATE_COMPLETED'):
            raise Blocked('The original native task is not completed in its recorded session')
        snapshot=self._pod(run,'read')
        if snapshot['state'].get('proposal'):
            raise Blocked('An existing repository proposal must be reconciled before continuing')
        repo=self._pod(run,'repository');config=self._config(run)
        if (str(repo.get('project_id'))!=config['project_id'] or repo.get('target_branch')!=config['target_branch']
                or repo.get('head_sha')!=run.get('data',{}).get('adapter',{}).get('rollout_sha')
                or repo.get('known_faulty_file') is not True):
            raise Blocked('Restored repository access does not match the current fault branch')
        return {'taskId':tid,'sessionId':sid}

    def _step_triage_continuation(self,run,observe):
        sid,tid=self._original_triage(run)
        path=self._workspace(run)/'operator-triage-continuation.json'
        send_path=self._workspace(run)/'triage-continuation-send.json'
        if not observe and not send_path.exists():
            self.validate_triage_continuation(run)
        message=('GitLab credentials for this same project were restored and independently verified. '
                 'Continue only the unfinished repository stage of your existing diagnosis. '
                 'Do not repeat Kubernetes, skills, knowledge, repository reads or polling. '
                 'Call propose_policy_fix once for the known one-field correction docker.io/libary/* to docker.io/library/*. '
                 'Then complete with the actual returned MR binding and CI, even if CI is pending; the controller inspects and waits for CI. '
                 'Do not merge, approve, apply, verify recovery or claim recovery. The incident and scope are unchanged.')
        body={'message':{'messageId':run['runId']+'-triage-credential-continuation','contextId':sid,
                        'role':'ROLE_USER','parts':[{'text':message}]},'configuration':{'returnImmediately':True}}
        carrier={'traceparent':run['_traceparent']} if run.get('_traceparent') else {}
        sent=self._once(run,'triage-continuation-send',lambda:self._rpc(self._agent('triage'),'SendMessage',body,**carrier),observe)
        accepted=sent.get('task',{})
        new_id=accepted.get('id')
        if not isinstance(new_id,str) or not new_id or new_id==tid or accepted.get('contextId')!=sid:
            raise Blocked('Native continuation acceptance lacks its distinct task and original session')
        task=self._rpc(self._agent('triage'),'GetTask',{'id':new_id,'historyLength':40})
        task=task.get('task',task)
        if task.get('id')!=new_id or task.get('contextId')!=sid:
            raise Blocked('Native continuation readback identity changed')
        binding={'original_task_id':tid,'session_id':sid,'task_id':new_id,
                 'send_receipt_sha256':hashlib.sha256(send_path.read_bytes()).hexdigest()}
        if path.exists():
            if json.loads(path.read_text())!=binding:
                raise Blocked('Original continuation receipt differs from its accepted native task')
        else: private_write(path,binding)
        result=self._step_triage(run,True)
        for event in result['events']: event['stage']='triage_continuation'
        return result

    @staticmethod
    def _review_verdict(task,binding):
        texts=[p['text'] for a in task.get('artifacts',[]) for p in a.get('parts',[]) if isinstance(p.get('text'),str)]
        if not texts: raise Blocked('Independent native reviewer has no actual verdict artifact')
        value=texts[-1].strip()
        if value.startswith('```json\n') and value.endswith('```'): value=value[8:-3].strip()
        try: verdict=json.loads(value)
        except ValueError: raise Blocked('Independent review verdict is not structured JSON') from None
        if verdict.get('verdict')!='PASS' or verdict.get('binding')!=binding or verdict.get('ci',{}).get('pipeline_sha')!=binding['head_sha'] or verdict.get('ci',{}).get('pipeline_status')!='success':
            raise Blocked('Independent native PASS and exact-head CI verdict are not proven')
        return verdict

    def _step_review(self,run,observe):
        snapshot=self._pod(run,'read'); binding=snapshot['state'].get('proposal',{}).get('binding')
        if not binding: raise Blocked('No real proposed MR binding')
        message='Independently review the exact MR binding using native knowledge skill and read-only tools. Inspect repository, diff, current incident, exact-head CI and named JUnit tests. Do not merge or approve. Return one JSON object: verdict PASS or FAIL, binding exactly as given, ci:{pipeline_sha,pipeline_status}, test_cases, pending_recovery. Static CI is not live recovery. Binding: '+json.dumps(binding,separators=(',',':'))
        task=self._task(run,'review',observe,message); state=task.get('status',{}).get('state')
        patch={'adapter':{'review_task_id':task['id'],'review_session_id':task['contextId'],'review_state':state}}
        if state in ('TASK_STATE_FAILED','TASK_STATE_CANCELED','TASK_STATE_REJECTED'): raise Blocked('Independent native review failed')
        if state!='TASK_STATE_COMPLETED': return self._result('review','pending','Independent native review is running',patch,'waiting_review')
        self._review_verdict(task,binding)
        control={'action':'record_review','binding':binding,'reviewer_id':self._config(run)['reviewer_id'],'task_id':task['id'],'task_state':'COMPLETED','verdict':'PASS','native_receipt_sha256':digest(task),'reviewed_at':int(self.clock()),'valid_admission':'pass','invalid_admission':'pass'}
        if not snapshot['state'].get('review'):
            self._once(run,'review-record',lambda:self._pod(run,'review',control))
        patch['remedy']={'review':'passed'}
        return self._result('review','completed','Independent native exact-head review passed; dashboard human approval required',patch,'waiting_human')

    @staticmethod
    def _approval_public(value):
        return {'approvalId':value['approval_id'],'headSha':value['binding']['head_sha'],
                'approvedBy':value['principal_id'],'approvedAt':value['approved_at'],
                'expiresAt':value['expires_at'],'state':'approved'}

    def approve(self,run,request_id,head_sha,observe=False):
        from flow_controller import ApprovalConflict, ApprovalUnknown
        with self.lock:
            try:
                state=self._pod(run,'read')['state']
                existing=state.get('flow_dashboard_approval')
                if existing:
                    if existing['binding']['head_sha']!=head_sha: raise Blocked('Approval differs from the displayed head')
                    return self._approval_public(existing)
                if observe: raise Uncertain('Original approval has no runtime readback')
                binding=state.get('proposal',{}).get('binding')
                if not binding or binding['head_sha']!=head_sha: raise Blocked('MR head changed before approval')
                principal=self.settings.get('dashboard_principal_id')
                if principal is None and len(self.settings['human_merger_ids'])==1:
                    principal=self.settings['human_merger_ids'][0]
                if principal not in self.settings['human_merger_ids']: raise Blocked('No configured dashboard human principal')
                now=int(self.clock())
                approval={'approval_id':request_id,'binding':binding,'principal_id':principal,
                          'approved_at':now,'expires_at':now+900}
                private_write(self._workspace(run)/'dashboard-approval-intent.json',approval)
                receipt=self._once(run,'dashboard-approval',lambda:self._pod(run,'approve_dashboard',approval))
                return self._approval_public(receipt)
            except Blocked as error:
                raise ApprovalConflict(str(error)) from None
            except Exception:
                raise ApprovalUnknown('Approval outcome requires readback of the original request') from None

    def _step_await_approval(self,run,observe):
        state=self._pod(run,'read')['state']; approval=state.get('flow_dashboard_approval')
        if not approval:
            return self._result('await_approval','pending','Waiting for human approval in the dashboard',phase='waiting_human')
        if approval['binding']!=state.get('proposal',{}).get('binding') or approval['expires_at']<=self.clock():
            raise Blocked('Dashboard approval is expired or bound to another fix')
        return self._result('await_approval','completed','Exact-head human dashboard approval recorded',
                            {'approval':self._approval_public(approval)},'merging')

    def _step_merge(self,run,observe):
        state=self._pod(run,'read')['state']
        if not state.get('flow_dashboard_approval'): raise Blocked('Dashboard human approval is required before native merge dispatch')
        task=self._task(run,'merge',observe,'MERGE ONLY. A human approved the exact recorded fix in the dashboard. Call merge_dashboard_approved_fix exactly once now. Return its actual result and complete. Never approve, retry a merge, propose a new fix, or claim application recovery. Do not call verify_recovery in this task.')
        status=task.get('status',{}).get('state')
        patch={'merge':{'taskId':task['id'],'taskState':status,'approvalId':state['flow_dashboard_approval']['approval_id']},
               'adapter':{'merge_task_id':task['id'],'merge_session_id':task['contextId']}}
        if status in ('TASK_STATE_FAILED','TASK_STATE_CANCELED','TASK_STATE_REJECTED'): raise Blocked('Native merge task did not complete successfully')
        if status!='TASK_STATE_COMPLETED':
            return self._result('merge','pending','Kagent is merging the dashboard-approved fix',patch,'merging')
        outputs=[]
        for artifact in task.get('artifacts',[]):
            for part in artifact.get('parts',[]):
                data=part.get('data') or {}
                if part.get('metadata',{}).get('kagent.dev/a2a/part-type')=='function_response' and data.get('name')=='merge_dashboard_approved_fix':
                    raw=data.get('response',{}).get('output')
                    if (not isinstance(raw,str) or len(raw)>65536 or not isinstance(data.get('id'),str) or not data['id']):
                        raise Blocked('Native merge response is not bounded structured tool output')
                    outputs.append(json.loads(raw))
        if len(outputs)==1 and outputs[0].get('state')=='unknown' and outputs[0].get('operation')=='flow-dashboard-merge':
            readback=self._pod(run,'dashboard_merge')
            if readback.get('state') not in ('unknown','reconciling'):
                raise Blocked('Native uncertain merge lacks its original runtime intent')
            patch['merge']['status']='readback_pending'
            return self._result('merge','completed','Native merge task completed with an uncertain outcome; observing its original intent without resending',patch,'merging')
        if (len(outputs)!=1 or outputs[0].get('state')!='reconciling'
                or outputs[0].get('approval_id')!=state['flow_dashboard_approval']['approval_id']
                or outputs[0].get('binding')!=state.get('proposal',{}).get('binding')
                or not re.fullmatch(r'[0-9a-f]{40}',outputs[0].get('merge_sha',''))):
            raise Blocked('Completed native task lacks one corroborated merge tool result')
        return self._result('merge','completed','Kagent completed the approved merge tool with actual GitLab readback',patch,'merging')

    def _step_observe_merge(self,run,observe):
        value=self._pod(run,'dashboard_merge')
        if value.get('state') in ('waiting','unknown','waiting_merge'):
            return self._result('observe_merge','pending','Waiting for readback of the original approved native merge',phase='merging')
        if value.get('state')!='reconciling': raise Blocked('Approved native merge receipt did not corroborate exact MR')
        return self._result('observe_merge','completed','Actual dashboard-approved Kagent merge observed',{'merge':{'sha':value['merge_sha'],'mergedBy':value['actor_id'],'status':'merged','approvalId':value['approval_id']}},'reconciling')

    def _step_await_recovery(self,run,observe):
        value=self._pod(run,'recovery_ready')
        if value.get('ready') is not True:
            return self._result('await_recovery','pending','Waiting for exact GitOps revision, healthy policy and live application',phase='reconciling')
        return self._result('await_recovery','completed','Actual GitOps and application readiness observed; beginning a fresh recovery measurement',phase='reconciling')

    def _step_measure_recovery(self,run,observe):
        recorded=self._pod(run,'recovery_window')
        if recorded.get('recorded') is True:
            return self._result('measure_recovery','completed','Existing measured recovery window validated against the current merge and freshness gates',phase='verifying')
        if observe:
            raise Uncertain('Interrupted recovery measurement requires reconciliation of retained physical receipts')
        def collect():
            c=self._config(run)
            initial=self._pod(run,'http')
            state=initial['state']; merged=state.get('merged'); baseline=state.get('flow_baseline')
            if not merged or not baseline: raise Blocked('Approved merge and original UIDs are required before recovery probes')
            if digest(initial['policy']['spec'])!=c['healthy_policy_spec_sha256']: raise Blocked('Flux has not reconciled the exact healthy policy yet')
            policy_before=initial['policy']; raw=[]; groups=[]
            for i in range(3):
                if i: self.sleep(31)
                valid=self._collect(run,'valid'); invalid=self._collect(run,'invalid'); live=self._pod(run,'http'); raw.extend([valid,invalid])
                private_write(self._workspace(run)/('recovery-group-'+str(i)+'.json'),{'valid':valid,'invalid':invalid,'live':live})
                policy=live['policy']; http=live['http']
                if (valid['result']!='admitted' or invalid['result']!='denied' or policy['metadata']['uid']!=baseline['policy_uid'] or live['deployment']['uid']!=baseline['deployment_uid'] or digest(policy['spec'])!=c['healthy_policy_spec_sha256'] or valid['policy_revision']!=merged['merge_sha'] or invalid['policy_revision']!=merged['merge_sha'] or http['status_code']!=c.get('expected_http_status',200) or http['body_sha256']!=c['expected_body_sha256']): raise Blocked('Actual recovery probe group did not satisfy scoped healthy gates')
                groups.append({'observed_at':http['observed_at'],'valid':{'receipt_id':valid['probe_id'],'result':valid['result']},'invalid':{'receipt_id':invalid['probe_id'],'result':invalid['result']},'http':{k:http[k] for k in ('probe_id','status_code','body_sha256')}})
            after=raw[-1]['policy_read_after']; before=raw[0]['policy_read_before']
            keys=('uid','generation','policy_spec_sha256','ready','deleting','enforcement')
            if any(before[k]!=after[k] for k in keys) or before['uid']!=policy_before['metadata']['uid']: raise Blocked('Policy changed across measured recovery window')
            window={'merge_sha':merged['merge_sha'],'deployment_uid':baseline['deployment_uid'],'policy_uid':baseline['policy_uid'],'policy_spec_sha256':c['healthy_policy_spec_sha256'],'started_at':groups[0]['observed_at'],'ended_at':groups[-1]['observed_at'],'observations':groups}
            if not 60<=window['ended_at']-window['started_at']<=120: raise Blocked('Measured recovery window is outside 60 through 120 seconds')
            receipt={'receipt_id':'operator-'+digest(raw)[:32],'run_id':c['run_id'],'incident_id':c['incident_id'],'source':'operator-kubernetes-dry-run','source_receipt_sha256':digest(raw),'merge_sha':merged['merge_sha'],'policy_uid':before['uid'],'generation':before['generation'],'observed_generation':raw[-1]['native_observed_generation'],'policy_spec_sha256':before['policy_spec_sha256'],'observations':[dict({k:p[k] for k in ('probe_id','observed_at','kind','result')},policy_name=c['policy_name'],rule_name=c['rule_name']) for p in raw]}
            if receipt['observed_generation'] is None: receipt.update(observation_method='stable-read-and-admission-probes',policy_read_before=before,policy_read_after=after)
            self._pod(run,'window',{'window':window,'receipt':receipt})
            return window
        self._once(run,'measured-recovery-window',collect)
        return self._result('measure_recovery','completed','Three actual admission and HTTP groups passed over a stable measured window',phase='verifying')

    def _step_verify(self,run,observe):
        state=self._pod(run,'read')['state']
        if not state.get('flow_recovery_window'): raise Blocked('Measured post-merge recovery window is required before native verification')
        task=self._task(run,'verify',observe,'Use your scoped read-only verify_recovery tool exactly once now. Return its actual result and complete. Do not propose, merge, approve, or modify resources. Report missing evidence honestly.')
        binding={'task_id':task['id'],'session_id':task['contextId']}
        if state.get('flow_verification_binding')!=binding:
            self._once(run,'verification-binding',lambda:self._pod(run,'verification_binding',binding))
        patch={'verification':{'taskId':task['id'],'state':task.get('status',{}).get('state')},'adapter':{'verification_task_id':task['id'],'verification_session_id':task['contextId']}}
        if task.get('status',{}).get('state')!='TASK_STATE_COMPLETED':
            if task.get('status',{}).get('state') in ('TASK_STATE_FAILED','TASK_STATE_REJECTED','TASK_STATE_CANCELED'): raise Blocked('Native verification task failed')
            return self._result('verify','pending','Actual native verification is running',patch,'verifying')
        result=self.closure_verifier(run)
        if not result.get('verified'): raise Blocked('Native verification lacks matching actual tool and independent runtime proof')
        patch['verification']['checks']={'verified':True,'evidenceDigest':result['evidence_digest']}
        return self._result('verify','completed','Terminal native tool proof and independent current runtime verification passed',patch,'closing_ticket')

    def closure_verifier(self,run):
        try:
            task=self._task(run,'verify',True)
            if task.get('status',{}).get('state')!='TASK_STATE_COMPLETED': return {'verified':False,'task_id':task['id'],'task_state':task.get('status',{}).get('state'),'evidence_digest':None}
            proof=self._pod(run,'closure_check',task)
            ticket=run.get('data',{}).get('ticket',{})
            if ticket.get('state')=='closed':
                actual=self._gl('/issues/'+str(ticket['iid']))
                proof.update(issue_closed=actual.get('state')=='closed' and actual.get('iid')==ticket['iid'],issue_iid=actual.get('iid'))
            return proof
        except Exception:
            return {'verified':False,'task_id':None,'task_state':None,'evidence_digest':None}

    def _step_close(self,run,observe):
        task=self._task(run,'verify',True)
        if observe:
            result=self._pod(run,'close_observe',task)
            if result.get('state')!='closed': return self._result('close','pending','Awaiting actual verified issue closure readback',phase='closing_ticket')
            ticket=result['ticket']
            actual=self._gl('/issues/'+str(ticket['iid']))
            if actual.get('state')!='closed': raise Blocked('Issue closed readback differs')
        else:
            result=self._pod(run,'close',task)
            if result.get('state')!='closed': raise Uncertain('Original verified issue closure is awaiting readback')
            ticket=result['ticket']
        return self._result('close','completed','Actual GitLab issue closed after corroborated native recovery verification',{'ticket':dict(ticket,closedVerified=True)},'closed')
