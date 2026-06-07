# GitLab Ticket: Prove A2A Smart Triage Fanout

## Summary

Prove that Kagent triage v2 can route one incident through the commander and
specialist agents over A2A, then return one evidence-backed synthesis.

## Feature

The smart-triage commander should receive an incident payload, fan out to
specialist agents, preserve shared context, and return a single response that
includes Kubernetes, Grafana, knowledge, GitOps, and remediation-safety state.

## Evidence Required

- Runtime readiness bundle has passed or blockers are recorded.
- A2A payload and endpoint used.
- Task/session/context ID.
- Specialist completion markers.
- Commander synthesis.
- Sanitized output check.

## Acceptance Criteria

- `A2A_BASELINE_COMPLETED: yes`
- `SPECIALIST_FANOUT_STARTED: yes`
- `KUBERNETES_SPECIALIST_COMPLETED: yes`
- `GRAFANA_SPECIALIST_COMPLETED: yes`
- `KNOWLEDGE_SPECIALIST_COMPLETED: yes`
- `GITOPS_SPECIALIST_COMPLETED: yes`
- `SYNTHESIS_CREATED: yes`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not claim this is proven from static manifests. The proof requires live A2A
request/response evidence or an explicit blocker.
