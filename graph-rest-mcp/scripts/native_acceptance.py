#!/usr/bin/env python3
"""Invoke native alpha17 in memory and write only allow-listed test receipts."""
import argparse
import json
import pathlib
import re
import subprocess
import time
import uuid

TOOL = 'get_graph_context'


def unpack_json(text):
    decoder = json.JSONDecoder()
    for offset, char in enumerate(text):
        if char == '{':
            try:
                value, _ = decoder.raw_decode(text[offset:])
            except ValueError:
                continue
            if isinstance(value, dict) and ('session' in value or 'task' in value):
                return value
    raise ValueError('native_protocol')


def context_objects(value):
    if isinstance(value, str) and value.startswith('{') and len(value) <= 65536:
        try:
            yield from context_objects(json.loads(value))
        except ValueError:
            pass
    elif isinstance(value, dict):
        if {'status', 'entities', 'views', 'relationships', 'source', 'scope'} <= value.keys():
            yield value
        else:
            for child in value.values():
                yield from context_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from context_objects(child)



def reported_compliance(answer, workload, expected):
    normalized = answer.lower().replace('`', '').replace('*', '')
    status = r'compliant' if expected == 'compliant' else r'(?:non[_ -]?compliant|not compliant)'
    pattern = (r'\b' + re.escape(workload) + r'(?![-\w])(?:\s+workload)?\s*'
               r'(?:=|:|\bis\b)\s*(?:marked\s+)?' + status + r'\b')
    return bool(re.search(pattern, normalized))



def grounded_relationships(answer, context):
    text = answer.lower().replace('`', '').replace('*', '').replace(chr(34), '').replace(chr(39), '').replace('\u2192', ' -> ')
    identifier = r'(?:prod|dev):[a-z0-9_-]+'
    ids = {n['id'].lower() for n in [*context['entities'], *context['views']]}
    mentioned = set(re.findall(identifier, text))
    if not mentioned or not mentioned <= ids:
        return False
    relation = r'assessed[_ ]by|owned[_ ]by|contains|evaluates|describes'
    pattern = '(' + identifier + r')\s+(?:is\s+)?(' + relation + r')\s+(?:(?:finding|policy|workload|view|team|namespace)\s+)?(' + identifier + ')'
    triples = [(a, r.replace(' ', '_'), b) for a, r, b in re.findall(pattern, text)]
    prefix_pattern = '(' + relation + r'):\s*(' + identifier + r')\s*->\s*(' + identifier + ')'
    triples.extend((a, r.replace(' ', '_'), b) for r, a, b in re.findall(prefix_pattern, text))
    allowed = {(e['source'].lower(), e['relation'].lower(), e['target'].lower()) for e in context['relationships']}
    if not triples or any(t not in allowed for t in triples):
        return False
    for node in context['entities']:
        if node.get('kind') == 'workload':
            opposite = 'non_compliant' if node['compliance'] == 'compliant' else 'compliant'
            if reported_compliance(answer, node['name'].lower(), opposite):
                return False
    return True


