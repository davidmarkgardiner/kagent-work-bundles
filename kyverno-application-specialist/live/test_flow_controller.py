from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
import uuid

from flow_controller import ApprovalConflict, ApprovalUnknown, ClosureProof, FlowController, FlowError, ResumeConflict, STEPS, StepResult


class Adapter:
    def __init__(self, pending=None, failure=None):
        self.calls, self.pending, self.failure = [], pending, failure
        self.approval, self.approval_calls = None, []

    def approve(self, run, request_id, head_sha, observe=False):
        self.approval_calls.append((request_id, head_sha, observe, run['_call'].copy()))
        if observe and self.approval is None:
            raise ApprovalUnknown('No actual grant')
        if self.approval is None:
            now = int(time.time())
            self.approval = {'approvalId':request_id, 'headSha':head_sha, 'approvedBy':7,
                             'approvedAt':now, 'expiresAt':now+900, 'state':'approved'}
        return self.approval

    def advance(self, run, step):
        self.calls.append((run["runId"], step, run["_call"].copy()))
        if step == self.failure:
            raise RuntimeError("private upstream data must never enter public events")
        if step == self.pending:
            return StepResult("pending", poll_after=0.01)
        if step == 'await_approval' and self.approval is None:
            return StepResult('pending', poll_after=0.01)
        patches = {
            "prepare": {"ticket": {"iid": 7, "state": "opened", "url": "https://gitlab.example.test/p/-/issues/7"}},
            "classify": {"classifier": {"decision": "investigate", "severity": "critical", "confidence": 0.97, "attempts": 1}},
            "dispatch": {"native": {"taskId": "actual-primary-task", "state": "WORKING"}},
            "triage": {"remedy": {"mrUrl": "https://gitlab.example.test/p/-/merge_requests/3", "headSha": "a" * 40, "ci":"passed", "review":"pending"}},
            "review": {"remedy":{"review":"passed"}},
            "await_approval": {"approval":self.approval},
            "merge": {"merge":{"taskId":"actual-merge-task", "taskState":"TASK_STATE_COMPLETED", "approvalId":self.approval["approvalId"] if self.approval else None}},
            "observe_merge": {"merge": {"status": "merged", "sha": "b" * 40, "mergedBy": "actual-agent-token-actor"}},
            "verify": {"verification": {"taskId": "actual-verification-task", "state": "completed"}},
            "close": {"ticket": {"state": "closed", "closedVerified": True}},
        }
        return StepResult("completed", patch=patches.get(step, {}))


class FlowControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "flow.sqlite"
        self.controllers = []
        self.addCleanup(self.close_controllers)

    def close_controllers(self):
        for controller in reversed(self.controllers):
            controller.close()

    def controller(self, adapter=None, **kwargs):
        controller = FlowController(self.path, adapter or Adapter(), scope={"namespace": "owned-demo", "targetBranch": "dashboard-main"}, autostart=False, **kwargs)
        self.controllers.append(controller)
        return controller

    def start(self, controller):
        return controller.start(str(uuid.uuid4()))

    def to_step(self, controller, step):
        for _ in range(STEPS.index(step)):
            self.tick(controller)

    def tick(self, controller):
        state = controller.public_state()
        if state["actions"]["approve"]["enabled"]:
            controller.approve(str(uuid.uuid4()), state["runId"], state["remedy"]["headSha"])
        return controller.run_once()

    @staticmethod
    def proof(run):
        return ClosureProof(True, "actual-verification-task", "TASK_STATE_COMPLETED", "c" * 64,
                            run["data"].get("ticket", {}).get("state") == "closed", 7)

    def test_insufficient_execution_allowance_waits_before_intent_call_and_telemetry(self):
        adapter=Adapter()
        adapter.execution_budget=lambda step:{'ready':False,'required':4,'remaining':2,'phase':'closed'}
        controller=self.controller(adapter)
        self.start(controller);self.to_step(controller,'merge')
        with controller._connection() as db:
            before=dict(db.execute('SELECT * FROM approval_requests').fetchone())
        callbacks=list(adapter.calls)
        observed=[]
        class Telemetry:
            def begin(self,run,step):observed.append(step)
        controller.telemetry=Telemetry()
        state=controller.run_once()
        self.assertEqual(state['phase'],'merging');self.assertTrue(state['running'])
        self.assertEqual(adapter.calls,callbacks);self.assertEqual(observed,[])
        self.assertEqual(state['approval']['state'],'approved')
        self.assertIn('no native task was sent',state['events'][-1]['message'])
        with controller._connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM intents WHERE step='merge'").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM calls WHERE step='merge'").fetchone()[0],0)
            self.assertEqual(dict(db.execute('SELECT * FROM approval_requests').fetchone()),before)

    def test_ready_execution_capacity_releases_one_first_execute_outside_transaction(self):
        adapter=Adapter();ready=[False];checks=[]
        controller=self.controller(adapter)
        def budget(step):
            probe=sqlite3.connect(self.path,timeout=.05)
            try:probe.execute('BEGIN IMMEDIATE');probe.rollback()
            finally:probe.close()
            checks.append(step)
            return {'ready':ready[0]}
        adapter.execution_budget=budget
        self.start(controller);self.to_step(controller,'merge')
        controller.run_once();ready[0]=True
        with controller._transaction() as db:db.execute('UPDATE runs SET next_poll=0')
        state=controller.run_once()
        self.assertEqual(state['phase'],'merging')
        merge=[call for call in adapter.calls if call[1]=='merge']
        self.assertEqual(len(merge),1);self.assertEqual(merge[0][2]['mode'],'execute')
        self.assertEqual(checks,['merge','merge'])

    def test_reserved_native_task_readback_does_not_wait_for_new_allowance(self):
        adapter=Adapter(pending='merge');ready=[True];checks=[]
        def budget(step):checks.append(step);return {'ready':ready[0]}
        adapter.execution_budget=budget
        controller=self.controller(adapter)
        self.start(controller);self.to_step(controller,'merge');controller.run_once()
        ready[0]=False
        with controller._transaction() as db:db.execute('UPDATE runs SET next_poll=0')
        controller.run_once()
        merge=[call for call in adapter.calls if call[1]=='merge']
        self.assertEqual([x[2]['mode'] for x in merge],['execute','observe'])
        self.assertEqual(merge[0][2]['intentId'],merge[1][2]['intentId'])
        self.assertEqual(checks,['merge'])

    def test_verification_waits_without_creating_a_task_then_executes_once(self):
        adapter=Adapter();verify_ready=[False]
        adapter.execution_budget=lambda step:{'ready':step=='merge' or verify_ready[0]}
        controller=self.controller(adapter)
        self.start(controller);self.to_step(controller,'verify')
        state=controller.run_once()
        self.assertEqual(state['phase'],'verifying')
        with controller._connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM intents WHERE step='verify'").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM calls WHERE step='verify'").fetchone()[0],0)
        self.assertFalse(any(call[1]=='verify' for call in adapter.calls))
        verify_ready[0]=True
        with controller._transaction() as db:db.execute('UPDATE runs SET next_poll=0')
        self.assertEqual(controller.run_once()['phase'],'closing_ticket')
        verify=[call for call in adapter.calls if call[1]=='verify']
        self.assertEqual(len(verify),1);self.assertEqual(verify[0][2]['mode'],'execute')

    def test_unknown_and_wrong_run_execution_allowances_fail_closed(self):
        for outcome in (None,{'ready':True,'boundRunId':'other-run'},'unverified'):
            adapter=Adapter();controller=self.controller(adapter)
            self.start(controller);self.to_step(controller,'merge')
            adapter.execution_budget=lambda step:outcome
            state=controller.run_once()
            self.assertEqual(state['phase'],'merging')
            self.assertFalse(any(call[1]=='merge' for call in adapter.calls))
            controller.close();self.controllers.remove(controller)
            self.path=Path(self.temporary.name)/(uuid.uuid4().hex+'.sqlite')

    def test_concurrent_clicks_attach_to_one_run_and_frozen_config(self):
        adapter = Adapter()
        controller = self.controller(adapter)
        with ThreadPoolExecutor(max_workers=8) as pool:
            runs = list(pool.map(lambda _: self.start(controller), range(24)))
        self.assertEqual(len({run["runId"] for run in runs}), 1)
        self.assertEqual(adapter.calls, [])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 24)
        self.assertEqual(len(list((self.path.parent / "runs").glob("*/config.json"))), 1)

    def test_telemetry_surrounds_actual_callback_and_propagates_its_carrier(self):
        order = []
        carrier = '00-' + 'a'*32 + '-' + 'b'*16 + '-01'
        class Telemetry:
            def begin(self, run, step):
                order.append(('begin', step))
                return carrier
            def observe(self, run, step, result=None, error=None):
                order.append(('observe', step, result.status if result else 'unknown'))
        class ObservedAdapter(Adapter):
            def advance(self, run, step):
                order.append(('callback', step, run.get('_traceparent')))
                return super().advance(run, step)
        controller = self.controller(ObservedAdapter(), telemetry=Telemetry())
        self.start(controller)
        controller.public_state()
        self.assertEqual(order, [])
        controller.run_once()
        self.assertEqual(order, [('begin', 'prepare'), ('callback', 'prepare', carrier), ('observe', 'prepare', 'completed')])
        controller.public_state()
        self.assertEqual(len(order), 3)

    def test_telemetry_failures_never_change_or_repeat_an_operation(self):
        class BrokenTelemetry:
            def begin(self, *args):
                raise OSError('private exporter failure')
            def observe(self, *args, **kwargs):
                raise OSError('private exporter failure')
        adapter = Adapter()
        controller = self.controller(adapter, telemetry=BrokenTelemetry())
        self.start(controller)
        self.assertEqual(controller.run_once()['phase'], 'preparing')
        self.assertEqual(controller.run_once()['phase'], 'fault_injected')
        self.assertEqual([call[1] for call in adapter.calls], ['prepare', 'inject_fault'])

    def test_actual_exception_ends_telemetry_without_claiming_completion(self):
        observed = []
        class Telemetry:
            def begin(self, *args):
                return None
            def observe(self, run, step, result=None, error=None):
                observed.append((step, result, type(error).__name__))
        controller = self.controller(Adapter(failure='prepare'), telemetry=Telemetry())
        self.start(controller)
        self.assertEqual(controller.run_once()['phase'], 'unknown')
        self.assertEqual(observed, [('prepare', None, 'RuntimeError')])

    def test_evidence_context_uses_only_current_actual_task_and_session_anchors(self):
        controller = self.controller()
        self.assertEqual(controller.evidence_context()['runId'], None)
        run = self.start(controller)
        data = {'adapter': {'task_id': 'triage-task', 'session_id': 'triage-session',
                           'review_task_id': 'review-task', 'review_session_id': 'review-session', 'review_state': 'TASK_STATE_WORKING',
                           'merge_task_id': 'merge-task', 'merge_session_id': 'merge-session',
                           'verification_task_id': 'verify-task', 'verification_session_id': 'verify-session', 'private': 'secret'},
                'native': {'state': 'TASK_STATE_WORKING'}, 'merge': {'taskState': 'TASK_STATE_COMPLETED'},
                'verification': {'state': 'TASK_STATE_WORKING'}}
        with controller._transaction() as db:
            db.execute('UPDATE runs SET data=? WHERE run_id=?', (json.dumps(data), run['runId']))
        context = controller.evidence_context()
        self.assertEqual(context['runId'], run['runId'])
        self.assertEqual(set(context['tasks']), {'triage', 'review', 'merge', 'verify'})
        self.assertEqual(context['tasks']['review'], {'taskId': 'review-task', 'sessionId': 'review-session', 'state': 'TASK_STATE_WORKING'})
        self.assertEqual(context['tasks']['verify']['taskId'], 'verify-task')
        self.assertNotIn('secret', json.dumps(context))

    def test_evidence_context_reads_actual_persisted_coordinator_identity(self):
        from flow_telemetry import FlowTelemetry
        telemetry=FlowTelemetry('http://unused.invalid',transport=lambda *args:None)
        self.addCleanup(telemetry.close)
        controller=self.controller(telemetry=telemetry)
        run=self.start(controller)
        self.assertEqual(controller.evidence_context()['coordinatorContexts'],[])
        controller.run_once()
        path=controller.run_root/run['runId']/'.flow-telemetry-prepare.json'
        actual=json.loads(path.read_text())
        anchors=controller.evidence_context()['coordinatorContexts']
        self.assertEqual(anchors,[{'runId':run['runId'],'step':'prepare','traceId':actual['traceId'],
                                  'spanId':actual['spanId'],'startedNs':str(actual['started_ns'])}])
        self.assertNotIn('workspace',json.dumps(anchors))
        self.assertNotIn('lastState',json.dumps(anchors))

    def test_coordinator_context_requires_current_intent_and_valid_bounded_private_receipt(self):
        controller=self.controller();run=self.start(controller)
        workspace=controller.run_root/run['runId']
        value={'runId':run['runId'],'step':'prepare','traceId':'a'*32,'spanId':'b'*16,'started_ns':1000}
        path=workspace/'.flow-telemetry-prepare.json';path.write_text(json.dumps(value))
        self.assertEqual(controller.evidence_context()['coordinatorContexts'],[])
        with controller._transaction() as db:
            db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?)',(run['runId'],'prepare','actual-intent','inflight','execute',None))
        self.assertEqual(len(controller.evidence_context()['coordinatorContexts']),1)
        for field,item in [('runId','other-run'),('step','classify'),('traceId','0'*32),
                           ('spanId','0'*16),('traceId','x'*32),('started_ns',False),('started_ns',0),
                           ('started_ns',2**64)]:
            path.write_text(json.dumps({**value,field:item}))
            self.assertEqual(controller.evidence_context()['coordinatorContexts'],[],field)
        for raw in ('{','[]','x'*4097):
            path.write_text(raw)
            self.assertEqual(controller.evidence_context()['coordinatorContexts'],[])
        path.unlink();outside=Path(self.temporary.name)/'outside-context.json';outside.write_text(json.dumps(value));path.symlink_to(outside)
        self.assertEqual(controller.evidence_context()['coordinatorContexts'],[])
        path.unlink()
        import os
        os.mkfifo(path)
        self.assertEqual(controller.evidence_context()['coordinatorContexts'],[])

    def test_repeated_waits_keep_the_first_observation_time_and_initial_stages(self):
        controller = self.controller()
        run = self.start(controller)
        event = {'stage':'observe_merge','state':'pending','message':'Waiting for human merge'}
        with controller._transaction() as db:
            for _ in range(120):
                controller._event(db, run['runId'], event)
        events = controller.public_state()['events']
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['stage'], 'prepare')
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 2)

    def test_reused_request_stays_on_its_closed_run(self):
        controller = self.controller(closure_verifier=self.proof)
        request = str(uuid.uuid4())
        original = controller.start(request)
        for _ in STEPS:
            self.tick(controller)
        self.assertEqual(controller.public_state()["phase"], "closed")
        fresh = self.start(controller)
        self.assertNotEqual(fresh["runId"], original["runId"])
        self.assertEqual(controller.start(request)["runId"], original["runId"])

    def test_recovery_wait_does_not_advance_measurement_or_verification_until_ready(self):
        adapter=Adapter(pending='await_recovery')
        controller=self.controller(adapter,closure_verifier=self.proof)
        self.start(controller);self.to_step(controller,'await_recovery')
        for _ in range(20):
            with controller._transaction() as db:db.execute('UPDATE runs SET next_poll=0')
            state=controller.run_once()
            self.assertEqual(state['phase'],'reconciling')
            self.assertFalse(state['ticket']['closedVerified'])
        self.assertNotIn('measure_recovery',[call[1] for call in adapter.calls])
        self.assertNotIn('verify',[call[1] for call in adapter.calls])
        adapter.pending=None
        with controller._transaction() as db:db.execute('UPDATE runs SET next_poll=0')
        controller.run_once();controller.run_once()
        self.assertEqual([call[1] for call in adapter.calls].count('measure_recovery'),1)

    def test_full_sequence_requires_readback_and_exposes_no_adapter_data(self):
        adapter = Adapter()
        controller = self.controller(adapter, closure_verifier=self.proof)
        self.start(controller)
        for _ in STEPS:
            state = self.tick(controller)
        self.assertEqual([step for _, step, _ in adapter.calls], list(STEPS))
        self.assertEqual(state["phase"], "closed")
        self.assertTrue(state["ticket"]["closedVerified"])
        self.assertFalse(state["running"])
        self.assertNotIn("adapter", state)
        self.assertNotIn("workspace", state)
        self.assertNotIn("config", state)
        self.assertNotIn("configPath", state)
        self.assertTrue(state["actions"]["start"]["enabled"])
        self.assertNotIn("merge", state["actions"])

    def test_pending_only_reobserves_the_original_intent_after_restart(self):
        adapter = Adapter(pending="dispatch")
        controller = self.controller(adapter)
        self.start(controller)
        self.to_step(controller, "dispatch")
        controller.run_once()
        first_intent = adapter.calls[-1][2]["intentId"]
        controller.close()
        restarted = self.controller(adapter)
        time.sleep(0.02)
        restarted.run_once()
        self.assertEqual(adapter.calls[-1][2], {"intentId": first_intent, "mode": "observe"})

    def test_interrupted_first_native_send_becomes_unknown_and_is_never_resent(self):
        adapter = Adapter()
        controller = self.controller(adapter)
        self.start(controller)
        self.to_step(controller, "dispatch")
        run_id = controller.public_state()["runId"]
        self.mark_interrupted(run_id, "dispatch", "execute")
        controller.close()
        restarted = self.controller(adapter)
        self.assertEqual(restarted.public_state()["phase"], "unknown")
        restarted.run_once()
        self.start(restarted)
        self.assertEqual(len(adapter.calls), STEPS.index("dispatch"))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)

    def mark_interrupted(self, run_id, step, mode):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE runs SET status='inflight' WHERE run_id=?", (run_id,))
            db.execute("INSERT INTO intents VALUES(?,?,?,'inflight',?,NULL)", (run_id, step, "original-intent", mode))

    def test_interrupted_read_only_wait_resumes_observation(self):
        adapter = Adapter(pending="observe_merge")
        controller = self.controller(adapter)
        self.start(controller)
        self.to_step(controller, "observe_merge")
        self.mark_interrupted(controller.public_state()["runId"], "observe_merge", "execute")
        controller.close()
        restarted = self.controller(adapter)
        restarted.run_once()
        self.assertEqual(adapter.calls[-1][2], {"intentId": "original-intent", "mode": "observe"})
        self.assertEqual(restarted.public_state()["phase"], "merging")

    def test_effect_failure_stops_and_redacts_the_exception(self):
        adapter = Adapter(failure="inject_fault")
        controller = self.controller(adapter)
        self.start(controller)
        controller.run_once()
        state = controller.run_once()
        controller.run_once()
        self.assertEqual(state["phase"], "unknown")
        self.assertEqual(len(adapter.calls), 2)
        self.assertNotIn("private upstream data", str(state))

    def test_no_closure_without_completed_native_task(self):
        adapter = Adapter()
        controller = self.controller(adapter, closure_verifier=lambda run: ClosureProof(True, "actual-verification-task", "TASK_STATE_WORKING", "c" * 64))
        self.start(controller)
        for _ in STEPS:
            state = self.tick(controller)
        self.assertEqual(state["phase"], "blocked")
        self.assertFalse(state["ticket"]["closedVerified"])
        self.assertNotIn("close", [step for _, step, _ in adapter.calls])

    def test_close_ack_without_actual_closed_readback_stays_unknown(self):
        controller = self.controller(closure_verifier=lambda run: ClosureProof(True, "actual-verification-task", "completed", "c" * 64))
        self.start(controller)
        for _ in STEPS:
            state = self.tick(controller)
        self.assertEqual(state["phase"], "unknown")
        self.assertFalse(state["ticket"]["closedVerified"])
        self.assertFalse(state["actions"]["start"]["enabled"])

    def test_classifier_completion_cannot_bypass_actual_admission(self):
        class LowConfidence(Adapter):
            def advance(self, run, step):
                result = super().advance(run, step)
                return StepResult("completed", {"classifier": {"decision": "investigate", "severity": "critical", "confidence": 0.94}}) if step == "classify" else result
        adapter = LowConfidence()
        controller = self.controller(adapter)
        self.start(controller)
        self.to_step(controller, "classify")
        self.assertEqual(controller.run_once()["phase"], "unknown")
        controller.run_once()
        self.assertNotIn("dispatch", [step for _, step, _ in adapter.calls])

    def test_autostart_runs_the_worker_without_a_manual_tick(self):
        adapter = Adapter(pending="observe_fault")
        controller = FlowController(self.path, adapter, scope={"namespace": "worker-demo"}, autostart=True)
        self.controllers.append(controller)
        self.start(controller)
        deadline = time.monotonic() + 2
        while len(adapter.calls) < 3 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertGreaterEqual(len(adapter.calls), 3)
        self.assertEqual(controller.public_state()["phase"], "observing")

    def at_approval(self, adapter=None):
        adapter = adapter or Adapter()
        controller = self.controller(adapter)
        self.start(controller)
        self.to_step(controller, 'await_approval')
        return controller, adapter

    def test_review_does_not_approve_or_send_a_merge(self):
        controller, adapter = self.at_approval()
        self.assertTrue(controller.public_state()['actions']['approve']['enabled'])
        controller.run_once()
        self.assertEqual(adapter.approval_calls, [])
        self.assertNotIn('merge', [step for _, step, _ in adapter.calls])
        self.assertEqual(controller.public_state()['phase'], 'waiting_human')

    def test_approval_records_exact_head_without_advancing_or_merging(self):
        controller, adapter = self.at_approval()
        before = controller.public_state()
        request = str(uuid.uuid4())
        result = controller.approve(request, before['runId'], 'a'*40)
        self.assertEqual(result['approval']['approvalId'], request)
        self.assertEqual(result['phase'], 'waiting_human')
        self.assertFalse(result['actions']['approve']['enabled'])
        self.assertNotIn('merge', [step for _, step, _ in adapter.calls])
        self.assertEqual(adapter.approval_calls, [(request, 'a'*40, False, {'intentId':request, 'mode':'execute'})])
        controller.run_once()
        self.assertEqual(controller.public_state()['phase'], 'merging')

    def test_concurrent_double_clicks_coalesce_one_canonical_grant(self):
        controller, adapter = self.at_approval()
        run_id = controller.public_state()['runId']
        requests = [str(uuid.uuid4()) for _ in range(20)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda request:controller.approve(request, run_id, 'a'*40), requests))
        self.assertEqual(len(adapter.approval_calls), 1)
        self.assertEqual(len({result['approval']['approvalId'] for result in results}), 1)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM approval_requests').fetchone()[0], 1)

    def test_approval_rejects_changed_run_head_and_missing_checks_before_callback(self):
        controller, adapter = self.at_approval()
        run_id = controller.public_state()['runId']
        for rid, head in [('other-run', 'a'*40), (run_id, 'b'*40)]:
            with self.assertRaises(ApprovalConflict):
                controller.approve(str(uuid.uuid4()), rid, head)
        for field in ('ci','review'):
            with controller._transaction() as db:
                row = db.execute('SELECT data FROM runs WHERE run_id=?',(run_id,)).fetchone()
                data = __import__('json').loads(row['data'])
                data['remedy'][field]='pending'
                db.execute('UPDATE runs SET data=? WHERE run_id=?',(__import__('json').dumps(data),run_id))
            with self.assertRaises(ApprovalConflict):
                controller.approve(str(uuid.uuid4()), run_id, 'a'*40)
            data['remedy'][field]='passed'
            with controller._transaction() as db:
                db.execute('UPDATE runs SET data=? WHERE run_id=?',(__import__('json').dumps(data),run_id))
        self.assertEqual(adapter.approval_calls, [])

    def test_unknown_approval_only_reads_original_grant_after_restart(self):
        class Lost(Adapter):
            def approve(self, run, request_id, head_sha, observe=False):
                receipt = super().approve(run, request_id, head_sha, observe)
                if not observe:
                    raise TimeoutError('private upstream response')
                return receipt
        adapter = Lost()
        controller, _ = self.at_approval(adapter)
        run_id = controller.public_state()['runId']; request = str(uuid.uuid4())
        with self.assertRaises(ApprovalUnknown):
            controller.approve(request, run_id, 'a'*40)
        self.assertFalse(controller.public_state()['actions']['approve']['enabled'])
        self.assertEqual(controller.public_state()['approval']['state'], 'unknown')
        self.assertNotIn('private upstream response', str(controller.public_state()))
        controller.close()
        restarted = self.controller(adapter)
        result = restarted.approve(str(uuid.uuid4()), run_id, 'a'*40)
        self.assertEqual(result['approval']['approvalId'], request)
        self.assertEqual([call[2] for call in adapter.approval_calls], [False, True])
        self.assertEqual([call[0] for call in adapter.approval_calls], [request, request])

    def test_worker_can_confirm_lost_ack_grant_without_a_new_approval_call(self):
        class Lost(Adapter):
            def approve(self, run, request_id, head_sha, observe=False):
                super().approve(run, request_id, head_sha, observe)
                raise TimeoutError()
        adapter = Lost()
        controller, _ = self.at_approval(adapter)
        state = controller.public_state()
        with self.assertRaises(ApprovalUnknown):
            controller.approve(str(uuid.uuid4()), state['runId'], 'a'*40)
        controller.run_once()
        self.assertEqual(controller.public_state()['phase'], 'merging')
        self.assertEqual(len(adapter.approval_calls), 1)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT status FROM approval_requests').fetchone()[0], 'recorded')

    def test_native_merge_cannot_complete_with_only_a_working_task(self):
        class WorkingMerge(Adapter):
            def advance(self, run, step):
                result = super().advance(run, step)
                if step == 'merge':
                    result.patch['merge']['taskState']='TASK_STATE_WORKING'
                return result
        controller, adapter = self.at_approval(WorkingMerge())
        self.tick(controller)
        self.assertEqual(controller.run_once()['phase'], 'unknown')
        self.assertNotIn('observe_merge', [step for _,step,_ in adapter.calls])

    def test_actual_approval_cannot_be_invented_by_an_await_callback(self):
        controller, adapter = self.at_approval()
        now = int(time.time())
        adapter.approval={'approvalId':str(uuid.uuid4()),'headSha':'a'*40,'approvedBy':7,'approvedAt':now,'expiresAt':now+900,'state':'approved'}
        self.assertEqual(controller.run_once()['phase'], 'unknown')
        self.assertNotIn('merge', [step for _,step,_ in adapter.calls])

    def blocked_triage(self):
        class ContinuationAdapter(Adapter):
            def __init__(self):super().__init__();self.remaining=8;self.valid=True
            def budget_state(self,force=False):return {'enabled':True,'available':self.remaining>0,'requestsRemaining':self.remaining,'inputBytesRemaining':100000}
            def validate_triage_continuation(self,run):
                if not self.valid:raise ValueError('Not repaired')
                return {'taskId':'actual-primary-task','sessionId':'original-session'}
            def advance(self,run,step):
                result=super().advance(run,step)
                if step=='dispatch':result.patch['adapter']={'task_id':'actual-primary-task','session_id':'original-session'}
                if step=='triage':return StepResult('blocked',patch={'native':{'taskId':'actual-primary-task','state':'TASK_STATE_COMPLETED'}})
                if step=='triage_continuation':return StepResult('completed',patch={
                    'native':{'taskId':'continued-task','state':'TASK_STATE_COMPLETED'},'adapter':{'task_id':'continued-task'},
                    'remedy':{'mrUrl':'https://gitlab.com/p/-/merge_requests/3','headSha':'a'*40,'ci':'passed','review':'pending'}})
                return result
        adapter=ContinuationAdapter();controller=self.controller(adapter);run=self.start(controller)['runId']
        self.to_step(controller,'triage');controller.run_once()
        return controller,adapter,run

    def test_operator_triage_continuation_preserves_original_intent_and_human_gate(self):
        controller,adapter,run=self.blocked_triage()
        with controller._connection() as db:original=dict(db.execute('SELECT * FROM intents WHERE run_id=? AND step=?',(run,'triage')).fetchone())
        request=str(uuid.uuid4());controller.request_triage_continuation(request,run)
        self.assertNotIn('triage_continuation',STEPS)
        adapter.remaining=0
        self.assertEqual(controller.request_triage_continuation(request,run)['runId'],run)
        self.assertEqual(controller.request_triage_continuation(str(uuid.uuid4()),run)['runId'],run)
        self.assertEqual(controller.run_once()['phase'],'waiting_review')
        self.assertEqual(controller.run_once()['phase'],'waiting_human')
        controller.run_once()
        self.assertNotIn('merge',[c[1] for c in adapter.calls])
        with controller._connection() as db:
            self.assertEqual(dict(db.execute('SELECT * FROM intents WHERE run_id=? AND step=?',(run,'triage')).fetchone()),original)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM triage_continuation_requests').fetchone()[0],1)
        self.assertEqual([c[1] for c in adapter.calls].count('triage_continuation'),1)

    def test_original_task_context_requires_the_accepted_hashed_continuation_receipt(self):
        import hashlib
        controller,adapter,run=self.blocked_triage();controller.request_triage_continuation(str(uuid.uuid4()),run)
        controller.run_once()
        workspace=controller.run_root/run
        send={'state':'completed','result':{'task':{'id':'continued-task','contextId':'original-session'}}}
        raw=json.dumps(send).encode();(workspace/'triage-continuation-send.json').write_bytes(raw)
        receipt={'original_task_id':'actual-primary-task','session_id':'original-session','task_id':'continued-task',
                 'send_receipt_sha256':hashlib.sha256(raw).hexdigest()}
        path=workspace/'operator-triage-continuation.json';path.write_text(json.dumps(receipt))
        ctx=controller.evidence_context()
        self.assertEqual(ctx['tasks']['triage']['taskId'],'continued-task')
        self.assertEqual(ctx['tasks']['triage_original']['taskId'],'actual-primary-task')
        receipt['send_receipt_sha256']='0'*64;path.write_text(json.dumps(receipt))
        self.assertNotIn('triage_original',controller.evidence_context()['tasks'])

    def test_triage_continuation_refuses_exhaustion_bad_identity_and_unrepaired_access(self):
        controller,adapter,run=self.blocked_triage();request=str(uuid.uuid4())
        adapter.remaining=0
        with self.assertRaises(ResumeConflict):controller.request_triage_continuation(request,run)
        adapter.remaining=8;adapter.valid=False
        with self.assertRaises(ResumeConflict):controller.request_triage_continuation(request,run)
        with self.assertRaises(ResumeConflict):controller.request_triage_continuation(request,'demo-'+'f'*32)
        with controller._connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM triage_continuation_requests').fetchone()[0],0)
        self.assertEqual(controller.public_state()['phase'],'blocked')

    def test_interrupted_first_continuation_send_does_not_automatically_resume(self):
        controller,adapter,run=self.blocked_triage();controller.request_triage_continuation(str(uuid.uuid4()),run)
        with controller._transaction() as db:
            db.execute('INSERT INTO intents VALUES(?,?,?,?,?,NULL)',(run,'triage_continuation','send-intent','inflight','execute'))
            db.execute("UPDATE runs SET status='inflight' WHERE run_id=?",(run,))
        controller.close();replacement=self.controller(adapter)
        self.assertEqual(replacement.public_state()['phase'],'unknown')
        replacement.run_once();self.assertNotIn('triage_continuation',[c[1] for c in adapter.calls])

    def suppressed_classification(self, followup_status='completed'):
        class FollowupAdapter(Adapter):
            def __init__(self):
                super().__init__();self.remaining=15;self.bound=None
            def budget_state(self,force=False):
                return {'enabled':True,'available':self.remaining>0,'requestsRemaining':self.remaining,
                        'inputBytesRemaining':10000,'boundRunId':self.bound}
            def advance(self,run,step):
                if step in {'inject_fault','observe_fault','classify','classification_followup'}:
                    self.calls.append((run['runId'],step,run['_call'].copy()))
                    if step=='inject_fault':return StepResult('completed',patch={'adapter':{'rollout_sha':'a'*40}})
                    if step=='observe_fault':return StepResult('completed',patch={'adapter':{'candidate_id':'b'*64}})
                    if step=='classify':return StepResult('suppressed',patch={'classifier':{'decision':'investigate','severity':'critical','confidence':.93,'threshold':.95,'attempts':1}})
                    return StepResult(followup_status,patch={'classifier':{'decision':'investigate','severity':'critical',
                        'confidence':.97 if followup_status=='completed' else .93,'threshold':.95,'attempts':2},'adapter':{'candidate_id':'c'*64}})
                return super().advance(run,step)
        adapter=FollowupAdapter();controller=self.controller(adapter);run=self.start(controller)
        self.to_step(controller,'classify');controller.run_once()
        return controller,adapter,run['runId']

    def test_operator_followup_preserves_first_classification_and_dispatches_only_new_admission(self):
        controller,adapter,run_id=self.suppressed_classification()
        with controller._connection() as db:
            original_intent=tuple(db.execute("SELECT * FROM intents WHERE step='classify'").fetchone())
            original_calls=[tuple(r) for r in db.execute("SELECT * FROM calls WHERE step='classify'")]
            original_config=db.execute('SELECT config FROM runs').fetchone()[0]
        request=str(uuid.uuid4());state=controller.request_classification_followup(request,run_id)
        self.assertTrue(state['running']);self.assertEqual(state['phase'],'classifying')
        self.assertNotIn('classification_followup',STEPS)
        self.assertEqual(controller.run_once()['phase'],'dispatching')
        self.assertEqual(controller.public_state()['classifier']['confidence'],.97)
        adapter.remaining=0
        for value in [request,str(uuid.uuid4())]:self.assertEqual(controller.request_classification_followup(value,run_id)['runId'],run_id)
        with controller._connection() as db:
            self.assertEqual(tuple(db.execute("SELECT * FROM intents WHERE step='classify'").fetchone()),original_intent)
            self.assertEqual([tuple(r) for r in db.execute("SELECT * FROM calls WHERE step='classify'")],original_calls)
            self.assertEqual(db.execute('SELECT config FROM runs').fetchone()[0],original_config)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM classification_followup_requests').fetchone()[0],1)
        self.assertEqual([c[1] for c in adapter.calls].count('classification_followup'),1)
        with self.assertRaises(ResumeConflict):controller.request_classification_followup(request,'demo-'+'e'*32)

    def test_concurrent_operator_followups_reserve_only_one_operation(self):
        controller,adapter,run_id=self.suppressed_classification()
        with ThreadPoolExecutor(max_workers=8) as pool:
            states=list(pool.map(lambda _:controller.request_classification_followup(str(uuid.uuid4()),run_id),range(20)))
        self.assertEqual({state['phase'] for state in states},{'classifying'})
        with controller._connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM classification_followup_requests').fetchone()[0],1)
        controller.run_once()
        self.assertEqual([c[1] for c in adapter.calls].count('classification_followup'),1)

    def recovery_coalesces_after_initial_readback(self, fixture, method_name, readback_name, table):
        controller,adapter,run_id=fixture()
        method=getattr(controller,method_name);readback=getattr(controller,readback_name)
        interleaved=False
        def race(request_id,requested_run):
            nonlocal interleaved
            prior=readback(request_id,requested_run)
            if prior is None and not interleaved:
                interleaved=True
                method(str(uuid.uuid4()),requested_run)
            return prior
        setattr(controller,readback_name,race)
        result=method(str(uuid.uuid4()),run_id)
        self.assertEqual(result['runId'],run_id)
        with controller._connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],1)

    def test_followup_coalesces_when_another_request_wins_after_readback(self):
        self.recovery_coalesces_after_initial_readback(self.suppressed_classification,
            'request_classification_followup','_classification_followup_readback','classification_followup_requests')

    def test_triage_continuation_coalesces_when_another_request_wins_after_readback(self):
        self.recovery_coalesces_after_initial_readback(self.blocked_triage,
            'request_triage_continuation','_triage_continuation_readback','triage_continuation_requests')

    def test_fault_resume_coalesces_when_another_request_wins_after_readback(self):
        self.recovery_coalesces_after_initial_readback(self.stopped_fault,
            'resume_fault','resume_readback','fault_resume_requests')

    def test_followup_rejects_exhausted_wrong_run_or_noncritical_without_changes(self):
        controller,adapter,run_id=self.suppressed_classification()
        before=controller.public_state();adapter.remaining=0
        with self.assertRaises(ResumeConflict):controller.request_classification_followup(str(uuid.uuid4()),run_id)
        self.assertEqual(controller.public_state(),before)
        adapter.remaining=15;adapter.bound='demo-'+'e'*32
        with self.assertRaises(ResumeConflict):controller.request_classification_followup(str(uuid.uuid4()),run_id)
        adapter.bound=run_id
        with controller._transaction() as db:
            data=json.loads(db.execute('SELECT data FROM runs').fetchone()[0]);data['classifier']['severity']='high'
            db.execute('UPDATE runs SET data=?',(json.dumps(data),))
        with self.assertRaises(ResumeConflict):controller.request_classification_followup(str(uuid.uuid4()),run_id)
        with controller._connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM classification_followup_requests').fetchone()[0],0)

    def test_followup_suppression_is_terminal_and_cannot_trigger_another_window(self):
        controller,adapter,run_id=self.suppressed_classification('suppressed')
        controller.request_classification_followup(str(uuid.uuid4()),run_id);controller.run_once()
        state=controller.public_state();self.assertEqual(state['phase'],'suppressed');self.assertFalse(state['running'])
        self.assertEqual(state['classifier']['attempts'],2)
        controller.request_classification_followup(str(uuid.uuid4()),run_id);controller.run_once()
        self.assertEqual([c[1] for c in adapter.calls].count('classification_followup'),1)
        self.assertNotIn('dispatch',[c[1] for c in adapter.calls])

    def test_interrupted_paid_followup_remains_unknown_without_automatic_observation(self):
        controller,adapter,run_id=self.suppressed_classification()
        controller.request_classification_followup(str(uuid.uuid4()),run_id)
        with controller._transaction() as db:
            db.execute("INSERT INTO intents VALUES(?,?,?,?,?,NULL)",(run_id,'classification_followup','paid-intent','inflight','execute'))
            db.execute("UPDATE runs SET status='inflight' WHERE run_id=?",(run_id,))
        controller.close();self.controllers.remove(controller)
        restarted=self.controller(adapter);self.assertEqual(restarted.public_state()['phase'],'unknown')
        calls=len(adapter.calls);restarted.run_once();self.assertEqual(len(adapter.calls),calls)

    def stopped_fault(self):
        class FaultAdapter(Adapter):
            def __init__(self):
                super().__init__()
                self.remaining=16
                self.health=[]
            def budget_state(self,force=False):
                self.health.append(force)
                return {'enabled':True,'available':self.remaining>0,'requestsRemaining':self.remaining,'inputBytesRemaining':10000}
            def advance(self,run,step):
                if step in ('inject_fault','observe_fault','recheck_fault'):
                    self.calls.append((run['runId'],step,run['_call'].copy()))
                    if step=='inject_fault':return StepResult('completed',patch={'adapter':{'rollout_sha':'a'*40}})
                    if step=='observe_fault':return StepResult('blocked')
                    return StepResult('completed',patch={'adapter':{'candidate_id':'c'*64}})
                return super().advance(run,step)
        adapter=FaultAdapter();controller=self.controller(adapter)
        run=self.start(controller)
        self.to_step(controller,'observe_fault');controller.run_once()
        return controller,adapter,run['runId']

    def test_resume_keeps_original_history_and_runs_only_one_new_recheck(self):
        controller,adapter,run_id=self.stopped_fault()
        before=controller.public_state()
        self.assertFalse(before['running']);self.assertTrue(before['actions']['resume']['enabled'])
        self.assertIn('stopped during fault observation',before['actions']['start']['reason'])
        with controller._connection() as db:
            intents=[tuple(r) for r in db.execute('SELECT * FROM intents ORDER BY step')]
            calls=[tuple(r) for r in db.execute('SELECT * FROM calls ORDER BY id')]
            config=db.execute('SELECT config FROM runs').fetchone()[0]
        request=str(uuid.uuid4());resumed=controller.resume_fault(request,run_id)
        self.assertTrue(resumed['running']);self.assertEqual(resumed['phase'],'observing')
        self.assertEqual(controller.run_once()['phase'],'classifying')
        adapter.remaining=0
        for identity in (request,str(uuid.uuid4())):
            self.assertEqual(controller.resume_fault(identity,run_id)['runId'],run_id)
        with controller._connection() as db:
            self.assertEqual([tuple(r) for r in db.execute("SELECT * FROM intents WHERE step!='recheck_fault' ORDER BY step")],intents)
            self.assertEqual([tuple(r) for r in db.execute("SELECT * FROM calls WHERE step!='recheck_fault' ORDER BY id")],calls)
            self.assertEqual(db.execute('SELECT config FROM runs').fetchone()[0],config)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM fault_resume_requests').fetchone()[0],1)
        self.assertEqual([step for _,step,_ in adapter.calls],['prepare','inject_fault','observe_fault','recheck_fault'])
        self.assertEqual(controller.public_state()['ticket'],before['ticket'])
        self.assertEqual(adapter.health,[True])
        with self.assertRaises(ResumeConflict):controller.resume_readback(request,'demo-'+'e'*32)

    def test_resume_requires_matching_bound_allowance(self):
        controller,adapter,run_id=self.stopped_fault();read=adapter.budget_state
        adapter.budget_state=lambda force=False:dict(read(force),boundRunId='demo-'+'e'*32)
        before=controller.public_state()
        with self.assertRaises(ResumeConflict):controller.resume_fault(str(uuid.uuid4()),run_id)
        self.assertEqual(controller.public_state(),before)
        adapter.budget_state=lambda force=False:dict(read(force),boundRunId=run_id)
        self.assertTrue(controller.resume_fault(str(uuid.uuid4()),run_id)['running'])

    def test_concurrent_resume_clicks_coalesce_without_repeating_fault(self):
        controller,adapter,run_id=self.stopped_fault()
        with ThreadPoolExecutor(max_workers=8) as pool:
            states=list(pool.map(lambda _:controller.resume_fault(str(uuid.uuid4()),run_id),range(20)))
        self.assertEqual({s['runId'] for s in states},{run_id})
        with controller._connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM fault_resume_requests').fetchone()[0],1)
        controller.run_once()
        self.assertEqual([step for _,step,_ in adapter.calls].count('recheck_fault'),1)
        self.assertEqual([step for _,step,_ in adapter.calls].count('inject_fault'),1)

    def test_resume_exhaustion_and_ineligible_state_do_not_change_incident(self):
        controller,adapter,run_id=self.stopped_fault();adapter.remaining=0
        before=controller.public_state()
        with self.assertRaises(ResumeConflict):controller.resume_fault(str(uuid.uuid4()),run_id)
        self.assertEqual(controller.public_state(),before)
        adapter.remaining=16
        with controller._transaction() as db:
            db.execute("UPDATE runs SET data=?",(json.dumps({'adapter':{'rollout_sha':'a'*40},'native':{'taskId':'actual-task'}}),))
        self.assertFalse(controller.public_state()['actions']['resume']['enabled'])
        with self.assertRaises(ResumeConflict):controller.resume_fault(str(uuid.uuid4()),run_id)
        with controller._connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM fault_resume_requests').fetchone()[0],0)

    def test_interrupted_recheck_recovers_only_new_intent_in_observe_mode(self):
        controller,adapter,run_id=self.stopped_fault()
        controller.resume_fault(str(uuid.uuid4()),run_id)
        with controller._transaction() as db:
            original=tuple(db.execute("SELECT * FROM intents WHERE step='observe_fault'").fetchone())
            db.execute("UPDATE runs SET status='inflight'")
            db.execute("INSERT INTO intents VALUES(?,?,'new-intent','inflight','execute',NULL)",(run_id,'recheck_fault'))
            db.execute("INSERT INTO calls(run_id,step,intent_id,mode,status,started_at) VALUES(?,?,'new-intent','execute','inflight',?)",(run_id,'recheck_fault',time.time()))
        controller.close();restarted=self.controller(adapter)
        self.assertEqual(restarted.run_once()['phase'],'classifying')
        self.assertEqual(adapter.calls[-1][2],{'intentId':'new-intent','mode':'observe'})
        with restarted._connection() as db:
            self.assertEqual(tuple(db.execute("SELECT * FROM intents WHERE step='observe_fault'").fetchone()),original)

    def test_invalid_requests_and_second_catalogue_owner_are_rejected(self):
        controller = self.controller()
        with self.assertRaises(FlowError):
            controller.start("bad-id")
        with self.assertRaises(BlockingIOError):
            self.controller()
        controller.close()
        with self.assertRaises(FlowError):
            FlowController(self.path, Adapter(), scope={"namespace": "different"}, autostart=False)


if __name__ == "__main__":
    unittest.main()
