# Reference Material

Use these as reference only; they are not office-ready manifests.

- `docs/observability/worker-to-management-evidence-triage.md` — fleet design,
  controls, envelope and rollout rationale.
- `observability/alloy-vector-kafka-triage/` — generic proof package.
- `observability/alloy-vector-kafka-triage/red/` — verified single-cluster
  implementation and evidence, including the real limits of that proof.
- `docs/observability/FABLE-WORKER-TO-MANAGEMENT-TRIAGE-CRITIQUE-PROMPT.md` —
  independent review instruction and expected feedback record.

Do not copy the red overlay directly into an office environment. Replace its
proof-only ConfigMap dedupe with an approved durable TTL store, establish
office Kafka identity/ACLs, and use only approved namespace/network values.