def evaluate(envelope, expected_status, environment, count, allow_local_refusal=False):
    task = envelope.get('task', {})
    calls, contexts, texts = [], [], []
    unknown_tool_part = False
    messages = [*task.get('history', []), *task.get('artifacts', [])]
    for message in messages:
        for part in message.get('parts', []):
            tag = part.get('metadata', {}).get('kagent.dev/a2a/part-type')
            if any(k in part for k in ('functionCall', 'function_call', 'toolCall', 'tool_call')):
                unknown_tool_part = True
            if tag not in (None, 'function_call', 'function_response') and isinstance(part.get('data'), dict) and 'name' in part['data']:
                unknown_tool_part = True
            if tag == 'function_call':
                calls.append(part.get('data', {}).get('name', 'UNKNOWN'))
            elif tag == 'function_response':
                contexts.extend(context_objects(part.get('data', {})))
            elif isinstance(part.get('text'), str) and message.get('role') not in ('ROLE_USER', 'user'):
                texts.append(part['text'])
    answer = '\n'.join(texts).lower()
    completed = task.get('status', {}).get('state') == 'TASK_STATE_COMPLETED'
    if allow_local_refusal and expected_status == 'unsupported':
        honest_source = bool(re.search(r'\bsource:\s*(?:none|not queried|unavailable)\b', answer))
        no_scope = bool(re.search(r'\bscope:\s*(?:unspecified|none|not applicable)\b', answer))
        limitation = any(word in answer for word in ('cannot', "can't", 'unable', 'unsupported', 'outside the scope'))
        weather_fact = bool(re.search(r'\b(?:sunny|raining|snowing)\b|\b\d+\s*(?:degrees|°)', answer))
        fake_metadata = any(word in answer for word in ('fixture-v1', 'prod:', 'dev:', 'checkout=', 'metrics='))
        passed = (completed and not calls and not contexts and not unknown_tool_part
                  and honest_source and no_scope and limitation and not weather_fact
                  and not fake_metadata and 'kagent_error_code' not in json.dumps(envelope))
        summary = {'source': 'none', 'environments': [], 'groupings': [], 'complete': False} if passed else None
        return calls, {}, summary, passed, 'none' if passed else 'refusal_mismatch'
    valid_calls = bool(calls) and all(name == TOOL for name in calls) and not unknown_tool_part
    matching = [c for c in contexts if c.get('status') == expected_status and c.get('source') == 'fixture-v1']
    context = matching[-1] if matching else None
    facts_ok = False
    if context:
        ids = {n['id']: n for n in context['entities']}
        scope_ok = context['scope']['result_count'] == count
        scope_ok &= context['scope']['environments'] == ([environment] if environment else (['production', 'development'] if expected_status == 'ambiguous' else []))
        if expected_status == 'supported':
            prefix = 'prod' if environment == 'production' else 'dev'
            facts_ok = (scope_ok and ids.get(prefix + ':checkout', {}).get('compliance') == ('compliant' if prefix == 'prod' else 'non_compliant')
                        and grounded_relationships(answer, context) and environment in answer and 'fixture-v1' in answer)
            if count == 10:
                facts_ok &= ids.get(prefix + ':metrics', {}).get('compliance') == ('non_compliant' if prefix == 'prod' else 'compliant')
            if count < 10:
                facts_ok &= bool(context['truncated']) and ('truncat' in answer or 'partial' in answer or 'limited' in answer)
        else:
            facts_ok = (scope_ok and bool(context.get('limitations')) and not context['entities']
                        and 'fixture-v1' in answer and any(word in answer for word in ('unsupported', 'cannot', 'limitation', 'ambiguous', 'clarif', 'not support', 'specify exactly one', 'specify one environment')))
    passed = completed and valid_calls and facts_ok and 'kagent_error_code' not in json.dumps(envelope)
    counts = {'entities': len(context['entities']), 'views': len(context['views']), 'relationships': len(context['relationships'])} if context else {}
    summary = None
    if context:
        env = context['scope']['environments']
        groups = context['scope']['groupings']
        if all(e in ('production', 'development') for e in env) and all(g in ('commerce', 'governance', 'platform') for g in groups):
            summary = {'source': 'fixture-v1', 'environments': env, 'groupings': groups, 'complete': bool(context['scope']['complete'])}
    return calls, counts, summary, passed, 'none' if passed else ('native_incomplete' if not completed else 'trace_or_answer_mismatch')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cli', required=True)
    parser.add_argument('--url', default='http://127.0.0.1:18183')
    parser.add_argument('--agent', default='graph-context-lab')
    parser.add_argument('--output', required=True)
    parser.add_argument('--timeout-seconds', type=int, default=180)
    parser.add_argument('--case', choices=['all', 'supported', 'development', 'unsupported', 'ambiguous', 'truncated'], default='all')
    args = parser.parse_args()
    if not 30 <= args.timeout_seconds <= 600:
        parser.error('timeout must be between 30 and 600 seconds')
    cases = [
        ('supported', 'Show production workload compliance relationships with context_size=10', 'supported', 'production', 10),
        ('development', 'Show development workload compliance relationships with context_size=10', 'supported', 'development', 10),
        ('unsupported', 'What is the weather?', 'unsupported', None, 0),
        ('ambiguous', 'Use get_graph_context with context_size=10 to check production and development compliance.', 'ambiguous', None, 0),
        ('truncated', 'Show production workload compliance relationships with context_size=3', 'supported', 'production', 3),
    ]
    base = [args.cli, '--api-url', args.url, '--gateway-url', args.url, '--user-id', 'graph-context-lab', '-n', 'kagent', '--timeout', str(args.timeout_seconds) + 's', '-o', 'json']
    def cli(*command):
        result = subprocess.run(base + list(command), capture_output=True, text=True, timeout=args.timeout_seconds + 10)
        if result.returncode:
            error = (result.stderr + result.stdout).lower()
            if any(x in error for x in ('usage_limit', 'quota', '429', 'session limit')):
                raise ValueError('provider_quota')
            if any(x in error for x in ('deadline exceeded', 'deadlineexceeded', 'timed out')):
                raise ValueError('native_timeout')
            raise ValueError('native_runtime')
        if len(result.stdout.encode()) > 524288:
            raise ValueError('native_envelope_oversize')
        return unpack_json(result.stdout)
    records = []
    for name, query, status, environment, count in cases:
        if args.case not in ('all', name):
            continue
        request_id = 'graph-' + name + '-' + uuid.uuid4().hex[:12]
        start = time.monotonic()
        record = {'request_identifier': request_id, 'agent_name': args.agent, 'expected_tool_names': [] if name == 'unsupported' else [TOOL], 'actual_tool_names': [], 'completion_status': 'FAIL', 'elapsed_seconds': 0, 'result_counts': {}, 'source_scope_summary': None, 'error_category': 'native_runtime'}
        try:
            session = cli('agent', 'session', 'create', '--agent', args.agent, '--request-id', request_id)['session']['id']
            envelope = cli('agent', 'invoke', '--session', session, '--task', query)
            calls, counts, summary, passed, error = evaluate(envelope, status, environment, count, allow_local_refusal=(name == 'unsupported'))
            record.update(actual_tool_names=calls, result_counts=counts, source_scope_summary=summary, completion_status='PASS' if passed else 'FAIL', error_category=error)
        except (ValueError, KeyError) as error:
            category = str(error)
            record['error_category'] = category if category in ('provider_quota', 'native_runtime', 'native_timeout', 'native_envelope_oversize', 'native_protocol') else 'native_protocol'
        except subprocess.TimeoutExpired:
            record['error_category'] = 'native_timeout'
        record['elapsed_seconds'] = round(time.monotonic() - start, 3)
        records.append(record)
        pathlib.Path(args.output).write_text(json.dumps(records, indent=2) + '\n')
        print(json.dumps(record), flush=True)
        if record['error_category'] in ('provider_quota', 'native_timeout', 'native_runtime'):
            break
    raise SystemExit(0 if records and all(r['completion_status'] == 'PASS' for r in records) else 1)


if __name__ == '__main__':
    main()
