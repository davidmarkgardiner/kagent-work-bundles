# Restart-safe Alloy to Vector to Kafka delivery

This is the work-agent handoff for two worker-pilot questions:

1. How do we prove a smoke signal travelled from Alloy, through Vector, and into Kafka?
2. How do we stop an Alloy restart replaying historical namespace logs into the triage topic?

Do not change the payload contract, dedupe keys, Kafka topic policy, or downstream Argo logic while making these storage changes.

## Short answer

The observed Alloy replay is expected with the current packaged configuration. Alloy is started with `--storage.path=/var/lib/alloy/data`, but that path is mounted from `emptyDir`. A restart loses its local positions/WAL state and may replay historical logs. Persist that directory on an Alloy-only volume before treating restart behaviour as stable.

Vector is different. Its current Kafka sink uses in-memory buffering and its dedupe cache is in memory. Adding `data_dir` alone does **not** make a Kafka sink durable. A persisted Vector buffer is a separate reliability change that must be tested with real production and consumption before adoption.

Kafka/Confluent owns retained topic storage. Do not share a filesystem volume between Alloy, Vector, and Kafka; they have different state and failure semantics.

## Current behaviour and ownership

| Component | Current state | Restart consequence | Required action |
|---|---|---|---|
| Alloy | `--storage.path=/var/lib/alloy/data` mounted from `emptyDir` | Local log positions are lost; historical logs may replay and forward | Mount an Alloy-only PVC at `/var/lib/alloy/data` |
| Vector | No `data_dir`; Kafka sink and dedupe cache are in memory | In-flight records and exact-repeat cache are lost | Keep this explicit for the pilot, or add a separately proven persistent buffer |
| Kafka | External broker/topic retention | Broker retains records according to topic policy | Configure retention and ACLs in Kafka, not with a workload PVC |
| Argo claim | ConfigMap 24-hour claim | Pilot-level ticket dedupe survives Vector restart | Treat durable claim storage as a separate production decision |

## Phase A: persist Alloy positions first

Create a dedicated PVC for Alloy and mount it only at `/var/lib/alloy/data`. Do not mount it into Vector. Keep Alloy at one replica until storage and replay behaviour have been proven.

For a single-replica Deployment, ensure the rollout strategy cannot create two writers against the same ReadWriteOnce volume. A `Recreate` strategy or a single-replica StatefulSet are both reasonable patterns; use the platform standard storage class and backup/encryption policy.

The acceptance test is behavioural, not merely `Bound` PVC status:

1. Send one uniquely stamped, allow-listed smoke log.
2. Record Vector's `kafka` produced counter and the Kafka consumer offset.
3. Restart Alloy.
4. Wait for it to become Ready, then send one new uniquely stamped smoke log.
5. Verify only the expected new delivery occurs. A burst of historical logs after restart is a failure.

The smoke marker must contain an allow-listed failure term such as `ERROR`, `FATAL`, or `timeout`; otherwise Vector will correctly filter it before Kafka.

## Phase B: prove transport hop by hop

Use a unique timestamp/marker so the before/after counters are unambiguous.

```text
Alloy saw marker
  + Vector alloy_otlp counter increased
  + Vector incident_signals counter increased
  + Vector kafka counter increased
  + Kafka consumer saw the same envelope
  = end-to-end delivery proven
```

The decisive Vector counter is:

```text
vector_component_sent_events_total{component_id="kafka"}
```

It must increase after the smoke signal. `alloy_otlp` proves Vector received telemetry; `incident_signals` proves it passed the triage filter; `kafka` proves the sink produced it. Absence of errors in pod logs is useful diagnosis but is not equivalent to broker delivery.

If the work deployment exposes Prometheus on `:9090`, query that endpoint. The home bundle uses `:9598`; either is fine if the Service, scrape configuration, and verification script agree. Retain Vector's separate health endpoint for readiness/liveness: Prometheus metrics are not a substitute for `/health`.

## Phase C: only then assess persistent Vector buffering

Do **not** make this a cosmetic `data_dir` change. To survive a Vector restart while Kafka is unavailable, all of the following must be true:

1. Vector has a dedicated PVC mounted at its own data directory, for example `/var/lib/vector`.
2. The Kafka sink is explicitly configured to use the supported persistent buffer mode for the pinned Vector image.
3. One Vector replica owns that ReadWriteOnce volume; it is never shared with Alloy or another Vector replica.
4. A controlled outage/restart test proves records are later produced and consumed, not merely accepted into a local buffer.
5. The produced Kafka counter recovers and the output contains each test marker once, subject to the documented dedupe policy.

The current verified Vector image is `timberio/vector:0.45.0-debian`. A prior disk-buffer attempt on this version accepted writes locally but did not drain to Kafka. Do not enable disk buffering on the strength of a rendered manifest or a healthy Pod. Keep the current in-memory buffer until this proof passes in the work non-production environment.

## What to change

| File | Phase A now | Phase C only after proof |
|---|---|---|
| `config/01-alloy.yaml` | Replace the `emptyDir` `data` volume with an Alloy PVC mounted at `/var/lib/alloy/data` | No Vector changes here |
| `config/02-vector.yaml` | No buffer change required | Add a Vector-only PVC, `data_dir`, and explicit supported Kafka disk-buffer settings; update rollout policy if required |
| `scripts/verify.sh` | Check Alloy PVC is Bound/mounted and retain the Kafka-produced counter check | Add a restart/outage proof that verifies real produced and consumed records |
| `fixtures/` | Use unique smoke markers for restart tests | Use an intentional Kafka-unavailable test only in approved non-production scope |

## Definition of done

Do not call restart safety complete until evidence shows all of the following:

- Alloy restart does not replay the historical namespace log set.
- The one new post-restart smoke marker reaches Vector and Kafka.
- Vector's Kafka-produced counter increases by the expected amount.
- A Kafka consumer reads the expected envelope.
- If Vector persistence is enabled, a Kafka-outage/restart drill drains the buffered marker after recovery.
- Triage workflow concurrency and incident dedupe remain bounded.

## Explicit non-goals

- Do not persist Kafka broker data in this Kubernetes workload.
- Do not share an Alloy/Vector PVC.
- Do not scale either collector to multiple replicas against one ReadWriteOnce volume.
- Do not assume `data_dir` alone makes Vector Kafka output durable.
- Do not promote disk buffering to Flux until the outage/restart proof is captured.
