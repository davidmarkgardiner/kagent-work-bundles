# Build and test the namespace-health job

This record captures the October 7 all-status publisher. The source now has
[selective Kafka admission](TRIAGE-PAYLOAD-AND-ADMISSION.md), which has passed
local behavior tests but has not been rebuilt into an image or exercised live.

The isolated home-lab trial uses `kind-namespace-health` (Kubernetes 1.35.0), Argo Events chart 2.4.24 / app 1.9.11, Argo Workflows chart 1.0.23 / app 4.0.8, and a single disposable Kafka 3.9.1 broker. The broker's PLAINTEXT NodePort exists only to let a separate Docker monitor consume trial status directly. Do not use this broker manifest or `LAB_PLAINTEXT` in a workplace environment. The assessor itself needs Kubernetes 1.32 or newer for the CronJob scheduled-timestamp annotation. The older Proxmox lab cluster was 1.31.14 and was not used for scheduled proof.

## Rebuild exactly

The Dockerfile pins the Python 3.12 Bookworm base by digest. `requirements.lock`
pins six packages and accepts only the recorded Linux arm64 and amd64 wheel
hashes. The repository ZIP excludes wheel binaries. On an approved connected
packaging host, prepare each required architecture from an approved package
index, then transfer the verified `wheelhouse/` directory and pinned base image
through the approved air-gap route. The script checks filenames and hashes
against `evidence/IMAGE-INVENTORY.json`; the Docker build itself makes no
package download. Keep generated wheels out of Git.

```bash
bash scripts-prepare-wheelhouse.sh arm64
bash scripts-prepare-wheelhouse.sh amd64
docker buildx build --platform linux/arm64 --provenance=false --sbom=false --load -t namespace-health:lab-arm64 .
docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load -t namespace-health:bank-amd64 .
docker run --rm --platform linux/amd64 namespace-health:bank-amd64 python -c 'import assess,collect,monitor,publish,receipt,confluent_kafka,requests; print("image imports OK")'
python3 -m unittest discover -s tests -q
```

The lab manifests use the arm64 tag loaded directly into kind. The work image must be published only to an approved registry under an immutable digest after its own admission checks. The locally saved amd64 tarball and its SHA-256 are recorded in `evidence/IMAGE-INVENTORY.json`; its local image ID is not a workplace registry digest.

## Recreate the isolated lab

Run these commands from this bundle directory. The disposable trial used a single-node kind cluster and these pinned chart versions; the namespace is created before Helm. Keep the Kafka/EventBus resources inside that trial namespace.

```bash
kind create cluster --name namespace-health --image kindest/node:v1.35.0
kubectl --context kind-namespace-health create namespace health-trial
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update argo
helm upgrade --install namespace-health-events argo/argo-events --version 2.4.24 --namespace health-trial --set controller.rbac.namespaced=true
helm upgrade --install namespace-health-workflows argo/argo-workflows --version 1.0.23 --namespace health-trial --set singleNamespace=true --set workflow.serviceAccount.create=true
```

This lab used kind's default node capacity for the functional canaries. The separate 100-Pod sizing fixture needed a temporary `maxPods: 150` kubelet setting on the disposable kind node, followed by a kubelet restart; this setting is specific to the sizing fixture and is not a workplace recommendation. The following commands are the exact manifest flow after Helm:

```bash
kind load docker-image --name namespace-health namespace-health:lab-arm64
kubectl --context kind-namespace-health apply -f manifests/lab-foundation.yaml
kubectl --context kind-namespace-health apply -f manifests/lab-fixtures.yaml
kubectl --context kind-namespace-health apply -f manifests/assessor-rbac.yaml
python3 scripts-render-lab.py kind-namespace-health /tmp/namespace-health-lab.yaml
kubectl --context kind-namespace-health apply --dry-run=server -f /tmp/namespace-health-lab.yaml
kubectl --context kind-namespace-health apply -f /tmp/namespace-health-lab.yaml
kubectl --context kind-namespace-health apply -f manifests/receiver.yaml
kubectl --context kind-namespace-health apply -f manifests/scheduled-receiver.yaml
kubectl --context kind-namespace-health apply -f manifests/receipt-cleanup.yaml
kubectl --context kind-namespace-health apply -f manifests/lab-topic-job.yaml
```

The separately hosted monitor in this trial was a Docker container on kind's Docker network, using its own Kafka consumer group and a bind-mounted state directory. The broker's advertised NodePort address is only reachable on that network. The test sink stores alert JSON lines outside Kubernetes. Start these before unsuspending the CronJob, substituting the first upcoming UTC hour for `{{FIRST_UTC_HOUR}}`:

