import copy
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from onboarding import (API, REQUIRED, ROLES, NamedObjectReader, ReviewedPlan, canonical,
                        observe, object_path, pin, project_receipt, publish, read_view)
import test_ui as runtime_ui
from test_ui import ui_span, ui_trace

NOW = 1792612800


def fixture():
    objects = {}
    for role, (api, kind, _) in ROLES.items():
        objects[role] = {'apiVersion': api, 'kind': kind,
            'metadata': {'name': role.lower(), 'namespace': 'kagent', 'uid': role + '-uid', 'generation': 1},
            'spec': {}, 'status': {'conditions': [{'type': c, 'status': 'True', 'observedGeneration': 1}
                for c in ('Accepted', 'Ready', 'ResolvedRefs', 'Compatible', 'EgressPoliciesApplied')]}}
    objects['declarations']['spec'] = {'ref': {'commit': 'a' * 40}}
    objects['declarations']['status']['artifact'] = {'revision': 'sha1:' + 'a' * 40}
    objects['flux']['status']['lastAppliedRevision'] = 'sha1:' + 'a' * 40
    objects['hosted']['metadata']['name'] = 'aks-onboarding-v1'
    objects['agent']['metadata']['name'] = 'hosted-aks-onboarding-v1'
    objects['golden']['metadata']['name'] = 'aks-onboarding-v1'
    profile = {'runtimeProfile': 'lab-kagent-1x-v1', 'modelProfile': 'skills-demo-gateway-v1',
        'modelConfig': {'name': 'model', 'specSha256': canonical({})},
        'harness': {'name': 'harness', 'specSha256': canonical({})}, 'packages': {}}
    hosted = objects['hosted']
    hosted['spec'] = {'runtimeProfile': profile['runtimeProfile'], 'modelProfile': profile['modelProfile'],
                      'toolGrantRefs': [], 'instructions': 'DO-NOT-EXPORT-INSTRUCTIONS'}
    bindings = []
    for role, field in [('skill', 'skillRefs'), ('knowledge', 'knowledgeBaseRefs')]:
        release, source, cm = (objects[k] for k in (role, role + 'Source', role + 'ConfigMap'))
        source['spec'] = {'ref': {'commit': 'a' * 40}}
        source['status']['artifact'] = {'revision': 'sha1:' + 'a' * 40}
        cm.update(immutable=True, data={'file00': 'DO-NOT-EXPORT-CONTENT'})
        cm.pop('spec')
        release['spec'] = {'sourceRef': {'name': source['metadata']['name']}, 'sourceCommit': 'a' * 40, 'contentSha256': 'b' * 64}
        release['status'].update(configMapRef={'name': cm['metadata']['name']}, contentSha256='b' * 64,
                                 observedSourceRevision='sha1:' + 'a' * 40)
        selected = {'name': release['metadata']['name'], 'sourceCommit': 'a' * 40, 'contentSha256': 'b' * 64}
        hosted['spec'][field] = [selected]
        entry = {**selected, 'sourceSpecSha256': canonical(source['spec']), 'releaseSpecSha256': canonical(release['spec']),
                 'image': 'registry.example.invalid/reviewed@sha256:' + 'c' * 64, 'packaging': 'reviewed-content-ustar-v3'}
        profile['packages'][release['kind'] + '/' + release['metadata']['name']] = entry
        bindings.append({**selected, 'kind': release['kind'], 'uid': release['metadata']['uid'], 'configMapName': cm['metadata']['name'],
            'configMapUID': cm['metadata']['uid'], 'sourceUID': source['metadata']['uid'], 'sourceRevision': 'sha1:' + 'a' * 40,
            'sourceSpecSha256': canonical(source['spec']), 'image': entry['image'], 'packaging': entry['packaging']})
    objects['profile'].pop('spec')
    objects['profile']['data'] = {'profile.json': json.dumps(profile)}
    objects['agent']['spec'] = {'template': {'ref': {'name': objects['template']['metadata']['name']}}}
    objects['agent']['status'].update(desiredRevision='d' * 64, latestSuccessfulRevision='d' * 64)
    hosted['status'].update(bindings=bindings, profileSha256=canonical(profile), agentRef={'name': objects['agent']['metadata']['name']},
        agentSpecSha256=canonical(objects['agent']['spec']), templateSpecSha256=canonical(objects['template']['spec']))
    refs = []
    for role, obj in objects.items():
        ref = {'role': role, 'apiVersion': obj['apiVersion'], 'kind': obj['kind'],
               'namespace': obj['metadata']['namespace'], 'name': obj['metadata']['name']}
        field = 'data' if obj['kind'] == 'ConfigMap' else 'spec'
        ref[field + 'Sha256'] = canonical(obj[field])
        refs.append(ref)
    plan = ReviewedPlan.parse({'schemaVersion': 1, 'namespace': 'kagent', 'hostedName': 'aks-onboarding-v1',
        'agentName': 'hosted-aks-onboarding-v1', 'profileSha256': canonical(profile), 'objects': refs})
    return plan, objects


