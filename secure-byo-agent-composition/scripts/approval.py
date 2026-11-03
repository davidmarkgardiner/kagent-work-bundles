"""Publish an explicitly requested lab approval from observed object identities."""
import argparse,base64,datetime as dt,hashlib,json,subprocess
p=argparse.ArgumentParser();p.add_argument('--kubeconfig',required=True);p.add_argument('--context',required=True);p.add_argument('--namespace',required=True,choices=['secure-byo-hosted','secure-byo-kro']);p.add_argument('--name',default='demo');p.add_argument('--state',required=True,choices=['Active','Revoked','Expired']);a=p.parse_args()
k=['kubectl','--kubeconfig',a.kubeconfig,'--context',a.context,'-n',a.namespace]
def get(kind,name):return json.loads(subprocess.check_output(k+['get',kind,name,'-o','json'],text=True))
def apply(o):subprocess.run(k+['apply','-f','-'],input=json.dumps(o),text=True,stdout=subprocess.DEVNULL,check=True)
request=get('hostedsecureagent' if a.namespace.endswith('hosted') else 'secureagent',a.name)
agent=get('agent',a.name)
if request['metadata'].get('deletionTimestamp'):raise ValueError('DeletingRequest')
users={}
for sa in ('approved-caller','approved-worker'):
 users['system:serviceaccount:'+a.namespace+':'+sa]=get('serviceaccount',sa)['metadata']['uid']
expiry=dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=-5 if a.state=='Expired' else 14400)
record={'state':'Active' if a.state=='Expired' else a.state,'expiresAt':expiry.isoformat(),'requestUID':request['metadata']['uid'],'agentUID':agent['metadata']['uid'],
 'agentSpecSha256':hashlib.sha256(json.dumps(agent['spec'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
 'callerUIDs':users,'callers':{'invoke':[u for u in users if u.endswith(':approved-caller')],'mcp':[u for u in users if u.endswith(':approved-worker')]}}
template=get('agenttemplate',agent['spec']['template']['ref']['name'])
deps=[('agenttemplates',template['metadata']['name']),('harnesses',agent['spec']['harnessRef']['name']),('modelconfigs',template['spec']['modelConfig']['name']),('remotemcpservers','approved-mcp')]
record['dependencies']=[]
for plural,name in deps:
 value=get(plural,name);record['dependencies'].append({'apiVersion':'api.kagent.dev/v1alpha3','plural':plural,'name':name,'uid':value['metadata']['uid'],'specSha256':hashlib.sha256(json.dumps(value['spec'],sort_keys=True,separators=(',',':')).encode()).hexdigest()})
if a.state=='Active':
 token=subprocess.check_output(k+['create','token','approved-worker','--audience=secure-byo','--duration=4h'],text=True).strip()
 apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'secure-byo-mcp-token','namespace':a.namespace},'type':'Opaque','stringData':{'token':token,'Authorization':'Bearer '+token}})
apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':a.name+'-approval','namespace':a.namespace},'data':{'approval.json':json.dumps(record)}})
print(json.dumps({'state':a.state,'namespace':a.namespace,'requestUID':record['requestUID'],'agentUID':record['agentUID']}))
