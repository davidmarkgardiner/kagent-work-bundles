# Implementation And Verification Plan

## Phase 0: Work Environment Variables

Read `../SHARED-VARIABLES.md` before running live checks. Resolve only the
values needed for this bundle and keep private values out of committed
artifacts.

Required for phase-1 proof:

- `{{KUBE_CONTEXT}}`
- `{{KAGENT_NAMESPACE}}`
- `{{ARGO_NAMESPACE}}`
- `{{ARGO_EVENTS_NAMESPACE}}`
- `{{GITLAB_PROJECT}}`
- `{{TARGET_BRANCH}}`
- `{{GITLAB_MCP_REMOTE_SERVER_NAME}}` or approved GitLab API wrapper
- `{{GITLAB_MR_URL}}` or `{{GITLAB_ISSUE_URL}}`
- `{{APPROVAL_CHANNEL}}`
- `{{DEMO_TARGET_NAMESPACE}}`
- `{{DEMO_TARGET_WORKLOAD}}`
- `{{PASSING_LIFECYCLE_CASE}}`
- `{{FAILING_LIFECYCLE_CASE}}`
- `{{RUN_ID}}`

Optional for this phase:

- `{{GRAFANA_MCP_REMOTE_SERVER_NAME}}`
- `{{GRAFANA_DASHBOARD_URL_OR_UID}}`

Evidence:

```text
WORK_VARIABLES_RESOLVED: yes
```

## Phase 1: Design Review

Read and summarize:

- `MEETING-ACTION-COVERAGE.md`
- `ARCHITECTURE-DECISION.md`
- `DATA-STORAGE-ACCESS-TRACEABILITY.md`
- `payload/REFERENCE.md`

Output:

```text
EVALUATION_FRAMEWORK_DESIGN: covered
OFFLINE_ONLINE_DESIGN: covered
KEY_METRICS_IDENTIFIED: covered
INLINE_VS_SEPARATE_ARCHITECTURE: covered
DATA_STORAGE_ACCESS_MODEL: covered
AUDIT_RETENTION_TRACEABILITY: covered
```

## Phase 2: Build Or Verify Offline Eval

Verify:

- golden cases exist
- passing lifecycle run scores above threshold
- failing lifecycle run scores below threshold or fails hard gate
- deterministic scorer exits non-zero on failed lifecycle

Evidence:

```text
PASSING_RUN_SCORED: yes
BELOW_THRESHOLD_RUN_SCORED: yes
HARD_FAILURES_ENFORCED: yes
```

## Phase 3: Build Or Verify Online Eval

Verify:

- `agent-lifecycle-eval` template can be installed/rendered
- runtime uses public image and ConfigMap-mounted scripts
- workflow passes `workflow_json` and `marker_evidence`
- ticket close or review route happens after evaluation, not before
- `templateRef` callers receive the evaluator ConfigMap volume from the reusable template
- passing and negative online hooks are both server-side validated
- the negative online hook fails evaluation and still emits a review-route stub

Evidence:

```text
ONLINE_EVALUATOR_RENDERED:
RUNTIME_IMAGE:
CONFIGMAP_RUNTIME:
ONLINE_HOOK_SUCCEEDED:
ONLINE_NEGATIVE_HOOK_FAILED:
REVIEW_ROUTE_PAYLOAD_CREATED:
TICKET_CLOSE_GATED:
```

## Phase 4: Metrics And Access

Verify:

- metrics render through `scripts/metrics.py`
- metric labels are low-cardinality
- no raw evidence is used as a label
- dashboard/alert rules consume the documented metric families

Evidence:

```text
KEY_METRICS_IDENTIFIED: covered
METRICS_EXPORTED: yes_or_blocked
METRIC_LABEL_POLICY: enforced_or_gap
```

## Phase 5: Storage, Retention, Traceability

Define for the work environment:

- where raw evidence is stored
- where sanitized lifecycle JSON is stored
- where eval results are stored
- where Markdown summary is attached
- where metrics are published
- who can read each class of data
- retention window for each class
- traceability IDs used in tickets and reports

Evidence:

```text
DATA_STORAGE_ACCESS_MODEL: covered
AUDIT_RETENTION_TRACEABILITY: covered
```

## Phase 6: Review Manager Route

For the failing run:

- keep ticket open or create review ticket
- attach hard failures and missing evidence
- include owner and next action

Evidence:

```text
REVIEW_MANAGER_ROUTED: yes
```

## Phase 7: Chaos Event To Eval And GitLab Evidence

Use the local chaos examples in this bundle as the upstream producer. If the
separate chaos reliability bundle is also available, it can be used as broader
background, but it is not required for this phase-1 proof.

- `examples/chaos/chaos-test-pod-delete.yaml`
- `examples/chaos/litmus-chaosengine-pod-delete.yaml`
- `examples/chaos/argo-workflow-dry-run.yaml`
- `examples/chaos/a2a-chaos-request-payload.json`

Use one approved event observation path:

- Litmus `ChaosResult` event via `chaos/litmus/manifests/eventsource-litmus.yaml`
- Kubernetes event watcher in an Argo workflow
- Argo workflow watch on the chaos lifecycle workflow

Verify:

- the chaos event is injected or an approved dry-run blocker is captured
- Argo Events or the watcher observes the event
- Kagent triage starts with the event payload
- lifecycle eval scores the resulting run with the `chaos-pod-delete` case
- failures or weak runs route to review-manager
- GitLab issue, MR, comment, or report is updated with the event, triage,
  evaluation, and next action

Grafana alert triggering is not required for phase 1. If dashboards or alerts
are available, attach them as extra evidence only.

Evidence:

```text
CHAOS_EVENT_FLOW_MAPPED: yes
ARGO_EVENTSOURCE_OR_WATCH_PROVEN: yes_or_blocked
CHAOS_TO_TRIAGE_TO_EVAL_FLOW: proven_or_blocked
GITLAB_EVIDENCE_UPDATED: yes_or_blocked
GRAFANA_ALERT_TRIGGER: not_required_for_phase_1
```

## Completion Criteria

- The six planning-meeting actions are explicitly covered.
- A passing eval and failing eval are both demonstrated.
- The failing case cannot be silently treated as success.
- A chaos-tested action is traced from event observation through triage,
  evaluation, and GitLab evidence, or an exact blocker is documented.
- Metrics are generated through the independent library.
- Access control and retention are documented.
- The safe online hook runs in Argo or the blocker is captured with logs.
- Output is sanitized.
