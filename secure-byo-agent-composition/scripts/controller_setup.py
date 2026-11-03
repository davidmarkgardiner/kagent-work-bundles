"""Render namespace-isolated native controller ownership before optional lab application."""
import argparse,copy,hashlib,json,subprocess
from pathlib import Path
import yaml
p=argparse.ArgumentParser();p.add_argument('--kubeconfig',required=True);p.add_argument('--context',required=True);p.add_argument('--namespace',default='kagent');p.add_argument('--deployment',default='kagent-controller');p.add_argument('--output',required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
out=Path(a.output).resolve()
if out.is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Private output must be outside the source bundle')
out.mkdir(parents=True,mode=0o700,exist_ok=False)
k=['kubectl','--kubeconfig',a.kubeconfig,'--context',a.context]
def get(*args):return json.loads(subprocess.check_output(k+list(args)+['-o','json'],text=True))
def clean(o):return {'apiVersion':o['apiVersion'],'kind':o['kind'],'metadata':{'name':o['metadata']['name'],'namespace':o['metadata']['namespace']},**{v:copy.deepcopy(o[v]) for v in ('spec','data') if v in o}}
def save(name,o):f=out/name;f.write_text(json.dumps(o,indent=2));f.chmod(0o600)
original=get('-n',a.namespace,'get','deployment',a.deployment);cm=get('-n',a.namespace,'get','cm',a.deployment)
save('original-deployment.json',original);save('original-config.json',cm)
config=yaml.safe_load(cm['data']['controller.yaml']);owned=['secure-byo-hosted','secure-byo-kro']
existing=config['kubernetes'].get('watchNamespaces',[])
if existing:retained=sorted(set(existing)-set(owned))
else:
 resources=get('get','agents,agenttemplates,harnesses,modelconfigs,remotemcpservers,egresspolicies','-A')
 retained=sorted({o['metadata']['namespace'] for o in resources['items']}-set(owned))
if a.namespace not in retained:retained.append(a.namespace)
old=clean(cm);old_cfg=copy.deepcopy(config);old_cfg['kubernetes']['watchNamespaces']=retained;old['data']['controller.yaml']=yaml.safe_dump(old_cfg)
new_cfg=copy.deepcopy(config);new_cfg['kubernetes']['watchNamespaces']=owned
new_cfg['kubernetes']['leaderElection']=False
new_cfg['database']['schema']='secure_byo'
api='http://secure-byo-native-controller.'+a.namespace+'.svc.cluster.local:8083'
new_cfg['gateway']['publicUrl']=api
new_cfg['runtimeDefaults']['controlPlaneUrl']='http://secure-byo.secure-byo-gateway-system.svc.cluster.local:8084'
new_cfg['runtimeDefaults']['gatewayUrl']=api
new_cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'secure-byo-native-controller','namespace':a.namespace},'data':{'controller.yaml':yaml.safe_dump(new_cfg)}}
new=clean(original);new['metadata']['name']='secure-byo-native-controller';new['spec']['replicas']=1;new['spec']['strategy']={'type':'Recreate'}
new['spec']['selector']={'matchLabels':{'app':'secure-byo-native-controller'}}
template=new['spec']['template'];template['metadata']['labels']={'app':'secure-byo-native-controller'}
template['metadata'].setdefault('annotations',{})['secure-byo.platform/config-sha256']=hashlib.sha256(new_cm['data']['controller.yaml'].encode()).hexdigest()
for volume in template['spec'].get('volumes',[]):
 if volume.get('configMap',{}).get('name')==a.deployment:volume['configMap']['name']='secure-byo-native-controller'
service={'apiVersion':'v1','kind':'Service','metadata':{'name':'secure-byo-native-controller','namespace':a.namespace},'spec':{'selector':{'app':'secure-byo-native-controller'},'ports':[{'name':'grpc','port':8083,'targetPort':8083,'appProtocol':'kubernetes.io/h2c'}]}}
new_list={'apiVersion':'v1','kind':'List','items':[new_cm,new,service]}
save('existing-controller-config.json',old);save('dedicated-controller.json',new_list)
if a.apply:
 subprocess.run(k+['apply','-f',str(out/'existing-controller-config.json')],check=True)
 subprocess.run(k+['-n',a.namespace,'rollout','restart','deployment/'+a.deployment],check=True)
 subprocess.run(k+['-n',a.namespace,'rollout','status','deployment/'+a.deployment,'--timeout=55s'],check=True)
 subprocess.run(k+['apply','-f',str(out/'dedicated-controller.json')],check=True)
 subprocess.run(k+['-n',a.namespace,'rollout','status','deployment/secure-byo-native-controller','--timeout=55s'],check=True)
print(json.dumps({'existingOwnership':retained,'dedicatedOwnership':owned,'applied':a.apply}))
