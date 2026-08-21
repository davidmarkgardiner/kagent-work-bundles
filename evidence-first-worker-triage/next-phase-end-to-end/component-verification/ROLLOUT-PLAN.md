# Namespace-to-Fleet Rollout Plan

Promote the Kubernetes evidence channel by evidence, not by copying the
collector across every namespace. Keep the human alerting route unchanged and
the agent read-only throughout.

## Stage 0 — discover and adapt before deploying

The work agent must not deploy `reference-config/` or `applied-config/`
verbatim. It must first inspect the existing work-cluster objects and use the
parameterised pilot overlay as the rendering base.

Required discovery record, held outside Git:

| Item | Verify before rendering | Stop if |
|---|---|---|
| Cluster contexts | Worker and management context names are intentional | The shell default points somewhere else or cannot be verified. |
| Namespaces and ownership | Existing Alloy, Vector, Argo Events, kagent, AKS MCP and GitLab integration namespaces/owners | A proof manifest would replace or duplicate an existing workload. |
| Images and API versions | Approved image tags, CRDs and installed resource schemas | A local proof image or CRD is unavailable or forbidden. |
| Identity and secrets | Existing service accounts, workload identity, Secret/CA reference names | Required identity/Secret reference is missing; never invent a replacement. |
| Kafka integration | Topic, EventSource group, producer/consumer principal and ACLs | Group/topic READ, network route or TLS trust is not already approved. |
| Security policy | NetworkPolicy, pod security, GitOps/Flux ownership and AKS MCP scope | The proposed path exceeds approved read-only or namespace scope. |

Render the overlay with private values, review the full output against that
record, then use a server-side dry run. A mismatch is a blocker to resolve with
the owner—not permission to patch local YAML until it happens to apply.

## Stage 1 — golden test namespace

Use one explicitly approved non-production namespace. Complete every component
gate and smoke case in this folder. Fix the configuration or policy at the
first failed boundary; do not compensate with manual workflow submissions.

Exit criteria: all smoke tests green, Confluent topic/group ACLs proven,
read-only AKS MCP proof captured, and no secret-shaped value in Kafka/workflow/
GitLab evidence.

## Stage 2 — one core application namespace

Choose a low-risk but representative core application namespace with a named
owner. Before enabling collection, agree:

- The namespace/service selector and data classification.
- The allow-listed application error signatures and Kubernetes Warning reasons.
- Expected on-call/ticket owner, severity policy, and acceptable ticket rate.
- The AKS MCP target cluster and read-only tool scope.

Repeat Cases A–F. Compare event volume, Kafka lag, workflow concurrency, DLQ/
quarantine rate, duplicate rate and ticket usefulness with the golden
namespace. Pause if the policy drops a useful signal silently or creates an
unexpected ticket.

## Stage 3 — core platform namespaces, one at a time

Onboard the next namespace only after the previous namespace has a documented
green result and a short observation window with stable lag/concurrency. Good
early candidates are platform components where events and logs have clear
ownership, such as DNS, policy, ingress or a selected application platform
service. Do not assume all core namespaces have the same log format or safe
data classification.

For each namespace:

1. Add its scoped collector/selector through the approved GitOps path.
2. Confirm Vector allow-list compatibility; add a versioned rule only when
   required and test it.
3. Run a controlled log and Warning-event smoke case.
4. Review the resulting ticket with the namespace owner.
5. Observe at least one normal operating period for noise, lag, DLQ and
   duplicate behaviour.
6. Record green/amber/red evidence in the rollout tracker before proceeding.

## Stage 4 — controlled fleet expansion

Expand in small batches grouped by data classification and operating owner,
not by a blanket cluster-wide wildcard. Retain the ability to remove one
namespace selector/reconciliation entry without stopping the rest of the
pilot.

Fleet gates:

- Consumer lag and queue age remain within the agreed threshold.
- Workflow concurrency stays within the configured semaphore/cap.
- DLQ/quarantine and Vector discard metrics are explained and reviewed.
- Duplicate ticket rate stays at zero for repeated signals; distinct incidents
  still create separate items.
- GitLab content remains bounded/redacted and useful to the owning team.
- AKS MCP remains read-only, target-scoped and healthy.

## Stop / rollback rule

Pause the next namespace immediately and remove only the newly enabled
namespace route if any of these occur: secret leakage, incorrect cluster
access, write-capable tool exposure, repeated duplicate tickets, sustained
Kafka lag, uncontrolled workflow concurrency, or misleading ticket content.
Capture the evidence, fix the failed gate, re-run the golden namespace smoke
tests, then retry the single namespace. Never respond by widening collection
or bypassing deduplication.
