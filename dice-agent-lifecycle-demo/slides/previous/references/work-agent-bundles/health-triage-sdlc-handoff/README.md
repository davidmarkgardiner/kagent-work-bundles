> Updated 2026-10-02: the requested worker-local hourly top-N design supersedes this direct/daily bridge handoff. Use [hourly-topn-worker-triage](../hourly-topn-worker-triage/README.md): worker terminal proves Kafka and stops; a separate agent terminal configures Argo/kagent triage with Kubernetes MCP via kmcp. This older snapshot/archive remains historical reference.

# Health digest -> SDLC rig triage: work-agent handoff

Start with **WORK-AGENT-PROMPT.md**, then **WORK-CLUSTER-RUNBOOK.md**.
Open **HANDOFF.html** for the integration overview and
**admission/WHAT-CHANGED-2026-10-01.html** for yesterday's detailed changes.
Read **DEPENDENCIES.md** before importing images or building anything.

This is an additive evaluation bundle for updating an existing setup. It contains
source snapshots of the 1 October admission gate and the current SDLC rig,
an executable digest-to-A2A bridge, a no-tools triage Agent renderer, a suspended
CronJob renderer, daily claim schema, tests, Linux-amd64 hashed dependency lock
and a deterministic package builder. The transfer archive also contains wheels.

## The integration

Alloy -> Vector -> admission/PostgreSQL -> 1–2 selected v2 records -> existing Kafka/Argo.
Separately: admission `GET /report` -> bridge freshness/identity/size checks ->
PostgreSQL daily call claim -> kagent A2A `sdlc-health-triage` in the existing rig ->
validated up-to-three-issue assessment stored in protected PostgreSQL.

The gate's `/health` endpoint only checks database access. It is NOT cluster health.
This bridge consumes `namespace-triage.digest.v1` at `/report`, not `/health`.
The initial triage Agent is **evidence-only**: no MCP tools, no Agent delegation,
no PM invocation, no GitLab tools, no tickets, no changes. It reports hypotheses
and coverage gaps. Fresh metrics/live health checks are a separate reviewed delta.
It does not automatically start the board-poller delivery flow or create a parent issue.

The existing rig has PM, builder, tester, reviewer and echo agents, but no triage
agent in the inspected source. Defaults add `sdlc-health-triage` using an existing
ModelConfig. If the workplace already has triage, inventory its capabilities and
adapt only the caller/Agent instruction delta; do not overwrite that Agent blindly.

## Claims and limits

- Gate evidence is the recorded 1 October isolated synthetic lab and CI proof.
- New bridge verification is listed in BUILD-EVIDENCE.md; fixture HTTP/A2A tests
  and real PostgreSQL claims do not establish live kagent/model execution.
- No workplace resources, cluster, images, agents or tickets were changed.
- No all-source ticket cap or healthy-cluster verdict is claimed.
- Invocation is off by default, CronJob always renders suspended, Job retry is off.
- One durable claim per cluster/local day is committed before a model call.
  Unknown, invalid, sending and completed states all prevent automatic retries.
  Database restore/state loss can erase claims: disable invocation and reconcile
  A2A history before recovery. Unlike the gate's Kafka audit, this bridge has no
  independent downstream durable-history audit. Preserve claim tombstones.

## Included files

- bridge.py, schema.sql, agent-output.schema.json: implementation and contracts.
- render.py, profile.example.json: additive credential-free rendering.
- test_bridge.py: freshness, wire envelope, output, evidence IDs, replay/concurrency.
- Dockerfile.offline / Dockerfile.admission.offline: no-network package install.
- requirements.linux-amd64.lock, WHEELS.linux-amd64.json: pinned dependency inventory.
- admission/: selected source snapshot, tests, rendering and historical evidence.
- rig/: complete selected handoff snapshot; no need for a sibling repo at work.
- SOURCE-PROVENANCE.json: source and packaged file hashes; integration links in the
  admission HTML/README are adjusted for the snapshot layout, not runtime behavior.
- package.py: archive and checksums; allowlisted source files only.

The supplied Docker base is not embedded, and installed controllers/runtime images
are not embedded. This bundle is ready for a work agent to review/adapt; deployment
requires the target checks in the runbook. Preserve object names, authentication,
namespace ownership, approved views, model routes, grants and delivery flows.
