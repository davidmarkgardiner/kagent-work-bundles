"""Instrument one fresh synthetic actor on a disposable kind host for a boundary proof."""
import argparse,json,subprocess,threading,time,urllib.request,urllib.error
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--kubeconfig',required=True);p.add_argument('--context',required=True);p.add_argument('--url',required=True);p.add_argument('--namespace',required=True,choices=['secure-byo-kro','secure-byo-hosted']);p.add_argument('--sibling-session',required=True);p.add_argument('--node-container',required=True);p.add_argument('--probe',required=True);p.add_argument('--output',required=True);a=p.parse_args()
out=Path(a.output);out.mkdir(mode=0o700,parents=True,exist_ok=False);k=['kubectl','--kubeconfig',a.kubeconfig,'--context',a.context,'-n',a.namespace]
def dirs():return set(subprocess.check_output(['docker','exec',a.node_container,'find','/var/lib/ate/actors','-mindepth','1','-maxdepth','1','-type','d'],text=True).splitlines())
before=dirs();token=subprocess.check_output(k+['create','token','approved-caller','--audience=secure-byo','--duration=1h'],text=True).strip();native={}
staged='/var/lib/ate/secure-byo-actor-probe'
subprocess.run(['docker','cp',a.probe,a.node_container+':'+staged],check=True,stdout=subprocess.DEVNULL)
def invoke():
 prompt='Synthetic security proof. Load both aks-known-issues and kb-aks-bootstrap. Read references/error-code-map.md and references/oras-pull-unauthorized.md from their respective skills. Call get_demo_status and cite the sources. Explain the bootstrap authorization case with code 212. No Azure actions.'
 req=urllib.request.Request(a.url+'/invoke',json.dumps({'prompt':prompt}).encode(),{'Content-Type':'application/json','Authorization':'Bearer '+token})
 try:
  with urllib.request.urlopen(req,timeout=115) as r:native['body']=json.load(r)
 except Exception as e:native['error']=type(e).__name__
thread=threading.Thread(target=invoke);thread.start();deadline=time.monotonic()+70;proof=None;binding=None
while time.monotonic()<deadline and thread.is_alive():
 for directory in sorted(dirs()-before):
  uid=directory.rsplit('/',1)[1]
  logs=subprocess.check_output(k+['logs','deploy/approved-worker','--since=2m'],text=True)
  names=[]
  for line in logs.splitlines():
   try:
    x=json.loads(line);lab=x.get('labels',{});name=lab.get('ate.actor.name','')
    if lab.get('ate.actor.uid')==uid and name.startswith('session-'):names.append(name)
   except ValueError:pass
  if not names:continue
  session=names[-1].removeprefix('session-');runsc=directory+'/sandbox-assets/gvisor/runsc';root='--root='+directory+'/runsc-state'
  result=subprocess.run(k+['exec','deploy/approved-worker','--',runsc,root,'list','--format=json'],text=True,capture_output=True)
  if result.returncode:continue
  values=json.loads(result.stdout) or [];container=next((x['id'] for x in values if x.get('status')=='running' and x.get('id')=='kagent'),None)
  if not container:continue
  flags=['--bridge','secure-byo.secure-byo-gateway-system.svc.cluster.local:8084','--own-session',session,'--sibling-session',a.sibling_session,'--direct-controller','http://kagent-controller.kagent.svc.cluster.local:8083/','--dedicated-controller','http://secure-byo-native-controller.kagent.svc.cluster.local:8083/','--direct-model','http://flow-gateway.agent-flow-demo.svc.cluster.local:8081/v1/models','--gateway','http://secure-byo.secure-byo-gateway-system.svc.cluster.local:'+('8081' if a.namespace.endswith('kro') else '8080')+'/mcp']
  result=subprocess.run(['docker','exec',a.node_container,'sh','-c','exec 3<"$1"; shift; exec "$@"','sh',staged,runsc,root,'exec','--exec-fd=3',container,'actor-probe']+flags,text=True,capture_output=True,timeout=35)
  (out/'probe-transport.txt').write_text(result.stdout+result.stderr)
  try:
   proof=json.JSONDecoder().raw_decode(result.stdout.lstrip())[0]
   if proof.get('mode')!='actor' or len(proof.get('checks',[]))!=7:raise ValueError('incomplete probe')
   proof['transportExit']=result.returncode
  except ValueError:proof={'passed':False,'error':'ActorProbeProtocol'}
  binding={'session':session,'actorUID':uid};break
 if proof is not None:break
 time.sleep(.2)
thread.join(timeout=120);(out/'native.json').write_text(json.dumps(native,indent=2));(out/'summary.json').write_text(json.dumps({'proof':proof,'binding':binding,'passed':bool(proof and proof.get('passed'))},indent=2));print(json.dumps({'proof':proof,'binding':binding}))
raise SystemExit(0 if proof and proof.get('passed') else 1)
