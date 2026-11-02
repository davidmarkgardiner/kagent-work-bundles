"""Pure current-run projection of controller receipts and retained OTel metadata."""
import math
import re
import time

STAGES = (
    ('fault', 'Inject and observe fault'), ('classify', 'Classify critical event'),
    ('triage', 'Kagent investigation'), ('review', 'Remedy and independent review'),
    ('approval', 'Human approval'), ('merge', 'Merge approved change'),
    ('recovery', 'Wait for application recovery'), ('verify', 'Native verification'),
    ('resolve', 'Resolve incident'),
)
STEP_STAGE = {step: stage for stage, steps in {
    'fault': ('prepare', 'inject_fault', 'observe_fault', 'recheck_fault'), 'classify': ('classify', 'classification_followup'),
    'triage': ('dispatch', 'triage', 'triage_continuation'), 'review': ('review',), 'approval': ('await_approval',),
    'merge': ('merge', 'observe_merge'), 'recovery': ('await_recovery', 'measure_recovery'),
    'verify': ('verify',), 'resolve': ('close',),
}.items() for step in steps}
TERMINAL_STEP = dict(zip((x[0] for x in STAGES), (
    'observe_fault', 'classify', 'triage', 'review', 'await_approval',
    'observe_merge', 'measure_recovery', 'verify', 'close')))
PHASE_STAGE = {'preparing':'fault', 'observing':'fault', 'fault_injected':'fault',
    'classifying':'classify', 'dispatching':'triage', 'triaging':'triage', 'waiting_ci':'triage',
    'waiting_review':'review', 'waiting_human':'approval', 'merging':'merge',
    'reconciling':'recovery', 'verifying':'verify', 'closing_ticket':'resolve', 'closed':'resolve'}
COMPONENTS = {'client', 'kagent', 'substrate', 'worker', 'actor', 'agentgateway', 'model', 'mcp', 'skills'}
DEMO_STATES = {'started', 'progress', 'completed', 'pending', 'suppressed', 'blocked', 'unknown'}
TASK_KEYS = ('a2a.task.id', 'gen_ai.task.id')
SESSION_KEYS = ('gen_ai.conversation.id', 'kagent.session.id')
LABELS = dict(STAGES)
MCP_BACKEND_TOOLS = {
    'kyverno-kubernetes-mcp': frozenset({'read_kyverno_incident', 'verify_recovery'}),
    'kyverno-gitlab-mcp': frozenset({'read_policy_repository', 'propose_policy_fix', 'inspect_policy_fix',
                                  'merge_policy_fix', 'merge_dashboard_approved_fix'}),
}


def _safe(value, limit=160):
    return value[:limit] if isinstance(value, str) else None


def _attrs(record):
    value = record.get('attributes', {})
    return value if isinstance(value, dict) else {}


def _coordinator(record, run_id, contexts=()):
    values = _attrs(record)
    declared_run = values.get('flow.run.id')
    if (record.get('service') != 'kyverno-demo-controller'
            or declared_run is not None and declared_run != run_id):
        return None, None
    step, state = values.get('flow.demo.step'), values.get('flow.demo.state')
    if not (values.get('flow.evidence.source') == 'demo-controller' and step in STEP_STAGE and state in DEMO_STATES):
        # Metadata retained by pre-upgrade receivers: restricted to this owned producer.
        workflow = values.get('flow.workflow', '')
        step = workflow.removeprefix('kyverno-demo.') if isinstance(workflow, str) and workflow.startswith('kyverno-demo.') else None
        state = values.get('flow.result')
    if step not in STEP_STAGE or state not in DEMO_STATES:
        return None, None
    if declared_run == run_id:
        return step, state
    if any(values.get(key) is not None for key in TASK_KEYS + SESSION_KEYS):
        return None, None
    for anchor in contexts:
        if (not isinstance(anchor, dict) or anchor.get('runId') != run_id or anchor.get('step') != step
                or anchor.get('traceId') != record.get('traceId') or anchor.get('spanId') != record.get('spanId')
                or not re.fullmatch(r'[a-f0-9]{32}', str(anchor.get('traceId', '')))
                or not int(anchor['traceId'], 16)
                or not re.fullmatch(r'[a-f0-9]{16}', str(anchor.get('spanId', '')))
                or not int(anchor['spanId'], 16)):
            continue
        try:
            started = int(anchor['startedNs'])
            observed = int(record.get('timestampNs', record.get('startNs')))
            if 0 < started <= observed < 2**64:
                return step, state
        except (KeyError, ValueError, TypeError):
            continue
    return None, None


