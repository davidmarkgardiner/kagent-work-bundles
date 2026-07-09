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

## Current Evidence Boundary

As of 2026-07-09, the live evidence proves several sub-paths:

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
```

No single continuous `run_id` has yet proven
`pod failure -> Grafana metric alert -> webhook -> Argo -> Kimi fan-out -> eval`
in one run. Treat that as the next required metrics smoke before claiming the
metric crashloop path is fully end to end.

The live evidence now proves one real Grafana-origin Kubernetes event alert via
Alloy and Loki. It also proves the explicit `NO_TRACE` fallback marker in a
live workflow. It does not yet prove application log alerts, real Tempo trace
alerts, alert-to-GitLab-ticket updates, or a single continuous metric crashloop
run all the way through Kimi and eval. Those smoke types remain required before
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

Per-source Grafana alert examples are in:

```text
ALERTMANAGER-EVENT-ROUTING.md
SOURCE-TYPE-ALERT-EXAMPLES.md
examples/grafana/agentic-triage-stack-health-dashboard.json
examples/grafana/source-type-alert-rules.yaml
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

The log smoke is intentionally marked `not_proven`: the pod emitted the marker,
but Promtail did not deliver it to Loki during the smoke window. The trace smoke
is marked `fallback_proven`, not real Tempo coverage.

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
