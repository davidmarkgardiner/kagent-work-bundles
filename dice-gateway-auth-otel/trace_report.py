"""Prove received gateway, runtime and MCP parent links for one native task."""
import argparse
import base64
import json
from pathlib import Path


def identifier(value, length):
    if len(value) == length and all(c in '0123456789abcdef' for c in value):
        return value
    return base64.b64decode(value, validate=True).hex()


def attributes(values):
    return {a['key']: next(iter(a['value'].values())) for a in values}


def execution_ids(value):
    found = set()
    if isinstance(value, dict):
        if 'executionId' in value:
            found.add(value['executionId'])
        for child in value.values():
            found.update(execution_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(execution_ids(child))
    elif isinstance(value, str) and value.startswith('{') and len(value) <= 4096:
        try:
            found.update(execution_ids(json.loads(value)))
        except ValueError:
            pass
    return found


def report(trace, native, gateway='agentgateway', agent='dice_lifecycle_recording', mcp='dice-status-mcp'):
    if 'body' in native:
        native = json.loads(native['body'])
    task = native['result']
    if task.get('status', {}).get('state') != 'completed':
        raise ValueError('Native task is not completed.')
    calls, results = {}, {}
    for message in task.get('history', []):
        if message.get('role') != 'agent':
            continue
        for part in message.get('parts', []):
            data = part.get('data', {})
            if part.get('kind') != 'data' or data.get('name') != 'get_demo_status':
                continue
            record_type = part.get('metadata', {}).get('kagent_type')
            if record_type == 'function_call' and data.get('args') == {}:
                calls[data['id']] = data
            if record_type == 'function_response' and data.get('response', {}).get('isError') is False:
                results[data['id']] = execution_ids(data['response'])
    if len(calls) != 1 or set(calls) != set(results):
        raise ValueError('Require one matched native get_demo_status call and successful result.')
    expected_executions = results[next(iter(calls))]
    spans = {}
    for batch in trace.get('batches', trace.get('resourceSpans', [])):
        service = attributes(batch['resource'].get('attributes', [])).get('service.name')
        for scope in batch.get('scopeSpans', []):
            for span in scope.get('spans', []):
                span_id = identifier(span['spanId'], 16)
                spans[span_id] = {
                    'id': span_id, 'trace': identifier(span['traceId'], 32), 'service': service,
                    'parent': identifier(span['parentSpanId'], 16) if span.get('parentSpanId') else '',
                    'attributes': attributes(span.get('attributes', [])), 'status': span.get('status', {}),
                    'kind': span.get('kind')}
    if not spans or len({s['trace'] for s in spans.values()}) != 1:
        raise ValueError('Require one received trace.')
    def ancestors(span):
        result, seen = [], {span['id']}
        parent = span['parent']
        while parent in spans:
            if parent in seen:
                raise ValueError('Trace parent cycle.')
            seen.add(parent)
            result.append(spans[parent]['service'])
            parent = spans[parent]['parent']
        return result
    actual_tasks = {s['attributes'].get('gen_ai.task.id') for s in spans.values()}
    if task['id'] not in actual_tasks:
        raise ValueError('Received trace does not identify this native task.')
    runtime = [s for s in spans.values() if s['service'] == agent and gateway in ancestors(s)]
    def both_gateway_hops(span):
        chain = ancestors(span)
        return any(service == agent and gateway in chain[:i] and gateway in chain[i + 1:]
                   for i, service in enumerate(chain))
    calls = [s for s in spans.values() if s['service'] == mcp
             and s['kind'] in (2, 'SPAN_KIND_SERVER')
             and s['status'].get('code') in (1, 'STATUS_CODE_OK')
             and s['attributes'].get('flow.execution.id') in expected_executions
             and both_gateway_hops(s)]
    if not runtime or not calls:
        raise ValueError('Missing gateway-to-agent-to-gateway-to-MCP parent links or native execution match.')
    if any(s['status'].get('code') in (2, 'STATUS_CODE_ERROR') for s in calls):
        raise ValueError('MCP server span failed.')
    return {'verified': True, 'taskId': task['id'], 'contextId': task['contextId'],
            'traceId': next(iter(spans.values()))['trace'],
            'executionIds': sorted({s['attributes']['flow.execution.id'] for s in calls}),
            'services': sorted({s['service'] for s in spans.values()}), 'spanCount': len(spans),
            'gatewayRuntimeMcpParentLinks': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace-file', type=Path, required=True)
    parser.add_argument('--native-receipt', type=Path, required=True)
    parser.add_argument('--agent-service', default='dice_lifecycle_recording')
    args = parser.parse_args()
    print(json.dumps(report(json.loads(args.trace_file.read_text()),
                            json.loads(args.native_receipt.read_text()), agent=args.agent_service), indent=2))


if __name__ == '__main__':
    main()