def _seconds(value, nano=False):
    try:
        result = float(value) / (1e9 if nano else 1)
        return result if math.isfinite(result) and result > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _recent(event, receipt, now):
    return event is not None and receipt is not None and 0 <= now-event <= 15 and 0 <= now-receipt <= 15


def _identity_conflict(records, run_id, task_id=None, session_id=None):
    for record in records:
        values = _attrs(record)
        if values.get('flow.run.id') and values['flow.run.id'] != run_id:
            return True
        if task_id and any(values.get(key) and values[key] != task_id for key in TASK_KEYS):
            return True
        if session_id and any(values.get(key) and values[key] != session_id for key in SESSION_KEYS):
            return True
    return False


def _task_match(records, task):
    task_id, session = task['taskId'], task['sessionId']
    if not task_id:
        return False
    return (any(any(_attrs(r).get(k) == task_id for k in TASK_KEYS) for r in records)
            and (not session or any(any(_attrs(r).get(k) == session for k in SESSION_KEYS) for r in records)))


def _causal_records(records, anchors):
    selected = {r.get('spanId') for r in anchors if r.get('spanId')}
    known = {r.get('spanId') for r in records}
    changed = True
    while changed:
        changed = False
        for record in records:
            span, parent = record.get('spanId'), record.get('parentSpanId')
            if span in selected and parent and parent in known:
                if parent not in selected:
                    selected.add(parent)
                    changed = True
            if parent in selected and span and span not in selected:
                selected.add(span)
                changed = True
    return [r for r in records if r.get('spanId') in selected]


def _span_interval(record):
    try:
        if any(type(record.get(k)) not in {str, int} for k in ('startNs', 'endNs')):
            return None
        start, end = int(record['startNs']), int(record['endNs'])
        return (start, end) if 0 < start < end < 2**64 else None
    except (ValueError, TypeError):
        return None


def _tool_name(record):
    values = _attrs(record)
    keys = ('gen_ai.tool.name', 'mcp.tool.name', 'tool.name')
    if any(k in values and (not isinstance(values[k], str) or not values[k]) for k in keys):
        return None
    names = {values[k] for k in keys
             if isinstance(values.get(k), str) and values[k]}
    return next(iter(names)) if len(names) == 1 else None


def _native_backend_pairs(records, selected, trace_id, task, run_id):
    if not task.get('taskId') or not task.get('sessionId'):
        return []
    expected = {'flow.run.id':run_id, **{k:task['taskId'] for k in TASK_KEYS},
                **{k:task['sessionId'] for k in SESSION_KEYS}}
    def conflicting(record):
        values = _attrs(record)
        return any(k in values and values[k] != value for k,value in expected.items())
    clients = {}
    for record in selected:
        if (record.get('traceId') == trace_id and record.get('component') == 'kagent'
                and any(_attrs(record).get(k) == task['taskId'] for k in TASK_KEYS)
                and isinstance(record.get('spanId'), str)
                and re.fullmatch(r'[a-f0-9]{16}', record['spanId'])
                and int(record['spanId'], 16) and _span_interval(record) and not conflicting(record)):
            clients.setdefault(_tool_name(record), []).append(record)
    known = {r.get('spanId') for r in records}
    selected_ids = {r.get('spanId') for r in selected}
    pairs = []
    for server in records[:4000]:
        parent = server.get('parentSpanId')
        interval, tool = _span_interval(server), _tool_name(server)
        if (server.get('spanId') in selected_ids or server.get('traceId') != trace_id
                or server.get('component') != 'mcp' or server.get('toolExecution') != 'server'
                or not isinstance(server.get('service'), str)
                or tool not in MCP_BACKEND_TOOLS.get(server.get('service'), ())
                or not isinstance(server.get('spanId'), str)
                or not re.fullmatch(r'[a-f0-9]{16}', server['spanId'])
                or not int(server['spanId'], 16)
                or not isinstance(parent, str) or not re.fullmatch(r'[a-f0-9]{16}', parent)
                or not int(parent, 16) or parent in known
                or not interval or conflicting(server)):
            continue
        matches = [client for client in clients.get(tool, [])
                   if _span_interval(client)[0] < interval[0] < interval[1] < _span_interval(client)[1]]
        if len(matches) == 1:
            pairs.append((matches[0], server))
    return pairs


