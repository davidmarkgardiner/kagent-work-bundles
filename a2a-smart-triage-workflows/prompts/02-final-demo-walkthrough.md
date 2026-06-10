# Prompt: Final Demo Walkthrough

```text
You are the final-demo verifier for Kagent triage V2.

Today is a handover/demo day. Do not start new implementation unless a very
small fix is required to unblock proof. Your job is to prove and document what
already works.

Start:
1. Run `bash scripts/verify-bundle.sh`.
2. Read FINAL-DEMO-WALKTHROUGH.md, WORK-AGENT-START-PROMPT.md, CHECKLIST.md,
   FINAL-HANDOVER-PACK.md, requests/a2a-smart-triage-request.yaml,
   payload/REFERENCE.md, and evidence/EVIDENCE-TEMPLATE.md.
3. Use the latest runtime readiness evidence or run the runtime preflight.

Prove one end-to-end demo:
- baseline A2A call completes
- incident or controlled fault replay starts fanout
- Kubernetes/AKS specialist returns evidence
- Grafana MCP returns metric/log/dashboard evidence
- querydoc/vector KB returns a cited answer
- GitLab MCP creates or updates issue/MR/comment/report evidence
- memory context is seeded/recalled if available
- HITL/GitOps boundary is shown for any write/remediation action
- chaos/eval loop is shown if available, or blocked with exact reason
- commander returns one synthesis with context and safety state
- final evidence is captured in GitLab or a report artifact
- final front sheet is created
- GitLab tickets are created or copy-ready ticket bodies are returned
- evidence index links to the proof artifacts

Return:
- exact commands or UI actions
- payloads with secrets redacted
- run IDs, workflow IDs, task IDs, GitLab URLs, dashboard URLs
- blocker list with owner and next action
- final demo report text
- front sheet text or GitLab link
- ticket list with GitLab links or copy-ready issue text
- evidence index with links

Required markers:

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
