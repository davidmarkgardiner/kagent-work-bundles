import copy
import json
import unittest
from demo_flow import build_demo_flow

NOW = 1000
TRACE = 'a' * 32
SPAN = 'b' * 16


def record(**attrs):
    return {'traceId': TRACE, 'spanId': SPAN, 'parentSpanId':'', 'startNs':str(995*10**9),
            'endNs':str(999*10**9), 'receivedAt':999, 'name':'invoke_agent', 'service':'kyverno-agent',
            'component':'kagent', 'status':'ok', 'attributes':{'a2a.task.id':'task-1',
            'gen_ai.conversation.id':'session-1', **attrs}}


def receiver(*records):
    return {'receiverConnected':True, 'traces':[{'traceId':TRACE, 'spans':list(records),
        'components':['kagent','model'], 'edges':[{'from':'kagent','to':'model',
        'spanIds':[SPAN], 'basis':'parent'}]}]}


def demo(**patch):
    return {'runId':'demo-1', 'phase':'triaging', 'native':{'taskId':'task-1', 'state':'working'}, **patch}


def context(**patch):
    return {'runId':'demo-1', 'tasks':{'triage':{'taskId':'task-1','sessionId':'session-1'}}, **patch}


class ProjectionTests(unittest.TestCase):
    def flow(self, state=None, data=None, ctx=None, logs=None):
        return build_demo_flow(data or demo(), state or receiver(record()),
                               {'logs':[]} if logs is None else logs, ctx or context(), NOW)

    def test_stage_controller_history_uses_canonical_mapping_including_continuations(self):
        groups={'fault':['prepare','inject_fault','observe_fault','recheck_fault'],
                'classify':['classify','classification_followup'],
                'triage':['dispatch','triage','triage_continuation'], 'review':['review'],
                'approval':['await_approval'], 'merge':['merge','observe_merge'],
                'recovery':['await_recovery','measure_recovery'], 'verify':['verify'], 'resolve':['close']}
        events=[{'id':step,'time':'2026-11-01T17:00:00Z','stage':step,'state':'completed','message':step+' recorded',
                 'private_unprojected':'not part of the display contract'} for steps in groups.values() for step in steps]
        events.append({'stage':'unrecognised_step','message':'Exclude me'})
        data=demo(events=events);before=copy.deepcopy(data)
        flow=self.flow(data=data,state={'receiverConnected':True,'traces':[]})
        self.assertEqual(data,before)
        for stage in flow['stages']:
            self.assertEqual([event['step'] for event in stage['controllerEvents']],groups[stage['id']])
            self.assertEqual(stage['observationCount'],0)
            self.assertTrue(all(set(event)=={'id','time','step','state','message'} for event in stage['controllerEvents']))

    def test_stage_history_is_bounded_without_fabricating_otel(self):
        events=[{'id':str(i),'stage':'triage','state':'pending','message':'x'*600,'time':'t'*90} for i in range(105)]
        flow=self.flow(data=demo(events=events),state={'receiverConnected':False,'traces':[]})
        history=flow['stages'][2]['controllerEvents']
        self.assertEqual(len(history),100)
        self.assertEqual(history[0]['id'],'5')
        self.assertEqual(len(history[0]['message']),500)
        self.assertEqual(len(history[0]['time']),64)
        self.assertEqual(flow['observations'],[])

    def test_exact_task_session_live_projection_and_inputs_unchanged(self):
        state = receiver(record())
        before = copy.deepcopy(state)
        flow = self.flow(state)
        self.assertEqual(state, before)
        self.assertEqual(flow['mode'], 'live')
        self.assertEqual(flow['tasks']['triage']['traceIds'], [TRACE])
        self.assertEqual(flow['scope']['components'], ['kagent','model'])
        self.assertEqual(flow['observations'][0]['id'], TRACE+'/'+SPAN)
        self.assertEqual(flow['stages'][2]['workflow'], 'active')

    def test_allowance_wait_explains_actual_pending_gate_without_implying_native_execution(self):
        message='Waiting for model allowance to complete merge and verification; no native task was sent.'
        flow=self.flow(data=demo(phase='merging',events=[{'stage':'merge','state':'pending','message':message}]))
        self.assertTrue(flow['narrative']['detail'].startswith(message))
        self.assertEqual(flow['stages'][5]['workflow'],'waiting')
        self.assertNotEqual(flow['stages'][5]['workflow'],'passed')
        completed=self.flow(data=demo(phase='merging',events=[
            {'stage':'merge','state':'pending','message':message},
            {'stage':'merge','state':'completed','message':'Actual native merge task completed'}]))
        self.assertFalse(completed['narrative']['detail'].startswith(message))

    def test_blocked_narrative_requires_reconciliation_not_reinjection(self):
        flow = self.flow(data=demo(phase='blocked', step='observe_fault', events=[
            {'stage':'observe_fault','state':'blocked','message':'Actual denial window did not satisfy admission gates'}]))
        self.assertIn('Reconcile the recorded failure', flow['narrative']['next'])
        self.assertIn('no action will be resent', flow['narrative']['next'])

    def test_recheck_coordinator_maps_to_fault_without_native_activity(self):
        span=record();span['service']='kyverno-demo-controller'
        span['attributes']={'flow.run.id':'demo-1','flow.workflow':'kyverno-demo.recheck_fault','flow.result':'started'}
        flow=self.flow(receiver(span),data=demo(phase='observing'))
        self.assertEqual(flow['observations'][0]['stageId'],'fault')
        self.assertEqual(flow['observations'][0]['source'],'coordinator')
        self.assertEqual(flow['observations'][0]['component'],'client')

    def test_recheck_receipts_clear_prior_block_only_through_real_workflow_events(self):
        events=[{'stage':'observe_fault','state':'blocked'},{'stage':'recheck_fault','state':'accepted'}]
        flow=self.flow(data=demo(phase='observing',events=events))
        self.assertEqual(flow['stages'][0]['workflow'],'active')
        events.append({'stage':'recheck_fault','state':'completed'})
        flow=self.flow(data=demo(phase='classifying',events=events))
        self.assertEqual(flow['stages'][0]['workflow'],'passed')

    def test_operator_followup_completion_replaces_suppressed_stage_state_only_with_actual_event(self):
        flow=self.flow(data=demo(phase='classifying',events=[
            {'stage':'classify','state':'suppressed','message':'Original confidence .93'},
            {'stage':'classification_followup','state':'accepted','message':'Operator requested fresh evidence'}]))
        self.assertEqual(flow['stages'][1]['workflow'],'active')
        done=self.flow(data=demo(phase='dispatching',events=[
            {'stage':'classify','state':'suppressed','message':'Original confidence .93'},
            {'stage':'classification_followup','state':'completed','message':'Actual fresh decision passed'}]))
        self.assertEqual(done['stages'][1]['workflow'],'passed')

    def test_session_only_never_matches(self):
        flow = self.flow(receiver(record(**{'a2a.task.id':'other-task'})))
        self.assertEqual(flow['scope']['traceIds'], [])
        self.assertEqual(flow['mode'], 'unavailable')

    def test_wrong_session_run_context_and_conflicting_trace_rejected(self):
        for attrs in ({'gen_ai.conversation.id':'other'}, {'flow.run.id':'old-run'},
                      {'gen_ai.task.id':'other-task'}):
            self.assertEqual(self.flow(receiver(record(**attrs)))['observations'], [])
        self.assertEqual(self.flow(ctx=context(runId='old-run'))['observations'], [])
        conflict = record(**{'flow.run.id':'old-run'})
        conflict['spanId'] = 'c'*16
        self.assertEqual(self.flow(receiver(record(), conflict))['observations'], [])

    def test_wrong_unretained_trace_and_no_task_anchor_not_clickable(self):
        orphan = {'id':'log-1', 'traceId':'d'*32, 'spanId':SPAN, 'timestampNs':str(999*10**9),
                  'receivedAt':999,'service':'native','attributes':{'a2a.task.id':'task-1'}}
        self.assertEqual(self.flow(receiver(), logs={'logs':[orphan]})['observations'], [])

    def test_scope_exposes_only_causally_selected_retained_span_ids(self):
        orphan=record()
        orphan['spanId']='c'*16
        orphan['attributes']={'gen_ai.tool.name':'unrelated_secret_tool'}
        flow=self.flow(receiver(record(),orphan))
        self.assertEqual(flow['scope']['spanIds'],{TRACE:[SPAN]})
        self.assertNotIn('unrelated_secret_tool',str(flow['observations']))

    def test_native_span_completion_cannot_complete_workflow(self):
        flow = self.flow()
        self.assertNotEqual(flow['stages'][2]['workflow'], 'passed')
        self.assertEqual(flow['stages'][-1]['workflow'], 'upcoming')

    def test_recorded_history_requires_both_event_and_receipt_freshness(self):
        for field, value in [('receivedAt',900), ('endNs',str(900*10**9)),
                             ('receivedAt',1001), ('endNs',str(1001*10**9))]:
            span = record()
            span[field] = value
            flow = self.flow(receiver(span))
            self.assertEqual(flow['mode'], 'recorded')
            self.assertFalse(flow['observations'][0]['recent'])

    def test_disconnected_keeps_recorded_evidence_without_pulse(self):
        state = receiver(record())
        state['receiverConnected'] = False
        flow = self.flow(state)
        self.assertEqual(flow['mode'], 'disconnected')
        self.assertFalse(flow['observations'][0]['recent'])

    def test_coordinator_has_only_owned_component_not_native_proof(self):
        span = record()
        span['service'] = 'kyverno-demo-controller'
        span['attributes'] = {'flow.run.id':'demo-1','flow.evidence.source':'demo-controller',
                              'flow.demo.step':'classify','flow.demo.state':'completed'}
        span['component'] = 'client'
        state = receiver(span)
        state['traces'][0].update(components=['client'],edges=[])
        flow = self.flow(state)
        self.assertEqual(flow['observations'][0]['source'], 'coordinator')
        self.assertEqual(flow['observations'][0]['component'], 'client')
        self.assertEqual(flow['tasks']['triage']['traceIds'], [])
        self.assertEqual(flow['stages'][1]['workflow'], 'upcoming')

    def test_log_receipt_required_missing_logs_and_eviction_explicit(self):
        log = {'id':'log-1','timestampNs':str(999*10**9),'traceId':'','spanId':'',
               'service':'kyverno-demo-controller','attributes':{
               'flow.run.id':'demo-1','flow.demo.step':'classify','flow.demo.state':'started',
               'flow.evidence.source':'demo-controller'}}
        flow = self.flow(receiver(), logs={'logs':[log]})
        self.assertEqual(flow['mode'], 'recorded')
        self.assertEqual(flow['scope']['traceIds'], [])
        flow = build_demo_flow(demo(), receiver(), None, context(), NOW)
        self.assertIn('log feed is unavailable', flow['narrative']['detail'])
        self.assertIn('missing or has been evicted', flow['narrative']['detail'])

    def test_skills_are_combined_arguments_and_bodies_never_exposed(self):
        span = record(**{'gen_ai.tool.name':'load_skill_resource', 'tool.arguments':'private-package',
                         'authorization':'secret', 'gen_ai.input.messages':'secret'})
        span['body'] = 'secret body'
        flow = self.flow(receiver(span))
        result = json.dumps(flow)
        self.assertIn('Skills & Knowledge', result)
        for private in ('private-package','secret','authorization'):
            self.assertNotIn(private, result)

    def test_bound_dedup_and_actual_edges_only(self):
        records = []
        for index in range(180):
            item = record()
            item['spanId'] = f'{index+1:016x}'
            records.append(item)
        state = receiver(*records, records[-1])
        state['traces'][0]['edges'].append({'from':'model','to':'mcp','spanIds':['f'*16]})
        flow = self.flow(state)
        self.assertEqual(len(flow['observations']),160)
        self.assertEqual(len({r['id'] for r in flow['observations']}),160)
        self.assertFalse(any(e['to']=='mcp' for e in flow['scope']['edges']))

    def test_legacy_alias_requires_owned_service_run_known_step_and_state(self):
        span = record()
        span['service'] = 'kyverno-demo-controller'
        span['attributes'] = {'flow.run.id':'demo-1','flow.workflow':'kyverno-demo.classify','flow.result':'started'}
        flow = self.flow(receiver(span))
        self.assertEqual(flow['observations'][0]['source'],'coordinator')
        self.assertEqual(flow['observations'][0]['stageId'],'classify')
        for field, value in [('service','other-service')]:
            bad = copy.deepcopy(span)
            bad[field] = value
            self.assertEqual(self.flow(receiver(bad))['observations'],[])
        for key, value in [('flow.workflow','kyverno-demo.fake'),('flow.result','fake'),('flow.run.id','old-run')]:
            bad = copy.deepcopy(span)
            bad['attributes'][key] = value
            self.assertEqual(self.flow(receiver(bad))['observations'],[])

    def test_viewer_arrival_is_distinct_and_cannot_make_old_log_live(self):
        log = {'id':'legacy-log','traceId':'','spanId':'','timestampNs':str(999*10**9),
               'viewerReceivedAt':999,'service':'kyverno-demo-controller',
               'attributes':{'flow.run.id':'demo-1','flow.workflow':'kyverno-demo.classify','flow.result':'started'}}
        flow = self.flow(receiver(),logs={'logs':[log]})
        obs = flow['observations'][0]
        self.assertIsNone(obs['receivedAt'])
        self.assertEqual(obs['receiptSource'],'viewer')
        self.assertEqual(flow['lastViewerReceivedAt'],999)
        self.assertIsNone(flow['lastReceivedAt'])
        self.assertEqual(obs['summary'],'Controller · Classify critical event · started')
        self.assertTrue(obs['recent'])
        self.assertIn('collector receipt times are unavailable',flow['narrative']['detail'])
        log['timestampNs'] = str(900*10**9)
        self.assertEqual(self.flow(receiver(),logs={'logs':[log]})['mode'],'recorded')

    @staticmethod
    def legacy_coordinator_context(**patch):
        return {'runId':'demo-1','step':'recheck_fault','traceId':TRACE,'spanId':SPAN,
                'startedNs':str(995*10**9),**patch}

    @staticmethod
    def legacy_coordinator_log(**patch):
        return {'id':'owned-start','traceId':TRACE,'spanId':SPAN,'timestampNs':str(999*10**9),
                'viewerReceivedAt':999,'service':'kyverno-demo-controller',
                'attributes':{'flow.workflow':'kyverno-demo.recheck_fault','flow.result':'started'},**patch}

    def test_actual_context_scopes_legacy_start_log_before_span_arrives(self):
        log=self.legacy_coordinator_log()
        ctx=context(coordinatorContexts=[self.legacy_coordinator_context()])
        before=copy.deepcopy((log,ctx))
        flow=self.flow(receiver(),data=demo(phase='observing'),ctx=ctx,logs={'logs':[log]})
        self.assertEqual((log,ctx),before)
        self.assertEqual(len(flow['observations']),1)
        obs=flow['observations'][0]
        self.assertEqual(obs['scopeBasis'],'coordinator-context')
        self.assertEqual(obs['source'],'coordinator')
        self.assertEqual(obs['component'],'client')
        self.assertEqual(obs['stageId'],'fault')
        self.assertTrue(obs['recent'])
        self.assertIsNone(obs['traceId'])
        self.assertEqual(flow['scope']['traceIds'],[])
        self.assertNotIn('flow.run.id',log['attributes'])

    def test_actual_context_scopes_retained_legacy_span_and_log(self):
        span=record()
        span.update(service='kyverno-demo-controller',component='client',
                    attributes={'flow.workflow':'kyverno-demo.recheck_fault','flow.result':'completed'})
        state=receiver(span);state['traces'][0].update(components=['client'],edges=[])
        ctx=context(coordinatorContexts=[self.legacy_coordinator_context()])
        flow=self.flow(state,data=demo(phase='observing'),ctx=ctx,logs={'logs':[self.legacy_coordinator_log()]})
        self.assertEqual(len(flow['observations']),2)
        self.assertEqual(flow['scope']['traceIds'],[TRACE])
        self.assertEqual(flow['scope']['spanIds'],{TRACE:[SPAN]})
        self.assertEqual(flow['scope']['components'],['client'])
        self.assertTrue(all(r['scopeBasis']=='coordinator-context' for r in flow['observations']))
        self.assertTrue(all(r['traceId']==TRACE for r in flow['observations']))

    def test_legacy_context_join_rejects_wrong_run_step_trace_span_time_or_service(self):
        anchor=self.legacy_coordinator_context()
        for field,value in [('runId','old-run'),('step','classify'),('traceId','c'*32),
                            ('spanId','c'*16),('traceId','0'*32),('spanId','0'*16),
                            ('startedNs',str(1000*10**9)),('startedNs','invalid')]:
            ctx=context(coordinatorContexts=[dict(anchor,**{field:value})])
            self.assertEqual(self.flow(receiver(),ctx=ctx,logs={'logs':[self.legacy_coordinator_log()]})['observations'],[],field)
        for field,value in [('service','foreign-service'),('traceId','c'*32),('spanId','c'*16),
                            ('timestampNs',str(990*10**9))]:
            log=self.legacy_coordinator_log(**{field:value})
            self.assertEqual(self.flow(receiver(),ctx=context(coordinatorContexts=[anchor]),logs={'logs':[log]})['observations'],[],field)
        self.assertEqual(self.flow(receiver(),ctx=context(runId='other-run',coordinatorContexts=[anchor]),logs={'logs':[self.legacy_coordinator_log()]})['observations'],[])

    def test_legacy_context_never_overrides_received_identity_or_native_metadata(self):
        ctx=context(coordinatorContexts=[self.legacy_coordinator_context()])
        attrs=self.legacy_coordinator_log()['attributes']
        for extra in ({'flow.run.id':'other-run'},{'flow.run.id':''},{'a2a.task.id':'task-1'},
                      {'gen_ai.task.id':'other'},{'gen_ai.conversation.id':'session-1'},
                      {'kagent.session.id':'other'},{'flow.workflow':'kyverno-demo.classify'},
                      {'flow.result':'made-up'}):
            log=self.legacy_coordinator_log(attributes={**attrs,**extra})
            self.assertEqual(self.flow(receiver(),ctx=ctx,logs={'logs':[log]})['observations'],[],extra)

    def test_legacy_context_does_not_refresh_old_event_or_override_arrival_provenance(self):
        ctx=context(coordinatorContexts=[self.legacy_coordinator_context(startedNs=str(800*10**9))])
        log=self.legacy_coordinator_log(timestampNs=str(900*10**9))
        flow=self.flow(receiver(),ctx=ctx,logs={'logs':[log]})
        obs=flow['observations'][0]
        self.assertEqual(flow['mode'],'recorded')
        self.assertFalse(obs['recent'])
        self.assertIsNone(obs['receivedAt'])
        self.assertEqual(obs['viewerReceivedAt'],999)
        self.assertEqual(obs['receiptSource'],'viewer')

    def coordinator_tree(self, received_run=False):
        anchor=record();anchor.update(service='kyverno-demo-controller',component='client',attributes={'flow.workflow':'kyverno-demo.classify','flow.result':'completed'})
        if received_run:anchor['attributes']['flow.run.id']='demo-1'
        gateway=record();gateway.update(spanId='c'*16,parentSpanId=SPAN,component='agentgateway',service='agentgateway',attributes={})
        model=record();model.update(spanId='d'*16,parentSpanId='c'*16,component='model',service='provider',attributes={})
        state=receiver(anchor,gateway,model);state['traces'][0].update(components=['client','agentgateway','model'],edges=[])
        ctx=context(coordinatorContexts=[self.legacy_coordinator_context(step='classify')])
        return state,ctx

    def test_owned_classifier_gateway_and_model_descendants_are_actual_observations(self):
        for direct in (False,True):
            state,ctx=self.coordinator_tree(direct);before=copy.deepcopy(state)
            flow=self.flow(state,data=demo(phase='classifying'),ctx=ctx)
            self.assertEqual(state,before)
            self.assertEqual({o['source'] for o in flow['observations']},{'coordinator','gateway','model'})
            self.assertTrue(all(o['stageId']=='classify' for o in flow['observations']))
            self.assertTrue(all(o['scopeBasis']=='coordinator-causal' for o in flow['observations'] if o['source']!='coordinator'))
            self.assertNotEqual(flow['stages'][1]['workflow'],'passed')
            self.assertNotIn('kagent',flow['scope']['components'])

    def test_classifier_ancestors_siblings_and_tool_intermediates_cannot_lend_scope(self):
        state,ctx=self.coordinator_tree()
        anchor,gateway,model=state['traces'][0]['spans']
        anchor['parentSpanId']='e'*16
        ancestor=copy.deepcopy(gateway);ancestor.update(spanId='e'*16,parentSpanId='')
        sibling=copy.deepcopy(model);sibling.update(spanId='f'*16,parentSpanId='e'*16)
        tool=copy.deepcopy(gateway);tool.update(spanId='1'*16,parentSpanId=SPAN,component='mcp')
        child=copy.deepcopy(gateway);child.update(spanId='2'*16,parentSpanId='1'*16)
        state['traces'][0]['spans'] += [ancestor,sibling,tool,child]
        flow=self.flow(state,ctx=ctx)
        self.assertEqual(set(flow['scope']['spanIds'][TRACE]),{SPAN,'c'*16,'d'*16})
        self.assertEqual(len(flow['observations']),3)
        gateway['attributes']['gen_ai.conversation.id']='foreign-session'
        flow=self.flow(state,ctx=ctx)
        self.assertEqual(flow['scope']['spanIds'][TRACE],[SPAN])
        self.assertEqual(len(flow['observations']),1)

    def test_original_triage_remains_exactly_scoped_beside_current_task(self):
        old=record();new=record();new.update(traceId='c'*32,spanId='d'*16)
        new['attributes']['a2a.task.id']='continued-task'
        state=receiver(old);other=receiver(new)['traces'][0];other['traceId']='c'*32;state['traces'].append(other)
        ctx=context(tasks={'triage':{'taskId':'continued-task','sessionId':'session-1'},
                           'triage_original':{'taskId':'task-1','sessionId':'session-1'}})
        flow=self.flow(state,ctx=ctx)
        self.assertEqual(set(flow['scope']['traceIds']),{TRACE,'c'*32})
        self.assertTrue(all(o['stageId']=='triage' for o in flow['observations']))
        old['attributes']['gen_ai.conversation.id']='wrong-session'
        self.assertEqual(self.flow(state,ctx=ctx)['scope']['traceIds'],['c'*32])

    def native_mcp_pair(self):
        client=record(**{'gen_ai.tool.name':'read_policy_repository'})
        client.update(toolExecution='native-internal',toolCategory='native')
        server=record()
        server.update(spanId='c'*16,parentSpanId='d'*16,startNs=str(996*10**9),endNs=str(998*10**9),
                      service='kyverno-gitlab-mcp',component='mcp',toolExecution='server',toolCategory='mcp',
                      attributes={'gen_ai.tool.name':'read_policy_repository','mcp.tool.name':'read_policy_repository'})
        state=receiver(client,server);state['traces'][0].update(components=['kagent','mcp'],edges=[])
        return state,client,server

    def test_missing_parent_backend_joins_only_exact_native_tool_window_and_labels_inference(self):
        state,client,server=self.native_mcp_pair();before=copy.deepcopy(state)
        flow=self.flow(state)
        self.assertEqual(state,before)
        self.assertEqual(flow['scope']['spanIds'][TRACE],[SPAN,'c'*16])
        self.assertEqual(flow['scope']['components'],['kagent','mcp'])
        backend=next(r for r in flow['observations'] if r['spanId']=='c'*16)
        self.assertEqual(backend['scopeBasis'],'native-tool-window')
        self.assertEqual(backend['source'],'mcp')
        self.assertEqual(backend['stageId'],'triage')
        self.assertTrue(backend['recent'])
        edge=flow['scope']['edges'][0]
        self.assertEqual((edge['from'],edge['to']),('kagent','mcp'))
        self.assertEqual(edge['traceIds'],[TRACE])
        self.assertEqual(set(edge['spanIds']),{SPAN,'c'*16})
        self.assertEqual(edge['basis'],'same trace, tool and interval (parent missing)')
        self.assertNotEqual(flow['stages'][2]['workflow'],'passed')
        self.assertNotIn('a2a.task.id',server['attributes'])

    def test_backend_window_rejects_ambiguous_and_unrelated_or_malformed_records(self):
        cases=[('service','foreign-mcp'),('traceId','e'*32),('component','kagent'),
               ('toolExecution','native-internal'),('parentSpanId',''),('parentSpanId','invalid'),
               ('parentSpanId','0'*16),('parentSpanId',1111111111111111),('spanId','0'*16),
               ('spanId',1111111111111111),('startNs',str(995*10**9)),
               ('endNs',str(999*10**9)),('startNs',str(990*10**9)),('endNs',str(1000*10**9)),
               ('startNs','nan'),('startNs',True),('endNs',None)]
        for field,value in cases:
            state,client,server=self.native_mcp_pair();server[field]=value
            flow=self.flow(state)
            self.assertFalse(any(r['source']=='mcp' for r in flow['observations']),(field,value))
            self.assertFalse(any(e['to']=='mcp' for e in flow['scope']['edges']),(field,value))
        for extra in ({'gen_ai.tool.name':'unrelated_secret_tool','mcp.tool.name':'unrelated_secret_tool'},
                      {'a2a.task.id':'other-task'},{'gen_ai.conversation.id':'other-session'},
                      {'flow.run.id':'other-run'},{'flow.run.id':''},{'a2a.task.id':''},{'kagent.session.id':None},{'mcp.tool.name':'different'}, {'mcp.tool.name':123},{'mcp.tool.name':None}):
            state,client,server=self.native_mcp_pair();server['attributes'].update(extra)
            self.assertFalse(any(r['source']=='mcp' for r in self.flow(state)['observations']),extra)
        state,client,server=self.native_mcp_pair()
        duplicate=copy.deepcopy(client);duplicate['spanId']='e'*16
        state['traces'][0]['spans'].append(duplicate)
        self.assertFalse(any(r['source']=='mcp' for r in self.flow(state)['observations']))
        state,client,server=self.native_mcp_pair()
        other=record();other.update(spanId='d'*16,attributes={})
        state['traces'][0]['spans'].append(other)
        self.assertFalse(any(r['source']=='mcp' for r in self.flow(state)['observations']))

    def test_backend_window_requires_native_role_and_preserves_stale_and_original_task_semantics(self):
        state,client,server=self.native_mcp_pair()
        self.assertEqual(self.flow(state,ctx=context(tasks={}))['observations'],[])
        no_session=self.flow(state,ctx=context(tasks={'triage':{'taskId':'task-1','sessionId':None}}))
        self.assertFalse(any(r['source']=='mcp' for r in no_session['observations']))
        server['receivedAt']=900
        flow=self.flow(state)
        backend=next(r for r in flow['observations'] if r['source']=='mcp')
        self.assertFalse(backend['recent'])
        ctx=context(tasks={'triage':{'taskId':'new-task','sessionId':'new-session'},
                           'triage_original':{'taskId':'task-1','sessionId':'session-1'}})
        flow=self.flow(state,ctx=ctx)
        self.assertEqual(next(r for r in flow['observations'] if r['source']=='mcp')['stageId'],'triage')
        self.assertEqual(flow['tasks']['triage_original']['traceIds'],[TRACE])

    def test_unconnected_span_not_included_from_matched_trace(self):
        unrelated = record()
        unrelated['spanId'] = 'c'*16
        unrelated['attributes'] = {}
        flow = self.flow(receiver(record(),unrelated))
        self.assertEqual(len(flow['observations']),1)
        child = copy.deepcopy(unrelated)
        child['parentSpanId'] = SPAN
        flow = self.flow(receiver(record(),child))
        self.assertEqual(len(flow['observations']),2)

    def test_actual_receipts_blocked_unknown_suppressed_and_resolution_gates(self):
        for state in ('blocked','unknown'):
            flow = self.flow(data=demo(phase=state,events=[{'stage':'observe_fault','state':state}]))
            self.assertEqual(flow['currentStage'],'fault')
            self.assertEqual(flow['stages'][0]['workflow'], state)
        flow = self.flow(data=demo(phase='suppressed',events=[{'stage':'classify','state':'suppressed'}]))
        self.assertEqual(flow['stages'][1]['workflow'],'waiting')
        self.assertIn('suppressed',flow['narrative']['detail'])
        for phase, verified, expected in [('closed',True,'passed'),('closed',False,'unknown'),('verifying',True,'unknown')]:
            flow = self.flow(data=demo(phase=phase,ticket={'closedVerified':verified},events=[{'stage':'close','state':'completed'}]))
            self.assertEqual(flow['stages'][-1]['workflow'],expected)


if __name__ == '__main__':
    unittest.main()
