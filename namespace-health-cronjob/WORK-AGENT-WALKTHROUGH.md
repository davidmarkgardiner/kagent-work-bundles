# Work agent walkthrough: selective two-namespace pilot

Use this runbook in the workplace environment. The requested outcome is an
hourly Python assessor watching **exactly two approved test namespaces**. It
reads Kubernetes state, Events, and bounded application-log samples. It sends
only threshold-qualified `namespace-health.report.v1` JSON to an isolated Kafka
topic. Argo Events accepts that JSON into a receipt-only Workflow. Do not
connect an agent, create a ticket, or enable remediation in this pilot.

The October 7 image and live receipts use the older all-status publisher. Build
a **new image from the current source** and establish new workplace receipts.
The public bundle has no workplace credentials, endpoints, or namespace names.
Keep filled config, rendered YAML, secrets, and evidence outside this repo.

## 1. Establish the real target and scope

Record, in private evidence, the source and receiver kube contexts, Kubernetes
and Argo versions, EventBus, approved source cluster ID, and the `kube-system`
namespace UID. Confirm the source cluster provides
`batch.kubernetes.io/cronjob-scheduled-timestamp` on a real CronJob-owned Job;
the assessor rejects a scheduled Job without it. Source and receiver may be
different clusters. Use an explicit `--context` for every `kubectl` command.

Obtain the two approved namespace names, the application containers to inspect,
excluded sidecars, and critical controller references such as
`Deployment/example-app`. Check real application logs for timestamped JSON and
the severity field the parser recognizes. Verify read access to Pods, logs,
Events, and controllers in those namespaces. Check source-to-API and
source-to-Kafka network paths, plus receiver-to-Kafka and Argo EventBus paths.
Stop if the real app log format does not match the collector's parser; do not
infer coverage from a healthy-looking report.

Confirm the existing broker's TLS/SASL mode, CA, advertised listeners, two
**distinct** pilot topics (canary and scheduled), and least-privilege source,
receiver, and independent-consumer ACLs. Confirm approved Secret management.
Neither topic should be the current production triage topic. Preserve existing
Alloy/Vector, paging, and Argo routes throughout the pilot.

## 2. Rebuild and validate the current source

On the approved Linux amd64 builder, run the offline behavior tests and build
the Dockerfile from this bundle. Push through the workplace's approved image
process and record the immutable `registry@sha256:...` reference, source hash,
scan/admission result, and architecture. Do not reuse the October 7 staging
archive: it predates quiet suppression. The receiver uses the **same image**
for `/app/receipt.py`.

The repository ZIP does not include Python wheels. Before the offline image
build, obtain the pinned amd64 wheels on an approved packaging host with
`bash scripts-prepare-wheelhouse.sh amd64`, or import those exact wheels through
the approved artifact route. The script verifies filenames and SHA-256 values
against `evidence/IMAGE-INVENTORY.json`. Transfer `wheelhouse/amd64/` into this
bundle's build context and keep the pinned base image available internally.
Do not make the disconnected builder fetch packages.

```bash
cd work-agent-bundles/namespace-health-cronjob
python3 -m unittest discover -s tests -p 'test_*.py'
```

If using the handoff ZIP instead of a worktree, extract it privately and
`cd namespace-health-cronjob` before running these commands.

The current test set includes a producer-path check for qualifying, quiet,
and unknown assessments. Passing these tests is local evidence; verify the
new image and actual broker path separately.

## 3. Fill and render private configuration

Copy `manifests/workplace/pilot-two-namespaces.config.template.json` to a
private location **outside** this public repository. Fill every placeholder:
the two namespace names, application containers, critical workloads, cluster
identity, new image digest, Kafka endpoints/topics, SASL mechanism, Secret
**names**, source/receiver namespaces, EventBus, and receiver group. Put actual
credentials and CA material in approved Kubernetes Secrets, not this JSON.
Review the generated policy's threshold (default 80), required application
containers, sidecar exclusions, and six-hour log-rotation ceiling.

Use a new, empty private output directory:

```bash
python3 scripts-render-workplace-pilot.py \
  /private/path/pilot-config.json \
  /private/path/empty-pilot-output
```

The renderer writes `source.yaml` (11 objects), `receiver.yaml` (13 objects),
and `canary-receiver.yaml` (two isolated Argo objects). Inspect the rendered
policy, namespace-scoped Roles, CronJob image and `suspend: true`, topic names,
EventSources, Sensors, WorkflowTemplate, and Secret references. The canary
EventSource has its own consumer group and listens only to the canary topic.

## 4. Validate against the actual clusters

Set these shell variables privately to the values selected above, then run
server dry-runs against the explicit contexts:

```bash
kubectl --context "$SOURCE_CONTEXT" apply --dry-run=server -f "$PRIVATE_OUTPUT/source.yaml"
kubectl --context "$RECEIVER_CONTEXT" apply --dry-run=server -f "$PRIVATE_OUTPUT/receiver.yaml"
kubectl --context "$RECEIVER_CONTEXT" apply --dry-run=server -f "$PRIVATE_OUTPUT/canary-receiver.yaml"
```

Check that the installed CRDs accept the Kafka EventSource, Sensor filters,
WorkflowTemplate and Workflow RBAC. A local YAML parse is insufficient.
Resolve any schema, policy, Secret, ACL, or CNI failure before applying.

## 5. Apply the isolated route while the assessor is suspended