def _workflow(demo):
    states = {stage: 'upcoming' for stage, _ in STAGES}
    current = PHASE_STAGE.get(demo.get('phase'))
    latest = None
    for event in demo.get('events', [])[-100:]:
        stage = STEP_STAGE.get(event.get('stage'))
        if not stage:
            continue
        latest = stage
        status = event.get('state')
        if status == 'completed' and (event.get('stage') == TERMINAL_STEP[stage] or event.get('stage') in {'recheck_fault', 'classification_followup', 'triage_continuation'}):
            states[stage] = 'passed'
        elif status in {'blocked', 'unknown'}:
            states[stage] = status
        elif status in {'pending', 'suppressed'}:
            states[stage] = 'waiting'
        elif status in {'accepted', 'started', 'progress'}:
            states[stage] = 'active'
    current = latest if demo.get('phase') in {'blocked', 'unknown', 'suppressed'} else current or latest
    if demo.get('classifier', {}).get('decision') and states['classify'] == 'upcoming':
        states['classify'] = 'passed'
    remedy = demo.get('remedy', {})
    if remedy.get('review') == 'passed' and remedy.get('ci') == 'passed':
        states['review'] = 'passed'
    if demo.get('merge', {}).get('status') == 'merged' and demo.get('merge', {}).get('sha'):
        states['merge'] = 'passed'
    if demo.get('approval', {}).get('state') == 'approved':
        states['approval'] = 'passed'
    if demo.get('ticket', {}).get('closedVerified') is True and demo.get('phase') == 'closed':
        states['resolve'] = 'passed'
    elif states['resolve'] == 'passed':
        states['resolve'] = 'unknown'
    if current:
        phase = demo.get('phase')
        if phase in {'blocked', 'unknown'}:
            states[current] = phase
        elif states[current] == 'upcoming':
            states[current] = 'waiting' if phase in {'waiting_human', 'waiting_ci', 'suppressed'} else 'active'
    return current, states


