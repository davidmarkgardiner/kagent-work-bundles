# Implementation And Verification Plan

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

Evidence:

```text
ONLINE_EVALUATOR_RENDERED:
RUNTIME_IMAGE:
CONFIGMAP_RUNTIME:
ONLINE_HOOK_SUCCEEDED:
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

## Completion Criteria

- The six Microsoft meeting actions are explicitly covered.
- A passing eval and failing eval are both demonstrated.
- The failing case cannot be silently treated as success.
- Metrics are generated through the independent library.
- Access control and retention are documented.
- The safe online hook runs in Argo or the blocker is captured with logs.
- Output is sanitized.
