import json
import unittest
from unittest.mock import patch
import backend
from backend import invocation_prompt, terminal_text
from telemetry import ActivityStore, parse_otlp, tool_execution


def export(spans, service="kagent"):
    return {"resourceSpans": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
                              "scopeSpans": [{"spans": spans}]}]}


def span(n=1, parent=None, values=None, trace=1):
    return {"traceId": f"{trace:032x}", "spanId": f"{n:016x}", "parentSpanId": f"{parent:016x}" if parent else "",
            "name": "chat", "startTimeUnixNano": "1000000000", "endTimeUnixNano": "1200000000",
            "attributes": [{"key": k, "value": {"intValue" if isinstance(v, int) else "stringValue": v}} for k, v in (values or {}).items()]}


def native_export(spans, service="hosted-aks-docs-v1", resource_values=None):
    payload = export(spans, service)
    values = {"kagent.runtime": "adk-go", "gen_ai.main_agent.id": "kagent/hosted-aks-docs-v1",
              "gen_ai.main_agent.name": "hosted-aks-docs-v1", "gen_ai.request.model": "test-model",
              **(resource_values or {})}
    payload["resourceSpans"][0]["resource"]["attributes"] += [
        {"key": key, "value": {"stringValue": value}} for key, value in values.items()]
    return payload


