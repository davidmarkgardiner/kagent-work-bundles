# GitLab Ticket: Prove A2A Smart Triage Fanout

## Summary

Prove that Kagent triage v2 can route one incident through the commander and
specialist agents over A2A, then return one evidence-backed synthesis. For the
final handover demo, use this issue to prove the integrations that are already
built rather than starting new implementation.

## Feature

The smart-triage commander should receive an incident payload, fan out to
specialist agents, preserve shared context, and return a single response that
includes Kubernetes, Grafana, knowledge, GitOps, memory, HITL, chaos/eval, and
remediation-safety state.

## Evidence Required

- Runtime readiness bundle has passed or blockers are recorded.
- A2A payload and endpoint used.
- Task/session/context ID.
- Specialist completion markers.
- querydoc/vector KB cited answer.
- Grafana MCP query/dashboard evidence.
- GitLab MCP issue/MR/comment/code-update evidence.
- Memory seed/recall evidence, or not-available reason.
- HITL suspend/approval route, or Teams-channel blocker.
- Chaos/eval evidence and GitLab report link.
- Commander synthesis.
- Final front sheet.
- Evidence index.
- Per-capability GitLab ticket set.
- Next actions and owners.
- Sanitized output check.

## Acceptance Criteria

- `A2A_BASELINE_COMPLETED: yes`
- `SPECIALIST_FANOUT_STARTED: yes`
- `KUBERNETES_SPECIALIST_COMPLETED: yes`
- `GRAFANA_SPECIALIST_COMPLETED: yes`
- `KNOWLEDGE_SPECIALIST_COMPLETED: yes`
- `GITOPS_SPECIALIST_COMPLETED: yes`
- `QUERYDOC_KB_PROVEN: yes_or_blocked`
- `GRAFANA_MCP_PROVEN: yes_or_blocked`
- `GITLAB_MCP_PROVEN: yes_or_blocked`
- `MEMORY_CONTEXT_PROVEN: yes_or_not_available`
- `HITL_GATE_PROVEN: yes_or_blocked`
- `CHAOS_EVAL_LOOP_PROVEN: yes_or_blocked`
- `SYNTHESIS_CREATED: yes`
- `FINAL_DEMO_REPORT_CREATED: yes`
- `FINAL_FRONT_SHEET_CREATED: yes`
- `GITLAB_TICKET_SET_CREATED: yes`
- `EVIDENCE_INDEX_CREATED: yes`
- `NEXT_ACTIONS_RECORDED: yes`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not claim this is proven from static manifests. The proof requires live A2A
request/response evidence or an explicit blocker.