Provision the isolated topics, scoped ACLs, Secrets, and independent
CronJob/Job monitor through approved workplace processes. The monitor must
detect failed Jobs and a missed scheduled Job without treating an empty Kafka
hour as a failure. Demonstrate its alert destination. The old direct-Kafka
missing-slot monitor is incompatible with selective publication.

Apply only the reviewed manifests to their matching contexts:

```bash
kubectl --context "$SOURCE_CONTEXT" apply -f "$PRIVATE_OUTPUT/source.yaml"
kubectl --context "$RECEIVER_CONTEXT" apply -f "$PRIVATE_OUTPUT/receiver.yaml"
kubectl --context "$RECEIVER_CONTEXT" apply -f "$PRIVATE_OUTPUT/canary-receiver.yaml"
```

Verify `namespace-health-assessor` remains suspended. Verify the two
EventSources and Sensors are healthy before publishing. Record the exact
object inventory and initial Kafka offsets in private evidence.

## 6. Exercise manual canaries

First create a `report-only` Job from the rendered source, using the helper
below. It reads the two test namespaces but does not publish. Capture its
structured report and check `coverage.required_failed`, the selected
namespaces, rule IDs, and measured log sampling. Resolve coverage failures
before treating an empty finding set as a quiet result.

```bash
python3 scripts-make-canary.py "$PRIVATE_OUTPUT/source.yaml" report-only > "$PRIVATE_OUTPUT/report-only-job.yaml"
kubectl --context "$SOURCE_CONTEXT" create -f "$PRIVATE_OUTPUT/report-only-job.yaml" -o name
```

For a positive canary, use an approved, reversible fault in a test workload.
Confirm a fresh `report-only` result has `status: investigate` and a selected
namespace at or above the configured threshold. Generate a **fresh** publish
Job immediately before creation:

```bash
python3 scripts-make-canary.py "$PRIVATE_OUTPUT/source.yaml" publish > "$PRIVATE_OUTPUT/qualifying-canary-job.yaml"
kubectl --context "$SOURCE_CONTEXT" create -f "$PRIVATE_OUTPUT/qualifying-canary-job.yaml" -o name
```

The helper reads the assessor namespace and canary topic from the rendered
source. It assigns a non-hourly UTC slot so the canary receipt cannot claim a
real CronJob hour. Consume the exact Kafka key and JSON value from an
**independent** group on the canary topic. Check key equals `slot_id`, schema,
cluster, source generation, `status: investigate`, selected namespace/rule,
`automation_allowed: false`, full payload digest, value size at most 8 KiB,
partition and offset. Confirm the canary Argo Workflow succeeded and its
receipt ConfigMap holds the same `slot_id` and finding digest. Kafka delivery
alone is not an Argo receipt. Use a new canary minute for a materially changed
positive finding; the receipt intentionally treats two different findings for
the same slot as a conflict.

After the test fault is cleared and its evidence window has passed, use a
fresh `report-only` Job to establish `no_breach_observed`. Then run a new
publish-mode canary and show the Job succeeds with `outcome: not_published`,
**no new canary-topic record** across a bounded observation interval with a
healthy independent consumer, and **no new receipt Workflow**. Record the
topic offsets before and after. For an unknown
case, use an approved temporary read-permission fault in the isolated scope
while no positive finding exists; show `coverage.required_failed: true`, a
failed Job, no Kafka record, and a monitoring alert. Restore the permission
and repeat `report-only`. Do not describe silence alone as proof of health.

## 7. Enable and observe the real hourly route

After the canaries, independent monitoring, and rollback path pass, unsuspend
only the pilot CronJob through the workplace's reviewed delivery method. Its
schedule is `0 * * * *` UTC, assessing the preceding hour. Capture **three real
hourly CronJob-owned Jobs** with controller scheduled-timestamp annotations.
For each Job record assessment status, coverage, runtime, and whether Kafka
publication was expected. Match each qualifying Job to an exact scheduled-topic
record and receipt Workflow. For each quiet Job, verify successful completion
and no scheduled-topic record for its slot. For each unknown Job, verify failure
and the independent alert. Temporarily deny only the pilot producer's write
ACL to exercise a delivery failure; verify the Job failure is visible, then
restore the pilot ACL before proceeding. Do not disrupt the shared broker.

Keep the existing alert route active during this pilot. Do not route reports to
an agent or grant remediation permissions. The current Event summary contains
only a warning count and generic reference, so it is not yet a complete
diagnostic payload for an agent. See `TRIAGE-PAYLOAD-AND-ADMISSION.md`.

## 8. Evidence and rollback

Return a private evidence pack containing the target contexts, approved two
namespaces, object inventory, source/image digests, version/CRD results,
server dry-runs, policy/Secret **names**, topic/group identities, exact offsets
and value hashes, Job logs/statuses, Workflow names/phases, receipt slot IDs,
monitor alerts, measured coverage/runtime, and rollback outcome. Redact
credentials, internal endpoints, and raw application logs from any material
copied back to the public repo. Separate lab, canary, and real hourly proof.

If a stage fails, suspend the pilot CronJob first, inspect any already active
Jobs, then reverse only the pilot objects from the recorded inventory. Retain
evidence and verify the existing routes remain healthy. Follow `ROLLBACK.md`
for the detailed reversal order. Report the exact failed gate; do not call a
render, dry-run, or broker acknowledgement workplace end-to-end proof.
