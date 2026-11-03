"""Run fresh authorization and native invocation probes without retaining bearer tokens."""
import argparse,copy,json,subprocess,time,urllib.request,urllib.error
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--kubeconfig',required=True);p.add_argument('--context',required=True);p.add_argument('--namespace',required=True,choices=['secure-byo-hosted','secure-byo-kro']);p.add_argument('--url',required=True);p.add_argument('--output',required=True);p.add_argument('--invoke',action='store_true');a=p.parse_args()
out=Path(a.output);out.mkdir(mode=0o700,parents=True,exist_ok=False)
k=['kubectl','--kubeconfig',a.kubeconfig,'--context',a.context,'-n',a.namespace]
checks=[]
def token(sa,audience='secure-byo'):return subprocess.check_output(k+['create','token',sa,'--audience='+audience,'--duration=1h'],text=True).strip()
caller,worker,sibling=token('approved-caller'),token('approved-worker'),token('sibling-caller')
def request(path,body,auth=None):
 headers={'Content-Type':'application/json'}
 if auth:headers['Authorization']='Bearer '+auth
 req=urllib.request.Request(a.url.rstrip('/')+path,data=json.dumps(body).encode(),headers=headers)
 try:
  with urllib.request.urlopen(req,timeout=115) as r:return r.status,json.loads(r.read(1048577))
 except urllib.error.HTTPError as e:
  data=e.read(65536).decode();
  try:data=json.loads(data)
  except ValueError: data={'error':data[:500]}
  return e.code,data

def check(name,condition,details=None):
 checks.append({'name':name,'passed':bool(condition),'details':details});print(name, 'PASS' if condition else 'FAIL',flush=True)
def mcp(method,params={}):return {'jsonrpc':'2.0','id':1,'method':method,'params':params}
status,witness=request('/witness',{},caller);check('authenticated-witness',status==200,{'http':status})
before=witness.get('counters',witness)
for name,path,body,auth,expected in [
 ('missing-token','/mcp',mcp('tools/list'),None,401),
 ('wrong-audience','/mcp',mcp('tools/list'),token('approved-worker','wrong-audience'),401),
 ('sibling-identity','/mcp',mcp('tools/list'),sibling,403),
 ('caller-cannot-use-runtime-token-lane','/mcp',mcp('tools/list'),caller,403),
 ('runtime-cannot-invoke-agent','/invoke',{'prompt':'test'},worker,403),
 ('session-api-denied','/sessions',{},caller,404)]:
 st,body=request(path,body,auth);check(name,st==expected,{'http':st})
st,body=request('/mcp',mcp('tools/call',{'name':'delete_pod','arguments':{}}),worker)
check('forbidden-tool',st==200 and 'error' in body,{'http':st})
st,body=request('/v1/chat/completions',{'model':'unapproved','messages':[]},worker)
check('unapproved-model',st==400,{'http':st})
_,after=request('/witness',{},caller);after=after.get('counters',after)
check('denials-no-dispatch',before.get('authorizedMcpCalls',0)==after.get('authorizedMcpCalls',0) and before.get('authorizedModelCalls',0)==after.get('authorizedModelCalls',0),{'before':before,'after':after})
st,body=request('/mcp',mcp('tools/list'),worker)
check('allowed-tool-discovery',st==200 and [v['name'] for v in body.get('result',{}).get('tools',[])]==['get_demo_status'],{'http':st})
st,body=request('/mcp',mcp('tools/call',{'name':'get_demo_status','arguments':{}}),worker)
check('allowed-tool-call',st==200 and body.get('result',{}).get('isError') is False,{'http':st})
_,after=request('/witness',{},caller);after=after.get('counters',after)
check('allowed-call-backend-witness',after.get('authorizedMcpCalls',0)==before.get('authorizedMcpCalls',0)+1,after)
cm=json.loads(subprocess.check_output(k+['get','cm','demo-approval','-o','json'],text=True))
record=json.loads(cm['data']['approval.json'])
def publish(state):
 value=copy.deepcopy(cm);value.pop('metadata',None);value['metadata']={'name':'demo-approval','namespace':a.namespace};r=copy.deepcopy(record);r['state']=state;value['data']['approval.json']=json.dumps(r)
 subprocess.run(k+['apply','-f','-'],input=json.dumps(value),text=True,check=True,stdout=subprocess.DEVNULL)
try:
 publish('Revoked');st,_=request('/mcp',mcp('tools/list'),worker);check('revoked-existing-token-mcp',st==403,{'http':st})
 st,_=request('/invoke',{'prompt':'test'},caller);check('revoked-existing-token-invoke',st==403,{'http':st})
finally:publish('Active')
if a.invoke:
 prompt='Synthetic documentation case only. Load both aks-known-issues and kb-aks-bootstrap. Read references/error-code-map.md from aks-known-issues and references/oras-pull-unauthorized.md from kb-aks-bootstrap. Call get_demo_status. Explain OrasPullUnauthorizedVMExtensionError exit 212 using the supplied documents. Cite sources and report the MCP status. No Azure actions.'
 st,result=request('/invoke',{'prompt':prompt},caller)
 (out/'native-invocation.json').write_text(json.dumps(result,indent=2))
 task=result.get('task',{})
 calls=[];responses=[]
 for message in [*task.get('history',[]),*task.get('artifacts',[])]:
  for part in message.get('parts',[]):
   tag=part.get('metadata',{}).get('kagent.dev/a2a/part-type')
   if tag=='function_call':calls.append(part.get('data',{}))
   if tag=='function_response':responses.append(part.get('data',{}))
 check('native-completed',st==200 and task.get('status',{}).get('state')=='TASK_STATE_COMPLETED',{'http':st})
 for tool in ('load_skill','load_skill_resource','get_demo_status'):
  matching=[c for c in calls if c.get('name','').endswith(tool)]
  matching_results=[r for r in responses if r.get('name','').endswith(tool)]
  check('native-used-'+tool,bool(matching) and bool(matching_results),{'calls':len(matching),'results':len(matching_results)})
 returned=json.dumps(responses)
 check('native-loaded-document-evidence','AKS-KB-ORAS-212-R1' in returned)
 check('native-returned-mcp-evidence','synthetic-ready' in returned)
 (out/'tool-evidence.json').write_text(json.dumps({'calls':calls,'responses':responses},indent=2))
summary={'namespace':a.namespace,'checks':checks,'passed':all(c['passed'] for c in checks)}
(out/'summary.json').write_text(json.dumps(summary,indent=2))
raise SystemExit(0 if summary['passed'] else 1)
