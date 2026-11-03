"""Discover existing native bindings and stage private lab inputs without printing credentials."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess

p=argparse.ArgumentParser()
p.add_argument('--kubeconfig',required=True);p.add_argument('--context',required=True)
p.add_argument('--output',required=True);p.add_argument('--runtime-image',required=True)
p.add_argument('--source-namespace',default='kagent');p.add_argument('--template',default='hosted-aks-docs-v1-71b1a37b953f')
p.add_argument('--model',default='flow-demo-model');p.add_argument('--harness',default='aks-docs-v1')
a=p.parse_args();out=Path(a.output).resolve()
if out.is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Private output must be outside the source bundle')
out.mkdir(mode=0o700,parents=True,exist_ok=False)
prefix=['kubectl','--kubeconfig',a.kubeconfig,'--context',a.context]
def k(*args):return json.loads(subprocess.check_output(prefix+list(args)+['-o','json'],text=True))
def save(name,data):
 f=out/name;f.write_text(json.dumps(data,indent=2));f.chmod(0o600)
snapshot={'items':[k('-n',a.source_namespace,'get',kind,name) for kind,name in [('agenttemplate',a.template),('modelconfig',a.model),('harness',a.harness)]]}
save('snapshot.json',snapshot)
worker=k('-n',a.source_namespace,'get','pods','-l','ate.dev/worker-pool=kagent-default')['items'][0]
worker_image=worker['status']['containerStatuses'][0]['imageID']
who=k('auth','whoami')['status']['userInfo']['username']
content=[s['source']['oci'] for s in snapshot['items'][0]['spec']['skills']]
tools=[{'mcp':{'server':{'kind':'RemoteMCPServer','name':'approved-mcp'},'tools':['get_demo_status']}}]
settings={'runtimeImage':a.runtime_image,'templateName':a.template,'modelName':a.model,'harnessName':a.harness,
 'upstreamURL':'http://secure-byo-native-controller.kagent.svc.cluster.local:8083',
 'kagentBinary':'/usr/local/bin/kagent','apiURL':'http://secure-byo-native-controller.kagent.svc.cluster.local:8083',
 'gatewayURL':'http://secure-byo-native-controller.kagent.svc.cluster.local:8083','nativeUserID':'secure-byo-lab',
 'centralRouting':True,'gatewayNamespace':'secure-byo-gateway-system',
 'workerPoolApiVersion':'ate.dev/v1alpha1','workerPoolSpec':{'replicas':1,'sandboxClasses':[{'configRef':{'name':'gvisor-default'},'name':'gvisor'}],
 'template':{'serviceAccountName':'approved-worker','resources':{'requests':{'cpu':'10m','memory':'256Mi'},'limits':{'cpu':'1','memory':'1536Mi'}}},'workerImage':worker_image}}
settings['policyConfig']={'namespaces':['secure-byo-hosted','secure-byo-kro'],
 'composerUsers':['system:serviceaccount:secure-byo-hosted:hosted-composer','system:serviceaccount:secure-byo-kro-system:secure-byo-kro'],
 'platformUsers':[who],'nativeControllerUsers':['system:serviceaccount:kagent:kagent-controller','system:serviceaccount:ate-system:ate-controller','system:kube-controller-manager','system:serviceaccount:kube-system:replicaset-controller','system:serviceaccount:kube-system:deployment-controller'],
 'garbageCollectorUsers':['system:kube-controller-manager','system:serviceaccount:kube-system:replicaset-controller','system:serviceaccount:kube-system:deployment-controller','system:serviceaccount:kube-system:generic-garbage-collector'],
 'modelConfig':'approved-model','harness':'approved-harness','contentImages':content,'templateTools':tools,
 'requestKinds':['secure.platform.kagent.dev/v1alpha1/HostedSecureAgent','kro.run/v1alpha1/SecureAgent'],
 'requestEquals':{'profileRef':'secure-readonly-v1'},'workloadServiceAccounts':['secure-byo-runtime','hosted-composer'],
 'workloadImages':[a.runtime_image],'reservedLabelPrefixes':['secure-byo.platform/','ate.dev/'],
 'workerException':{'serviceAccount':'approved-worker','images':[worker_image],'deploymentName':'approved-worker',
 'controllerUsers':['system:serviceaccount:ate-system:ate-controller','system:kube-controller-manager','system:serviceaccount:kube-system:replicaset-controller','system:serviceaccount:kube-system:deployment-controller'],
 'namespaces':['secure-byo-hosted','secure-byo-kro']}}
api=k('-n','default','get','endpoints','kubernetes')
api_cidrs=[v['ip']+'/32' for subset in api['subsets'] for v in subset['addresses']]
api_cidrs.append(k('-n','default','get','service','kubernetes')['spec']['clusterIP']+'/32')
settings['network']={'workerSelector':{'ate.dev/worker-pool':'approved-worker'},'gatewaySelector':{'gateway.networking.k8s.io/gateway-name':'secure-byo'},
 'apiCIDRs':api_cidrs,'nativePorts':[8083],'modelNamespace':'agent-flow-demo','modelPort':8081}
save('settings.json',settings)
model=snapshot['items'][1]['spec'];sec=k('-n',a.source_namespace,'get','secret',model['apiKeySecret'])
secrets=[]
for ns in settings['policyConfig']['namespaces']:
 secrets.append({'apiVersion':'v1','kind':'Secret','metadata':{'name':'secure-byo-model-token','namespace':ns},'type':'Opaque','data':sec['data']})
save('private-secrets.json',{'apiVersion':'v1','kind':'List','items':secrets})
save('jwks.json',json.loads(subprocess.check_output(prefix+['get','--raw','/openid/v1/jwks'],text=True)))
print('Private inputs staged; credentials omitted from output.')
