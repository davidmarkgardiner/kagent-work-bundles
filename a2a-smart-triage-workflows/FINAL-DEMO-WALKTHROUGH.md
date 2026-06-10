# Final Demo Walkthrough

## Purpose

Use this A2A bundle as the last-day demo controller. The goal is to prove and
document what already exists in the work lab, not to build new features.

## Demo Story

```text
SRE brings an incident or controlled fault -> commander fans out over A2A ->
specialists gather evidence -> HITL/GitOps boundaries are respected ->
chaos/eval evidence is scored -> GitLab contains the final report.
```

## Minimum Demo Path

1. Confirm runtime readiness or record the blocker.
2. Send one baseline A2A call and capture the completed response.
3. Replay one incident or controlled chaos payload.
4. Fan out to specialists:
   - Kubernetes/AKS triage
   - Grafana MCP metrics/logs/dashboard evidence
   - querydoc/vector KB lookup with source citation
   - GitLab MCP issue/MR/comment/code-update evidence
   - memory recall if installed
   - policy/HITL safety state
5. If chaos is in scope, show the chaos event and lifecycle eval result.
6. Produce one commander synthesis.
7. Update GitLab with the demo evidence and next actions.
8. Create the final handover front sheet and ticket set described in
   `FINAL-HANDOVER-PACK.md`.

## Required Output

```text
A2A_BASELINE_COMPLETED: yes
SPECIALIST_FANOUT_STARTED: yes
KUBERNETES_SPECIALIST_COMPLETED: yes
GRAFANA_SPECIALIST_COMPLETED: yes
KNOWLEDGE_SPECIALIST_COMPLETED: yes
GITOPS_SPECIALIST_COMPLETED: yes
QUERYDOC_KB_PROVEN: yes_or_blocked
GRAFANA_MCP_PROVEN: yes_or_blocked
GITLAB_MCP_PROVEN: yes_or_blocked
MEMORY_CONTEXT_PROVEN: yes_or_not_available
HITL_GATE_PROVEN: yes_or_blocked
CHAOS_EVAL_LOOP_PROVEN: yes_or_blocked
CONTEXT_PRESERVED: yes
SYNTHESIS_CREATED: yes
FINAL_DEMO_REPORT_CREATED: yes
FINAL_FRONT_SHEET_CREATED: yes
GITLAB_TICKET_SET_CREATED: yes
EVIDENCE_INDEX_CREATED: yes
NEXT_ACTIONS_RECORDED: yes
OUTPUT_SANITIZED: yes
```

If any integration is unavailable, do not spend the day rebuilding it. Record
the exact blocker, owner, and next action in the final report.
