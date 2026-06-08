# Prompt: Prove Chaos Event To Eval To GitLab

```text
You are the work-environment verifier for the Kagent triage V2 lifecycle loop.

Do not start by scoring sample files only. First resolve the work variables from
../SHARED-VARIABLES.md and confirm the private values outside the public repo.

Required variable map:
- {{KUBE_CONTEXT}}
- {{KAGENT_NAMESPACE}}
- {{ARGO_NAMESPACE}}
- {{ARGO_EVENTS_NAMESPACE}}
- {{GITLAB_PROJECT}}
- {{TARGET_BRANCH}}
- {{GITLAB_MCP_REMOTE_SERVER_NAME}} or approved GitLab API wrapper
- {{GITLAB_MR_URL}} or {{GITLAB_ISSUE_URL}}
- {{APPROVAL_CHANNEL}}
- {{DEMO_TARGET_NAMESPACE}}
- {{DEMO_TARGET_WORKLOAD}}
- {{RUN_ID}}

Goal:
Prove, or explicitly block, the phase-1 flow:

chaos action -> event observed -> Kagent triage -> lifecycle evaluation -> GitLab evidence

Phase-1 trigger rule:
Grafana alert triggering is not required. Use Argo Events, a Litmus
ChaosResult EventSource, a Kubernetes event watcher, or an Argo workflow watch.
If Grafana is not used, report:

GRAFANA_ALERT_TRIGGER: not_required_for_phase_1

Steps:
1. Read:
   - FRONT-SHEET.md
   - CHAOS-TO-EVAL-FLOW.md
   - IMPLEMENTATION-VERIFY-PLAN.md
   - requests/lifecycle-evaluation-request.yaml
   - payload/REFERENCE.md
   - evidence/EVIDENCE-TEMPLATE.md
2. Run:
   bash scripts/verify-bundle.sh
3. Use the chaos reliability bundle examples or the installed work equivalents
   to create a pod-delete chaos action against the approved demo namespace and
   workload. If live chaos is not approved, use the dry-run Argo workflow and
   record the approval blocker.
4. Show the exact event observation path:
   - EventSource name, Sensor name, watcher workflow, or watch command
   - event UID or workflow ID
   - payload sent to triage
5. Show the Kagent triage action:
   - agent name
   - input payload
   - run ID or workflow ID
   - remediation recommendation/action
6. Score the resulting lifecycle run with the `chaos-pod-delete` eval case.
   Include the command, score, pass/fail, hard failures, and result artifact.
7. If the run is weak or failed, create or show the review-manager route.
8. Use the GitLab MCP or approved GitLab API wrapper to update an issue, MR,
   comment, or report with:
   - chaos event
   - triage summary
   - lifecycle eval result
   - evidence links
   - next action/owner
9. Return evidence in the shape of evidence/EVIDENCE-TEMPLATE.md.

Required final markers:

WORK_VARIABLES_RESOLVED: yes
EVAL_CASES_LOADED: yes
PASSING_RUN_SCORED: yes
BELOW_THRESHOLD_RUN_SCORED: yes
HARD_FAILURES_ENFORCED: yes
REVIEW_MANAGER_ROUTED: yes
CHAOS_EVENT_FLOW_MAPPED: yes
ARGO_EVENTSOURCE_OR_WATCH_PROVEN: yes_or_blocked
CHAOS_TO_TRIAGE_TO_EVAL_FLOW: proven_or_blocked
GITLAB_EVIDENCE_UPDATED: yes_or_blocked
GRAFANA_ALERT_TRIGGER: not_required_for_phase_1
OUTPUT_SANITIZED: yes

Do not report complete if the only thing proven is local sample scoring. Use
`blocked` for any missing RBAC, CRD, namespace, MCP tool, GitLab permission, or
chaos approval, and include the exact command/error that proves the blocker.
```
