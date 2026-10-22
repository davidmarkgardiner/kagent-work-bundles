"""Compose document acceptance with one fixed MCP result and independent audit."""
import copy
import json
import re

from acceptance import PROMPT, check
from contract import Rejected, canonical

COMBINED_PROMPT = PROMPT + (' Also call get_demo_status exactly once with no arguments. Quote its evidenceCode and executionId, '
    'explicitly labelled synthetic demo data. That fixed status lookup is the only permitted operational tool. '
    'Include the exact contiguous plain-text phrase "exit 212", without Markdown inside that phrase.')


def check_combined(raw, context, contents, release, source, audit):
    if not isinstance(raw, dict) or not isinstance(raw.get('result'), dict):
        raise Rejected('NativeHistoryMissing')
    history = raw.get('result', {}).get('history', [])
    if not isinstance(history, list) or len(history) > 64:
        raise Rejected('NativeHistoryMissing')
    seen, pending, mcp_calls, mcp_results = set(), {}, [], []
    input_seen = False
    for message in history:
        if not isinstance(message, dict):
            raise Rejected('MalformedNativeHistory')
        parts = message.get('parts')
        if not isinstance(parts, list) or len(parts) > 32:
            raise Rejected('MalformedNativeHistory')
        if message.get('role') == 'user' and parts == [{'kind': 'text', 'text': COMBINED_PROMPT}]:
            input_seen = True
        for part in parts:
            if not isinstance(part, dict):
                raise Rejected('MalformedNativeHistory')
            if part.get('kind') != 'data':
                continue
            if not input_seen:
                raise Rejected('ToolEvidenceBeforeInput')
            data, meta = part.get('data'), part.get('metadata')
            if not isinstance(data, dict) or not isinstance(meta, dict):
                raise Rejected('MalformedNativeHistory')
            call_id, name = data.get('id'), data.get('name')
            if not isinstance(call_id, str) or not call_id:
                raise Rejected('MissingToolIdentity')
            if meta.get('kagent_type') == 'function_call':
                if call_id in seen or len(seen) >= 7:
                    raise Rejected('DuplicateOrExcessiveToolCalls')
                seen.add(call_id); pending[call_id] = name
                if name == 'get_demo_status':
                    if data.get('args') != {}:
                        raise Rejected('UnexpectedMCPArguments')
                    mcp_calls.append(data)
            elif meta.get('kagent_type') == 'function_response':
                if call_id not in pending or pending.pop(call_id) != name:
                    raise Rejected('ToolResultAttributionMismatch')
                if name == 'get_demo_status':
                    mcp_results.append(data)
            else:
                raise Rejected('UnexpectedNativeEvent')
    if pending or len(mcp_calls) != 1 or len(mcp_results) != 1:
        raise Rejected('RequiredMCPResultMissing')
    response = mcp_results[0].get('response')
    if not isinstance(response, dict) or set(response) != {'content', 'isError'} or response['isError'] is not False:
        raise Rejected('MCPResultFailed')
    content = response['content']
    if (not isinstance(content, list) or len(content) != 1 or set(content[0]) != {'type', 'text'}
            or content[0]['type'] != 'text' or not isinstance(content[0]['text'], str)
            or len(content[0]['text'].encode()) > 1024):
        raise Rejected('MCPResultUnbounded')
    result = json.loads(content[0]['text'])
    if (not isinstance(result, dict) or set(result) != {'caseCode', 'evidenceCode', 'executionId', 'resourceVersion', 'sourceUID', 'status'}
            or not isinstance(result.get('executionId'), str) or not re.fullmatch('[a-f0-9]{32}', result['executionId'])):
        raise Rejected('MCPResultShapeMismatch')
    expected = {**source['data'], 'sourceUID': source['metadata']['uid'], 'resourceVersion': source['metadata']['resourceVersion']}
    if {k: v for k, v in result.items() if k != 'executionId'} != expected:
        raise Rejected('MCPResultSourceMismatch')
    events = [e for e in audit.get('events', []) if e.get('executionId') == result['executionId']]
    if (len(events) != 1 or events[0].get('result') != 'passed' or events[0].get('resultSha256') != canonical(result)
            or events[0].get('sourceUID') != result['sourceUID'] or events[0].get('resourceVersion') != result['resourceVersion']):
        raise Rejected('MCPBackendAuditMismatch')
    partition = copy.deepcopy(raw)
    call_id = mcp_calls[0]['id']
    for message in partition['result']['history']:
        message['parts'] = [p for p in message['parts'] if p.get('kind') != 'data' or p['data']['id'] != call_id]
    receipt = check(partition, context, contents, release, prompt=COMBINED_PROMPT)
    answer = '\n'.join(p.get('text', '') for artifact in raw['result']['artifacts'] for p in artifact['parts'] if p.get('kind') == 'text')
    missing = [key for key in ('evidenceCode', 'executionId') if result[key] not in answer]
    if 'synthetic' not in answer.lower():
        missing.append('synthetic demo data label')
    receipt['missingAnswerTerms'].extend(missing)
    if missing:
        receipt['phase'] = 'Failed'
    receipt.update(mcpCallId=call_id, mcpExecutionId=result['executionId'], mcpResultSha256=canonical(result),
                   backendTraceId=events[0]['traceId'], backendSpanId=events[0]['spanId'])
    receipt['toolCalls'].append(mcp_calls[0])
    receipt['toolResultSha256'][call_id] = canonical(response)
    return receipt
