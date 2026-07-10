# Agentic Triage Smoke Checklist

## Preflight

- [ ] Work target is non-production and approved.
- [ ] Real values are kept out of public repo files.
- [ ] Runtime readiness smoke is green.
- [ ] Grafana contact point or Alertmanager route is test-only.
- [ ] Smart-triage EventSource, Sensor, WorkflowTemplate, and RBAC are ready.

## Source-Type Smokes

- [ ] Metrics crashloop/restart smoke completed.
- [ ] Metrics CPU/memory pressure smoke completed or explicitly skipped with reason.
- [x] Loki log error-burst pattern live-proven in the reference environment.
  A new deployment must produce its own evidence against `DESIRED-STATE.md`.
- [x] Kubernetes event smoke completed.
- [x] Trace smoke completed or `NO_TRACE` fallback was explicit. Current status: fallback only, not real Tempo.
- [ ] Duplicate fingerprint suppresses duplicate fan-out.

## Agent Correctness

- [ ] Alert labels survived into normalized incident.
- [ ] Specialist markers are present.
- [ ] Agent output cites Grafana and Kubernetes evidence.
- [ ] Agent stayed in the target namespace and workload.
- [ ] No read-only smoke attempted mutation.
- [ ] HITL/GitOps boundary is visible before any write-capable remediation.
- [ ] Lifecycle eval passes with no hard failures.
- [ ] Real ticket-system update is captured when ticket hygiene is claimed.
- [ ] Smoke score is published with `agentic_triage_smoke_score >= 0.85`.
- [ ] Smoke score hard failures are zero.

## Grafana Health

- [ ] Stack-health dashboard imported or equivalent dashboard verified.
- [ ] Fleet dashboard shows target agent readiness.
- [ ] Incident received, triaged, remediation, and verified counters move.
- [ ] Latest lifecycle score is visible out of 10.
- [ ] Negative low-score or hard-failure alert fires.
- [ ] agentgateway and kagent controller health are visible.
- [ ] Argo workflow, EventSource/Sensor, and Vector/Kafka health are visible
      where those components are in the path.
- [ ] Latest scheduled smoke timestamp is visible.
- [ ] Stale scheduled smoke alert fires when no successful run appears in the
      expected window.
- [ ] `healthy`, `degraded`, or `broken` periodic verdict is visible.

## Periodic Health

- [ ] Quick profile proves model route, single A2A, and metric freshness.
- [ ] Daily profile proves webhook replay and one real metrics alert.
- [ ] Weekly profile proves one controlled target fault with HITL/GitOps
      boundary preserved.
- [ ] Monthly/full-source profile proves metrics, logs, events, and
      trace-or-fallback source coverage.
- [ ] Scheduled runs publish score, pass/fail, hard failures, last success
      timestamp, profile, target, and run ID.
- [ ] Target rotation is documented for whiskey app, podinfo, cert-manager, and
      external-dns or explicitly narrowed.

## Closeout

- [ ] Evidence template is complete.
- [ ] Cleanup completed for temporary alerts, chaos, and smoke workloads.
- [ ] Critique prompt sent to a separate agent.