def reader(objects):
    return lambda ref: copy.deepcopy(objects[ref['role']])


def stage(value, role):
    return next(s for s in value['stages'] if s['key'] == role)


def runner_files(objects):
    pins = {obj['kind'] + '/' + obj['metadata']['name']: {'uid': obj['metadata']['uid'], 'generation': 1,
            'spec': obj.get('spec'), 'data': obj.get('data'), 'immutable': obj.get('immutable')}
            for role, obj in objects.items() if role in REQUIRED}
    before = {'pins': pins, 'agentRevision': 'd' * 64}
    session = {'id': 'session-1', 'preparedRevision': 'd' * 64,
               'agent': {'namespace': 'kagent', 'name': 'hosted-aks-onboarding-v1'}}
    return {'before': before, 'after': copy.deepcopy(before),
        'receipt': {'result': 'Passed', 'sessionId': 'session-1', 'taskId': 'task-1',
                    'agentName': session['agent']['name'], 'agentRevision': 'd' * 64,
                    'dependenciesUnchanged': True, 'dependencyPinsSha256': canonical(before)},
        'scenario': {**objects['golden'], 'spec': {'hostedAgentRef': {'name': 'aks-onboarding-v1'}}},
        'task': {'task': {'id': 'task-1', 'contextId': 'session-1', 'status': {'state': 'TASK_STATE_COMPLETED'},
                          'artifacts': [{'text': 'DO-NOT-EXPORT-PROOF'}]}},
        'session-created': {'session': copy.deepcopy(session)}, 'session-after': {'session': session}}


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.objects = fixture()

    def test_ready_named_two_pass_metadata_only(self):
        calls = []
        def get(ref):
            calls.append(object_path(ref))
            return copy.deepcopy(self.objects[ref['role']])
        result = observe(self.plan, get, NOW)
        self.assertTrue(all(s['state'] == 'ready' for s in result['stages']), result['stages'])
        self.assertEqual(len(calls), 30)
        self.assertTrue(all(p.count('/namespaces/') == 1 for p in calls))
        self.assertNotIn('DO-NOT-EXPORT', json.dumps(result))
        self.assertEqual(result['history'][0]['observedAt'], NOW)

    def test_stale_conditions_and_failed_revision_cannot_be_ready(self):
        for condition in ('Accepted', 'ResolvedRefs', 'Compatible', 'EgressPoliciesApplied', 'Ready'):
            objects = copy.deepcopy(self.objects)
            next(c for c in objects['agent']['status']['conditions'] if c['type'] == condition)['observedGeneration'] = 0
            self.assertEqual(stage(observe(self.plan, reader(objects), NOW), 'agent')['reasonCode'], 'StaleGeneration')
        self.objects['agent']['status']['latestSuccessfulRevision'] = 'e' * 64
        result = observe(self.plan, reader(self.objects), NOW)
        self.assertEqual(stage(result, 'agent')['reasonCode'], 'RevisionMismatch')
        self.assertNotEqual(stage(result, 'hosted')['state'], 'ready')

    def test_source_commit_and_binding_uid_drift_block(self):
        for role, change in [('skillSource', lambda o: o['status']['artifact'].update(revision='sha1:' + 'e' * 40)),
                             ('skillConfigMap', lambda o: o['metadata'].update(uid='replaced'))]:
            objects = copy.deepcopy(self.objects)
            change(objects[role])
            self.assertEqual(stage(observe(self.plan, reader(objects), NOW), 'skill')['state'], 'blocked')

    def test_uid_replacement_stays_blocked_across_polls(self):
        original = observe(self.plan, reader(self.objects), NOW)
        self.objects['hosted']['metadata']['uid'] = 'replacement'
        changed = observe(self.plan, reader(self.objects), NOW + 3, original)
        again = observe(self.plan, reader(self.objects), NOW + 6, changed)
        self.assertEqual(stage(again, 'hosted')['reasonCode'], 'UIDChanged')
        self.assertEqual(again['pins']['hosted']['uid'], 'replacement')
        self.assertEqual(again['uidPins']['hosted'], 'hosted-uid')

    def test_missing_denied_and_deleting_replace_green(self):
        previous = observe(self.plan, reader(self.objects), NOW)
        for code, expected in [(404, 'pending'), (403, 'unknown'), (500, 'unknown')]:
            def failed(ref):
                if ref['role'] == 'agent':
                    raise urllib.error.HTTPError('', code, 'DO-NOT-EXPORT-EXCEPTION', {}, None)
                return self.objects[ref['role']]
            value = observe(self.plan, failed, NOW + 1, previous)
            self.assertEqual(stage(value, 'agent')['state'], expected)
            self.assertNotIn('DO-NOT-EXPORT', json.dumps(value))
        self.objects['agent']['metadata']['deletionTimestamp'] = '2026-10-21T00:00:00Z'
        self.assertNotEqual(stage(observe(self.plan, reader(self.objects), NOW), 'agent')['state'], 'ready')

    def test_flux_ready_for_old_commit_is_pending(self):
        self.objects['flux']['status']['lastAppliedRevision'] = 'sha1:' + 'f' * 40
        result = observe(self.plan, reader(self.objects), NOW)
        self.assertEqual(stage(result, 'declarations')['state'], 'pending')
        self.assertEqual(stage(result, 'declarations')['reasonCode'], 'DeliveryRevisionMismatch')

    def test_torn_status_rejected(self):
        calls = {}
        def torn(ref):
            obj = copy.deepcopy(self.objects[ref['role']])
            calls[ref['role']] = calls.get(ref['role'], 0) + 1
            if ref['role'] == 'agent' and calls['agent'] == 2:
                obj['status']['desiredRevision'] = 'e' * 64
            return obj
        self.assertEqual(stage(observe(self.plan, torn, NOW), 'agent')['reasonCode'], 'TornSample')

    def test_agent_readiness_requires_current_profile_dependencies(self):
        for dependency in ('model', 'harness', 'profile'):
            calls = {}
            def torn(ref):
                role = ref['role']
                obj = copy.deepcopy(self.objects[role])
                calls[role] = calls.get(role, 0) + 1
                if role == dependency and calls[role] == 2:
                    obj['status']['conditions'][0]['status'] = 'False'
                return obj
            value = observe(self.plan, torn, NOW)
            self.assertEqual(stage(value, 'agent')['reasonCode'], 'DependencyMismatch')

    def test_flux_plan_requires_both_source_and_kustomization(self):
        for role in ('declarations', 'flux'):
            value = copy.deepcopy(self.plan.value)
            value['objects'] = [obj for obj in value['objects'] if obj['role'] != role]
            with self.assertRaises(ValueError):
                ReviewedPlan.parse(value)

    def test_snapshot_expiry_future_and_injected_content_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            value = observe(self.plan, reader(self.objects), NOW)
            publish(path, value)
            self.assertEqual(read_view(path, NOW + 1)['freshness'], 'current')
            for clock in (NOW - 1, NOW + 16):
                self.assertTrue(all(s['state'] == 'unknown' for s in read_view(path, clock)['stages']))
            for mutate in (lambda v: v.update(instructions='PRIVATE'),
                           lambda v: v['pins']['hosted'].update(spec={'prompt': 'PRIVATE'}),
                           lambda v: v['stages'][0].update(reasonCode='PRIVATE'),
                           lambda v: v['history'][0].update(statusMessage='PRIVATE')):
                injected = copy.deepcopy(value)
                mutate(injected)
                path.write_text(json.dumps(injected))
                result = read_view(path, NOW + 1)
                self.assertEqual(result['freshness'], 'unavailable')
                self.assertNotIn('PRIVATE', json.dumps(result))
            path.write_text('x' * (128 * 1024 + 1))
            self.assertEqual(read_view(path, NOW)['freshness'], 'unavailable')

    def test_history_bounded_actual_changes_only(self):
        value = None
        for n in range(40):
            self.objects['agent']['status']['latestSuccessfulRevision'] = ('d' if n % 2 else 'e') * 64
            value = observe(self.plan, reader(self.objects), NOW + n, value)
        self.assertEqual(len(value['history']), 32)
        unchanged = observe(self.plan, reader(self.objects), NOW + 41, value)
        self.assertEqual(unchanged['history'], value['history'])

    def test_plan_rejects_broad_routes_unknown_keys_and_unreviewed_hashes(self):
        for mutate in (lambda p: p.update(url='https://unreviewed.invalid'),
                       lambda p: p['objects'][0].update(name='../secrets'),
                       lambda p: p['objects'][0].pop('specSha256'),
                       lambda p: p['objects'][0].update(kind='Secret')):
            value = copy.deepcopy(self.plan.value)
            mutate(value)
            with self.assertRaises(ValueError):
                ReviewedPlan.parse(value)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.objects = fixture()
        self.objects['golden']['spec'] = {'hostedAgentRef': {'name': 'aks-onboarding-v1'}}
        for ref in self.plan.value['objects']:
            if ref['role'] == 'golden':
                ref['specSha256'] = canonical(self.objects['golden']['spec'])
        self.files = runner_files(self.objects)

    def project(self, files):
        with tempfile.TemporaryDirectory() as directory:
            for name, value in files.items():
                (Path(directory) / (name + '.json')).write_text(json.dumps(value))
            return project_receipt(directory, NOW)

    def test_receipt_projects_exact_thirteen_pins_and_compares_current(self):
        record = self.project(self.files)
        self.assertEqual(len(record['pins']), 13)
        self.assertNotIn('DO-NOT-EXPORT', json.dumps(record))
        value = observe(self.plan, reader(self.objects), NOW, receipt=record)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            publish(path, value)
            self.assertTrue(read_view(path, NOW + 1)['golden']['appliesToCurrent'])
            value['pins']['agent']['uid'] = 'different'
            publish(path, value)
            self.assertFalse(read_view(path, NOW + 1)['golden']['appliesToCurrent'])
            self.assertEqual(read_view(path, NOW + 16)['golden']['result'], 'passed')
            self.assertFalse(read_view(path, NOW + 16)['golden']['appliesToCurrent'])

    def test_receipt_rejects_changed_dependencies_revision_session_task_and_noncompletion(self):
        changes = [lambda f: f['after']['pins']['Agent/hosted-aks-onboarding-v1'].update(uid='new'),
            lambda f: f['receipt'].update(dependencyPinsSha256='0' * 64),
            lambda f: f['receipt'].update(result='Failed'),
            lambda f: f['receipt'].update(dependenciesUnchanged=False),
            lambda f: f['session-after']['session'].update(preparedRevision='e' * 64),
            lambda f: f['task']['task'].update(contextId='different'),
            lambda f: f['task']['task']['status'].update(state='TASK_STATE_WORKING'),
            lambda f: f['receipt'].update(taskId='different')]
        for mutate in changes:
            files = copy.deepcopy(self.files)
            mutate(files)
            with self.assertRaises(ValueError):
                self.project(files)

    def test_historical_pass_never_applies_to_unstable_dependency_sample(self):
        record = self.project(self.files)
        for dependency in REQUIRED:
            for failure in ('uid', 'status', 'denied'):
                calls = {}
                def torn(ref):
                    role = ref['role']
                    obj = copy.deepcopy(self.objects[role])
                    calls[role] = calls.get(role, 0) + 1
                    if role == dependency and calls[role] == 2:
                        if failure == 'denied':
                            raise urllib.error.HTTPError('', 403, 'PRIVATE-ERROR-BODY', {}, None)
                        if failure == 'uid':
                            obj['metadata']['uid'] = 'changed-between-reads'
                        else:
                            obj['status']['conditions'][0]['status'] = 'False'
                    return obj
                value = observe(self.plan, torn, NOW, receipt=record)
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / 'snapshot.json'
                    publish(path, value)
                    view = read_view(path, NOW + 1)
                    self.assertEqual(view['golden']['result'], 'passed')
                    self.assertFalse(view['golden']['appliesToCurrent'], (dependency, failure))
                    self.assertIn(view['sampleErrors'][dependency], {'TornSample', 'Unavailable'})
                    self.assertNotIn('PRIVATE-ERROR-BODY', json.dumps(view))


