# Fleet Topology: Worker Evidence to Management Triage

## Placement decision

Run **both Alloy and Vector in every worker cluster**.

```text
worker cluster A                 worker cluster B                 worker cluster N
Alloy -> local Vector            Alloy -> local Vector            Alloy -> local Vector
             |                               |                               |
             +------------------- authenticated Kafka ------------------------+
                                              |
                                     management cluster
                           Kafka consumer -> validator/TTL store -> Argo
                                                -> read-only kagent -> GitLab
```

Alloy should normally be node-local for pod logs. Vector should be a
cluster-local, HA aggregation Deployment in the same worker cluster, behind a
Service and with persistent disk buffers. Vector is **not** a central service
shared by all workers: local processing keeps sensitive/noisy raw evidence in
the worker boundary until it has been redacted, bounded and normalised.

## Why Vector belongs in every worker cluster

| Worker-local Vector responsibility | Why it happens before Kafka |
|---|---|
| Attach worker cluster/environment identity | Preserve provenance at the source. |
| Redact secrets/PII and cap evidence | Do not send unbounded or unsafe raw logs across clusters. |
| Normalise logs/events into one envelope | Give management a stable contract. |
| Correlate and suppress immediate bursts | Avoid paying Kafka/agent cost for obvious local noise. |
| Disk-buffer during management Kafka outage | Keep worker failures from becoming immediate evidence loss. |

## What stays central in management

Management must not rely on any worker-local cache for the final decision. It
owns schema/cluster validation, quarantine, durable TTL idempotency,
cross-worker policy, concurrency, the read-only agent and GitLab credentials.

This gives each worker a self-contained collection/processing boundary, but
keeps triage policy, agent spend, ticket audit and secrets in one controlled
management plane.

## Kafka direction

Workers produce evidence records keyed by the incident fingerprint to the
approved Kafka/Redpanda topology. The management consumer group reads those
records and creates Argo work only after validation and the durable claim.
Kafka is the handoff and replay boundary; Argo is not deployed in every worker
cluster for this initial model.

## Do not confuse this with the red proof

The red proof ran Alloy, Vector, Redpanda and Argo in one cluster. It proves
the data path and ticket result, not the fleet network/security model. The
first work pilot must prove the worker-to-management Kafka identity, ACLs,
buffers, delivery semantics and failure drills listed in `DESIRED-STATE.md`.
