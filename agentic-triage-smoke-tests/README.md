# Agentic Triage Smoke Tests

## TL;DR

Use this bundle after installing the agentic triage system on a new server or
dev cluster. It proves that Grafana-origin problem signals reach kagent,
specialists fan out, agentgateway/model calls complete, evidence is visible in
Grafana, and the agent output passes deterministic lifecycle checks.

The smoke target can be the whiskey app, `podinfo`, or another explicitly
approved non-production workload. Keep every value placeholder-safe in this
public bundle and fill real values only inside the approved work environment.

## What This Feature Does

- Runs runtime readiness before alert-path tests.
- Exercises Grafana alert categories for metrics, logs, Kubernetes events, and
  traces or trace fallback.
- Replays Alertmanager-compatible payloads into the smart-triage fan-out path.
- Captures workflow, kagent, Grafana, Loki, Prometheus/Mimir, Tempo, and
  agentgateway evidence.
- Scores the completed run with the lifecycle evaluator.
- Publishes run health to the fleet dashboard and alert rules.
- Defines periodic dev-cluster smoke checks for future app targets such as
  cert-manager and external-dns.

## Work Replication Note

The Loki log and Kubernetes event alert path does not require a separate custom
tool or a new event bridge. It is ordinary LGTM configuration:

```text
pod logs -> Alloy or Promtail -> Loki -> Grafana LogQL alert
Kubernetes events -> Alloy loki.source.kubernetes_events -> Loki -> Grafana LogQL alert
Grafana alert -> Alertmanager/contact point -> Vector or direct webhook -> triage
```

What changes is the alert source and query language. Metrics alerts use
PromQL against Prometheus/Mimir. Log and event alerts use LogQL against Loki
after the relevant records have been ingested. The delivery path after the
Grafana alert fires can be the same smart-triage webhook path used for metric
alerts.

This is not automatic metric-alert correlation. If a Prometheus metric alert
fires and the agents need nearby logs or Kubernetes events, add an enrichment
step or have the triage agent query Loki/Tempo using the alert labels and time
window. For log and event smokes, the triggering evidence should already be in
the Loki alert result and annotations.

## Current Evidence Boundary

As of 2026-07-10, the live evidence proves several sub-paths:

```text
Run A:
pod failure -> Grafana metric alert -> webhook/EventSource -> Argo Workflow
-> incident normalization

Run B:
manual fan-out -> agentgateway Kimi route -> smart-triage specialists
-> HITL/eval success

Run C:
Kubernetes FailedScheduling event -> Alloy Kubernetes event source -> Loki
-> Grafana Loki alert -> smart-triage webhook/EventSource -> Argo Workflow
-> HITL/eval success

Run D:
pod error logs -> Promtail -> Loki -> Grafana LogQL alert
-> smart-triage webhook/EventSource -> Argo Workflow -> Kimi specialists
-> incident synthesis -> HITL gate

Run E:
metadata-only alert context -> kagent Tier 2 agent -> Grafana MCP Loki query
+ read-only AKS MCP pod/events/logs -> correlated diagnosis

Run F:
pod log failure -> Loki -> Grafana LogQL alert -> Vector webhook -> Kafka
-> Argo EventSource/Sensor -> Tier 2 Workflow -> kagent MCP investigation
-> deterministic 7/7 score
```

No single continuous `run_id` has yet proven
`pod failure -> Grafana metric alert -> webhook -> Argo -> Kimi fan-out -> eval`
in one run. Treat that as the next required metrics smoke before claiming the
metric crashloop path is fully end to end.

The live evidence now proves real Grafana-origin Kubernetes event and
application-log alerts via Loki, including reason, pod/workload identity, full
event message or parsed log failure, and a ready-to-run evidence query in the
triage payload. It also proves the explicit `NO_TRACE` fallback marker in a
live workflow. It does not yet prove a real Tempo trace alert,
alert-to-GitLab-ticket updates, or a single continuous metric crashloop run all
the way through Kimi and eval. Those smoke types remain required before
claiming full source coverage.

## Required Upstream Repo Assets

