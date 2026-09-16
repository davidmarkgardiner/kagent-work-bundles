# Workplace test and promotion plan

## Gate 0: inventory and ownership

- Confirm the GitOps owner of Alloy, Argo Events, kagent, AKS-MCP and the worker
  namespaces.
- Record the installed Argo Events, Argo Workflows, kagent and AKS-MCP
  versions. Confirm the platform-managed controller/runtime images and the
  pods those controllers generate meet internal image and restricted-admission
  policy; they are dependencies, not images supplied by this bundle.
- List the actual Alloy Kubernetes-event and pod-log namespace selectors. They
  must produce the same ordered scope as `fox-mesh/namespaces.json`.
- Inventory every consumer of the existing incident topic. The new cluster
  health topic must have a unique consumer group and no ticket-writing
  consumer.
- Confirm the Kafka Secret has `bootstrap`, `key` and `secret` keys in
  `cluster-health-system` and `argo-events`, delivered by the approved secret
  mechanism rather than committed YAML.
- Select the SRE GitLab project and pre-create the three stable labels. Deliver
  a project-scoped issue token in `argo-events`; keep
  `GITLAB_WRITE_ENABLED=false` through the agent-only proof.

## Gate 1: images and static manifests

- Fox internal-fork tests prove state-only mode never constructs a publisher.
- Assessor/controller unit tests pass.
- Image scan and SBOM policy pass; all four runtime images are pinned by
  registry digest.
- `scripts/verify.py` passes.
- Server-side dry-run and negative RBAC tests pass with `verify-live.sh`.
- Post-apply readiness and state checks pass with `verify-running.sh`.
- Admission policy accepts restricted security contexts, resource bounds,
  projected token use and NetworkPolicies.
- Inspect effective EventSource, Sensor, Workflow and Agent pods after their
  controllers create them; capture image IDs, security contexts and denials.

## Gate 2: report-only canary

Start with a reviewed subset containing `kube-system` and the dedicated smoke
namespace. Keep the manager Sensor absent during this gate.

- Every Fox pod is Ready and updates only its named state ConfigMap.
- Broker address remains `127.0.0.1:1`; packet/flow evidence shows Fox makes no
  workplace Kafka connection.
- Three consecutive B1 snapshots complete within four minutes, remain below
  256 KiB and report honest partial/complete coverage.
- Compare Fox and native groups. Record mismatches by stable workload and
  symptom family; do not tune around a single sample.

## Gate 3: Kafka daily-record proof

Deploy the alert bridge with no Argo consumer initially.

- Vector healthcheck succeeds against the approved Kafka service.
- A synthetic contract message in a disposable test topic proves produced and
  consumed offsets, not merely buffer acceptance.
- During a 30-minute broker denial, B1 collection remains on schedule, Fox
  restart count stays zero and the bridge memory buffer remains bounded.
- On recovery, no historical per-finding burst occurs.
- Accelerate the UTC slot in a disposable overlay and prove many five-minute
  snapshots plus restarts produce one record for one date. Restore the real
  daily time before promotion.

## Gate 4: controlled fault and agent proof

With change approval, create one reversible failure in the dedicated smoke
namespace. Prefer one unschedulable Deployment or one unavailable replica set;
do not inject faults into shared system workloads.

Expected sequence:

1. Fox and/or native collection observes the symptom.
2. B1 groups replica/pod churn under one stable workload cause.
3. Critical breaches immediately; degraded breaches only on the second
   complete assessment.
4. At the configured daily slot, exactly one `cluster-health.alert.v1`
   `investigate` record is produced for the date. Its payload is under 64 KiB
   and contains no raw log/event text.
5. Exactly one Workflow is created. Rate limiting constrains admission and the
   deterministic `dispatch.workflow_name` makes Kafka/controller replay hit
   `AlreadyExists` instead of creating another Workflow.
6. The agent tool audit targets the supplied worker alias/context and only the
   supplied namespaces plus justified cluster-level checks.
7. The response starts with `## TL;DR`, groups symptoms under root causes and
   performs no mutation or direct ticket write.
8. Remove the fault. After deterministic recovery, the next daily record is
   `healthy` and creates no investigation Workflow.

Repeat with Kafka unavailable, AKS-MCP unavailable, stale snapshots, invalid
cluster targets and malformed alert payloads. Each must fail closed without
broadening cluster access.

## Gate 5: single GitLab summary

Use a disposable SRE test project with the stable labels, then set
`GITLAB_WRITE_ENABLED=true`.

- First unhealthy daily Workflow creates exactly one labelled issue.
- Kafka replay and Workflow replay create no second Workflow or issue.
- The next unhealthy daily Workflow updates that issue's title/managed body;
  it does not overwrite comments.
- Two pre-existing matching issues, paginated identity search, missing labels,
  token denial, API timeout and ambiguous create all fail closed without a
  second create attempt in that run.
- The Agent pod has no GitLab Secret; only the fixed writer step receives it.
- A healthy daily record performs no GitLab call. Issues are not automatically
  closed.

## Gate 6: full scope and soak

- Expand to the exact Alloy namespace scope and verify all collectors Ready.
- Run through at least five working days plus a weekend.
- Measure API calls, Fox/B1 CPU and memory, snapshot time, false-positive rate,
  daily records, agent calls, issue creates/updates, Kafka errors and operator
  value.
- Promotion requires SRE sign-off on thresholds and explicit evidence that one
  underlying failure produces one summary rather than workload-level fan-out.

Only after this soak should the team consider reducing the individual
Alloy/Vector incident lane. Keep it available during calibration; gathering
logs/events for targeted evidence is different from using every line as a
trigger.