class OnboardingUiTests(unittest.TestCase):
    run_ui = runtime_ui.UiBehaviorTests.run_ui

    def state(self, trace=None):
        plan, objects = fixture()
        view = observe(plan, reader(objects), NOW)
        view.update(freshness='current', capturedAt=4102444000, expiresAt=4102444060)
        return {'revision': 1, 'traces': [trace] if trace else [], 'invocation': {'status': 'idle'},
            'sessionActivity': None, 'onboarding': view, 'runtime': {'readOnlyViewer': True, 'executionTargets': []}}

    def test_three_tabs_keyboard_and_browser_freshness(self):
        self.run_ui(self.state(), r"""
          setView('onboarding');assert.equal($('onboarding-view').hidden,false);assert.equal($('prompt-column').hidden,true);
          renderOnboarding(4102444001);assert.equal($('onboarding-pipeline').children.length,6);
          assert.match($('onboarding-pipeline').textContent,/ready/);assert.match($('onboarding-golden').textContent,/No validated/);
          renderOnboarding(4102444061);assert.match($('onboarding-freshness').textContent,/Expired/);
          assert.doesNotMatch($('onboarding-pipeline').textContent,/ready/);
          $('tab-onboarding').onkeydown({key:'ArrowRight',preventDefault(){}});assert.equal($('visual-view').hidden,false);
          $('tab-visual').onkeydown({key:'ArrowRight',preventDefault(){}});assert.equal($('logs-view').hidden,false);
          $('tab-logs').onkeydown({key:'ArrowRight',preventDefault(){}});assert.equal($('onboarding-view').hidden,false);
          $('tab-onboarding').onkeydown({key:'End',preventDefault(){}});assert.equal($('tab-onboarding').attributes['aria-selected'],'true');
          setView('visual');assert.equal($('prompt-column').hidden,false);
        """)

    def test_golden_runtime_exact_native_identity_and_separate_read_counts(self):
        spans = [ui_span(1, 'load_skill', 'skill', 'native-skill'), ui_span(2, 'load_skill_resource', 'skill', 'native-skill')]
        for span in spans:
            span['attributes'].update({'gen_ai.conversation.id': 'session-1', 'a2a.task.id': 'task-1',
                                      'gen_ai.main_agent.name': 'hosted-aks-onboarding-v1'})
        trace = ui_trace(spans=spans)
        trace['nativeRuntimeIdentity']['agentName'] = 'hosted-aks-onboarding-v1'
        value = self.state(trace)
        value['onboarding']['golden'] = {'result': 'passed', 'scenarioName': 'aks-onboarding-v1', 'recordedAt': NOW,
            'agentRevision': 'd' * 64, 'agentName': 'hosted-aks-onboarding-v1', 'namespace': 'kagent',
            'sessionId': 'session-1', 'taskId': 'task-1', 'appliesToCurrent': False}
        self.run_ui(value, r"""
          renderOnboarding(4102444001);assert.equal($('onboarding-trace').disabled,false);
          assert.match($('onboarding-runtime').textContent,/1 load_skill · 1 load_skill_resource/);
          assert.match($('onboarding-golden').textContent,/Historical result/);
          $('onboarding-trace').onclick();assert.equal(selectedId,'11111111111111111111111111111111');
          state.traces[0].spans[0].attributes['a2a.task.id']='different';state.traces[0].spans[1].attributes['a2a.task.id']='different';
          renderOnboarding(4102444001);assert.equal($('onboarding-trace').disabled,true);
          for(const span of state.traces[0].spans)span.attributes['a2a.task.id']='task-1';
          state.traces[0].nativeRuntimeIdentity={agentName:'other',agentId:'kagent/other'};
          renderOnboarding(4102444001);assert.equal($('onboarding-trace').disabled,true);
          state.traces=[];renderOnboarding();assert.equal($('onboarding-trace').disabled,true);
          assert.match($('onboarding-runtime').textContent,/No retained native trace/);
          assert.equal(calls.filter(c=>c.url==='/api/invoke').length,0);
        """)

    def test_exact_runtime_reads_aggregate_across_traces_without_duplicates(self):
        value = self.state()
        traces = []
        for number, tool in [(1, 'load_skill'), (2, 'load_skill_resource')]:
            span = ui_span(number, tool, 'skill', 'native-skill')
            span['traceId'] = str(number) * 32
            span['attributes'].update({'gen_ai.conversation.id': 'session-1', 'a2a.task.id': 'task-1',
                                      'gen_ai.main_agent.name': 'hosted-aks-onboarding-v1'})
            trace = ui_trace(trace_id=span['traceId'], spans=[span, copy.deepcopy(span)])
            trace['nativeRuntimeIdentity']['agentName'] = 'hosted-aks-onboarding-v1'
            traces.append(trace)
        value['traces'] = traces
        value['onboarding']['golden'] = {'result': 'passed', 'scenarioName': 'aks-onboarding-v1', 'recordedAt': NOW,
            'agentRevision': 'd' * 64, 'agentName': 'hosted-aks-onboarding-v1', 'namespace': 'kagent',
            'sessionId': 'session-1', 'taskId': 'task-1', 'appliesToCurrent': False}
        self.run_ui(value, r"""
          renderOnboarding(4102444001);
          assert.match($('onboarding-runtime').textContent,/1 load_skill · 1 load_skill_resource/);
          assert.match($('onboarding-runtime').textContent,/across 2 retained traces/);
          assert.equal($('onboarding-other-traces').children.length,1);
          $('onboarding-other-traces').children[0].onclick();assert.equal(selectedId,'22222222222222222222222222222222');
        """)


    def configured_trace(self, trace_id='1' * 32, start='1000000000', native=True):
        spans = [ui_span(n, 'load_skill' if n < 4 else 'load_skill_resource', 'skill', 'native-skill') for n in range(1, 7)]
        for span in spans:
            span['traceId'] = trace_id
            span['attributes'].update({'gen_ai.conversation.id': 'session-1', 'a2a.task.id': 'task-1',
                                      'gen_ai.main_agent.name': 'hosted-aks-onboarding-v1'})
        trace = ui_trace(trace_id=trace_id, spans=spans)
        trace.update(startNs=start, nativeRequest=native)
        trace['nativeRuntimeIdentity'] = {'runtime': 'adk-go', 'agentName': 'hosted-aks-onboarding-v1',
                                         'agentId': 'kagent/hosted-aks-onboarding-v1'}
        return trace

    def test_onboarding_composes_one_graph_owner_with_real_node_and_card_interactions(self):
        self.assertIn('.agent-workspace.onboarding-wide{grid-template-columns:minmax(0,1fr)}',
                      (Path(__file__).parent / 'ui/style.css').read_text())
        self.run_ui(self.state(self.configured_trace()), r"""
          const owner=$('runtime-flow'),diagram=$('diagram'),arrow=$('arrow');
          assert.equal(owner.parentNode,$('visual-flow-slot'));
          setView('onboarding');
          assert.equal(owner.parentNode,$('onboarding-flow-slot'));
          assert.equal($('agent-workspace').className.includes('onboarding-wide'),true);
          assert.equal($('visual-flow-slot').children.length,0);
          assert.equal($('onboarding-flow-slot').children.length,1);
          assert.equal($('onboarding-readiness-details').open,false);
          renderOnboarding(4102444001);assert.match($('onboarding-readiness').textContent,/6 \/ 6 onboarding checks ready/);
          const sections=$('onboarding-view').children;
          assert.ok(sections.indexOf($('onboarding-flow-slot'))<sections.indexOf($('onboarding-readiness-details')));
          $('node-skills').dispatchEvent({type:'click'});
          assert.equal(filter,'skills');assert.equal($('timeline').children.length,6);
          assert.match($('timeline-title').textContent,/Skills and knowledge/);
          $('observed-skills').children[4].onclick();
          assert.equal(follow,false);assert.equal(currentView,'onboarding');
          assert.match($('inspection').textContent,/load_skill_resource/);
          assert.equal($('node-mcp').className.includes('absent'),true);
          assert.equal($('mcp-servers').children.length,0);
          assert.match($('mcp-explanation').textContent,/0 tool grants. No MCP tools attached/);
          assert.equal($('edges').children.some(edge=>edge.className.includes('observed')&&edge.children[0].textContent.includes('→ mcp')),false);
          assert.match($('observed-skills-title').parentNode.textContent,/cannot be attributed to a skill or knowledge package/);
          for(const view of ['visual','onboarding','logs','onboarding','visual'])setView(view);
          assert.equal(owner.parentNode,$('visual-flow-slot'));
          assert.equal($('onboarding-flow-slot').children.length,0);
          assert.equal($('diagram'),diagram);assert.equal($('arrow'),arrow);
          const descendants=node=>[node,...node.children.filter(child=>typeof child!=='string').flatMap(descendants)];
          const nodes=descendants(root);
          assert.equal(nodes.filter(node=>node===owner).length,1);
          assert.equal(nodes.filter(node=>node.attributes.id==='diagram').length,1);
          assert.equal(nodes.filter(node=>node.attributes.id==='arrow').length,1);
          assert.equal(calls.filter(c=>c.options?.method==='POST').length,0);
        """)

    def test_follow_uses_latest_configured_native_request_and_keeps_manual_choice(self):
        value = self.state()
        value['traces'] = [ui_trace('9' * 32), self.configured_trace('3' * 32, '4000000000', False),
                           self.configured_trace('1' * 32), self.configured_trace('2' * 32, '2000000000')]
        self.run_ui(value, r"""
          setView('onboarding');assert.equal(selectedId,'22222222222222222222222222222222');
          assert.match($('onboarding-flow-scope').textContent,/Following · Observed request · not an acceptance test/);
          selectedId='11111111111111111111111111111111';follow=false;render();
          await poll();assert.equal(selectedId,'11111111111111111111111111111111');
          setView('visual');setView('onboarding');assert.equal(selectedId,'11111111111111111111111111111111');
          assert.match($('onboarding-flow-scope').textContent,/Manual selection/);
          selectedId='99999999999999999999999999999999';render();await poll();setView('onboarding');
          assert.equal(selectedId,'99999999999999999999999999999999');
          assert.match($('onboarding-flow-scope').textContent,/agent arbitrary-agent \(outside configured agent scope\)/);
          $('follow').onclick();assert.equal(selectedId,'22222222222222222222222222222222');
          state.traces=state.traces.filter(trace=>trace.traceId==='99999999999999999999999999999999'||!trace.nativeRequest);
          setView('onboarding');assert.equal(selectedId,null);
          assert.match($('onboarding-flow-scope').textContent,/No retained native request for the configured agent/);
          assert.equal($('node-skills').className.includes('absent'),true);
          state.onboarding=null;setView('onboarding');assert.equal(selectedId,null);
        """)

    def test_follow_prefers_exact_golden_task_over_newer_native_request(self):
        value = self.state(self.configured_trace())
        newer = self.configured_trace('2' * 32, '4000000000')
        for span in newer['spans']:
            span['attributes']['a2a.task.id'] = 'other-task'
        value['traces'].insert(0, newer)
        value['onboarding']['golden'] = {'result': 'passed', 'scenarioName': 'aks-onboarding-v1', 'recordedAt': NOW,
            'agentRevision': 'd' * 64, 'agentName': 'hosted-aks-onboarding-v1', 'namespace': 'kagent',
            'sessionId': 'session-1', 'taskId': 'task-1', 'appliesToCurrent': False}
        self.run_ui(value, r"""
          setView('onboarding');assert.equal(selectedId,'11111111111111111111111111111111');
          assert.match($('onboarding-flow-scope').textContent,/Recorded acceptance session \/ task/);
          assert.match($('onboarding-golden').textContent,/Historical result/);
          assert.match($('onboarding-runtime').textContent,/3 load_skill · 3 load_skill_resource spans across 1 retained traces/);
          await poll();assert.equal(selectedId,'11111111111111111111111111111111');
          for(const span of selected().spans)span.attributes['gen_ai.conversation.id']='other-session';
          setView('onboarding');assert.equal(selectedId,'22222222222222222222222222222222');
          assert.match($('onboarding-flow-scope').textContent,/Observed request · not an acceptance test/);
        """)
