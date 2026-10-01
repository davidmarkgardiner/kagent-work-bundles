#!/usr/bin/env python3
"""Extract model usage and tool ordering without publishing response content."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('session',type=Path);a=p.parse_args()
x=json.loads(a.session.read_text())['data']['events']; sequence=[];usage=[]
for event in sorted(x,key=lambda e:e['created_at']):
 d=json.loads(event['data']) if isinstance(event['data'],str) else event['data']
 if d.get('UsageMetadata'): usage.append(d['UsageMetadata'])
 for part in (d.get('Content') or {}).get('parts',[]):
  for key in ['functionCall','functionResponse']:
   if part.get(key): sequence.append({'type':key,'tool':part[key]['name']})
responses=[i for i,e in enumerate(sequence) if e=={'type':'functionResponse','tool':'get_neighborhood'}]
queries=[i for i,e in enumerate(sequence) if e=={'type':'functionCall','tool':'query_documentation'}]
print(json.dumps({'sequence':sequence,'radar_completed_before_search':bool(responses and queries and responses[0]<queries[0]),'model_requests':len(usage),'input_tokens':sum(u.get('promptTokenCount',0) for u in usage),'output_tokens':sum(u.get('candidatesTokenCount',0) for u in usage),'per_request_usage':usage},indent=2))
