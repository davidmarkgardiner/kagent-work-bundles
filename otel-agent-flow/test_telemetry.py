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
