# Reference Config — provenance and phase map

These are the **actual verified-working manifests** from the red/proof cluster
run (`observability/alloy-vector-kafka-triage/red/`), copied here so this folder
is self-contained and downloadable. They are the config behind the happy path
that already fires end to end.

## Source and status

- Origin: `observability/alloy-vector-kafka-triage/red/` in the kagent repo.
- Verified: `VERIFICATION-2026-07-13.md`, `STRESS-TEST-2026-07-13.md`.
- Proof-grade, single-cluster. **Not office-ready as-is.**
- **Pre-corrected:** the YAML here is NOT a verbatim copy — it has the
  `severity`/`container` fields and the widened log+event filters already
  applied. See `CHANGES-FROM-PROOF.md` for every delta. The verbatim proof
  stays at the origin path above. These edits are applied-but-unproven; the
  Phase 0 gate proves them.

## Read this before applying anything

This is the **red proof**, not an office manifest. Per the parent bundle
(`../../payload/REFERENCE.md`), do **not** copy it straight into the office:

- Idempotency here is a **ConfigMap dedupe** (`claim-24h-window` in
  `03-argo.yaml`). The office needs an **approved durable TTL store** — this is
  Phase 3/5 work, not a copy-paste. Separately, this file's delete-then-create
  claim refresh is also non-atomic (a correctness bug, not just a durability
  gap) — see `../KNOWN-DEFECTS-AND-REPROVE.md` and
  `../applied-config/03-argo-augmented.yaml` for the compare-and-swap fix.
- Kafka is single-cluster Redpanda. Office needs **Confluent identity + ACLs**.
- Namespace/topic/endpoint values are proof values. Replace with approved ones.
- Secrets are **references only** (`${CONFLUENT_SA_SECRET}`, `$GITLAB_TOKEN`,
  serviceaccount token path). No real credentials are in these files. Keep it
  that way — fill real values in an approved secret store, never in Git.

Redaction is real and tested: `02-vector.yaml` and `03-argo.yaml` both carry the
password/token/api-key/secret redaction regex, proven by the redaction fixture.

## File → phase map

| File | What it is | Phase that uses it |
|---|---|---|
| `01-alloy.yaml` | Read-only node-local log/event collection | Phase 2 (config), Phase 1 (smoke) |
| `02-vector.yaml` | Worker Vector: redaction, envelope, Kafka produce | Phase 2 (config), Phase 4 (payload) |
| `03-argo.yaml` | Management backend: claim-24h dedupe → agent → **create/update GitLab issue** | Phase 3 + Phase 5 (backend + tickets) |
| `00-namespace.yaml`, `00-topic.yaml`, `kustomization.yaml` | Namespace, topic, kustomize wiring | all |
| `log-fixture.yaml` | Application log error fixture | Phase 1 (log path) |
| `crashloop-fixture.yaml` | Crashloop/event fixture | Phase 1 (event path) |
| `confluent-scenarios.yaml`, `retest-fixtures.yaml`, `stress-fixtures.yaml` | Event classes, redaction retest, burst/stress | Phase 1, Phase 4, Phase 5 |
| `VERIFICATION-2026-07-13.md`, `STRESS-TEST-2026-07-13.md` | The evidence these were proven with | reference |

## Where the working GitLab ticket backend already is

`03-argo.yaml` is the answer to "do we have the Argo→GitLab code": yes, at proof
level. It has:

- `claim-24h-window` — idempotency claim (ConfigMap dedupe today → durable TTL
  store for office).
- `create-gitlab-issue` — curl to GitLab API with `PRIVATE-TOKEN`, redacted body.
- update-existing-on-duplicate — so a repeat updates, not re-creates.

Phase 3 promotes the claim store; Phase 5 makes it the standing backend.
