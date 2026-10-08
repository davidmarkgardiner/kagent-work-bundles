# Work agent start: two-namespace namespace-health pilot

Follow [the full workplace walkthrough](WORK-AGENT-WALKTHROUGH.md) for the
render, isolated canary receiver, exact checks, and rollback. This page is a
short checklist.

Build the **same hourly assessor and receipt-only Argo route** in an approved workplace test scope of exactly two namespaces. Use this bundle as a source and evidence package. Do not substitute the older Alloy/Vector path or add Python intake, PostgreSQL or an LLM to the first milestone.

The job is scheduled `0 * * * *` UTC and assesses the preceding hour. It reads workload state, recent Events and bounded timestamped Pod-log samples; applies deterministic tier rules; and publishes one report of at most 8 KiB only when a namespace qualifies for investigation. Quiet runs publish nothing to Kafka; incomplete required coverage without a positive finding fails the Job. See [the payload and admission contract](TRIAGE-PAYLOAD-AND-ADMISSION.md). A five-minute lookback on that hourly schedule would leave a 55-minute gap. If a five-minute cadence is required, stop and review it as a separate change to schedule, slot identity, report volume, freshness and deduplication.

## Establish workplace inputs before applying anything

1. Select the actual source and Argo receiver cluster contexts. Confirm Kubernetes 1.32 or newer and observe `batch.kubernetes.io/cronjob-scheduled-timestamp` on a real CronJob-owned Job. Record the source cluster's `kube-system` UID and approved cluster ID.
2. Obtain two approved test namespace names, their application-container names, excluded sidecars and critical controller identities. Confirm representative JSON severity fields in their logs. Do not infer application names from Pod-name suffixes.
3. Build and approve a new immutable amd64 image from the selective-admission source; the October 7 image archive predates this change. Confirm registry admission, Kafka TLS/SASL mechanism, topic names, scoped producer/consumer ACLs, advertised listener path, Argo Events/Workflows versions, EventBus and receiver namespace. Confirm independent CronJob/Job monitoring and alert destination.
4. Create a **private** config from `manifests/workplace/pilot-two-namespaces.config.template.json`. Supply Secret **names** in the config; keep credentials and CA material in approved Secret management. Run `scripts-render-workplace-pilot.py` with the private config and an empty private output directory. Inspect `source.yaml`, `receiver.yaml`, `canary-receiver.yaml` and the embedded policy; verify only the two test namespaces appear in source read roles.

## Prove the route in stages

1. Run `kubectl apply --dry-run=server` for all three rendered manifests against their respective actual contexts. Confirm the target Argo CRDs and EventBus are compatible. Source and receiver may reside in different clusters; never assume the local kubeconfig default context.
2. Provision isolated canary and scheduled topics, least-privilege producer/receiver groups, and independent CronJob/Job monitoring. Apply the source with its CronJob **suspended**, the scheduled receiver, and the separate canary receiver. Preserve all existing telemetry and urgent alert routes. Do not use the old Kafka missing-slot monitor against this selective topic.
3. Run one report-only Job. Publish a qualifying manual canary to the canary topic, consume its exact bytes from a separate group, validate `report.schema.json`, compare the Kafka key with `slot_id`, and capture an accepted Argo receipt. Prove a quiet Job succeeds with **no Kafka record** and a required-coverage-failed Job fails with **no Kafka record**. The receiver WorkflowTemplate is receipt-only; it performs no model call, ticket write or remediation.
4. Unsuspend only after independent monitoring detects a failed Job and a missed schedule. Capture three **real hourly** CronJob-owned Jobs and their controller timestamp annotations; expect Kafka values and receiver outcomes only for qualifying runs. Exercise a broker outage and monitoring alerts within the approved test scope.
5. Record the selected contexts, object inventory, image digest, topic/group identities, offsets, value hashes, workflow names/phases, monitor alerts, measured runtime/coverage and rollback result in a private workplace evidence pack. Keep private values out of this public bundle.

Home-lab proof is indexed in `evidence/LIVE-RECEIPTS.json`, `evidence/SCHEDULED-RUNS.json` and `evidence/HOURLY-SOAK-MONITOR.json`. The last file proves later valid hourly reports reached the independent consumer; exact broker replay and Argo inspection for those hours were blocked in the follow-up session. The unaccelerated missing-slot alarm remains open. `WORKPLACE-HANDOFF.md` lists all target-specific prerequisites, and `ROLLBACK.md` gives the reversal order. No workplace deployment or canary has been performed by this bundle.
