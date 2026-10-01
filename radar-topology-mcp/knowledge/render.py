#!/usr/bin/env python3
"""Render only the Agent delta; preserve existing KB deployment and credentials."""
import argparse,json,re
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--config',type=Path,required=True)
p.add_argument('--runtime',choices=['go','legacy'],default='go')
a=p.parse_args()
template=Path(__file__).with_name('agent.yaml.tmpl').read_text()
config=json.loads(a.config.read_text())
required=set(re.findall(r'\{\{([A-Z_]+)\}\}',template))
if set(config)!=required: p.error('config keys must exactly match '+','.join(sorted(required)))
for k,v in config.items():
 if not isinstance(v,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,252}',v): p.error('invalid value for '+k)
 if k in {'KAGENT_NAMESPACE','MODEL_CONFIG','RADAR_MCP_NAME','KB_MCP_NAME'} and not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,61}[a-z0-9]|[a-z0-9]',v): p.error('invalid Kubernetes name for '+k)
 template=template.replace('{{'+k+'}}',v)
if a.runtime=='legacy': template=template.replace('    runtime: go\n','')
print(template,end='')
