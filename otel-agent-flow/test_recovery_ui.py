"""Exercise the existing JavaScript/HTML with offline reducer output."""
import time
import unittest

from recovery import project_recovery
from test_recovery import activity_store, valid_documents
from test_ui import UiBehaviorTests


def state_for(mode="live", spans=True):
    now = int(time.time())
    plan, snapshot = valid_documents(now, mode)
    activity = activity_store(now).snapshot() if spans else {"revision": 0, "traces": []}
    return {**activity, "invocation": {"status": "idle"}, "sessionActivity": None,
            "nativeActivities": {}, "recovery": project_recovery(plan, snapshot, activity, now),
            "runtime": {"readOnlyViewer": True, "executionTargets": [], "label": "Offline test viewer", "demoMode": "connected"}}


class RecoveryUiTests(unittest.TestCase):
    run_ui = UiBehaviorTests.run_ui

    def test_recovery_tab_reuses_existing_map_and_exact_trace_inspection(self):
        self.run_ui(state_for(), r"""
          setView('recovery');
          assert.equal($('recovery-view').hidden,false);
          assert.equal($('runtime-flow').parentNode,$('recovery-flow-slot'));
          assert.equal($('prompt-column').hidden,true);
          assert.equal($('recovery-status').textContent,'Recovery verified');
          assert.equal($('recovery-stages').children.length,12);
          assert.match($('recovery-scope').textContent,/native-task-1/);
          assert.match($('recovery-repository').textContent,/MR 17/);
          assert.match($('recovery-telemetry-status').textContent,/Recovery and referenced execution evidence complete/);
          assert.equal($('node-skills').className.includes('observed'),true);
          assert.equal($('node-agentgateway').className.includes('observed'),true);
          const verification=$('recovery-telemetry').children[6];
          assert.equal(verification.disabled,false);verification.onclick();
          assert.equal(currentView,'visual');
          assert.equal(selectedId,'11111111111111111111111111111111');
          assert.match($('inspection').textContent,/native-task-1/);
          assert.equal($('runtime-flow').parentNode,$('visual-flow-slot'));
        """)

    def test_recovery_logs_use_the_same_exact_trace_filter(self):
        self.run_ui(state_for(), r"""
          setView('recovery');$('recovery-logs').onclick();
          assert.equal(currentView,'logs');assert.equal($('log-scope').value,'selected');
          assert.equal(selectedId,'11111111111111111111111111111111');
          await pollLogs();
          assert.ok(calls.some(call=>call.url==='/api/logs?traceId=11111111111111111111111111111111'));
        """)

    def test_expiry_disconnect_and_failed_snapshot_remove_green_without_new_spans(self):
        self.run_ui(state_for(), r"""
          setView('recovery');renderRecovery(state.recovery.expiresAt);
          assert.equal($('recovery-status').textContent,'Recovery unknown');
          assert.equal($('recovery-status').className.includes('recovered'),false);
          assert.equal($('recovery-stages').children[0].className.includes('unknown'),true);
          receiverConnected=false;renderRecovery();
          assert.equal($('recovery-status').textContent,'Recovery unknown');
          receiverConnected=true;state.recovery.state='blocked';state.recovery.label='Recovery blocked';
          state.recovery.reasons=['Later invalid probe was admitted'];await poll();
          assert.equal($('recovery-status').textContent,'Recovery blocked');
          assert.match($('recovery-reasons').textContent,/Later invalid probe/);
        """)

    def test_fixture_receipts_never_turn_green_or_create_telemetry(self):
        self.run_ui(state_for("fixture", spans=False), r"""
          setView('recovery');
          assert.equal($('recovery-status').textContent,'Fixture replay passed');
          assert.equal($('recovery-status').className.includes('recovered'),false);
          assert.match($('recovery-scope').textContent,/FIXTURE REPLAY/);
          assert.match($('recovery-telemetry-status').textContent,/Live runtime execution remains unverified/);
          assert.equal($('node-skills').className.includes('absent'),true);
          assert.equal($('node-mcp').className.includes('absent'),true);
          assert.equal($('recovery-logs').disabled,true);
          assert.ok($('recovery-telemetry').children.every(button=>button.disabled));
          assert.equal(calls.filter(call=>call.url==='/api/invoke').length,0);
        """)

    def test_default_without_snapshot_and_keyboard_navigation_preserve_existing_views(self):
        state = state_for()
        del state["recovery"]
        self.run_ui(state, r"""
          assert.equal(currentView,'visual');assert.equal($('recovery-view').hidden,true);
          $('tab-onboarding').onkeydown({key:'ArrowRight',preventDefault(){}});
          assert.equal(currentView,'recovery');
          assert.equal($('tab-recovery').attributes['aria-selected'],'true');
          assert.equal($('recovery-status').textContent,'Recovery unknown');
          $('tab-recovery').onkeydown({key:'ArrowRight',preventDefault(){}});
          assert.equal(currentView,'visual');assert.equal($('prompt-column').hidden,false);
          assert.equal($('runtime-flow').parentNode,$('visual-flow-slot'));
        """)

    def test_metadata_is_rendered_only_as_text_and_unretained_refs_cannot_open(self):
        state = state_for()
        state["recovery"]["summary"]["fault"] = '<script>outside()</script>'
        self.run_ui(state, r"""
          setView('recovery');
          assert.equal($('recovery-fault').textContent,'<script>outside()</script>');
          assert.equal($('recovery-fault').children.length,0);
          state.traces=[];renderRecovery();
          assert.ok($('recovery-telemetry').children.every(button=>button.disabled));
          assert.equal($('recovery-logs').disabled,true);
          const before=selectedId;
          openRecoveryTrace({state:'observed',traceId:'99999999999999999999999999999999',spanId:'9999999999999999'});
          assert.equal(selectedId,before);
        """)


if __name__ == "__main__":
    unittest.main()
