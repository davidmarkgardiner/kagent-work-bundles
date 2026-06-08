# Chaos To Evaluation Flow

## Purpose

This file defines the phase-1 proof loop for the work agent:

```text
chaos action -> event observed -> Kagent triage -> lifecycle evaluation -> GitLab evidence
```

Grafana alerts can be added later, but they are not required to prove this
phase. The preferred phase-1 trigger is Argo Events, Litmus `ChaosResult`, a
Kubernetes event watcher, or an Argo workflow watch.

## Required Inputs

Resolve these from `../SHARED-VARIABLES.md` before live testing:

- `{{KUBE_CONTEXT}}`
- `{{KAGENT_NAMESPACE}}`
- `{{ARGO_NAMESPACE}}`
- `{{ARGO_EVENTS_NAMESPACE}}`
- `{{GITLAB_PROJECT}}`
- `{{TARGET_BRANCH}}`
- `{{GITLAB_MCP_REMOTE_SERVER_NAME}}` or the approved GitLab API wrapper
- `{{GITLAB_MR_URL}}` or `{{GITLAB_ISSUE_URL}}`
- `{{APPROVAL_CHANNEL}}`
- `{{DEMO_TARGET_NAMESPACE}}`
- `{{DEMO_TARGET_WORKLOAD}}`
- `{{RUN_ID}}`

## Event Contract

The event sent to triage should carry these fields, even if some values are
dry-run placeholders:

```yaml
run_id: "{{RUN_ID}}"
source: "lifecycle-evaluation-review-manager/examples/chaos"
event_type: "chaos_pod_delete"
target_namespace: "{{DEMO_TARGET_NAMESPACE}}"
target_workload: "{{DEMO_TARGET_WORKLOAD}}"
chaos_experiment_id: "{{CHAOS_EXPERIMENT_ID}}"
event_uid: "{{KUBERNETES_EVENT_UID}}"
observed_by: "argo-events-or-workflow-watch"
triage_agent: "{{KAGENT_TRIAGE_AGENT_NAME}}"
gitlab_project: "{{GITLAB_PROJECT}}"
gitlab_target: "{{GITLAB_MR_URL_OR_ISSUE_URL}}"
```

## Proof Steps

1. Produce the chaos action or approved dry-run using the chaos reliability
   bundle examples.
2. Observe the event with one of:
   - Litmus `ChaosResult` EventSource
   - Kubernetes event watcher
   - Argo workflow watch
3. Send the observed event payload to the Kagent triage front door or workflow.
4. Capture the triage run output and trace fields.
5. Score the run using `chaos-pod-delete` lifecycle evaluation.
6. Route weak or failed runs to review-manager.
7. Update GitLab with the event, triage summary, evaluation result, evidence,
   and next action.

## Definition Of Done

```text
WORK_VARIABLES_RESOLVED: yes
CHAOS_EVENT_FLOW_MAPPED: yes
ARGO_EVENTSOURCE_OR_WATCH_PROVEN: yes_or_blocked
CHAOS_TO_TRIAGE_TO_EVAL_FLOW: proven_or_blocked
GITLAB_EVIDENCE_UPDATED: yes_or_blocked
GRAFANA_ALERT_TRIGGER: not_required_for_phase_1
OUTPUT_SANITIZED: yes
```

If the live cluster cannot inject chaos, record `blocked` with the exact RBAC,
namespace, CRD, image, or approval blocker. Do not mark the flow complete from
sample scoring alone.
