import unittest
from unittest.mock import patch
from substrate_call import invoke_session, terminal_text
from telemetry import ActivityStore, component
from test_telemetry import export, span


class SubstrateInvocationTests(unittest.TestCase):
    def test_session_identity_and_trace_context_reach_a2a_call(self):
        session = "12345678-1234-1234-1234-123456789abc"
        state = {}
        result = {"task": {"status": {"state": "TASK_STATE_COMPLETED"},
                           "artifacts": [{"parts": [{"text": "Ready"}]}]}}
        with patch("substrate_call.rpc", side_effect=[{"session": {"id": session}}, result]) as rpc:
            self.assertEqual(invoke_session("hello", "00-trace-span-01", state), "Ready")
        self.assertEqual(state["actorName"], "session-" + session)
        args = rpc.call_args_list[1].args
        self.assertEqual(args[1]["message"]["contextId"], session)
        self.assertEqual(args[1]["message"]["parts"], [{"text": "hello"}])
        self.assertEqual(args[2], "00-trace-span-01")

    def test_failed_task_is_not_a_successful_reply(self):
        with self.assertRaises(ValueError):
            terminal_text({"task": {"status": {"state": "TASK_STATE_FAILED"},
                                    "artifacts": [{"parts": [{"text": "partial"}]}]}})

    def test_native_services_distinguish_runtime_worker_and_control_plane(self):
        self.assertEqual(component("otel-substrate-reader", "generate_content", {}), "kagent")
        self.assertEqual(component("ateapi", "CreateActor", {"ate.actor.name": "session-test"}), "actor")
        self.assertEqual(component("ateom-gvisor", "RestoreWorkload", {}), "worker")
        self.assertEqual(component("atenet-router", "ListActors", {}), "substrate")

    def test_session_links_require_exact_actor_identity(self):
        store = ActivityStore()
        snapshot = {"traces": [
            {"traceId": "request", "spans": [], "components": ["kagent"], "edges": []},
            {"traceId": "lifecycle", "spans": [{"attributes": {"ate.actor.name": "session-a"}}],
             "components": ["worker"], "edges": [{"from": "substrate", "to": "worker"}]},
            {"traceId": "other", "spans": [{"attributes": {"ate.actor.name": "session-b"}}],
             "components": ["actor"], "edges": []}]}
        activity = store.actor_activity(snapshot, "session-a", "request")
        self.assertEqual(activity["traceIds"], ["request", "lifecycle"])
        self.assertEqual(activity["components"], ["kagent", "worker"])
        self.assertEqual(activity["edges"], [{"from": "substrate", "to": "worker", "traceId": "lifecycle"}])
        self.assertIsNone(store.actor_activity(snapshot, None, "request"))

    def test_routine_polls_do_not_displace_agent_request_history(self):
        store = ActivityStore(max_traces=3)
        store.ingest(export([span(trace=1)], "kagent-controller"))
        for n in range(2, 7):
            record = span(trace=n)
            record["name"] = "ateapi.Control/ListActors"
            store.ingest(export([record], "ateapi"))
        traces = store.snapshot()["traces"]
        self.assertEqual(len(traces), 3)
        self.assertIn(f"{1:032x}", [t["traceId"] for t in traces])

    def test_active_actor_worker_trace_survives_control_plane_polling(self):
        store = ActivityStore(max_traces=3)
        store.focus(f"{1:032x}", "session-a")
        store.ingest(export([span(trace=1)], "kagent-controller"))
        store.ingest(export([span(trace=2)], "ateom-gvisor"))
        store.ingest_logs({"resourceLogs": [{"scopeLogs": [{"logRecords": [{
            "timeUnixNano": "1000000000", "traceId": f"{2:032x}", "spanId": f"{1:016x}",
            "eventName": "ate.actor.state_changed", "attributes": [
                {"key": "ate.actor.name", "value": {"stringValue": "session-a"}},
                {"key": "ate.actor.state", "value": {"stringValue": "resuming"}}]}]}]}]})
        for n in range(3, 12):
            record = span(trace=n)
            record["name"] = "ateapi.Control/GetActor"
            store.ingest(export([record], "ateapi"))
        retained = [t["traceId"] for t in store.snapshot()["traces"]]
        self.assertEqual(len(retained), 3)
        self.assertIn(f"{1:032x}", retained)
        self.assertIn(f"{2:032x}", retained)
