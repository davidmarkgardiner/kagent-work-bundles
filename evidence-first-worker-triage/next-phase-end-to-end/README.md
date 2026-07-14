# Next Phase: Full End-to-End Working Scenario

The parallel pilot path now fires end to end on the red/proof cluster:

```text
pod fires -> Alloy picks it up -> Vector -> Kafka -> Argo picks it up
```

This folder is the ordered work list to turn that happy path into a **full,
proven, value-producing end-to-end scenario** — real evidence for logs *and*
events, a verified-efficient Alloy/Vector config, an Argo backend that actually
opens GitLab tickets off the agent triage/remediation output, payload proof,
then a controlled namespace-by-namespace rollout across the whole cluster.

It sits on top of the parent bundle. It does **not** replace it. Every gate in
`../DESIRED-STATE.md` and every safety rule in `../WORK-AGENT-START-PROMPT.md`
still applies (parallel non-production path only; no Alertmanager/Grafana/proxy
changes; read-only agent; no remediation actions; secrets stay in approved
stores, never in Git).

## How to use this folder

1. Read `00-WORK-AGENT-START-PROMPT.md` — the framing prompt for the work agent.
2. Work the phases **in order**. Each `PHASE-N-*.md` is self-contained:
   - **Goal** — what "done" means in one line.
   - **Prompt** — a copy-paste block to hand the work agent.
   - **Do** — the concrete steps/commands.
   - **Evidence to capture** — what must land in `../evidence/`.
   - **Done when** — the markers that gate the next phase.
3. Track progress in `ROLLOUT-TRACKER.md`.
4. Do not start a phase until the previous phase's `Done when` markers are all
   `yes`. A rendered manifest, a Ready pod, or a workflow that merely *ran* is
   not evidence.

## Phase map

| Phase | File | Outcome |
|---|---|---|
| 0 | `KNOWN-DEFECTS-AND-REPROVE.md` | **Gate.** Re-prove the two patched-but-unproven P0 fixes (redaction leak, event correlation) before any new build. |
| 1 | `PHASE-1-smoke-tests-logs-and-events.md` | Logs **and** events both proven into the workflow. |
| 2 | `PHASE-2-vector-alloy-verified-config.md` | The tested, most-efficient Alloy + Vector config, documented. |
| 3 | `PHASE-3-argo-gitlab-ticket-backend.md` | Argo backend opens GitLab tickets from agent triage/remediation output. |
| 4 | `PHASE-4-payload-proof-and-efficiency.md` | Prove the exact payload arrives; prove it is as lean as possible. |
| 5 | `PHASE-5-backend-workflow-live-tickets.md` | The real backend workflow runs; live tickets create value. |
| 6 | `PHASE-6-namespace-by-namespace-specialist-routing.md` | One namespace at a time (external-dns / Kyverno first) routed to specialist agents. |
| 7 | `PHASE-7-fleet-rollout-all-apps.md` | Every application on the cluster onboarded, one controlled step at a time. |

## Signal coverage

`SIGNAL-COVERAGE.md` answers "are we missing anything that should fire?" Both
filters (the Vector log regex and the Vector+Argo event reason list) are
narrower than "anything suggesting the app is wrong." It gives the widened,
aligned filter sets and a per-class verification list, so the golden namespace
catches everything before other namespaces copy it. It also states the
read-only boundary: the agent diagnoses and advises; it does not auto-remediate.

## Payload field proof

`PAYLOAD-FIELD-PROOF.md` answers "does the workflow receive everything the agent
needs — cluster, message type, the actual message, what the error is, pod,
service?" It maps every envelope field to where it is set, whether it reaches
the agent, and whether it lands in the ticket, backed by the two real red-proof
tickets (#430 log path, #431 event path). It also flags the two fields the work
agent must add and prove: `severity` and `container`. Phases 1 and 4 point here.

## Working config included

`reference-config/` holds the **actual verified-working manifests** from the
red/proof cluster — the Alloy, Vector, and Argo config (including the Argo→GitLab
ticket backend) behind the happy path that already fires. Read
`reference-config/PROVENANCE.md` first: it maps each file to a phase and states
what must change before office use (durable TTL store, Confluent ACLs, approved
namespace/topic values, real secrets in an approved store). It is proof-grade —
**not** copy-paste ready for the office.

## Guardrails (unchanged from parent bundle)

- Parallel, additive, reversible path only — never touch the human alert path.
- Agent is read-only. Triage/remediation output is **advice written into a
  ticket**, not an action taken on the cluster.
- Every phase ends with a sanitized evidence artifact in `../evidence/`.
- Escalate — do not invent — when a value needs owner authority, a credential,
  a network route, or a policy decision.