| Asset | Use |
|---|---|
| `work-agent-bundles/kagent-agentic-cluster-smoke-tests.md` | Runtime and A2A completion gate before alert testing |
| `a2a/smart-triage-fanout-demo/` | Alertmanager replay, fan-out workflow, dedup, HITL, lifecycle eval hook |
| `agents/grafana-evidence-agent/` | Shared Grafana metrics/logs/traces evidence specialist |
| `observability/agent-evals/` | Deterministic agent and lifecycle scoring |
| `work-agent-bundles/agentic-triage-smoke-tests/SCORECARD.md` | Programmatic smoke score before lifecycle eval |
| `observability/agent-evals/grafana/kagent-fleet-overview-dashboard.json` | Dashboard that shows agent readiness, run funnel, and scores out of 10 |
| `observability/agent-evals/alerting/agent-eval-rules.yaml` | Starter score and hard-failure alerts |
| `chaos/reliability/` | Controlled future chaos and self-heal test patterns |

## Smoke Matrix

| Smoke | Grafana source | Synthetic failure | Required proof |
|---|---|---|---|
| `metric-crashloop` | Prometheus/Mimir alert | Pod restart or CrashLoopBackOff threshold | Alert fires, run starts, Kubernetes + Grafana specialists complete, lifecycle score passes |
| `metric-cpu` | Prometheus/Mimir alert | CPU saturation or throttling on target pod | Alert labels survive, PromQL evidence links to target workload, agent recommends observe or scale path only |
| `log-errorburst` | Loki alert | Error log burst from target container | LogQL evidence is cited, agent does not invent Kubernetes state |
| `event-failedscheduling` | Kubernetes event surfaced through Grafana/Loki/Mimir | Unschedulable pod, quota, image pull, or warning event | Event reason/context survive into the normalized incident and agent output |
| `trace-latency` | Tempo trace alert or trace-linked Grafana alert | High latency span or missing trace fallback | Trace ID/deeplink is included, or `NO_TRACE` fallback is explicit and scored |
| `dedup-replay` | Alertmanager/Grafana replay | Same fingerprint posted twice | First alert fans out, second alert suppresses duplicate fan-out |
| `negative-agent-health` | Fleet/eval metrics | Missing completion, hard failure, or low score | Grafana dashboard and PrometheusRule show red/critical state |

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Fill `requests/agentic-triage-smoke-request.yaml` in the work context.
3. Run `WORK-AGENT-START-PROMPT.md` with the work-side agent.
4. Execute runtime readiness from `work-agent-bundles/kagent-agentic-cluster-smoke-tests.md`.
5. Execute the smoke matrix in `SMOKE-RUNBOOK.md`.
6. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.
7. Score the smoke with `scripts/score-smoke-run.py`.
8. Send `prompts/CRITIQUE-PROMPT.md` to a separate review agent.

## Repeatability Status

The application-log and Kubernetes-event paths are documented, live-tested,
and represented by placeholder-safe configuration in this bundle:

| Layer | Reusable asset | Live status |
|---|---|---|
| Application log generator | `examples/k8s/crashloop-smoke-target.yaml` | Proven pattern |
| Pod log collection | `examples/monitoring/promtail-smoke-namespace-values.yaml` | Proven configuration shape |
| Kubernetes event generator | `examples/k8s/failed-scheduling-smoke-target.yaml` | Proven |
| Kubernetes event export | `examples/alloy/kubernetes-events-to-loki.yaml` | Proven configuration shape |
| Grafana LogQL rules and contact point | `examples/grafana/source-type-alert-rules.yaml` | Log/event query shapes proven; provisioning schema must match installed Grafana |
| Webhook and workflow routing | `a2a/smart-triage-fanout-demo/` and this bundle's routing examples | Direct route proven |
| Enriched triage normalization | `a2a/smart-triage-fanout-demo/workflow-template.yaml` | Proven with captured live Grafana payload |
| Tier 2 kagent investigator | `examples/kagent/tier-two-mcp-triage-agent.yaml` | Grafana MCP plus AKS MCP investigation proven from metadata-only input |
| AKS MCP least privilege | `examples/kagent/aks-mcp-readonly-values.yaml` and `platform/aks-mcp/chart/templates/rbac.yaml` | Pods, events, and pod logs allowed; Secrets and mutations denied |
| Grafana MCP service access | `examples/kagent/grafana-mcp-host-validation-values.yaml` | Tool discovery and Loki query proven after explicit Host allowlist |
| Periodic Tier 2 workflow | `examples/argo/tier-two-mcp-triage-workflow-template.yaml` | Vector/Kafka-triggered metadata-only MCP investigation and strict 7/7 score proven |

