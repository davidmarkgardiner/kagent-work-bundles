"""Exercise actual Kubernetes/Kyverno admission with allowed and denied controls."""
import argparse,copy,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--kubeconfig',required=True);p.add_argument('--context',required=True);p.add_argument('--profile',required=True);p.add_argument('--output',required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'composition'));from compose import generate
profile=json.load(open(a.profile));ns=profile['namespace'];out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
k=['kubectl','--kubeconfig',a.kubeconfig,'--context',a.context,'-n',ns]
request={'apiVersion':'secure.platform.kagent.dev/v1alpha1','kind':'HostedSecureAgent','metadata':{'name':'admission-proof','namespace':ns},'spec':{'profileRef':profile['name'],'instructions':'Read approved documentation.'}}
objects=generate(profile,request,owner=False);template=next(o for o in objects if o['kind']=='AgentTemplate')
composer='system:serviceaccount:secure-byo-hosted:hosted-composer'
image=next(o for o in objects if o['kind']=='Deployment')['spec']['template']['spec']['containers'][0]['image']
pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':'admission-proof','namespace':ns},'spec':{'serviceAccountName':'secure-byo-runtime','restartPolicy':'Never','securityContext':{'runAsNonRoot':True,'runAsUser':65532},'containers':[{'name':'check','image':image,'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}}}]}}
fixture_user='secure-byo-admission-fixture'
rbac=[{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':{'name':'admission-fixture','namespace':ns},'rules':[{'apiGroups':[''],'resources':['pods','configmaps'],'verbs':['create']},{'apiGroups':['networking.k8s.io'],'resources':['networkpolicies'],'verbs':['create','delete']}]},{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':{'name':'admission-fixture','namespace':ns},'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'admission-fixture'},'subjects':[{'kind':'User','name':fixture_user}]}]
cases=[]
def add(name,o,user,allowed,rule=None):cases.append((name,o,user,allowed,rule))
add('approved-template',template,composer,True)
for label,path,value in [('unapproved-model',['spec','modelConfig','name'],'foreign-model'),('unapproved-content',['spec','skills',0,'source','oci'],'example.invalid/content@sha256:'+'a'*64),('unapproved-tool',['spec','tools',0,'mcp','tools'],['delete_pod'])]:
 o=copy.deepcopy(template);v=o
 for key in path[:-1]:v=v[key]
 v[path[-1]]=value;add(label,o,composer,False,'template-model-and-content')
add('approved-restricted-pod',pod,fixture_user,True)
for label,mutation in [('privileged',lambda o:o['spec']['containers'][0]['securityContext'].update(privileged=True,allowPrivilegeEscalation=True)),('host-network',lambda o:o['spec'].update(hostNetwork=True)),('foreign-account',lambda o:o['spec'].update(serviceAccountName='default')),('extra-capability',lambda o:o['spec']['containers'][0]['securityContext']['capabilities'].update(add=['SYS_ADMIN'])),('spoof-runtime-label',lambda o:o['metadata'].update(labels={'secure-byo.platform/agent':'demo'}))]:
 o=copy.deepcopy(pod);mutation(o);add(label,o,fixture_user,False,'workload-safety-0')
add('self-approval',{'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'admission-proof-approval','namespace':ns},'data':{'approval.json':'{}'}},composer,False,'approval')
add('tenant-allow-all-network',{'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':'admission-proof','namespace':ns},'spec':{'podSelector':{},'policyTypes':['Ingress','Egress'],'ingress':[{}],'egress':[{}]}},fixture_user,False,'platform-owned-scaffolding')
worker_pods=json.loads(subprocess.check_output(k+['get','pods','-l','ate.dev/worker-pool=approved-worker','-o','json'],text=True))['items']
if len(worker_pods)!=1:raise ValueError('Expected one actual approved worker for exception controls')
live_worker=worker_pods[0]
worker_pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':'approved-worker-admission-proof','namespace':ns,
 'ownerReferences':copy.deepcopy(live_worker['metadata']['ownerReferences'])},'spec':copy.deepcopy(live_worker['spec'])}
for reference in worker_pod['metadata']['ownerReferences']:reference.pop('blockOwnerDeletion',None)
worker_controller='system:serviceaccount:kube-system:replicaset-controller'
add('approved-worker-lineage',worker_pod,worker_controller,True)
add('copied-worker-identity',copy.deepcopy(worker_pod),fixture_user,False,'workload-safety-0')
o=copy.deepcopy(worker_pod);o['spec']['containers'][0]['image']='example.invalid/worker@sha256:'+'a'*64
add('changed-worker-image',o,worker_controller,False,'workload-safety-0')
o=copy.deepcopy(worker_pod);o['metadata']['ownerReferences'][0]['name']='unapproved-replicaset'
add('wrong-worker-lineage',o,worker_controller,False,'workload-safety-0')
results=[]
subprocess.run(k+['apply','-f','-'],input=json.dumps({'apiVersion':'v1','kind':'List','items':rbac}),text=True,stdout=subprocess.DEVNULL,check=True)
try:
 for name,obj,user,allowed,rule in cases:
  r=subprocess.run(k+['--as',user,'create','--dry-run=server','-f','-'],input=json.dumps(obj),text=True,capture_output=True)
  detail=(r.stderr+r.stdout)[-5000:];passed=(r.returncode==0)==allowed and (allowed or ('kyverno' in detail and (not rule or rule in detail)))
  results.append({'name':name,'passed':passed,'expectedAllow':allowed,'response':detail});print(name,'PASS' if passed else 'FAIL',flush=True)
finally:
 subprocess.run(k+['delete','rolebinding','admission-fixture','--ignore-not-found'],check=True,stdout=subprocess.DEVNULL)
 subprocess.run(k+['delete','role','admission-fixture','--ignore-not-found'],check=True,stdout=subprocess.DEVNULL)
(out/'summary.json').write_text(json.dumps({'checks':results,'passed':all(r['passed'] for r in results)},indent=2))
raise SystemExit(0 if all(r['passed'] for r in results) else 1)
