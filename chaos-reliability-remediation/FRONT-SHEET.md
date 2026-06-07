# Chaos Reliability Remediation Work-Agent Bundle

Purpose: prove SRE can request controlled lower-environment chaos, watch Kagent
triage the incident, gate any remediation, verify recovery, and produce a report.

## One-Line Ask

Run one approved low-risk chaos or regression test against a non-production
target, route it through Kagent triage, collect Grafana/cluster evidence, gate
remediation through HITL/GitOps, and return a scored report.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/chaos-reliability-request.yaml`
5. `prompts/01-run-controlled-chaos-demo.md`
6. `payload/REFERENCE.md`
7. `evidence/EVIDENCE-TEMPLATE.md`

## Required Markers

```text
CHAOS_REQUEST_ACCEPTED: yes
TARGET_NON_PROD: yes
CHAOS_INJECTED: yes
TRIAGE_STARTED: yes
GRAFANA_EVIDENCE_ATTACHED: yes
HITL_REQUIRED_FOR_REMEDIATION: yes
RECOVERY_VERIFIED: yes
LIFECYCLE_EVAL_RECORDED: yes
REPORT_CREATED: yes
OUTPUT_SANITIZED: yes
```

## Definition Of Done

- Chaos is limited to an approved non-production namespace and workload.
- Any remediation path is bound to `{{APPROVAL_CHANNEL}}` and requires HITL or
  GitOps review before non-read-only action.
- Recovery, Grafana evidence, lifecycle eval, and a sanitized report are
  returned before the exercise is considered complete.