```bash
docker run -d --name namespace-health-alert-sink --restart unless-stopped -p 8769:8769 -v "$PWD/tests/alert_sink.py:/app/alert_sink.py:ro" -v /tmp:/alerts python:3.12-slim-bookworm python /app/alert_sink.py /alerts/namespace-health-alerts.jsonl 8769
mkdir -p /tmp/namespace-health-scheduled-monitor-state
docker run -d --name namespace-health-scheduled-monitor --restart unless-stopped --network kind -v /tmp/namespace-health-scheduled-monitor-state:/state -e MONITOR_STATE_PATH=/state/monitor.json -e KAFKA_BOOTSTRAP_SERVERS=namespace-health-control-plane:30092 -e KAFKA_SECURITY_PROTOCOL=PLAINTEXT -e LAB_PLAINTEXT=true -e TRUSTED_CLUSTER=kind-namespace-health -e MONITOR_START_AT={{FIRST_UTC_HOUR}} -e KAFKA_MONITOR_GROUP=namespace-health-external-scheduled -e KAFKA_TOPIC=namespace-health-trial-v1 -e ALERT_WEBHOOK_URL=http://host.docker.internal:8769/alerts namespace-health:lab-arm64 python -m monitor
```

These commands are for the disposable local trial. The workplace monitor must use its approved external host, durable storage, TLS/SASL credentials, and alert destination.

`assessor.template.yaml` leaves the CronJob suspended. `scripts-render-lab.py` reads the selected cluster's `kube-system` namespace UID, embeds the public fixture policy, and refuses an unresolved placeholder. The source ServiceAccount has only the five fixture namespace reads, Pod logs and its own Job/Pod metadata; the receipt ServiceAccount can create/get ConfigMaps in the isolated receiver namespace. Argo's executor also needs `workflowtaskresults` create/patch, which the receiver Role grants. The cleanup account can list/delete ConfigMaps in that same isolated namespace; its code filters the exact owned labels and 72-hour age before deletion.

Generate a manual report-only job with `python3 scripts-make-canary.py /tmp/namespace-health-lab.yaml report-only > /tmp/health-report.yaml`, then `kubectl --context kind-namespace-health create -f /tmp/health-report.yaml`. Use `publish` instead of `report-only` to write the separate canary topic. A manual canary has an explicit slot and cannot write the scheduled topic. The regular CronJob uses the controller's timestamp annotation, checks its Job ownership, and refuses a manually instantiated Job on that route. Once the scheduled receiver and independent monitor are ready, unsuspend only this trial CronJob:

```bash
kubectl --context kind-namespace-health patch cronjob namespace-health-assessor -n health-trial --type merge -p '{"spec":{"suspend":false}}'
```

Read a report independently using `scripts-capture-topic.py` mounted into the same image. It validates the Kafka key and report before writing the exact JSON value to stdout; offset and SHA-256 metadata go to stderr. For the first scheduled hour in this trial:

```bash
docker run --rm --network kind -v "$PWD/scripts-capture-topic.py:/app/capture-topic.py:ro" -e KAFKA_BOOTSTRAP_SERVERS=namespace-health-control-plane:30092 -e KAFKA_SECURITY_PROTOCOL=PLAINTEXT -e LAB_PLAINTEXT=true -e TRUSTED_CLUSTER=kind-namespace-health namespace-health:lab-arm64 python /app/capture-topic.py namespace-health-trial-v1 {{FIRST_UTC_HOUR}} > /tmp/namespace-health-scheduled-value.json
```

The capture command is read-only and uses a separate disposable group. Keep any workplace capture in a private location because it contains a report from that environment.

## What was proved

The 17 assessor/monitor behavior tests cover availability state, log-only errors with ready pods, healthy info noise, Job/Event timestamp handling, stable unresolved owners, terminating pods, partial essential-API failure, report digests, top-three ranking, receipt duplicate/conflict behavior, rotation and monitor alerts. Two additional tests check the two-namespace workplace renderer's scope, suspended schedule and fail-closed inputs; all 19 tests pass. `evidence/LIVE-RECEIPTS.json` contains the exact measured outputs. On 100 running fixture pods, 20 sequential report-only runs had p95 2.804 seconds, at most 60 API calls, 18 sampled logs per run, and 36,084 KiB peak process RSS. The stable-inventory sample cycle was six hourly slots. The 60-call budget, rather than the 24-log ceiling, limits that scope to 18 log reads.

