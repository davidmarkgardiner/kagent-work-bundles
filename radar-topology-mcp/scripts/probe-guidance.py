#!/usr/bin/env python3
"""Exercise real HTTP MCP envelopes and identity/error boundaries. No model call."""
import argparse
import asyncio
import json
import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

p = argparse.ArgumentParser()
p.add_argument('--url', default='http://127.0.0.1:9290/mcp')
p.add_argument('--cluster', default='radar-lab')
p.add_argument('--namespace', default='cert-manager')
p.add_argument('--name', default='cert-manager')
a = p.parse_args()


async def main():
    target = dict(cluster=a.cluster, namespace=a.namespace, kind='Deployment', name=a.name)
    sizes = []

    async def capture(response):
        if response.request.method != 'POST':
            return
        request = json.loads(response.request.content)
        if request.get('method') == 'tools/call':
            assert 'application/json' in response.headers.get('content-type', ''), 'Expected bounded JSON response'
            raw = await response.aread()
            sizes.append(len(raw))
            assert len(raw) <= 16384, 'Complete MCP JSON-RPC response exceeded 16 KiB budget'

    def client_factory(headers=None, timeout=None, auth=None):
        return httpx.AsyncClient(headers=headers, timeout=timeout or 30, auth=auth,
                                 event_hooks={'response': [capture]})

    async with streamablehttp_client(a.url, httpx_client_factory=client_factory) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            catalog = await session.list_tools()
            assert {t.name for t in catalog.tools} == {'find_guidance', 'read_guidance'}
            assert all(t.annotations.readOnlyHint for t in catalog.tools)
            assert all(set(t.inputSchema['properties']['kind']['enum']) ==
                       {'Deployment', 'StatefulSet', 'DaemonSet', 'CronJob'}
                       for t in catalog.tools)

            async def call(name, args):
                result = await session.call_tool(name, args)
                return result

            found = await call('find_guidance', target)
            assert not found.isError
            data = json.loads(found.content[0].text)
            assert data['status'] == 'matched' and not data['truncated']
            for reference in data['references']:
                read_result = await call('read_guidance', dict(target, reference_id=reference['id']))
                assert not read_result.isError
                assert json.loads(read_result.content[0].text)['status'] == 'ok'
            missing = await call('find_guidance', dict(target, name='unbound-workload'))
            assert json.loads(missing.content[0].text)['status'] == 'no_binding'
            wrong_scope = await call('read_guidance', dict(target, namespace='unapproved', reference_id=data['references'][0]['id']))
            assert json.loads(wrong_scope.content[0].text)['status'] == 'not_bound'
            transient = await call('find_guidance', dict(target, kind='Pod', name='cert-manager-random-pod'))
            assert transient.isError
            print(json.dumps({'transport': 'Streamable HTTP', 'tools': 2,
                              'checks': ['bound references read', 'no binding', 'wrong scope denied', 'Pod rejected'],
                              'complete_jsonrpc_response_bytes_per_call': sizes,
                              'cumulative_jsonrpc_response_bytes': sum(sizes),
                              'model_calls': 0, 'agent_integration': 'not tested'}, indent=2))


asyncio.run(main())
