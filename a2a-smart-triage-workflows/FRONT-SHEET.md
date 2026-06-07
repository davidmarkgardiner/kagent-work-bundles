# A2A Smart Triage Workflows Work-Agent Bundle

Purpose: prove that Kagent agents can collaborate through A2A, call specialist
skills, preserve context, and return one synthesized incident answer.

## One-Line Ask

Replay or trigger one incident, fan out to specialist agents, collect their
findings, and produce a single commander synthesis with citations, evidence,
and remediation safety state.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/a2a-smart-triage-request.yaml`
5. `prompts/01-prove-a2a-fanout.md`
6. `payload/REFERENCE.md`
7. `evidence/EVIDENCE-TEMPLATE.md`

Static verification proves this bundle is internally consistent. It does not
prove live kagent, A2A, specialist-agent, Grafana, GitLab, KB, or cluster
behavior.

## Required Markers

```text
A2A_BASELINE_COMPLETED: yes
SPECIALIST_FANOUT_STARTED: yes
KUBERNETES_SPECIALIST_COMPLETED: yes
GRAFANA_SPECIALIST_COMPLETED: yes
KNOWLEDGE_SPECIALIST_COMPLETED: yes
GITOPS_SPECIALIST_COMPLETED: yes
CONTEXT_PRESERVED: yes
SYNTHESIS_CREATED: yes
OUTPUT_SANITIZED: yes
```
