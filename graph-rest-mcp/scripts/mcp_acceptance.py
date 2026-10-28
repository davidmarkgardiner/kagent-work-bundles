#!/usr/bin/env python3
"""Exercise a running MCP/REST chain and emit only sanitized receipts."""
import argparse
import asyncio
import json
import logging
import pathlib
import time
import uuid

from fastmcp import Client

TOOL = 'get_graph_context'


async def run(url):
    records = []
    cases = [('production', 'Show production workload compliance relationships', 10, 'supported', 'production'), ('development', 'Show development workload compliance relationships', 10, 'supported', 'development'), ('truncated', 'production compliance', 3, 'supported', 'production'), ('unsupported', 'What is the weather?', 10, 'unsupported', None), ('ambiguous', 'production and development compliance', 10, 'ambiguous', None), ('sql-denied', 'SELECT * FROM production workloads', 10, 'unsupported', 'production')]
    async with Client(url) as client:
        tools = await client.list_tools()
        names = [t.name for t in tools]
        discovery_ok = names == [TOOL] and tools[0].annotations.read_only_hint is True and tools[0].annotations.destructive_hint is False
        for name, query, size, status, environment in cases:
            start = time.monotonic()
            record = {'request_identifier': 'mcp-' + name + '-' + uuid.uuid4().hex[:12], 'agent_name': 'direct-mcp-client', 'expected_tool_names': [TOOL], 'actual_tool_names': [], 'completion_status': 'FAIL', 'elapsed_seconds': 0, 'result_counts': {}, 'source_scope_summary': None, 'error_category': 'contract_mismatch'}
            try:
                result = await client.call_tool(TOOL, {'query': query, 'context_size': size})
                record['actual_tool_names'] = [TOOL]
                c = result.structured_content
                nodes = [*c['entities'], *c['views']]
                ids = {n['id'] for n in nodes}
                good = discovery_ok and not result.is_error and c['status'] == status and c['source'] == 'fixture-v1'
                good &= c['scope']['result_count'] == len(nodes) and len(nodes) <= size
                good &= all(e['source'] in ids and e['target'] in ids for e in c['relationships'])
                good &= len(json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': {'content': [b.model_dump(mode='json') for b in result.content], 'structuredContent': c, 'isError': result.is_error}}).encode()) <= 65536
                if status == 'supported':
                    good &= c['scope']['environments'] == [environment] and len(nodes) == size and c['truncated'] == (size < 10)
                    prefix = 'prod' if environment == 'production' else 'dev'
                    entities = {n['id']: n for n in c['entities']}
                    good &= entities[prefix + ':checkout']['compliance'] == ('compliant' if prefix == 'prod' else 'non_compliant')
                    if size == 10:
                        good &= len(c['entities']) == 8 and len(c['views']) == 2 and len(c['relationships']) == 11
                        good &= entities[prefix + ':metrics']['compliance'] == ('non_compliant' if prefix == 'prod' else 'compliant')
                else:
                    good &= not nodes and not c['relationships'] and bool(c['limitations'])
                record.update(result_counts={'entities': len(c['entities']), 'views': len(c['views']), 'relationships': len(c['relationships'])}, source_scope_summary={'source': 'fixture-v1', 'environments': c['scope']['environments'], 'groupings': c['scope']['groupings'], 'complete': c['scope']['complete']}, completion_status='PASS' if good else 'FAIL', error_category='none' if good else 'contract_mismatch')
            except Exception:
                record['error_category'] = 'mcp_transport_or_contract'
            record['elapsed_seconds'] = round(time.monotonic() - start, 3)
            records.append(record)
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000/mcp')
    parser.add_argument('--output')
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    records = asyncio.run(run(args.url))
    text = json.dumps(records, indent=2) + '\n'
    if args.output:
        pathlib.Path(args.output).write_text(text)
    print(text, end='')
    raise SystemExit(0 if records and all(r['completion_status'] == 'PASS' for r in records) else 1)


if __name__ == '__main__':
    main()