This does not mean every observability source is complete. A real Tempo trace
alert, structured container image enrichment, parameterized periodic alert
rules, and source-accurate post-HITL lifecycle scoring remain explicit gaps.

The direct Tier 2 proof is documented in
`evidence/PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md`. The continuous
Grafana-to-Vector-to-Kafka proof is documented in
`evidence/PROXMOX-TIER-TWO-KAFKA-E2E-2026-07-10.md`. The workflow includes
controller-task polling for retryable A2A response failures.

## Configuration

Fill values in `requests/agentic-triage-smoke-request.yaml`, then substitute the
matching placeholders in the example manifests. Important observability values
include:

```text
{{CLUSTER_NAME}}
{{CLUSTER_ENVIRONMENT}}
{{CLUSTER_REGION}}
{{MONITORING_NAMESPACE}}
{{SMOKE_NAMESPACE}}
{{SMOKE_CONTAINER}}
{{EVENT_SMOKE_POD}}
{{PROMETHEUS_DATASOURCE_UID}}
{{LOKI_DATASOURCE_UID}}
{{LOKI_GATEWAY_SERVICE}}
{{GRAFANA_ALERT_WEBHOOK_URL}}
{{ALLOY_IMAGE}}
```

Use an approved local-registry image where the target cluster blocks public
registries. Do not write credentials or environment-specific private URLs into
the public bundle. Replace only the uppercase environment placeholders. Keep
Grafana runtime templates such as `{{ $labels.pod }}` and LogQL templates such
as `{{.name}}` intact; Grafana/Loki evaluates those at runtime.

Per-source Grafana alert examples are in:

```text
ALERTMANAGER-EVENT-ROUTING.md
LGTM-EVIDENCE-BRIDGE-GAP.md
LGTM-FIT-FOR-PURPOSE-ASSESSMENT.md
LGTM-INTEGRATION-PROBLEM-STATEMENT.md
LGTM-LOG-EVENT-TRIAGE-README.md
LGTM-METRICS-ONLY-COVERAGE.md
SOURCE-TYPE-ALERT-EXAMPLES.md
examples/grafana/agentic-triage-stack-health-dashboard.json
examples/grafana/source-type-alert-rules.yaml
examples/monitoring/promtail-smoke-namespace-values.yaml
examples/alertmanager-payloads/
```

## Live Evidence

The first real alert-intake smoke result is captured in:

```text
evidence/PROXMOX-E2E-SMOKE-2026-07-09.md
```

That run proved the Grafana alert webhook and Argo intake path, then failed at
agent completion because the model backend behind agentgateway was not Ready.

The follow-up provider, capacity, and full fan-out evidence is captured in:

```text
evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md
```

That separate manual run proved agentgateway Kimi routing, kagent A2A
completion, worker capacity recovery, full specialist fan-out, HITL resume, and
lifecycle eval success.

The live `FailedScheduling` event-routing proof is captured in:

```text
evidence/PROXMOX-EVENT-ALERTMANAGER-ROUTING-2026-07-09.md
```

That run proved a Kubernetes scheduling-failure symptom alert through
Prometheus, Alertmanager, the smart-triage webhook EventSource, full fan-out,
HITL resume, and lifecycle eval success.

The live Alloy-to-Loki Kubernetes event exporter proof is captured in:

```text
evidence/PROXMOX-ALLOY-K8S-EVENTS-TO-LOKI-2026-07-09.md
```

That run proved a raw Kubernetes scheduling event collected by Alloy into Loki,
a Grafana Loki alert routed to the smart-triage webhook, EventSource/Sensor
delivery, HITL resume, and lifecycle eval success. The specialist evidence
inside the current WorkflowTemplate is still partly synthetic and must be
replaced before claiming source-backed agent reasoning.

