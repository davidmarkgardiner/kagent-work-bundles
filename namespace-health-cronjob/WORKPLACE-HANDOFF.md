# Workplace transfer: reviewed source, fresh local wiring

Use the same `src/`, `report.schema.json`, locked wheel inventory, tests and receipt semantics. The home-lab result proves behavior in a fixture cluster. It does not prove the workplace namespace inventory, broker ACLs, EventBus placement, monitor delivery or real application log formats.

The source now has [selective Kafka admission](TRIAGE-PAYLOAD-AND-ADMISSION.md). The October 7 image and live evidence predate it; rebuild and revalidate the image before workplace use. The former Kafka missing-slot monitor is incompatible with a topic that intentionally omits quiet hours.

## Two-namespace workplace pilot

Use [the private-config skeleton](manifests/workplace/pilot-two-namespaces.config.template.json), [the two-namespace policy](manifests/workplace/pilot-two-namespaces.policy.template.json), [the scoped source template](manifests/workplace/pilot-two-namespaces.source.template.yaml) and the existing [receiver template](manifests/workplace/receiver.template.yaml). Fill the config with **two approved namespace names**, their application-container names and critical controller identities (`Deployment/name`, `StatefulSet/name` or `DaemonSet/name`). The remaining fields name the approved image by immutable digest, cluster identity, separate Kafka topics and Secret references, broker, Argo EventBus and receiver group. Put the filled config outside this public repo; it contains references, not Kafka passwords or TLS key material.

Render with `python3 scripts-render-workplace-pilot.py /private/path/pilot-config.json /private/path/empty-output-dir`. The renderer refuses an image tag without a digest, duplicate watched namespaces, a shared canary/scheduled topic, unresolved placeholders, a nonempty output directory or paths inside this repo. It emits 11 source, 13 scheduled receiver and two canary receiver objects. The source has read roles only in the two watched namespaces, and the CronJob starts **suspended**. The canary EventSource uses the separate canary topic and consumer group. A synthetic two-namespace render passed local YAML and scope checks; server dry-run against the actual workplace CRDs is still required. Follow [the work-agent walkthrough](WORK-AGENT-WALKTHROUGH.md) for the complete sequence.

Keep the proven cadence for this pilot: `0 * * * *` in UTC with a one-hour lookback. The job reads recent Events and timestamped, bounded Pod-log samples, applies deterministic rules, and publishes one compact report only for qualifying findings. A five-minute lookback with an hourly CronJob would leave 55 minutes unchecked. A five-minute cadence would change report volume, slot freshness, replay and deduplication behavior and must be reviewed and tested as a separate variant.

Before unsuspending, provision the two Kafka topics and scoped producer/consumer ACLs, source and receiver Secrets, a newly approved image digest, independent CronJob/Job monitoring, and isolated Argo receivers. Apply the source suspended, run a report-only Job, then publish a qualifying manual canary to its own topic and observe the exact broker value and canary Argo receipt. Prove a quiet canary produces no Kafka record and an unknown-coverage run fails its Job without publishing. Only then enable the hourly topic and watch three real scheduled occurrences plus a demonstrated missed-schedule alarm. Keep the existing workplace observability route intact throughout the pilot.

## Required workplace inputs

| Input | Verify before rendering |
|---|---|
| Source cluster | Kubernetes 1.32+; `batch.kubernetes.io/cronjob-scheduled-timestamp` on an actual CronJob Job; stable cluster name and the protected `kube-system` UID. |
| Scope and policy | Up to five approved namespaces, critical controller allowlist, application-container names, sidecar exclusions, structured JSON error fields, threshold and maximum acceptable rotation hours. Application teams approve any free-text matcher before adding it. |
| Image | Approved Python base and six locked wheels, built for Linux amd64, scanned, pushed to approved registry, referenced by immutable digest. The local amd64 tar is a staging artifact, not a deployable workplace image reference. |
| Kafka | Existing broker endpoints, advertised listeners, TLS CA, SASL credentials, create/write/read ACLs, separate canary/scheduled topics and consumer groups. Producer uses `acks=all`, idempotence and observed delivery callbacks. |
| Argo | Installed Events/Workflows versions, EventBus and controller namespace scopes, receiver service accounts and workflow executor's `workflowtaskresults` RBAC. Deploy a new EventSource and Sensor for `namespace-health.report.v1`; never reuse the old pod-incident Sensor. |
| Operational monitor | A monitor independent of the selective Kafka topic must verify CronJob schedule/Job completion, failed Jobs, and unknown coverage from logs or metrics. Demonstrate a missed schedule and required-coverage failure. A direct Kafka consumer may inspect qualifying records and broker reachability, but must not use absence of a record as a missing-slot alarm. |
| Egress | Verified CNI-specific restrictions for API, DNS and Kafka. Kafka publisher credentials stay out of the receipt workflow. |

Before any workplace mutation, fill the placeholders in the source/receiver templates under `manifests/workplace/`, render them to a private location, inspect the result, and run `kubectl apply --dry-run=server` against the actual target clusters. The public bundle intentionally contains no workplace values or secrets. Start with a suspended CronJob and an isolated canary topic; require a full produced/consumed report and Argo receipt before enabling the scheduled route. Keep the old routine route unchanged during the canary. Do not claim operational readiness until the real hourly soak and external alarms pass on the actual infrastructure.

The handoff maps evidence boundaries:

- `evidence/iteration1-live.json`: early trial including an Argo executor RBAC failure and a terminating-pod false positive; both were corrected.
- `evidence/LIVE-RECEIPTS.json`: final isolated canary, top-three, benchmark, alert and runtime receipts.
- `evidence/SCHEDULED-RUNS.json`: first real hourly run and separately labeled accelerated controller-created transitions, with exact Kafka values in `scheduled-kafka-values.jsonl`.
- `evidence/HOURLY-SOAK-MONITOR.json`: independent direct-Kafka consumer's persisted 13:00–17:00 hourly status state; later exact broker replay and Argo inspection remain open.
- `evidence/IMAGE-INVENTORY.json`: source/base/dependency/image hashes and the amd64 staging tar path.
- `PLAN.md` and `REVIEW-RESOLUTION.md`: reviewed design and the resolved Opus/Kimi conditions.

Workplace acceptance still requires its own TLS/SASL broker, representative application logs, target CNI, and real Kafka/EventBus failure exercises. Broker acceptance alone is never an Argo receipt. A change from receipts to model calls or ticketing needs its own recurrence and durable claim gate.
