"""Observe real Pod traffic with a reachable gateway as a positive control."""
import argparse,json,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--kubeconfig',required=True);p.add_argument('--context',required=True);p.add_argument('--image',required=True);p.add_argument('--output',required=True);p.add_argument('--worker-probe',default='/var/lib/ate/secure-byo-network-probe');a=p.parse_args()
out=Path(a.output);out.mkdir(parents=True,exist_ok=False);k=['kubectl','--kubeconfig',a.kubeconfig,'--context',a.context]
checks=[]
probe='''import json,urllib.request,urllib.error
urls=json.loads(__import__('os').environ['URLS']);out={}
for key,url in urls.items():
 try:
  r=urllib.request.urlopen(url,timeout=2);out[key]=r.status
 except urllib.error.HTTPError as e:out[key]=e.code
 except Exception:out[key]='blocked'
print(json.dumps(out))
'''
subprocess.run(k+['create','namespace','secure-byo-rogue'],stdout=subprocess.DEVNULL,check=True)
try:
 for ns in ('secure-byo-rogue','secure-byo-hosted','secure-byo-kro'):
  worker=ns!='secure-byo-rogue';lane='kro' if ns.endswith('kro') else 'hosted';target='secure-byo-'+lane
  urls={'gateway':'http://secure-byo.secure-byo-gateway-system.svc.cluster.local:'+str(8081 if lane=='kro' else 8080)+'/mcp','controller':'http://kagent-controller.kagent.svc.cluster.local:8083/','dedicated-controller':'http://secure-byo-native-controller.kagent.svc.cluster.local:8083/','frontdoor':'http://demo-frontdoor.'+target+'.svc.cluster.local:8080/healthz'}
  if worker:urls['direct-model']='http://flow-gateway.agent-flow-demo.svc.cluster.local:8081/v1/models'
  if worker:
   args=[]
   for key,url in urls.items():args.extend([key,url])
   raw=subprocess.check_output(k+['-n',ns,'exec','deploy/approved-worker','--',a.worker_probe]+args,text=True)
   result=json.loads(raw)
  else:
   obj={'apiVersion':'v1','kind':'Pod','metadata':{'name':'secure-byo-network-proof','namespace':ns},'spec':{'restartPolicy':'Never','automountServiceAccountToken':False,'securityContext':{'runAsNonRoot':True,'runAsUser':65532},'containers':[{'name':'probe','image':a.image,'command':['python3','-c',probe],'env':[{'name':'URLS','value':json.dumps(urls)}],'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}}}]}}
   subprocess.run(k+['create','-f','-'],input=json.dumps(obj),text=True,check=True,stdout=subprocess.DEVNULL)
   try:
    deadline=time.monotonic()+50
    while time.monotonic()<deadline:
     status=json.loads(subprocess.check_output(k+['-n',ns,'get','pod','secure-byo-network-proof','-o','json'],text=True))['status']['phase']
     if status in ('Succeeded','Failed'):break
     time.sleep(1)
    result=json.loads(subprocess.check_output(k+['-n',ns,'logs','secure-byo-network-proof'],text=True))
   finally:subprocess.run(k+['-n',ns,'delete','pod','secure-byo-network-proof','--ignore-not-found'],stdout=subprocess.DEVNULL,check=True)
  expected={'gateway':401,'controller':'blocked','dedicated-controller':'blocked','frontdoor':200 if worker else 'blocked'}
  if worker:expected['direct-model']='blocked'
  checks.append({'namespace':ns,'observed':result,'expected':expected,'passed':result==expected});print(ns,checks[-1]['passed'],flush=True)
finally:subprocess.run(k+['delete','namespace','secure-byo-rogue','--wait=false'],stdout=subprocess.DEVNULL,check=True)
summary={'checks':checks,'passed':all(c['passed'] for c in checks),'boundary':'Pod network witnesses; actor tunnel requires separate evidence'}
(out/'summary.json').write_text(json.dumps(summary,indent=2));raise SystemExit(0 if summary['passed'] else 1)
