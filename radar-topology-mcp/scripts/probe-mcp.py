#!/usr/bin/env python3
"""Make one bounded neighborhood query; prints summary, never full object bodies."""
import argparse
import json
import urllib.error
import urllib.request

p = argparse.ArgumentParser()
p.add_argument('--url', default='http://127.0.0.1:19280/mcp-readonly')
p.add_argument('--namespace', required=True)
p.add_argument('--kind', default='Service')
p.add_argument('--name', required=True)
a = p.parse_args()
if not a.url.rstrip('/').endswith('/mcp-readonly'):
    p.error('Use Radar /mcp-readonly')
session = None
sequence = 0

def send(method, params, notification=False):
    global session, sequence
    sequence += 1
    payload = {'jsonrpc': '2.0', 'method': method, 'params': params}
    if not notification:
        payload['id'] = sequence
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
    if session:
        headers['Mcp-Session-Id'] = session
        headers['MCP-Protocol-Version'] = '2025-03-26'
    request = urllib.request.Request(a.url, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        session = response.headers.get('Mcp-Session-Id') or session
        body = response.read().decode()
    if notification:
        return None
    events = [line[6:] for line in body.splitlines() if line.startswith('data: ')]
    result = json.loads(events[-1] if events else body)
    if 'error' in result:
        raise RuntimeError(result['error'])
    return result['result']

try:
    initial = send('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {}, 'clientInfo': {'name': 'work-topology-probe', 'version': '1'}})
    send('notifications/initialized', {}, notification=True)
    tools = send('tools/list', {})['tools']
    names = {t['name'] for t in tools}
    if not {'get_neighborhood', 'get_topology'} <= names:
        raise RuntimeError('Required topology tools missing')
    if any(t.get('annotations', {}).get('readOnlyHint') is not True for t in tools):
        raise RuntimeError('Catalog contains a tool without readOnlyHint; inspect the server version')
    result = send('tools/call', {'name': 'get_neighborhood', 'arguments': {'kind': a.kind, 'namespace': a.namespace, 'name': a.name, 'hops': 1, 'max_nodes': 10}})
    if result.get('isError'):
        raise RuntimeError('Neighborhood tool returned an error')
    blocks = [c['text'] for c in result.get('content', []) if c.get('type') == 'text']
    if len(blocks) != 1:
        raise RuntimeError('Unexpected tool result shape')
    graph = json.loads(blocks[0])
    subgraph = graph['subgraph']
    if not subgraph['nodes']:
        raise RuntimeError('No nodes: confirm resource identity, scope, and permissions')
    if len(subgraph['nodes']) > 10:
        raise RuntimeError('Neighborhood exceeded requested node budget')
    print(json.dumps({'server': initial['serverInfo'], 'read_only_tools': len(tools), 'root': graph['root'], 'nodes': len(subgraph['nodes']), 'edges': len(subgraph['edges']), 'edge_types': sorted({e['type'] for e in subgraph['edges']}), 'truncated': graph.get('truncated'), 'scope': {k: graph[k] for k in ('partialScope', 'scopeNamespaces', 'accessDenied') if k in graph}}, indent=2))
finally:
    if session:
        try:
            urllib.request.urlopen(urllib.request.Request(a.url, method='DELETE', headers={'Mcp-Session-Id': session}), timeout=5).close()
        except (urllib.error.URLError, TimeoutError):
            pass
