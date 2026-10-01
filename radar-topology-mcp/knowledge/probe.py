#!/usr/bin/env python3
"""Record real querydoc replies and full MCP response body bytes (no model claims)."""
import argparse,asyncio,json,time
from pathlib import Path
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
async def main():
 bodies=[]
 async def response_hook(response):
  if any(t in response.headers.get('content-type','') for t in ['application/json','text/event-stream']):
   raw=await response.aread()
   try:
    payload=raw.decode()
    if 'text/event-stream' in response.headers.get('content-type',''): payload=next(line[5:].strip() for line in payload.splitlines() if line.startswith('data:'))
    body=json.loads(payload)
    if 'id' in body and ('result' in body or 'error' in body): bodies.append(len(raw))
   except (ValueError,StopIteration): pass
 async with httpx.AsyncClient(event_hooks={'response':[response_hook]}) as http:
  async with streamable_http_client(a.url,http_client=http) as (read,write,_):
   async with ClientSession(read,write) as client:
    await client.initialize();listed=await client.list_tools()
    tool=next(t for t in listed.tools if t.name=='query_documentation')
    cases=[]
    for name,query,version in [
     ('cert','cert-manager HTTP01 challenge pending self-check ingress class','current'),
     ('checkout','checkout-api demo-payments CrashLoopBackOff after configuration rollout','current'),
     ('unrelated','orbital-reactor quantum flux overdrive failure','current'),
     ('wrong-version','cert-manager HTTP01 challenge pending','nonexistent-version')]:
     started=time.monotonic();before=len(bodies)
     result=await client.call_tool('query_documentation',{'queryText':query,'productName':'platform-kb','version':version,'dbName':'platform-kb.db','limit':2})
     cases.append({'case':name,'query':query,'elapsed_seconds':round(time.monotonic()-started,3),'mcp_response_body_bytes':bodies[before:],'result':result.model_dump(mode='json')})
    a.output.write_text(json.dumps({'tool_schema':tool.inputSchema,'cases':cases},indent=2))
    print(json.dumps({'cases':[{'case':c['case'],'bytes':c['mcp_response_body_bytes'],'seconds':c['elapsed_seconds']} for c in cases]}))
asyncio.run(main())
