"""Render the lab-only template with the selected cluster's kube-system UID."""
import json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent
context=sys.argv[1] if len(sys.argv)>1 else 'kind-namespace-health'
uid=json.loads(subprocess.check_output(['kubectl','--context',context,'get','namespace','kube-system','-o','json']))['metadata']['uid']
policy=(root/'policy.example.json').read_text().strip()
template=(root/'manifests/assessor.template.yaml').read_text()
# JSON encoded as a YAML single-quoted scalar. None of the policy values may inject YAML quotes.
if "'" in policy:raise SystemExit('single quote in policy is unsupported by the safe renderer')
out=template.replace('{{CLUSTER_UID}}',uid).replace("'{{POLICY_JSON}}'", "'"+policy.replace('\n','')+"'")
if '{{' in out:raise SystemExit('unrendered placeholder')
Path(sys.argv[2] if len(sys.argv)>2 else '/tmp/namespace-health-lab.yaml').write_text(out)
