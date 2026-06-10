# A2A Smart Triage Workflows Work-Agent Bundle

Purpose: prove that Kagent agents can collaborate through A2A, call specialist
skills, preserve context, and return one synthesized incident answer.

For the final handover demo, use this as the orchestration bundle that proves
the current work-lab capabilities end to end. Do not build new features unless
there is a small blocker fix. Prefer evidence collection, screenshots,
transcripts, GitLab links, and a concise demo report.

## One-Line Ask

Replay or trigger one incident, fan out to specialist agents, collect their
findings, and produce a single commander synthesis with citations, evidence,
and remediation safety state. For the final demo, include querydoc/vector KB,
Grafana MCP, GitLab MCP, memory where available, HITL, chaos, lifecycle eval,
and final GitLab evidence.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/a2a-smart-triage-request.yaml`
5. `prompts/01-prove-a2a-fanout.md`
6. `prompts/02-final-demo-walkthrough.md`
7. `FINAL-DEMO-WALKTHROUGH.md`
8. `FINAL-HANDOVER-PACK.md`
9. `payload/REFERENCE.md`
10. `evidence/EVIDENCE-TEMPLATE.md`

Static verification proves this bundle is internally consistent. It does not
prove live kagent, A2A, specialist-agent, Grafana, GitLab, KB, or cluster
behavior.

## Live Prerequisite

Run `../runtime-model-gateway-readiness/` first. Do not start fanout proof until
the selected model backend is ready, Agent Gateway or direct A2A routing is
reachable, and a minimal A2A call completes. If the preflight blocks, return the
runtime-readiness evidence instead of burning tokens on specialist fanout.

## Required Markers

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