The live log smoke blocker and trace fallback evidence are captured in:

```text
evidence/PROXMOX-LOG-LOKI-SMOKE-BLOCKED-2026-07-09.md
evidence/PROXMOX-TRACE-FALLBACK-2026-07-09.md
```

The 2026-07-09 log smoke is intentionally marked `not_proven`: the pod emitted
the marker, but Promtail did not deliver it to Loki during that smoke window.
The 2026-07-10 retest below closes that log-ingestion gap. The trace smoke is
still marked `fallback_proven`, not real Tempo coverage.

The 2026-07-10 recovery and final live event/log alert proof is captured in:

```text
evidence/PROXMOX-LGTM-BRIDGE-LIVE-PREFLIGHT-2026-07-10.md
```

That retest identifies and fixes the Promtail namespace filter, proves both
LogQL alerts and their enriched webhook payloads, fixes specialist OOM and
hard-coded demo context, and verifies corrected incident synthesis at the HITL
gate.

The metadata-only Tier 2 investigation proof is captured in:

```text
evidence/PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md
```

That run proves a kagent Agent can use Grafana MCP and read-only AKS MCP to
recover and correlate Loki logs, pod state, Kubernetes events, and container
logs. At the time of that direct proof, automatic Kafka/workflow dispatch and
the A2A recovery path were still open; the follow-up below closes the dispatch
path and implements controller polling.

The follow-up continuous Kafka proof is captured in:

```text
evidence/PROXMOX-TIER-TWO-KAFKA-E2E-2026-07-10.md
```

That run preserves one run ID from Grafana through Vector, Kafka, Argo Events,
kagent, Grafana MCP, AKS MCP, and a deterministic 7/7 workflow score.

The specialist capacity fix is captured in:

```text
evidence/PROXMOX-SPECIALIST-CAPACITY-FIX-2026-07-09.md
```

The remaining open gaps are summarized in:

```text
evidence/OPEN-GAPS-2026-07-09.md
```

## Programmatic Scoring

Use the smoke scorecard before lifecycle eval:

```bash
python3 scripts/score-smoke-run.py \
  --run examples/score/proxmox-2026-07-09-smoke-run.json \
  --output-dir /tmp/agentic-triage-smoke-score
```

Expected for the first Proxmox run:

```text
score=0.75 passed=false
hard_failures=agent_path_failed
```

Then use `observability/agent-evals/scripts/score-lifecycle-run.py` once the
agent path is healthy and the smoke includes HITL/remediation/verification.

## Periodic Health Mode

Once the install smoke is green, run a low-risk periodic profile in dev:

- every 15 minutes: direct agentgateway model call, kagent A2A single-agent
  completion, and dashboard metric freshness;
- daily: one Grafana webhook replay with a unique fingerprint and one real
  metrics alert against an approved smoke workload;
- weekly: one controlled fault on a rotating target such as whiskey app,
  `podinfo`, cert-manager, or external-dns;
- monthly or before upgrades: full source matrix across metrics, logs, events,
  and trace or explicit trace fallback.

Periodic runs must publish `agentic_triage_smoke_score`,
`agentic_triage_smoke_passed`, and `agentic_triage_smoke_hard_failures`.
Grafana must alert when no successful dev smoke completed in the expected
window, when any hard failure appears, or when the score drops below `0.85`.

## Definition Of Done

The new server is green only when:

- agentgateway/model direct smoke passes;
- one A2A request and one alert-triggered smart-triage run complete;
- every selected smoke type has a completed run or an explicitly documented
  unsupported-source fallback;
- lifecycle eval passes with no hard failures;
- Grafana dashboard panels show agent health, incident funnel movement, and
  latest lifecycle score;
- the stack-health dashboard is imported or an equivalent dashboard is verified
  for kagent, agentgateway, workflows, EventSource/Sensor, Vector/Kafka, smoke
  freshness, and source coverage;
- low-score, non-completion, and hard-failure alerts are tested with a negative
  case and visibly fire.