class NativeProjectionTests(unittest.TestCase):
    def test_native_request_survives_background_eviction_and_late_transport(self):
        store = ActivityStore(max_traces=4, max_spans=20)
        model = span(values={"gen_ai.operation.name": "generate_content", "gen_ai.request.model": "test-model", "gen_ai.usage.input_tokens": 12,
                             "gen_ai.usage.output_tokens": 3, "gen_ai.conversation.id": "session-1", "a2a.task.id": "task-1"})
        model["name"] = "generate_content test-model"
        store.ingest(native_export([model], "kagent", {"gen_ai.request.model": ""}))
        self.assertEqual(len(store.snapshot()["traces"][0]["modelCalls"]), 1)
        for trace_id in range(2, 6):
            store.ingest(export([span(trace=trace_id)], "background-runtime"))
        late = span(2)
        late["name"] = "UpdateTask"
        transport = span(3)
        transport["name"] = "a2a.request"
        store.ingest(native_export([late, transport], "kagent", {"gen_ai.request.model": ""}))
        request = next(t for t in store.snapshot()["traces"] if t["traceId"] == f"{1:032x}")
        self.assertEqual(len(request["modelCalls"]), 1)
        self.assertEqual(request["inputTokens"], 12)
        self.assertEqual(request["spanCount"], 3)
        self.assertTrue(request["nativeRequest"])
        self.assertIsNone(store.focus_trace)

    def test_native_resource_identity_is_independent_of_arbitrary_service_name(self):
        for service in ("hosted-aks-docs-v1", "some-agent", "contains-mcp-but-is-an-agent"):
            with self.subTest(service=service):
                store = ActivityStore()
                store.ingest(native_export([span(values={"gen_ai.operation.name": "generate_content"})], service))
                trace = store.snapshot()["traces"][0]
                self.assertIn("kagent", trace["components"])
                self.assertNotIn("mcp", trace["components"])
                self.assertEqual(trace["nativeRuntimeIdentity"], {"runtime": "adk-go", "agentId": "kagent/hosted-aks-docs-v1", "agentName": "hosted-aks-docs-v1"})

    def test_agent_name_without_typed_runtime_does_not_establish_native_identity(self):
        for runtime in ("", "unknown-future-runtime"):
            store = ActivityStore()
            store.ingest(native_export([span(values={"gen_ai.operation.name": "generate_content"})], resource_values={"kagent.runtime": runtime}))
            trace = store.snapshot()["traces"][0]
            self.assertIsNone(trace["nativeRuntimeIdentity"])
            self.assertFalse(trace["nativeRequest"])
            self.assertEqual(trace["modelCalls"], [])

    def test_resource_model_does_not_manufacture_model_calls_for_transport_or_tools(self):
        model = span(1, values={"gen_ai.operation.name": "generate_content"})
        skill = span(2, values={"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "load_skill"})
        transport = span(3)
        transport["name"] = "a2a.request"
        store = ActivityStore()
        store.ingest(native_export([model, skill, transport]))
        trace = store.snapshot()["traces"][0]
        self.assertEqual([c["spanId"] for c in trace["modelCalls"]], [model["spanId"]])
        self.assertIsNone(trace["costUsd"])
        self.assertFalse(trace["usageComplete"])

    def test_native_reports_own_usage_with_missing_gateway_parents(self):
        observations = [
            (1, 10, "native", "1000000000", "2951116312", "2040", "95"),
            (2, 1, "http", "1007186613", "2950935942", None, None),
            (3, 11, "gateway", "1036295812", "2950121118", "2040", "95"),
            (4, 10, "native", "2960267832", "5579845347", "4956", "242"),
            (5, 4, "http", "2973170056", "5579655619", None, None),
            (6, 12, "gateway", "2976552082", "5578995972", "4956", "242"),
            (7, 10, "native", "5586313471", "19091468573", "8697", "970"),
            (8, 7, "http", "5586911429", "19021158100", None, None),
            (9, 13, "gateway", "5591541422", "14057901656", "8697", "970"),
        ]
        store = ActivityStore()
        observed_attributes = {}
        for span_id, parent_id, report, start, end, inp, out in observations:
            native = report != "gateway"
            values = {"kagent.runtime": "adk-go", "gen_ai.main_agent.id": "kagent/native-agent",
                      "gen_ai.main_agent.name": "native-agent"} if native else {}
            if inp is not None:
                values.update({"gen_ai.operation.name": "generate_content" if native else "chat",
                               "gen_ai.request.model": "test-model", "gen_ai.usage.input_tokens": inp,
                               "gen_ai.usage.output_tokens": out, "gen_ai.usage.cache_read.input_tokens": "0" if native else inp})
            else:
                values.update({"http.request.method": "POST", "http.response.status_code": "200"})
            raw = span(span_id, parent=parent_id, values=values)
            raw.update(startTimeUnixNano=start, endTimeUnixNano=end,
                       name="HTTP POST" if report == "http" else "generate_content test-model" if native else "POST request",
                       kind=3 if report == "http" else 1 if native else 2)
            store.ingest(export([raw], "native-agent" if native else "agentgateway"))
            observed_attributes[raw["spanId"]] = values
        trace = store.snapshot()["traces"][0]
        self.assertEqual(len(trace["modelCalls"]), 3)
        self.assertEqual(trace["modelUsageSource"], "native-runtime")
        self.assertEqual({c["spanId"] for c in trace["modelCalls"]},
                         {f"{n:016x}" for n in (1, 4, 7)})
        self.assertEqual((trace["inputTokens"], trace["outputTokens"]), (15693, 1307))
        self.assertTrue(trace["usageComplete"])
        self.assertIsNone(trace["costUsd"])
        self.assertEqual(trace["costSource"], "unknown")
        self.assertEqual(trace["spanCount"], 9)
        self.assertEqual({s["spanId"]: s["parentSpanId"] for s in trace["spans"]},
                         {f"{row[0]:016x}": f"{row[1]:016x}" for row in observations})
        for observed in trace["spans"]:
            self.assertTrue(observed_attributes[observed["spanId"]].items() <= observed["attributes"].items())
        self.assertEqual({(e["from"], e["to"]): set(e["spanIds"]) for e in trace["edges"]},
                         {("kagent", "model"): {f"{n:016x}" for n in (1, 4, 7)},
                          ("agentgateway", "model"): {f"{n:016x}" for n in (3, 6, 9)}})

    def test_native_model_owns_usage_with_correlated_gateway_child(self):
        usage = {"gen_ai.operation.name": "generate_content", "gen_ai.request.model": "test-model",
                 "gen_ai.usage.input_tokens": 12, "gen_ai.usage.output_tokens": 3}
        store = ActivityStore(prices={"test-model": {"inputPerMillion": 2, "outputPerMillion": 6}})
        store.ingest(native_export([span(values=usage), span(3)]))
        store.ingest(export([span(2, parent=1, values={**usage, "gen_ai.usage.cost_usd": "0.2"})], "agentgateway"))
        trace = store.snapshot()["traces"][0]
        self.assertEqual(len(trace["modelCalls"]), 1)
        self.assertEqual(trace["inputTokens"], 12)
        self.assertEqual(trace["outputTokens"], 3)
        self.assertEqual(trace["modelUsageSource"], "native-runtime")
        self.assertEqual(trace["modelCalls"][0]["spanId"], f"{1:016x}")
        self.assertIsNone(trace["costUsd"])
        self.assertEqual(trace["costSource"], "unknown")
        self.assertIsNone(trace["modelCalls"][0]["pricingSource"])
        self.assertEqual(trace["spanCount"], 3)
        self.assertIn(("kagent", "agentgateway"), [(e["from"], e["to"]) for e in trace["edges"]])

    def test_native_missing_usage_is_not_filled_from_gateway_reports(self):
        for values in ({}, {"gen_ai.usage.input_tokens": 12}):
            with self.subTest(values=values):
                store = ActivityStore()
                native = span(1, parent=2, values={"gen_ai.operation.name": "generate_content", **values})
                gateway_usage = {"gen_ai.request.model": "test-model", "gen_ai.usage.input_tokens": 999,
                                 "gen_ai.usage.output_tokens": 999, "gen_ai.usage.cost_usd": "0.2"}
                store.ingest(native_export([native]))
                store.ingest(export([span(2, values=gateway_usage), span(3, parent=1, values=gateway_usage),
                                     span(4, values=gateway_usage)], "agentgateway"))
                trace = store.snapshot()["traces"][0]
                self.assertEqual([c["spanId"] for c in trace["modelCalls"]], [f"{1:016x}"])
                self.assertEqual(trace["inputTokens"], values.get("gen_ai.usage.input_tokens"))
                self.assertIsNone(trace["outputTokens"])
                self.assertIsNone(trace["costUsd"])
                self.assertFalse(trace["usageComplete"])
                self.assertEqual(trace["spanCount"], 4)

    def test_native_model_name_is_not_required_for_source_ownership(self):
        store = ActivityStore()
        store.ingest(native_export([span(values={"gen_ai.operation.name": "generate_content"})],
                                   resource_values={"gen_ai.request.model": ""}))
        store.ingest(export([span(2, values={"gen_ai.request.model": "test-model", "gen_ai.usage.input_tokens": 999,
                                           "gen_ai.usage.output_tokens": 999})], "agentgateway"))
        trace = store.snapshot()["traces"][0]
        self.assertEqual(trace["modelUsageSource"], "native-runtime")
        self.assertEqual([c["spanId"] for c in trace["modelCalls"]], [f"{1:016x}"])
        self.assertIsNone(trace["modelCalls"][0]["model"])
        self.assertIsNone(trace["inputTokens"])
        self.assertIsNone(trace["outputTokens"])
        self.assertFalse(trace["usageComplete"])
        self.assertEqual(trace["spanCount"], 2)

    def test_nested_native_reports_reconcile_only_within_native_source(self):
        store = ActivityStore()
        store.ingest(native_export([
            span(values={"gen_ai.operation.name": "generate_content", "gen_ai.usage.input_tokens": 12,
                         "gen_ai.usage.output_tokens": 3, "gen_ai.usage.cost_usd": "0.1"}),
            span(2, parent=1, values={"gen_ai.operation.name": "generate_content", "gen_ai.usage.input_tokens": 12})]))
        store.ingest(export([span(3, parent=2, values={"gen_ai.request.model": "test-model", "gen_ai.usage.input_tokens": 999,
                                                    "gen_ai.usage.output_tokens": 999, "gen_ai.usage.cost_usd": "0.2"})], "agentgateway"))
        trace = store.snapshot()["traces"][0]
        self.assertEqual(trace["modelUsageSource"], "native-runtime")
        self.assertEqual(len(trace["modelCalls"]), 1)
        self.assertEqual(trace["modelCalls"][0]["spanId"], f"{2:016x}")
        self.assertEqual((trace["inputTokens"], trace["outputTokens"]), (12, 3))
        self.assertEqual(trace["costUsd"], .1)
        self.assertEqual(trace["costSource"], "reported")
        self.assertEqual(trace["spanCount"], 3)

    def test_equal_native_siblings_are_independent_reports(self):
        store = ActivityStore()
        usage = {"gen_ai.operation.name": "generate_content", "gen_ai.usage.input_tokens": 12, "gen_ai.usage.output_tokens": 3}
        store.ingest(native_export([span(1, values=usage), span(2, values=usage)]))
        store.ingest(export([span(3, values={**usage, "gen_ai.request.model": "test-model"})], "agentgateway"))
        trace = store.snapshot()["traces"][0]
        self.assertEqual([c["spanId"] for c in trace["modelCalls"]], [f"{1:016x}", f"{2:016x}"])
        self.assertEqual((trace["inputTokens"], trace["outputTokens"]), (24, 6))
        self.assertEqual(trace["spanCount"], 3)

    def test_native_skills_and_local_tools_do_not_claim_mcp_execution(self):
        tools = [span(n, values={"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": name})
                 for n, name in enumerate(("load_skill", "load_skill_resource", "read_file"), 1)]
        for tool in tools:
            tool.update(kind=1, name="execute_tool " + tool["attributes"][1]["value"]["stringValue"])
        store = ActivityStore()
        store.ingest(native_export(tools))
        trace = store.snapshot()["traces"][0]
        self.assertIn("skills", trace["components"])
        self.assertNotIn("mcp", trace["components"])
        self.assertEqual([(s["toolCategory"], s["toolExecution"]) for s in trace["spans"]],
                         [("skill", "native-skill"), ("skill", "native-skill"), ("native", "native-internal")])
        skill_edge = next(e for e in trace["edges"] if e["to"] == "skills")
        self.assertEqual(skill_edge["spanIds"], [tools[0]["spanId"], tools[1]["spanId"]])

    def test_actual_mcp_metadata_remains_mcp_for_a_native_caller(self):
        tool = span(values={"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "search_docs", "mcp.tool.name": "search_docs"})
        tool["kind"] = 3
        store = ActivityStore()
        store.ingest(native_export([tool]))
        trace = store.snapshot()["traces"][0]
        self.assertIn("mcp", trace["components"])
        self.assertEqual(trace["spans"][0]["toolCategory"], "mcp")
        self.assertEqual(trace["spans"][0]["toolExecution"], "")

    def test_untyped_tool_names_do_not_establish_mcp(self):
        for service in ("kagent", "agentgateway"):
            with self.subTest(service=service):
                tools = [span(n, values={"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": tool})
                         for n, tool in enumerate(("skills", "read_file", "search_docs"), 1)]
                for tool in tools:
                    tool["kind"] = 1
                store = ActivityStore()
                store.ingest(export(tools, service))
                trace = store.snapshot()["traces"][0]
                self.assertNotIn("mcp", trace["components"])
                self.assertEqual([s["toolCategory"] for s in trace["spans"]], ["", "", ""])

    def test_explicit_mcp_metadata_identifies_an_untyped_tool(self):
        tool = span(values={"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "read_file",
                            "mcp.tool.name": "read_file"})
        tool["kind"] = 2
        store = ActivityStore()
        store.ingest(export([tool]))
        trace = store.snapshot()["traces"][0]
        self.assertIn("mcp", trace["components"])
        self.assertEqual(trace["spans"][0]["toolCategory"], "mcp")
        self.assertEqual(trace["spans"][0]["toolExecution"], "server")

    def test_native_unset_status_is_not_reported_as_explicit_success(self):
        tool = span(values={"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "load_skill"})
        tool.update(kind=1, status={"code": 0})
        store = ActivityStore()
        store.ingest(native_export([tool]))
        trace = store.snapshot()["traces"][0]
        self.assertEqual(trace["spans"][0]["otelStatus"], "unset")
        self.assertEqual(trace["spans"][0]["status"], "unknown")
        self.assertEqual(trace["status"], "unknown")

    def test_native_fragment_with_gateway_span_has_no_task_success_status(self):
        store = ActivityStore()
        store.ingest(native_export([span(values={"rpc.method": "UpdateTask"})]))
        store.ingest(export([span(2, values={"http.response.status_code": 200})], "agentgateway"))
        trace = store.snapshot()["traces"][0]
        self.assertFalse(trace["nativeRequest"])
        self.assertIsNotNone(trace["nativeRuntimeIdentity"])
        self.assertEqual(trace["status"], "unknown")

    def test_native_totals_disclose_excluded_mixed_runtime_reports(self):
        store = ActivityStore()
        store.ingest(native_export([span(values={"gen_ai.operation.name": "generate_content",
            "gen_ai.request.model": "native-model", "gen_ai.usage.input_tokens": 10,
            "gen_ai.usage.output_tokens": 2, "gen_ai.usage.cost_usd": "0.1"})]))
        store.ingest(export([span(2, parent=1, values={"gen_ai.operation.name": "chat",
            "gen_ai.request.model": "other-model", "gen_ai.usage.input_tokens": 500,
            "gen_ai.usage.output_tokens": 50, "gen_ai.usage.cost_usd": "0.5"})], "kagent-python-subagent"))
        trace = store.snapshot()["traces"][0]
        self.assertEqual((trace["inputTokens"], trace["outputTokens"]), (10, 2))
        self.assertEqual(len(trace["modelCalls"]), 1)
        self.assertFalse(trace["usageComplete"])
        self.assertEqual(trace["excludedModelReports"], 1)
        self.assertEqual(trace["costUsd"], .1)
        self.assertEqual(trace["costSource"], "partial")
        self.assertEqual(trace["spanCount"], 2)

    def test_native_priority_does_not_change_manual_focus_or_hard_bounds(self):
        store = ActivityStore(max_traces=4, max_spans=6)
        store.focus(f"{99:032x}", "manual-actor")
        store.ingest(export([span(trace=99)]))
        for trace_id in range(1, 20):
            store.ingest(native_export([span(trace=trace_id, values={"gen_ai.operation.name": "generate_content"})]))
            snapshot = store.snapshot()
            self.assertLessEqual(len(snapshot["traces"]), 4)
            self.assertLessEqual(sum(t["spanCount"] for t in snapshot["traces"]), 6)
        self.assertEqual(store.focus_trace, f"{99:032x}")
        self.assertEqual(store.focus_actor, "manual-actor")
        self.assertIn(f"{99:032x}", [t["traceId"] for t in snapshot["traces"]])
        self.assertEqual(len(store.recent_native_requests), 8)
        self.assertIn(f"{19:032x}", [t["traceId"] for t in snapshot["traces"]])
        store.ingest(native_export([span(n, trace=30, values={"gen_ai.operation.name": "generate_content"}) for n in range(1, 8)]))
        self.assertLessEqual(sum(t["spanCount"] for t in store.snapshot()["traces"]), 6)

    def test_native_metadata_allowlist_retains_identity_but_not_content(self):
        safe = {"gen_ai.agent.name": "subagent", "gen_ai.agent.id": "kagent/subagent", "gen_ai.conversation.id": "session-id",
                "a2a.task.id": "task-id", "a2a.method": "SendMessage", "a2a.task.state": "completed", "kagent.genai.producer": "runtime"}
        content = {key: "PRIVATE_MARKER" for key in ("enduser.id", "gen_ai.input.messages", "gen_ai.output.messages", "gen_ai.tool.call.arguments", "gen_ai.tool.call.result", "http.request.header.authorization")}
        store = ActivityStore()
        store.ingest(native_export([span(values={**safe, **content})]))
        result = store.snapshot()
        attributes = result["traces"][0]["spans"][0]["attributes"]
        self.assertTrue(safe.items() <= attributes.items())
        self.assertNotIn("PRIVATE_MARKER", json.dumps(result))

    def test_external_lifecycle_requires_shared_observed_actor_identity(self):
        store = ActivityStore()
        store.ingest(native_export([span(values={"gen_ai.operation.name": "generate_content"})]))
        unrelated = span(trace=2, values={"ate.actor.name": "other-actor"})
        store.ingest(export([unrelated], "ateapi"))
        self.assertIsNone(store.observed_activity(store.snapshot(), f"{1:032x}"))
        store.ingest(native_export([span(2, values={"ate.actor.name": "observed-actor", "ate.actor.uid": "actor-uid"})]))
        for n, actor in ((3, "observed-actor"), (4, "other-actor")):
            record = log_record(trace=n)
            record["attributes"] = [{"key": key, "value": {"stringValue": value}} for key, value in {
                "ate.actor.name": actor, "ate.actor.uid": "actor-uid" if n == 3 else "other-uid", "ate.actor.state": "suspended"}.items()]
            store.ingest_logs(log_export([record], "ateapi"))
            store.ingest(export([span(trace=n, values={"ate.actor.name": actor, "ate.actor.uid": "actor-uid" if n == 3 else "other-uid"})], "ateapi"))
        activity = store.observed_activity(store.snapshot(), f"{1:032x}")
        self.assertEqual(activity["actorName"], "observed-actor")
        self.assertEqual(set(activity["traceIds"]), {f"{1:032x}", f"{3:032x}"})
        self.assertEqual(activity["requestTraceId"], f"{1:032x}")
        self.assertEqual([s["traceId"] for s in activity["states"]], [f"{3:032x}"])

    def test_external_lifecycle_rejects_reused_names_and_conflicting_request_identity(self):
        store = ActivityStore()
        identity = {"ate.actor.name": "actor", "ate.actor.uid": "original-uid", "ate.atespace": "space"}
        store.ingest(native_export([span(values={"gen_ai.operation.name": "generate_content", **identity})]))
        store.ingest(export([span(trace=2, values={**identity, "ate.actor.uid": "replacement-uid"})], "ateapi"))
        self.assertEqual(store.observed_activity(store.snapshot(), f"{1:032x}")["traceIds"], [f"{1:032x}"])
        store.ingest(native_export([span(2, values={"ate.actor.name": "actor", "ate.actor.uid": "conflicting-uid"})]))
        self.assertIsNone(store.observed_activity(store.snapshot(), f"{1:032x}"))


class TraceProjectionTests(unittest.TestCase):
    def test_pinned_kubernetes_internal_handler_is_execution_but_client_is_not(self):
        values = {"mcp.tool.name": "k8s_get_resources"}
        self.assertEqual(tool_execution(1, "flow-kubernetes-mcp", "mcp.tool.k8s_get_resources", values), "kagent-tools-internal")
        self.assertEqual(tool_execution(3, "flow-kubernetes-mcp", "mcp.tool.k8s_get_resources", values), "")
        self.assertEqual(tool_execution(1, "other-client", "mcp.tool.k8s_get_resources", values), "")
        self.assertEqual(tool_execution(1, "flow-kubernetes-mcp", "planning", values), "")

    def test_server_and_client_evidence_survives_projection(self):
        store = ActivityStore()
        server, client = span(1), span(2)
        server.update(kind=2, status={"code": 1})
        client.update(kind="SPAN_KIND_CLIENT")
        store.ingest(export([server, client], "flow-kubernetes-mcp"))
        projected = store.snapshot()["traces"][0]["spans"]
        self.assertEqual([(s["kind"], s["otelStatus"]) for s in projected], [("server", "ok"), ("client", "unset")])

    def test_live_presets_use_deployment_namespace_and_separate_tools(self):
        with patch.dict(backend.os.environ, {"DEMO_MODE": "live-tools", "DEMO_NAMESPACE": "demo-alternate", "DEMO_PROMPT": "combined"}):
            presets = backend.live_scenarios()
        self.assertIn("namespace demo-alternate", presets[0]["prompt"])
        self.assertIn("Call only k8s_get_resources", presets[0]["prompt"])
        self.assertIn("Call only gitlab_get_project and gitlab_get_latest_pipeline", presets[1]["prompt"])
        self.assertEqual(presets[2]["prompt"], "combined")
        with patch.dict(backend.os.environ, {"DEMO_MODE": "connected"}):
            self.assertEqual(backend.live_scenarios(), [])

    def test_recent_requested_runs_survive_unclassified_background_traffic(self):
        store = ActivityStore(max_traces=10, max_spans=100)
        for n in (1, 2):
            store.focus(f"{n:032x}")
            store.ingest(export([span(trace=n)]))
        for n in range(3, 50):
            store.ingest(export([span(trace=n)], "background-runtime"))
        snapshot = store.snapshot()
        ids = {t["traceId"] for t in snapshot["traces"]}
        self.assertTrue({f"{1:032x}", f"{2:032x}"} <= ids)
        self.assertEqual(len(ids), 10)
        self.assertEqual(store.recent_requests.maxlen, 8)

    def test_otlp_transport_retry_is_deduplicated(self):
        store = ActivityStore()
        payload = export([span()])
        store.ingest(payload)
        store.ingest(payload)
        self.assertEqual(store.snapshot()["traces"][0]["spanCount"], 1)
        self.assertEqual(store.snapshot()["revision"], 1)

    def test_missing_usage_is_not_zero(self):
        store = ActivityStore()
        store.ingest(export([span(values={"gen_ai.request.model": "test"})]))
        result = store.snapshot()["traces"][0]
        self.assertIsNone(result["inputTokens"])
        self.assertIsNone(result["costUsd"])

    def test_zero_usage_stays_zero(self):
        store = ActivityStore()
        store.ingest(export([span(values={"gen_ai.request.model": "test", "gen_ai.usage.input_tokens": 0, "gen_ai.usage.output_tokens": 0})]))
        self.assertEqual(store.snapshot()["traces"][0]["inputTokens"], 0)
        self.assertIsNone(store.snapshot()["traces"][0]["costUsd"])

    def test_gateway_child_usage_replaces_duplicate_runtime_usage(self):
        usage = {"gen_ai.request.model": "test", "gen_ai.usage.input_tokens": 100, "gen_ai.usage.output_tokens": 20}
        store = ActivityStore()
        store.ingest(export([span(values=usage)]))
        store.ingest(export([span(n=2, parent=1, values=usage)], "agentgateway"))
        result = store.snapshot()["traces"][0]
        self.assertEqual(result["inputTokens"], 100)
        self.assertEqual(result["outputTokens"], 20)
        self.assertEqual(len(result["modelCalls"]), 1)
        self.assertNotIn({"from": "kagent", "to": "model"}, [{"from": e["from"], "to": e["to"]} for e in result["edges"]])

    def test_two_model_calls_are_both_counted(self):
        usage = {"gen_ai.request.model": "test", "gen_ai.usage.input_tokens": 100, "gen_ai.usage.output_tokens": 20}
        store = ActivityStore()
        store.ingest(export([span(1, values=usage), span(2, values=usage)], "agentgateway"))
        self.assertEqual(store.snapshot()["traces"][0]["inputTokens"], 200)

    def test_distinct_nested_models_are_independent_calls(self):
        store = ActivityStore()
        store.ingest(export([span(values={"gen_ai.request.model": "outer", "gen_ai.usage.input_tokens": 100, "gen_ai.usage.output_tokens": 10}),
                             span(2, parent=1, values={"gen_ai.request.model": "inner", "gen_ai.usage.input_tokens": 20, "gen_ai.usage.output_tokens": 2})]))
        result = store.snapshot()["traces"][0]
        self.assertEqual(result["inputTokens"], 120)
        self.assertEqual(result["outputTokens"], 12)
        self.assertEqual(len(result["modelCalls"]), 2)

    def test_secret_and_prompt_attributes_are_dropped(self):
        store = ActivityStore()
        store.ingest(export([span(values={"authorization": "Bearer SECRET", "gen_ai.prompt": "SECRET", "http.url": "https://private/?token=SECRET", "gen_ai.request.model": "test"})]))
        self.assertNotIn("SECRET", json.dumps(store.snapshot()))

    def test_invalid_export_is_atomic(self):
        store = ActivityStore()
        invalid = span(2)
        invalid["traceId"] = "bad"
        with self.assertRaises(ValueError):
            store.ingest(export([span(), invalid]))
        self.assertEqual(store.snapshot()["traces"], [])

    def test_bounded_retention(self):
        store = ActivityStore(max_traces=2)
        for n in range(1, 4):
            store.ingest(export([span(trace=n)]))
        self.assertEqual([t["traceId"] for t in store.snapshot()["traces"]], [f"{n:032x}" for n in [3, 2]])

    def test_span_limit_evicts_whole_trace(self):
        store = ActivityStore(max_spans=2)
        store.ingest(export([span(n=n) for n in range(1, 4)]))
        self.assertEqual(store.snapshot()["traces"], [])

    def test_late_parent_creates_correlated_edge(self):
        store = ActivityStore()
        store.ingest(export([span(2, parent=1)], "agentgateway"))
        self.assertEqual(store.snapshot()["traces"][0]["edges"], [])
        store.ingest(export([span()], "kagent"))
        self.assertEqual(store.snapshot()["traces"][0]["edges"][0]["basis"], "parent span")

    def test_missing_substrate_cannot_light_up(self):
        store = ActivityStore()
        store.ingest(export([span()]))
        result = store.snapshot()
        self.assertNotIn("substrate", result["traces"][0]["components"])
        self.assertEqual(next(n for n in result["components"] if n["id"] == "substrate")["availability"], "unobserved")

    def test_substrate_actor_requires_substrate_span(self):
        store = ActivityStore()
        store.ingest(export([span(values={"substrate.actor.id": "test-actor"})], "substrate-api"))
        self.assertIn("actor", store.snapshot()["traces"][0]["components"])

    def test_pricing_is_explicit_and_labelled(self):
        store = ActivityStore(prices={"test": {"inputPerMillion": 2, "outputPerMillion": 6, "source": "test configuration"}})
        store.ingest(export([span(values={"gen_ai.request.model": "test", "gen_ai.usage.input_tokens": 100, "gen_ai.usage.output_tokens": 20})]))
        result = store.snapshot()["traces"][0]
        self.assertAlmostEqual(result["costUsd"], .00032)
        self.assertEqual(result["costSource"], "estimated")

    def test_bad_token_values_are_unknown(self):
        store = ActivityStore()
        store.ingest(export([span(values={"gen_ai.request.model": "test", "gen_ai.usage.input_tokens": "NaN", "gen_ai.usage.output_tokens": -5})]))
        self.assertIsNone(store.snapshot()["traces"][0]["inputTokens"])

    def test_unknown_sibling_keeps_cost_partial(self):
        store = ActivityStore(prices={"test": {"inputPerMillion": 2, "outputPerMillion": 6}})
        known = {"gen_ai.request.model": "test", "gen_ai.usage.input_tokens": 100, "gen_ai.usage.output_tokens": 20}
        store.ingest(export([span(1, values=known), span(2, values={"gen_ai.request.model": "test"})]))
        result = store.snapshot()["traces"][0]
        self.assertEqual(len(result["modelCalls"]), 2)
        self.assertEqual(result["costSource"], "partial")
        self.assertFalse(result["usageComplete"])

    def test_partial_child_recovers_one_matching_parent(self):
        store = ActivityStore()
        store.ingest(export([span(values={"gen_ai.request.model": "test", "gen_ai.usage.input_tokens": 100, "gen_ai.usage.output_tokens": 20, "gen_ai.usage.cost_usd": "0.2"})]))
        store.ingest(export([span(2, parent=1, values={"gen_ai.request.model": "test", "gen_ai.usage.input_tokens": 100})], "agentgateway"))
        result = store.snapshot()["traces"][0]
        self.assertEqual(result["outputTokens"], 20)
        self.assertEqual(result["costUsd"], .2)

    def test_partial_children_do_not_repeat_aggregate_parent(self):
        store = ActivityStore()
        store.ingest(export([span(values={"gen_ai.request.model": "test", "gen_ai.usage.output_tokens": 200})]))
        store.ingest(export([span(n, parent=1, values={"gen_ai.request.model": "test", "gen_ai.usage.input_tokens": 100}) for n in [2, 3]], "agentgateway"))
        self.assertIsNone(store.snapshot()["traces"][0]["outputTokens"])

    def test_cost_without_tokens_is_retained(self):
        store = ActivityStore()
        store.ingest(export([span(values={"gen_ai.request.model": "test", "gen_ai.usage.cost_usd": "0.1"})]))
        self.assertEqual(store.snapshot()["traces"][0]["costUsd"], .1)
        self.assertIsNone(store.snapshot()["traces"][0]["inputTokens"])

    def test_nonfinite_number_rejected_atomically(self):
        store = ActivityStore()
        payload = export([span(values={"gen_ai.request.model": "test"})])
        payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"].append({"key": "gen_ai.usage.input_tokens", "value": {"doubleValue": float("inf")}})
        with self.assertRaises(ValueError):
            store.ingest(payload)
        self.assertEqual(store.snapshot()["traces"], [])
        json.dumps(store.snapshot(), allow_nan=False)

    def test_replay_retains_each_repeated_model_edge(self):
        store = ActivityStore()
        store.ingest(export([span(n, values={"gen_ai.request.model": "test"}) for n in [1, 2]], "agentgateway"))
        self.assertEqual(store.snapshot()["traces"][0]["edges"][0]["spanIds"], [f"{n:016x}" for n in [1, 2]])

    def test_http_span_names_drop_urls_and_query_secrets(self):
        raw = span()
        raw["name"] = "GET https://private.internal/query?token=SECRET"
        store = ActivityStore()
        store.ingest(export([raw]))
        self.assertNotIn("SECRET", json.dumps(store.snapshot()))
        self.assertNotIn("private.internal", json.dumps(store.snapshot()))

    def test_underscore_runtime_service_is_kagent(self):
        store = ActivityStore()
        store.ingest(export([span()], "otel_flow_reader"))
        self.assertIn("kagent", store.snapshot()["traces"][0]["components"])

    def test_completed_caller_preserves_success_with_failed_child_probe(self):
        store = ActivityStore()
        store.ingest(export([span()], "flow-client"))
        child = span(2, parent=1)
        child["status"] = {"code": 2}
        store.ingest(export([child]))
        result = store.snapshot()["traces"][0]
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["errorSpanCount"], 1)

    def test_nonterminal_task_cannot_be_reported_as_completed(self):
        with self.assertRaises(ValueError):
            terminal_text({"result": {"kind": "task", "status": {"state": "working"}, "artifacts": [{"parts": [{"kind": "text", "text": "Still running"}]}]}})

    def test_completed_task_and_direct_message_text(self):
        part = {"kind": "text", "text": "Observed ready"}
        self.assertEqual(terminal_text({"result": {"kind": "message", "parts": [part]}}), "Observed ready")
        self.assertEqual(terminal_text({"result": {"kind": "task", "status": {"state": "completed"}, "artifacts": [{"parts": [part]}]}}), "Observed ready")


class PromptTests(unittest.TestCase):
    def test_prompt_preserves_user_text_and_trims_outer_whitespace(self):
        self.assertEqual(invocation_prompt({"prompt": "  Check inventory\nand explain health.  "}), "Check inventory\nand explain health.")

    def test_blank_nonstring_and_wrong_target_payloads_are_rejected(self):
        for payload in ({"prompt": "   "}, {"prompt": 1}, {}, [], {"prompt": "Hello", "agent": "another-agent"}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                invocation_prompt(payload)

    def test_prompt_limit(self):
        self.assertEqual(len(invocation_prompt({"prompt": "x" * 4000})), 4000)
        with self.assertRaises(ValueError):
            invocation_prompt({"prompt": "x" * 4001})

    def test_user_prompt_reaches_a2a_and_is_absent_from_telemetry(self):
        prompt = "Check the inventory and say PROVIDED_PROMPT_MARKER."
        response = {"result": {"kind": "message", "parts": [{"kind": "text", "text": "Observed ready"}]}}
        with patch("backend.post", side_effect=[response, {}]) as call, patch.dict(backend.INVOCATION, {}, clear=True), patch.dict(backend.os.environ, {"KAGENT_USER_ID": "demo-user"}):
            self.assertTrue(backend.INVOKING.acquire(blocking=False))
            backend.invoke(prompt, "1" * 32)
            request = call.call_args_list[0].args[1]
            self.assertEqual(request["params"]["message"]["parts"][0]["text"], prompt)
            self.assertEqual(call.call_args_list[0].args[2]["traceparent"].split("-")[1], "1" * 32)
            self.assertEqual(call.call_args_list[0].args[2]["X-User-Id"], "demo-user")
            self.assertNotIn("PROVIDED_PROMPT_MARKER", json.dumps(call.call_args_list[1].args[1]))
            self.assertEqual(backend.INVOCATION["status"], "completed")
            self.assertFalse(backend.INVOKING.locked())


def log_export(records, service="otel_flow_reader"):
    return {"resourceLogs": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
                              "scopeLogs": [{"logRecords": records}]}]}


def log_record(timestamp=1000000000, trace=1):
    return {"timeUnixNano": str(timestamp), "traceId": f"{trace:032x}", "spanId": "0000000000000001",
            "severityNumber": 9, "eventName": "gen_ai.assistant.message", "body": {"stringValue": "PRIVATE CONTENT"}}


class LogProjectionTests(unittest.TestCase):
    def test_service_filter_precedes_limit_and_keeps_all_service_choices(self):
        store = ActivityStore()
        store.ingest_logs(log_export([log_record(1)], "flow-gitlab-mcp"))
        store.ingest_logs(log_export([log_record(100+n) for n in range(220)], "agentgateway"))
        result = store.logs_snapshot(service="flow-gitlab-mcp")
        self.assertEqual(result["matching"], 1)
        self.assertEqual(result["logs"][0]["service"], "flow-gitlab-mcp")
        self.assertEqual(result["services"], ["agentgateway", "flow-gitlab-mcp"])

    def test_tool_log_uses_metadata_and_never_result_body(self):
        store = ActivityStore()
        record = log_record()
        record["attributes"] = [{"key": "gen_ai.tool.name", "value": {"stringValue": "gitlab_get_project"}}]
        store.ingest_logs(log_export([record], "flow-gitlab-mcp"))
        result = store.logs_snapshot()["logs"][0]
        self.assertEqual(result["message"], "Tool gitlab_get_project")
        self.assertNotIn("PRIVATE CONTENT", json.dumps(result))

    def test_gateway_api_details_preserve_path_and_status_without_query(self):
        store = ActivityStore()
        record = log_record()
        record["attributes"] = [{"key": key, "value": {"stringValue": value}} for key, value in {
            "http.method": "POST", "http.path": "/kimi/v1/chat/completions?credential=FAKE#fragment",
            "http.status": "200", "gen_ai.request.model": "test-model"}.items()]
        store.ingest_logs(log_export([record], "kimi-lab-gateway"))
        result = store.logs_snapshot()["logs"][0]
        self.assertEqual(result["message"], "POST /kimi/v1/chat/completions · 200 · test-model")
        self.assertNotIn("credential", json.dumps(result))
        self.assertNotIn("fragment", json.dumps(result))

    def test_real_log_shape_preserves_correlation_and_omits_content(self):
        store = ActivityStore()
        store.ingest_logs(log_export([log_record()]))
        result = store.logs_snapshot()["logs"][0]
        self.assertEqual(result["traceId"], f"{1:032x}")
        self.assertEqual(result["severity"], "INFO")
        self.assertEqual(result["event"], "gen_ai.assistant.message")
        self.assertNotIn("PRIVATE CONTENT", json.dumps(store.logs_snapshot()))

    def test_log_transport_retry_is_deduplicated(self):
        store = ActivityStore()
        for _ in range(2):
            store.ingest_logs(log_export([log_record()]))
        self.assertEqual(store.logs_snapshot()["retained"], 1)

    def test_same_metadata_distinct_log_bodies_not_collapsed(self):
        store = ActivityStore()
        one, two = log_record(), log_record()
        two["body"] = {"stringValue": "DIFFERENT PRIVATE CONTENT"}
        store.ingest_logs(log_export([one, two]))
        self.assertEqual(store.logs_snapshot()["retained"], 2)
        self.assertNotIn("PRIVATE CONTENT", json.dumps(store.logs_snapshot()))

    def test_trace_filter_precedes_display_limit(self):
        store = ActivityStore()
        store.ingest_logs(log_export([log_record(1000000000+n, trace=2) for n in range(205)] + [log_record(trace=1)]))
        self.assertEqual(len(store.logs_snapshot()["logs"]), 200)
        self.assertEqual(len(store.logs_snapshot(f"{1:032x}")["logs"]), 1)

    def test_logs_are_bounded_separately_from_traces(self):
        store = ActivityStore()
        store.max_logs = 2
        store.ingest_logs(log_export([log_record(1000000000+n) for n in range(3)]))
        self.assertEqual(store.logs_snapshot()["retained"], 2)
        self.assertEqual(store.snapshot()["traces"], [])

    def test_bad_log_export_is_atomic(self):
        store = ActivityStore()
        bad = log_record()
        bad["traceId"] = "bad"
        with self.assertRaises(ValueError):
            store.ingest_logs(log_export([log_record(), bad]))
        self.assertEqual(store.logs_snapshot()["retained"], 0)

    def test_observed_timestamp_and_uncorrelated_record(self):
        store = ActivityStore()
        record = log_record(0)
        record.update(observedTimeUnixNano="2000000000", traceId="", spanId="")
        store.ingest_logs(log_export([record]))
        self.assertEqual(store.logs_snapshot()["logs"][0]["timestampNs"], "2000000000")
        self.assertEqual(store.logs_snapshot()["logs"][0]["traceId"], "")


if __name__ == "__main__":
    unittest.main()