A Kafka consumer in a separate group validated the full JSON bytes and offsets. The canary topic carried an investigate report, a changed finding for the same slot, a quiet report, an unknown report and a five-namespace report that selected three and marked two omitted. The rebuilt final image produced a further five-namespace report at offset 5; Argo accepted its receipt. A deliberately forbidden Events list in one namespace also showed that a partial essential-API failure retains critical controller findings and marks required coverage failed; the Role was restored. Argo accepted a first receipt, suppressed a same-finding replay, and rejected the material conflict while retaining the first digest. The external Docker monitor consumed the Kafka topic directly and delivered coverage and conflict alerts to a test webhook. An accelerated backdated activation proved a missing-slot webhook; a deliberately unreachable bootstrap proved broker-unreachable alerting. Neither accelerated alarm substitutes for a real two-hour freshness soak.

The first real hourly occurrence was 13:00 UTC on 7 October. The CronJob-owned Job exposed the controller's exact scheduled-timestamp annotation, published Kafka offset 0, and produced an accepted Argo receipt. With 100 Pods and 130 Events in one namespace, a 100-item API page added a call and reduced the scheduled run to 16 log reads, seven-hour rotation and `required_failed=true`. The external monitor consumed that report and delivered a real coverage-gap webhook. Increasing the bounded page size to 200 removed this avoidable extra call while preserving the 60-call, 8 MiB and six-hour fail-closed limits. The corrected controller-created 13:03 run used 17 log reads, computed a six-hour rotation and had complete required coverage.

For a short integration drill, the same CronJob ran once per minute, then returned to `0 * * * *`. It produced six exact scheduled-topic values at offsets 0–5: four `investigate` values with accepted Argo receipts, and two `no_breach_observed` values with no Argo workflow. The 13:07 report selected a ready Deployment solely from 24 structured application error lines at tier 80. The external direct Kafka monitor recorded every slot. [SCHEDULED-RUNS.json](evidence/SCHEDULED-RUNS.json) has offsets, hashes, coverage and receipt mappings; [scheduled-kafka-values.jsonl](evidence/scheduled-kafka-values.jsonl) preserves the exact consumed JSON values. These accelerated occurrences do not count as three real hourly transitions.

The scheduled hourly soak remains distinct: check at least three actual hourly occurrences, their Kafka records, receiver receipts for investigate reports, and external monitor state. The unaccelerated two-hour missing-slot deadline also remains to be exercised. Existing urgent paging remains outside this trial. The lab's single broker is ephemeral; a broker restart can erase its local topic data, so its resilience is not evidence about workplace Kafka.

At 17:25 UTC, the independent monitor's persisted state contained valid Kafka status reports for the 13:00–17:00 hourly slots: the first was `investigate` and the following four were `no_breach_observed`. The real 13:00 report, Kafka offset and Argo receipt are recorded above. [HOURLY-SOAK-MONITOR.json](evidence/HOURLY-SOAK-MONITOR.json) records the later monitor state and its checksum. That follow-up session could not open the cluster API or Docker socket, so it did not independently replay the 14:00–17:00 broker values or inspect Argo for those hours. Treat the five-hour direct-consumer observation as strong freshness evidence, not as full receiver certification. The unaccelerated missing-slot alarm is still untested because none of those expected hourly slots was absent.

When lab runtime access is available, run `bash scripts-capture-hourly-lab.sh /private/path/empty-output-dir` from this bundle to replay exact Kafka values for all five hours and export current Workflow/CronJob and monitor state. The capture tool marks those old values `historical_replay=true`; replay validates their contract and presence, not their original timeliness. CronJob history retains only two successful Jobs, so a later replay cannot recover every old Job's controller annotation. Record that evidence limit explicitly rather than recreating Jobs as substitutes.

## Resource and safety boundaries

The assessor uses one sequential API reader, a 120-second process deadline, 8 MiB structured response cap, 60 API calls, at most 24 log reads / 3 MiB, and an 8 KiB report. It never sends raw log lines or Event messages. A missing required read yields `unknown` unless positive evidence already warrants `investigate`, in which case the coverage gap remains in the report. Each namespace takes its highest rule tier, with default admission at 80; the report selects at most three namespaces. This is sampled detection: for the tested 100-pod stable inventory, an otherwise healthy workload's log sample can be delayed up to six hours. Deleted pods and short incidents between runs can be missed.

No lossless outbox or cross-hour investigation cooldown is claimed. The initial Argo WorkflowTemplate only creates a receipt; it performs no model call, ticket write or remediation. NetworkPolicy enforcement was not verified in kind; the workplace deployment must use the controls supported by its CNI after testing actual API, DNS and Kafka paths.
