"""Propose two exact Substrate credential namespace mappings without widening existing ones."""
import argparse,json,subprocess
from pathlib import Path
import yaml
p=argparse.ArgumentParser();p.add_argument('--kubeconfig',required=True);p.add_argument('--context',required=True);p.add_argument('--output',required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
out=Path(a.output).resolve()
if out.is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Private output must be outside the source bundle')
out.mkdir(mode=0o700,parents=True,exist_ok=False);k=['kubectl','--kubeconfig',a.kubeconfig,'--context',a.context,'-n','ate-system']
cm=json.loads(subprocess.check_output(k+['get','cm','k8s-credential-provider-namespace-policy','-o','json'],text=True));(out/'before.json').write_text(json.dumps(cm,indent=2))
value=yaml.safe_load(cm['data']['namespace-policy.yaml'])
for ns in ('secure-byo-hosted','secure-byo-kro'):
 matches=[v for v in value['policies'] if v['atespace']==ns]
 if len(matches)>1 or matches and matches[0].get('allowedNamespaces')!=[ns]:raise ValueError('Conflicting existing namespace authority')
 if not matches:value['policies'].append({'atespace':ns,'allowedNamespaces':[ns]})
proposal={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':cm['metadata']['name'],'namespace':'ate-system'},'data':dict(cm['data'],**{'namespace-policy.yaml':yaml.safe_dump(value)})}
path=out/'proposal.json';path.write_text(json.dumps(proposal,indent=2))
if a.apply:
 subprocess.run(k+['apply','-f',str(path)],check=True)
 subprocess.run(k+['rollout','restart','deploy/k8s-credential-provider'],check=True)
 subprocess.run(k+['rollout','status','deploy/k8s-credential-provider','--timeout=50s'],check=True)
print(json.dumps({'applied':a.apply,'mappings':['secure-byo-hosted->secure-byo-hosted','secure-byo-kro->secure-byo-kro']}))
