# Add Gateway telemetry to the existing collection path

The base bundle already connects agents, models and MCP through Agent Gateway with JWT and destination consent. This amendment adds the missing Gateway observability configuration and target evidence. Reuse the installed collector and LGTM paths. Do not install dashboards or replace shared pipelines.

## Current evidence and its boundary

Read-only inspection of the native home lab on 3 November 2026 found four accepted/attached secure Gateway JWT policies with no frontend telemetry configuration. The inspected `agent-flow-demo/flow-collector` exports traces/logs to `otlp_http/viewer` and `otlp_http/old_demo`; no Tempo/Loki exporter appears in that collector. This does not establish whether a different LGTM path exists and says nothing conclusive about the office collector. Inspect it before changing anything.

The installed Gateway policy CRD and the upstream `v1.5.0` source support Gateway-scoped `spec.frontend.tracing` and `spec.frontend.accessLog.otlp`. Current website documentation may describe a newer release. Use the actual installed CRD, not an old standalone `rawConfig` example or an inferred version field.

## Render the additive proposal

Export the actual installed CRD and full policy list to a private directory using the explicit approved target context. Copy and complete `examples/telemetry-settings.json` there. Discover selectors from the actual Gateway and collector workloads. The sample intentionally fails before its placeholders and scope/privacy decisions are resolved.

```sh
kubectl --context '{{TARGET_CONTEXT}}' get crd agentgatewaypolicies.agentgateway.dev -o json \
  > '{{PRIVATE_DIR}}/policy-crd.json'
kubectl --context '{{TARGET_CONTEXT}}' get agentgatewaypolicy -A -o json \
  > '{{PRIVATE_DIR}}/policies.json'
python3 render_telemetry.py \
  --settings '{{PRIVATE_DIR}}/settings.json' \
  --policy-crd '{{PRIVATE_DIR}}/policy-crd.json' \
  --policy-snapshot '{{PRIVATE_DIR}}/policies.json' \
  --output '{{NEW_PRIVATE_PROPOSAL_DIRECTORY}}'
```

The renderer emits `resources.json`, `networkFragments.json`, and `review.json`. It never applies, installs or upgrades anything. The resource List contains a new Gateway-scoped telemetry policy and, for a cross-namespace collector, an exact destination ReferenceGrant from `AgentgatewayPolicy` to the named collector Service. It leaves JWT route policies intact. If existing Gateway tracing or access-log policies would conflict, it refuses and requires a reviewed owner merge.

The policy affects the whole selected Gateway. Use a dedicated demo Gateway or obtain the shared Gateway owner's scope decision. A sampling ratio of `1.0` is for a bounded rehearsal. Keep production sampling and cost decisions separate.

Network output contains rule fragments only. Merge them into the existing reviewed network baseline, preserving its DNS, API, model, MCP and existing producer paths. Creating a first partial Ingress or Egress policy can isolate traffic that previously worked. Inspect effective additive policies and actual Service/container ports; do not assume a new allow object overrides an existing broader permit.

`collectorPort` is the collector Service port used by the policy backend reference. `collectorPodPort` is the actual numeric receiving Pod port used in the network fragments. Resolve named `targetPort` values from actual workload/endpoints; the two ports are not necessarily equal. The target CNI's Service translation and effective rules still require a traffic test.

Review the private proposal and run server dry-run. Then use the existing platform delivery process within its supplied authority. Require actual current policy `Accepted`/`Attached` conditions, route status, destination consent and consumer connectivity. A dry-run checks admission; it does not prove attachment or telemetry export.

## Preserve collection and privacy before fan-out

1. Capture the current collector/alloy configuration, deployment ownership and rollback inputs. Record each existing receiver, processor, exporter, pipeline, authentication reference and downstream destination.
2. Disable producer message/content/raw-API-body capture using the actual installed producer's settings. Do not add headers, bearer tokens, JWT claims, user prompts, tool arguments/results, arbitrary baggage or provider response/error bodies as trace fields.
3. Require an owner-reviewed metadata-only collector path **before** any new LGTM fan-out. The existing dashboard's `telemetry.py` projection protects its retained view only; it does not sanitize the collector's other exporters. Preserve unrelated existing pipelines. Use a dedicated approved receiver/pipeline if shared-path privacy requirements cannot be merged safely.
4. Allow bounded request identity, Gateway/listener/route/backend identity, method/status, duration, observed trace/span/parent IDs, actual task/session IDs, model and tool names, and reported token counts. Remove or sanitize event names, events, status/error messages and URLs that might contain content. Keep target metadata private when necessary.
5. Reuse the actual Tempo trace exporter and Loki/log export path supported by the installed collector. Preserve existing viewer/old-demo destinations. Validate auth, CA, protocol, port and destination from the exporting workload. The viewer needs OTLP HTTP JSON without compression; that is not a blanket requirement for Tempo or Loki.
6. Verify traces, logs and metrics separately. Gateway OTLP traces/access logs do not install a Prometheus scrape or send metrics to Mimir. Reuse the current approved scrape/remote-write pipeline. Do not put trace, session, run or task IDs into Prometheus labels.