def build_demo_flow(demo, receiver_state, receiver_logs, context, now=None):
    """Return a metadata-only flow; controller and receiver inputs are never mutated."""
    now = time.time() if now is None else float(now)
    run_id = _safe(demo.get('runId'))
    connected = receiver_state.get('receiverConnected', True) is not False
    context = context if isinstance(context, dict) and context.get('runId') == run_id and run_id else {}
    coordinator_contexts = context.get('coordinatorContexts', [])
    coordinator_contexts = coordinator_contexts[:32] if isinstance(coordinator_contexts, list) else []
    tasks = {}
    fields = {'triage':'native', 'review':'review', 'merge':'merge', 'verify':'verification'}
    if isinstance(context.get('tasks', {}).get('triage_original'), dict):
        fields['triage_original'] = 'native_original'
    for role, field in fields.items():
        supplied = context.get('tasks', {}).get(role, {})
        public = demo.get(field, {})
        tasks[role] = {'taskId': _safe(supplied.get('taskId')), 'sessionId': _safe(supplied.get('sessionId')),
                       'state': _safe(supplied.get('state') or public.get('state') or public.get('taskState')),
                       'traceIds': []}
    traces = {}
    trace_roles = {}
    coordinator_stages = {}
    backend_pairs = {}
    for trace in receiver_state.get('traces', [])[:200]:
        trace_id, records = trace.get('traceId'), trace.get('spans', [])
        if not run_id or not re.fullmatch(r'[a-f0-9]{32}', str(trace_id)) or not records or _identity_conflict(records, run_id):
            continue
        matches = [role for role, task in tasks.items() if _task_match(records, task)
                   and not _identity_conflict(records, run_id, task['taskId'], task['sessionId'])]
        coordinator = any(_coordinator(r, run_id, coordinator_contexts)[0] for r in records)
        explicit_tasks = {str(_attrs(r)[k]) for r in records for k in TASK_KEYS if _attrs(r).get(k)}
        if len(matches) != 1 and (not coordinator or explicit_tasks):
            continue
        role = matches[0] if len(matches) == 1 else None
        anchors = [r for r in records if any(_attrs(r).get(k) == tasks[role]['taskId'] for k in TASK_KEYS)] if role else [
            r for r in records if _coordinator(r, run_id, coordinator_contexts)[0]]
        selected = _causal_records(records, anchors)
        pairs = _native_backend_pairs(records, selected, trace_id, tasks[role], run_id) if role else []
        if pairs:
            backend_pairs[trace_id] = {server['spanId'] for _, server in pairs}
            retained_ids = {r.get('spanId') for r in selected} | backend_pairs[trace_id]
            selected = [r for r in records if r.get('spanId') in retained_ids]
        if role is None:
            stages = {STEP_STAGE[_coordinator(r, run_id, coordinator_contexts)[0]] for r in anchors}
            allowed = {r.get('spanId') for r in anchors}
            if len(stages) == 1:
                children = {}
                for record in records:
                    children.setdefault(record.get('parentSpanId'), []).append(record)
                pending = list(allowed)
                while pending:
                    for child in children.get(pending.pop(), []):
                        attrs = _attrs(child)
                        component = child.get('component') or attrs.get('flow.component')
                        if (child.get('spanId') not in allowed and component in {'agentgateway', 'model'}
                                and not any(attrs.get(k) is not None for k in TASK_KEYS + SESSION_KEYS)
                                and not _identity_conflict([child], run_id)):
                            allowed.add(child['spanId'])
                            pending.append(child['spanId'])
                coordinator_stages[trace_id] = next(iter(stages))
            selected = [r for r in selected if r.get('spanId') in allowed]
        extra_edges = [{'from':'kagent', 'to':'mcp',
                        'basis':'same trace, tool and interval (parent missing)',
                        'spanIds':[client['spanId'], server['spanId']]} for client, server in pairs]
        traces[trace_id], trace_roles[trace_id] = dict(trace, spans=selected, edges=list(trace.get('edges', [])) + extra_edges), role
        if role:
            tasks[role]['traceIds'].append(trace_id)
    observations = {}

    def observe(record, kind, trace_id, role):
        values = _attrs(record)
        demo_step, demo_state = _coordinator(record, run_id, coordinator_contexts)
        coordinator = bool(demo_step)
        if _identity_conflict([record], run_id, tasks[role]['taskId'] if role else None,
                              tasks[role]['sessionId'] if role else None):
            return
        component = record.get('component') or values.get('flow.component')
        causal = not coordinator and not role and trace_id in coordinator_stages
        if not coordinator and not role and (not causal or kind != 'span'
                or component not in {'agentgateway', 'model'}
                or any(values.get(k) is not None for k in TASK_KEYS + SESSION_KEYS)):
            return
        if coordinator and not role and any(values.get(k) for k in TASK_KEYS):
            return
        stage = STEP_STAGE.get(demo_step) if coordinator else 'triage' if role == 'triage_original' else role or coordinator_stages.get(trace_id)
        if stage not in LABELS:
            return
        if not component and kind == 'log' and trace_id in traces:
            component = next((s.get('component') for s in traces[trace_id].get('spans', [])
                              if s.get('spanId') == record.get('spanId')), None)
        if coordinator:
            component, source = 'client', 'coordinator'
        else:
            component = component if component in COMPONENTS else 'kagent'
            source = {'mcp':'mcp', 'agentgateway':'gateway', 'model':'model'}.get(component, 'native')
        operation = values.get('gen_ai.tool.name') or values.get('mcp.tool.name') or values.get('gen_ai.operation.name') or record.get('event') or record.get('name') or 'OTel operation'
        operation = 'demo.' + demo_step if coordinator else (_safe(operation, 120) or 'OTel operation')
        # Redacted tool inputs cannot identify a particular knowledge package.
        if operation in {'load_skill', 'load_skill_resource'}:
            component = 'skills'
            summary = 'Skills & Knowledge · ' + operation
        else:
            summary = ('Controller · ' + LABELS[stage] + ' · ' + demo_state) if coordinator else operation
        span_id = _safe(record.get('spanId'), 16) or ''
        identity = trace_id + '/' + span_id if kind == 'span' else _safe(record.get('id'), 64)
        if not identity or (kind == 'span' and not span_id):
            return
        event_ns = record.get('startNs') if kind == 'span' else record.get('timestampNs')
        end_ns = record.get('endNs') if kind == 'span' else event_ns
        # A span is received on completion; freshness follows its actual end, not an old start.
        event_time = _seconds(end_ns if kind == 'span' else event_ns, nano=True)
        receipt = _seconds(record.get('receivedAt'))
        viewer_receipt = _seconds(record.get('viewerReceivedAt')) if kind == 'log' and receipt is None else None
        observations[identity] = {'id':identity, 'kind':kind, 'source':source, 'stageId':stage,
            'component':component, 'operation':operation, 'traceId':trace_id if trace_id in traces else None,
            'spanId':span_id, 'timeNs':str(event_ns or '0'), 'endNs':str(end_ns or '0'),
            'receivedAt':receipt, 'viewerReceivedAt':viewer_receipt,
            'receiptSource':'collector' if receipt else 'viewer' if viewer_receipt else 'unknown',
            'status':_safe(demo_state or record.get('status') or record.get('severity'), 32),
            'scopeBasis':'native-tool-window' if record.get('spanId') in backend_pairs.get(trace_id, set()) else 'coordinator-causal' if causal else 'coordinator-context' if coordinator and values.get('flow.run.id') is None else 'received-run-id' if coordinator else 'native-task',
            'summary':summary, 'recent':connected and _recent(event_time, receipt or viewer_receipt, now)}

    for trace_id, trace in traces.items():
        for record in trace.get('spans', [])[:4000]:
            observe(record, 'span', trace_id, trace_roles[trace_id])
    logs_available = isinstance(receiver_logs, dict) and isinstance(receiver_logs.get('logs'), list)
    for record in (receiver_logs.get('logs', []) if logs_available else [])[:200]:
        trace_id = record.get('traceId', '')
        if trace_id in traces:
            observe(record, 'log', trace_id, trace_roles[trace_id])
        elif run_id and _coordinator(record, run_id, coordinator_contexts)[0]:
            observe(record, 'log', trace_id, None)
    observations = sorted(observations.values(), key=lambda r: (_seconds(r['endNs'], True) or _seconds(r['timeNs'], True) or 0, r['id']))[-160:]
    current, workflow = _workflow(demo)
    stage_values = []
    for stage, label in STAGES:
        seen = [r for r in observations if r['stageId'] == stage]
        history = [{'id':_safe(event.get('id'), 128), 'time':_safe(event.get('time'), 64),
                    'step':event['stage'], 'state':_safe(event.get('state'), 32),
                    'message':_safe(event.get('message'), 500)}
                   for event in demo.get('events', [])[-100:]
                   if isinstance(event, dict) and isinstance(event.get('stage'), str)
                   and STEP_STAGE.get(event['stage']) == stage]
        stage_values.append({'id':stage, 'label':label, 'workflow':workflow[stage],
            'telemetry':'recent' if any(r['recent'] for r in seen) else 'recorded' if seen else 'none',
            'observationCount':len(seen), 'traceIds':sorted({r['traceId'] for r in seen if r['traceId']}),
            'controllerEvents':history})
    newest = observations[-1] if observations else None
    active = newest['traceId'] if newest else None
    if not newest and traces:
        active = next(reversed(traces))
    observed_components = set()
    for trace in traces.values():
        retained = {r.get('spanId') for r in trace.get('spans', [])}
        projected = set(trace.get('components', [])) & COMPONENTS
        observed_components.update(r.get('component') for r in trace.get('spans', []) if r.get('component') in projected)
        for edge in trace.get('edges', []):
            if any(s in retained for s in edge.get('spanIds', [])):
                observed_components.update(c for c in (edge.get('from'), edge.get('to')) if c in projected)
    components = sorted(observed_components)
    edges = {}
    for trace_id, trace in traces.items():
        retained = {r.get('spanId') for r in trace.get('spans', [])}
        for edge in trace.get('edges', []):
            origin, target = edge.get('from'), edge.get('to')
            span_ids = [s for s in edge.get('spanIds', []) if s in retained]
            if origin not in components or target not in components or not span_ids:
                continue
            key = (origin, target)
            item = edges.setdefault(key, {'from':origin, 'to':target, 'basis':_safe(edge.get('basis'), 120), 'spanIds':[], 'traceIds':[]})
            item['spanIds'] = sorted(set(item['spanIds']) | set(span_ids))
            item['traceIds'] = sorted(set(item['traceIds']) | {trace_id})
    mode = 'disconnected' if not connected else 'live' if any(r['recent'] for r in observations) else 'recorded' if observations else 'unavailable'
    title = LABELS.get(current, 'Ready to start')
    status = workflow.get(current)
    if demo.get('phase') == 'suppressed':
        detail = 'The classifier suppressed this event. No native investigation was started.'
    elif status in {'blocked', 'unknown'}:
        detail = 'The controller reports ' + status + '. The incident remains open.'
        reason = next((_safe(e.get('message'), 320) for e in reversed(demo.get('events', [])[-100:])
                       if STEP_STAGE.get(e.get('stage')) == current and e.get('state') in {'blocked', 'unknown'}), None)
        if reason:
            detail += ' ' + reason
    elif current == 'approval' and status != 'passed':
        detail = 'Review the exact commit and approve it in this dashboard before the agent can merge.'
    elif current == 'resolve' and workflow['resolve'] == 'passed':
        detail = 'Application recovery and native verification were confirmed; issue closure was verified.'
    else:
        detail = {
            'fault':'Waiting for the injected fault to be observed before classification.',
            'classify':'The classifier decides whether this critical event should reach Kagent.',
            'triage':'Waiting for the native investigation and repository remedy.',
            'review':'Waiting for exact-commit checks and independent review.',
            'merge':'Waiting for the native merge task and confirmed repository merge.',
            'recovery':'Waiting for GitOps reconciliation and observed application recovery.',
            'verify':'Waiting for native verification of the recovered application.',
            'resolve':'Waiting for verified issue closure after application recovery.',
        }.get(current, 'Start the demo to open an incident and inject the bounded test fault.')
    latest_stage_event = next((e for e in reversed(demo.get('events', [])[-100:])
                               if STEP_STAGE.get(e.get('stage')) == current), {})
    pending_allowance = _safe(latest_stage_event.get('message'), 240)
    if (latest_stage_event.get('state') == 'pending' and pending_allowance
            and pending_allowance.startswith('Waiting for model allowance')):
        detail = pending_allowance
    if mode == 'disconnected':
        detail += ' The OTel receiver is disconnected.'
    elif not observations:
        detail += ' Current-run telemetry is missing or has been evicted.'
    elif mode == 'recorded':
        detail += ' Retained telemetry is recorded history, not live activity.'
    if not logs_available:
        detail += ' The OTel log feed is unavailable.'
    elif any(r['receiptSource'] == 'viewer' for r in observations):
        detail += ' Legacy log arrival times are measured by this viewer; collector receipt times are unavailable.'
    pending = next((label for stage, label in STAGES if workflow[stage] != 'passed'), None)
    if status in {'blocked', 'unknown'}:
        pending = 'Reconcile the recorded failure before continuing; no action will be resent automatically'
    actor = ('session-' + tasks[trace_roles[active]]['sessionId']) if active in trace_roles and trace_roles[active] and tasks[trace_roles[active]]['sessionId'] else None
    return {'schemaVersion':1, 'runId':run_id, 'currentStage':current, 'mode':mode,
        'telemetryConnected':connected, 'lastReceivedAt':max((r['receivedAt'] for r in observations if r['receivedAt']), default=None),
        'lastViewerReceivedAt':max((r['viewerReceivedAt'] for r in observations if r['viewerReceivedAt']), default=None),
        'stages':stage_values, 'narrative':{'title':title, 'detail':detail, 'next':pending or 'Incident resolved'},
        'scope':{'traceIds':list(traces), 'activeTraceId':active, 'label':'Current incident · retained OTel evidence',
                 'spanIds':{key:sorted({s['spanId'] for s in trace['spans']}) for key,trace in traces.items()},
                 'actorName':actor, 'requestTraceId':active, 'components':components, 'edges':list(edges.values())},
        'tasks':tasks, 'observations':observations}
