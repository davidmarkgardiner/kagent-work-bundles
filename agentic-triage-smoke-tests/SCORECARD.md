# Programmatic Smoke Scorecard

## TL;DR

Use two gates:

1. **Smoke readiness score**: proves the alert path and agent path are working.
2. **Lifecycle eval score**: proves the agent did the right job after triage,
   including HITL, remediation, verification, and ticket hygiene when a real or
   explicitly stubbed ticket-system action is captured.

The Proxmox run on 2026-07-09 passed the alert-intake part but failed the agent
completion part because the model backend returned `502`.

For the `tier-two-continuous` profile, `DESIRED-STATE.md` is stricter than the
weighted campaign score below: all mandatory gates must pass in one continuous
`run_id`, and the dedicated Workflow score must be exactly `7/7`. The `0.85`
threshold remains the aggregate readiness gate for the broader
`full-source-campaign`; it cannot be used to accept a partial Tier 2 path.

## Gate 1: Smoke Readiness

This gate answers:

```text
Can a real workload fault create a real Grafana alert, deliver it by webhook,
create a triage workflow, normalize the incident, and complete agent work?
```

Score dimensions:

| Dimension | Weight | Evidence source |
|---|---:|---|
| failure injected | 0.10 | Kubernetes pod/event/log or chaos object |
| signal visible | 0.10 | Prometheus/Mimir, Loki, Kubernetes event, or Tempo query |
| Grafana alert firing | 0.15 | Grafana alert state or Alertmanager payload |
| webhook delivered | 0.15 | Argo EventSource log or captured webhook payload |
| workflow created | 0.10 | Argo Workflow object |
| incident normalized | 0.15 | `INCIDENT_NORMALIZED: yes` plus labels |
| agent completed | 0.20 | A2A completed/specialist markers |
| eval published | 0.05 | `agent_lifecycle_eval_*` or smoke score metric |

Pass condition:

```text
score >= 0.85
hard_failures == []
```

Hard failures:

- no real injected failure;
- no Grafana alert state or webhook payload;
- no workflow created;
- incident namespace/workload mismatch;
- agent path failed after workflow creation;
- production target mutated without explicit approval;
- public-safety leak in captured evidence.

## Gate 2: Lifecycle Eval

Once Gate 1 is green, run the existing lifecycle evaluator for cases that
include HITL, remediation, self-heal, verification, and ticket updates.
Only pass `--ticket-system`, `--ticket-id`, and `--ticket-url` when there is
real ticket evidence or an approved test stub with an evidence file:

```bash
python3 observability/agent-evals/scripts/collect-lifecycle-evidence.py \
  --evidence {{MARKER_LOG}} \
  --argo-workflow {{SANITIZED_WORKFLOW_JSON}} \
  --output /tmp/lifecycle-run.json \
  --workflow-name {{WORKFLOW_NAME}} \
  --namespace {{TARGET_NAMESPACE}} \
  --workload {{TARGET_WORKLOAD}} \
  --failure-mode {{FAILURE_MODE}} \
  --ticket-system GitLab \
  --ticket-id {{TICKET_ID}} \
  --ticket-url {{TICKET_URL}} \
  --remediation-mode gitops_or_workflow_only

python3 observability/agent-evals/scripts/score-lifecycle-run.py \
  --case observability/agent-evals/lifecycle-cases/chaos-pod-delete.yaml \
  --run /tmp/lifecycle-run.json \
  --output-dir /tmp/kagent-lifecycle-evals
```

Lifecycle pass condition for self-heal/remediation smoke:

```text
agent_lifecycle_eval_passed = 1
agent_lifecycle_eval_score >= 0.85
agent_lifecycle_eval_hard_failures = 0
```

Do not use lifecycle eval alone to prove alert intake. It starts after evidence
has already been captured. Use Gate 1 to prove delivery into the agent system,
then Gate 2 to prove the agent did the right operational work.

## Grafana Dashboard Logic

Publish both gate results to Prometheus/Mimir:

```prometheus
agentic_triage_smoke_score{cluster,namespace,workload,run_id,smoke}
agentic_triage_smoke_passed{cluster,namespace,workload,run_id,smoke}
agentic_triage_smoke_hard_failures{cluster,namespace,workload,run_id,smoke}
agent_lifecycle_eval_score{cluster,namespace,agent,case_id,run_id,workflow_name,env_tier}
agent_lifecycle_eval_passed{cluster,namespace,agent,case_id,run_id,workflow_name,env_tier}
agent_lifecycle_eval_hard_failures{cluster,namespace,agent,case_id,run_id,workflow_name,env_tier}
```

For periodic stack-health runs, also publish:

```prometheus
agentic_triage_smoke_last_success_timestamp_seconds{cluster,env_tier,profile}
agentic_triage_smoke_source_coverage{cluster,env_tier,source,status}
```

Dashboard panels should show:

- latest smoke score out of 10;
- pass/fail by smoke type;
- hard failures by run ID;
- alert-to-workflow count;
- workflow-to-agent completion count;
- lifecycle score once remediation/self-heal is enabled.
- latest scheduled success timestamp by profile;
- source coverage status for metrics, logs, events, and traces.

Alert rules:

```promql
absent_over_time(agentic_triage_smoke_score{env_tier="dev"}[2h])
  and absent_over_time(agentic_triage_smoke_passed{env_tier="dev"}[2h])
  and absent_over_time(agentic_triage_smoke_hard_failures{env_tier="dev"}[2h])
agentic_triage_smoke_passed == 0
agentic_triage_smoke_hard_failures > 0
absent_over_time(agentic_triage_smoke_score{env_tier="dev"}[24h])
time() - agentic_triage_smoke_last_success_timestamp_seconds{env_tier="dev",profile="daily"} > 90000
absent_over_time(agentic_triage_smoke_score{env_tier="dev",profile="quick"}[30m])
agentic_triage_smoke_source_coverage{env_tier="dev",source=~"metrics|logs|events|traces",status=~"not_run|unsupported"} > 0
agent_lifecycle_eval_hard_failures > 0
agent_lifecycle_eval_score < 0.85
```

## Periodic Pass Logic

Use three verdicts for recurring runs:

| Verdict | Rule |
|---|---|
| `healthy` | latest required profile passed, score is at least `0.85`, hard failures are zero, and the run is fresh |
| `degraded` | run completed but score is low, source coverage is incomplete, or the run is stale |
| `broken` | model route, A2A, webhook delivery, workflow creation, normalization, agent completion, or eval publication failed |

Fast checks should not inject faults. They should only prove that the model,
A2A, dashboard, and score publication paths are alive. Daily and weekly checks
are the right place to prove real alerting and controlled failure scenarios.

## Proxmox 2026-07-09 Interpretation

That run should score as:

```text
failure injected: yes
signal visible: yes
Grafana alert firing: yes
webhook delivered: yes
workflow created: yes
incident normalized: yes
agent completed: no
eval published: no
```

Expected score:

```text
0.75
passed=false
hard_failure=agent_path_failed
```

The operational conclusion is precise:

```text
Alert delivery into the agent system is proven.
The agentic triage system is not healthy until the model/backend path completes.
```

Follow-up evidence in
`evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md` proves the
model/backend path, A2A specialist path, full fan-out, HITL resume, and lifecycle
eval success after the worker-capacity fix. It does not replace the need for
one continuous alert-triggered crashloop run, and it does not replace the need
for live Loki log and real Tempo trace source smokes. Kubernetes event via
Alloy/Loki/Grafana is now proven separately, and trace fallback is proven as
`NO_TRACE`, not as real Tempo coverage.
