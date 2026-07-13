# Evidence-First Worker Triage Work Bundle

## Purpose

This is a clean work-side handoff for agent triage from Kubernetes logs and
events without Alertmanager in the trigger path.

```text
worker cluster
  Alloy -> Vector -> Kafka
management cluster
  Kafka -> Argo -> read-only kagent -> idempotent GitLab work item
```

It deliberately excludes Alertmanager receivers, Grafana alert webhooks,
custom Go proxies, chaos automation and remediation. The existing Confluent
Kafka connection is an expected dependency for the work-side implementation;
reuse it rather than creating a parallel broker or a duplicate credential.

## Start here

1. `FRONT-SHEET.md`
2. `STAKEHOLDER-DESIGN-DECISION.md`
3. `TEAMS-STAKEHOLDER-MESSAGE.md`
4. `VISUAL.html` — stakeholder presentation with old/new flow diagrams
5. `FLEET-TOPOLOGY.md` — worker-local Alloy/Vector and management ownership
6. `DESIRED-STATE.md`
7. `CHECKLIST.md`
8. `WORK-AGENT-START-PROMPT.md`
9. `FABLE-FEEDBACK-RESPONSE.md`
10. `templates/` and `scripts/` — reviewed render scaffolds; customise, dry
    run and apply them when the execution gates pass
11. `requests/evidence-first-worker-triage-request.yaml`
12. `payload/REFERENCE.md`
13. `evidence/EVIDENCE-TEMPLATE.md`

## Human-operated pilot commands

Create a private values file from `templates/pilot-values.env.example`; it
contains secret *references*, never credential values. Then run:

```bash
# Render and prove the manifests can be accepted, without changing the cluster.
bash scripts/deploy-pilot.sh --values /secure/pilot-values.env

# Apply the additive worker/management pilot after the server dry run passes.
bash scripts/deploy-pilot.sh --values /secure/pilot-values.env --apply

# Confirm Vector, Argo consumer objects, required secrets and recent workflows.
bash scripts/verify-healthy.sh --values /secure/pilot-values.env

# Generate a log error, OOM, scheduling and image-pull event in the pilot namespace.
bash scripts/simulate-failures.sh --values /secure/pilot-values.env

# Remove only the controlled fixtures when evidence has been captured.
bash scripts/simulate-failures.sh --values /secure/pilot-values.env --cleanup
```

The Alloy fragment must be merged into the already-installed Alloy release.
The management claim endpoint is deliberately an approved durable TTL service;
the scripts refuse placeholder values rather than replacing it with a
proof-only ConfigMap dedupe.

Run the local structure check first:

```bash
bash scripts/verify-bundle.sh
```

## Review gate

The independent critique returned **sound with material gaps**. Do not
implement this in an office environment until the owner has accepted the
required corrections in `FABLE-FEEDBACK-RESPONSE.md`:

```text
docs/observability/FABLE-WORKER-TO-MANAGEMENT-TRIAGE-FEEDBACK.md
```

The red-cluster proof validates a single-cluster path only. It does not prove
office network connectivity, Kafka ACLs, data classification, retention,
multi-cluster ordering, a durable fleet idempotency store, or production
capacity.

## Required markers

```text
CRITIQUE_FEEDBACK_REVIEWED: yes
FLEET_CORRECTIONS_DEFINED: yes
CRITIQUE_CORRECTIONS_ACCEPTED: yes
STAKEHOLDER_DECISION: approved_parallel_pilot
WORKER_ALLOY_READ_ONLY: yes
WORKER_VECTOR_REDACTION: yes
WORKER_VECTOR_CORRELATION: yes
KAFKA_CLUSTER_IDENTITY_AND_ACL: yes
MANAGEMENT_TTL_IDEMPOTENCY: yes
ARGO_AGENT_READ_ONLY: yes
GITLAB_TICKET_IDEMPOTENT: yes
LOG_EVIDENCE_PATH_PROVEN: yes
EVENT_EVIDENCE_PATH_PROVEN: yes
REPLAY_SUPPRESSED: yes
ALERTMANAGER_UNCHANGED: yes
ROLLBACK_TESTED: yes
OUTPUT_SANITIZED: yes
```
