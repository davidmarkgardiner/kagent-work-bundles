# Native KAgent 1.x model and skill telemetry

The native documentation-agent rehearsal uses KAgent `1.0.0-alpha17`, its
Go ADK runtime, and Substrate `0.6.0-alpha3`. It runs separately from the earlier
dual-runtime demo. These are tested pins, not a rolling version recommendation.

## What the viewer observes

Native runtime identity comes from `kagent.runtime` and
`gen_ai.main_agent.id` / `gen_ai.main_agent.name`, rather than a hard-coded
agent service name. `gen_ai.conversation.id` and `a2a.task.id` retain the session
and task correlation. On the native path, only actual model operations count
as model calls. Runtime-level `gen_ai.request.model` also appears on transport
and tool spans.

When native model operations are present, token totals use the native runtime's
reports. Gateway spans remain visible with their own reported usage. The viewer
does not add usage across reporting layers or match orphan gateway spans by
time or equal token counts. A missing intermediate parent can leave the gateway
path incomplete even when its spans share the request trace.
Other, unselected runtime model reports make the total partial and are counted
in `excludedModelReports`. Gateway reports alone do not make a native total partial.

`load_skill` and `load_skill_resource` appear under **Skills and knowledge**.
These are native runtime tools. MCP activity requires separate MCP evidence.
Merged tool bookkeeping spans do not count as individual skill reads.

Recent observed native requests receive bounded retention priority independently
of the explicitly selected UI request. The existing maximum trace/span limits
still apply. A busy viewer can eventually evict older requests; it is an
in-memory demonstration, not a durable trace archive.
Cross-trace lifecycle summaries cover eight recent native requests. Older traces
remain inspectable. Those summaries require an observed actor name and prefer
the actor UID when it is also present. A UID alone does not create an association.

The viewer accepts only allowlisted, bounded metadata. It omits prompts,
messages, tool arguments/results, raw log bodies, and headers. The graph proves
observed calls and correlation. The GoldenScenario's separate A2A receipt checks
the actual returned skill and knowledge-file bytes.

## Configuration

For the KAgent alpha17 Helm chart, point both controller and runtime defaults
at the collector. Preserve the rest of the installed values:

```yaml
config:
  telemetry:
    captureContent: false
    captureRawApiBodies: false
    traces:
      endpoint: http://flow-collector.agent-flow-demo.svc.cluster.local:4317
      protocol: grpc
    logs:
      endpoint: http://flow-collector.agent-flow-demo.svc.cluster.local:4317
      protocol: grpc
  runtimeDefaults:
    telemetry:
      captureContent: false
      captureRawApiBodies: false
      traces:
        endpoint: http://flow-collector.agent-flow-demo.svc.cluster.local:4317
        protocol: grpc
      logs:
        endpoint: http://flow-collector.agent-flow-demo.svc.cluster.local:4317
        protocol: grpc
```

For the paired Substrate chart, preserve its other settings and use:

```yaml
otel:
  endpoint: http://flow-collector.agent-flow-demo.svc.cluster.local:4317
  traces:
    enabled: true
    samplingRatio: 1
  logs:
    enabled: true
  metrics:
    enabled: false
```

The installed agentgateway 1.5 frontend policy uses the same collector host
for `frontendPolicies.tracing.host` and
`frontendPolicies.accessLog.otlp.host`, with `protocol: grpc`. Validate those
fields against the installed gateway before reusing them elsewhere.

The collector must export OTLP HTTP **JSON**, with compression disabled, to
the viewer's `/v1/traces` and `/v1/logs` endpoints. The application does not
decode OTLP protobuf.

For an observation-only viewer, set `READ_ONLY_VIEWER=true`. This disables
`POST /api/invoke` and hides the prompt controls. The viewer needs no model
credentials, Kubernetes service-account token, or agent-invocation adapter.
Keep access on a trusted local forwarding route: this flag is not an
authentication layer for the telemetry ingestion endpoints. Default interactive
demo behavior remains available when the flag is absent.

## Verification boundary

Use a fresh native session and compare actual semantic span IDs with its
GoldenScenario task. Check model-call reconciliation across the runtime and
gateway, all six native skill/resource reads, session/task identity, token
usage, and continued retention under ordinary background traffic. Missing
cost remains **Not reported**. Lifecycle links require a shared trace or an
observed actor identity; elapsed time alone establishes no connection.

The read-only viewer setting does not make the hosted agent a read-only
security boundary. Agent execution permissions and builtin file-writing tools
require their own controls. See the [native CRD guide](../../platform/skills-registry/native/README.md).