Do not copy a whole collector ConfigMap from this amendment. Its actual destinations and credentials belong to the target owner. Missing pipeline permissions, privacy review, export or query access is a concrete gate to resolve, not evidence of successful LGTM integration.

## Instrument the standalone producer now

Use the existing application/agent workload's supported OTel configuration and instrumentation without Substrate. Verify real model/MCP calls and Gateway spans for that workload. Missing standalone instrumentation is a gap to fix or report, not a reason to switch to native execution or wait for Substrate.

## Native producer configuration is future reference only

Do not apply this section for the current no-Substrate demo. Native/Substrate installation and telemetry are deferred.

The existing `otel-agent-flow/NATIVE-KAGENT-OTEL.md` documents the native alpha17 configuration. It configures **both** controller `config.telemetry` and `config.runtimeDefaults.telemetry`, with content/raw-body capture disabled. The paired Substrate 0.6 configuration uses its own `otel` settings. Preserve all other values and the existing native-controller ownership split.

Do not run the old `otel-agent-flow/scripts/platform-telemetry.py` helper for this amendment. It pins alpha8/Substrate 0.4-era charts and performs Helm upgrades and shared egress changes. The renderer here does not invoke it. A no-Substrate target stays on its existing path and does not acquire native-only prerequisites.

## Prove correlation without inventing a single trace

The base `runtime/server.py` does not propagate incoming `traceparent` through its CLI-created native session or its model proxy. Gateway tracing alone therefore does not prove one caller-to-agent-to-model/MCP parent chain. The work agent must add version-compatible instrumentation/propagation at those actual boundaries and test it, or explicitly report multiple observed traces linked by actual session/task IDs or emitted span links. Timing or equal token totals is not a relationship.

`probe_trace.py request` creates fresh W3C context and stores only status, timing, requested IDs, response size/hash and an unverified outcome. It never stores a response body or token. This is client evidence, not an observed Gateway span or a functional workflow verdict.

```sh
python3 probe_trace.py request \
  --url '{{APPROVED_GATEWAY_INVOKE_URL}}' \
  --payload '{{PRIVATE_DIR}}/reviewed-prompt.json' \
  --token-file '{{PRIVATE_DIR}}/caller.jwt' \
  --expected-status 200 --output '{{NEW_PRIVATE_REQUEST_RECEIPT}}'
```

Use files readable only by their owner for credentials. Omit `--token-file` for the missing-token negative control. `--allow-http` is an explicit option for an approved internal or operator-forwarded test endpoint; HTTPS certificate verification remains enabled by default. Forwarded environment proxies and redirects are not used.

Retrieve the requested trace ID if propagation preserved it, or the actual Gateway trace ID from its current approved access logs. Query the existing approved Tempo frontend:

```sh
python3 probe_trace.py trace \
  --tempo-url '{{APPROVED_TEMPO_QUERY_BASE}}' \
  --trace-id '{{ACTUAL_TRACE_ID}}' \
  --expected-service agentgateway-secure-onboarding \
  --output '{{NEW_PRIVATE_TRACE_RECEIPT}}'
```

Optional `--auth-file`, `--tenant`, and `--ca-file` use the target's approved query mechanism. Never forward an agent caller JWT to Tempo as a substitute for its query credentials. The helper requests JSON from `/api/traces/{id}`, accepts known Tempo/OTLP envelopes and hex/base64 protobuf identifiers, checks actual trace/service identity and projects metadata only. Unknown envelopes require target adaptation. A 404, missing service, missing span or query denial is not a trace pass. There is no automatic retry or alternate provider.

The projected trace does not prove full workflow ancestry, allowed tool output, denial side effects, log delivery, metrics collection or cost. Pair it with real functional/backend receipts, actual logs and separate metrics evidence. Preserve the selected runtime's reported usage without summing the same model call across Gateway and runtime layers. Unreported cost remains unreported.

The helper retains observed trace/span/parent IDs but omits span links. If cross-trace correlation depends on emitted span links, retain separate owner-reviewed private evidence of those actual links. Do not infer them from this projection.

## Versioned sources

- [Agent Gateway v1.5.0 frontend translator](https://github.com/agentgateway/agentgateway/blob/v1.5.0/controller/pkg/agentgateway/plugins/frontend_policies.go).
- [Agent Gateway v1.5.0 policy CRD](https://github.com/agentgateway/agentgateway/blob/v1.5.0/controller/install/helm/agentgateway-crds/templates/agentgateway.dev_agentgatewaypolicies.yaml).
- [Agent Gateway v1.5.0 OTLP access-log fixture](https://github.com/agentgateway/agentgateway/blob/v1.5.0/controller/pkg/agentgateway/plugins/testdata/frontendpolicy/accesslog-otlp.yaml).
- [Tempo HTTP query API](https://grafana.com/docs/tempo/latest/api_docs/). Verify the installed target response format.
