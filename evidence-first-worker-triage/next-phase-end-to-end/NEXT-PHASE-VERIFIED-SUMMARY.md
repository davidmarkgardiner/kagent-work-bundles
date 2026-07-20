# Next-Phase Verified Summary

Run on the `red` (homelab proof) cluster, 2026-07-20. Gate 0 and Phases 1-5
are complete; see `ROLLOUT-TRACKER.md` for per-phase state (2 green, 3 amber
— every amber has a named, evidenced reason and a recommended fix, not a
silent gap) and `evidence/` for the full evidence trail this summary cites.

## (a) What is now proven working end to end on `red`

The full path — **worker Alloy (read-only, namespace-scoped) → worker
Vector (redacts, normalises, correlates) → real Confluent Cloud → management
Argo (validates, deduplicates, calls the read-only triage agent) → idempotent
GitLab work item** — runs live and has been proven, with real evidence, to:

- **Not leak secrets.** Synthetic password/token/Bearer values are redacted
  before Kafka and scrubbed a second time before the agent's own diagnosis
  reaches GitLab, closing the 2026-07-13 P0-1 defect
  (`evidence/phase0-reprove-redaction-and-correlation.md`, tickets
  [#448](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/448)/[#451](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/451)).
- **Correlate a log and a later event into one ticket, in the right order or
  the wrong one.** A live claim-store race that *reproduced* the 2026-07-13
  P0-2 defect (two tickets for one incident, #446/#447) was caught and fixed
  with a resourceVersion-guarded compare-and-swap; the fixed path was proven
  with a log+event race producing exactly one ticket
  ([#450](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/450))
  and a dedicated claim-failure/retry drill
  ([#452](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/452)).
- **Carry both application logs and Kubernetes events**, across three real
  event classes (`FailedScheduling`, `BackOff`/image-pull, `Unhealthy`) plus
  four log fixtures, each reaching a workflow with `severity` and `container`
  populated (`evidence/phase1-smoke-tests.md`,
  `evidence/phase4-payload-contract.md`).
- **Meter, not silently drop, filtered signals** — a live Vector metric shows
  exactly how many records were policy-discarded vs. produced
  (`evidence/phase2-efficiency.md`).
- **Open real GitLab work items from the agent's own read-only diagnosis**,
  idempotently (create-once, update-on-repeat, retry-after-failure with no
  duplicate) — `evidence/phase3-*.md`.
- **Quarantine and replay bad or stale records**, and **bound concurrency
  under a burst** — both built new this pass (they did not exist at proof
  level before today), each proven with a real drill including two bugs
  found and fixed before being trusted with live traffic
  (`evidence/phase5-backend-drills.md`).
- In total, **~19 real GitLab work items** were created across this session,
  each carrying a rendered incident contract and a genuine read-only agent
  diagnosis (`evidence/phase5-live-tickets.md`).

Two real, still-open gaps were found, evidenced, and deliberately **not**
silently fixed under time pressure (both amber in `ROLLOUT-TRACKER.md`, both
with a recommended fix):

- **Fingerprint is not stable under pod churn** (DS-04): the same logical
  service failing under two different pod names got two different tickets
  (`evidence/phase4-payload-contract.md`, tickets #480/#481). The
  obvious fix (key on the `service` label) was evaluated and rejected because
  it would reintroduce the just-fixed log/event correlation bug — a
  workload-suffix-stripping fix is recommended but needs its own regression
  pass.
- **Vector is not fleet-grade** (DS-03): a disk-buffer attempt broke Kafka
  delivery outright and was reverted; HA/PDB/topology-spread were not
  attempted because `red` is a single-node cluster with no real target to
  prove against (`evidence/phase2-vector-config.md`).

## (b) The pilot in one paragraph

We built and proved, on a disposable lab cluster, a path that watches one
namespace's application logs and Kubernetes warning events, automatically
strips anything secret-shaped, figures out whether a log and a later
Kubernetes event belong to the same underlying problem, asks a read-only AI
agent to diagnose it (never to fix anything), and opens or updates a single
GitLab ticket that already contains the evidence and the diagnosis — so a
human opens the ticket already knowing what's wrong instead of starting from
scratch. This pass re-checked two previously-found security/correctness bugs
were genuinely fixed (and, in re-checking, caught a *new* variant of one of
them live and fixed that too), then proved the whole thing end to end with
real tickets, added a safety net for bad or stale data and for traffic
bursts, and was honest about the two things that are still not
production-ready (ticket fingerprinting under pod restarts, and Vector's own
resilience) rather than papering over them.

## (c) What must change before this could run against a work/office cluster

Reading `reference-config/PROVENANCE.md` plus what this pass additionally
found:

1. **Durable TTL store.** The idempotency claim is a Kubernetes ConfigMap
   with an `expires_at` field checked by hand — correctness-safe now (proven
   under concurrency and failure in this pass), but not a real TTL store
   (Redis, etcd lease, or similar) with proper expiry semantics at scale.
2. **Confluent identity + ACLs for the office environment.** This proof
   already talks to a real Confluent Cloud cluster (not the local Redpanda
   the original reference config assumed), but it is a lab/dev project and
   topic (`k8s-events`) discovered on `red` — the office needs its own
   approved project, service-account identity, and topic ACLs, not reuse of
   this one.
3. **Approved namespace/topic values.** `agentic-triage-proof` and the
   `k8s-events` topic are lab values. Office rollout needs sign-off on the
   real pilot namespace and topic name(s).
4. **Real secrets in an approved store.** `gitlab-credentials` and
   `confluent-credentials` are plain Kubernetes `Opaque` secrets on `red`,
   created directly — **not** sourced via the `external-secrets` operator
   that is already installed on this cluster. Office rollout should source
   both from the organisation's approved secret store via an `ExternalSecret`,
   not a manually-created K8s Secret.
5. **GitLab target.** Tickets in this pass went to `davidmarkgardiner/mcp-test-repo`,
   a sandbox project. Office needs the real target project ID (and to decide
   whether that's a shared "automated-triage" project or per-team).
6. **Fingerprint stability fix** (see gap above) — should land before any
   real Deployment-managed workload (which churns pod names on every
   restart/reschedule) is onboarded, or every restart will look like a new
   incident.
7. **Vector resilience** (see gap above) — a working disk buffer (this
   pass's attempt broke delivery on Vector `0.45.0-debian`'s `kafka` sink and
   was reverted) and real HA/PDB/topology-spread, validated on a multi-node
   cluster where topology-spread has an actual target.
8. **Broker outage/drain drill** — not attempted against the real managed
   Confluent Cloud broker without a scheduled, owner-approved maintenance
   window; needs one before claiming loss-accounting is proven.
9. **OOMKilled event-class coverage** — this cluster's kubelet does not emit
   a discrete `OOMKilled`/`OOMKilling` Kubernetes Event at all (verified: a
   real OOM kill occurred, container status showed `OOMKilled`, no
   corresponding Event ever appeared cluster-wide). Confirm whether the
   office cluster's kubelet/version behaves differently before assuming this
   class routes there.
10. **Cluster IDs, endpoints, CA data, and GitLab project IDs** — never
    written to Git in this pass (kept in `secretKeyRef`s and cluster-side
    ConfigMaps/Secrets only); the office rollout needs the same discipline
    with its own real values.
