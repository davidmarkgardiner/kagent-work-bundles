# PRD: Fox collector mesh with cluster-health admission

## Problem and user outcome

The Alloy/Vector evidence lane observes an explicit namespace scope but emits
incident-shaped signals. We need broader deterministic namespace health checks
without allowing object- or pod-level findings to create another ticket storm.
Operators should receive the existing bounded cluster assessment, enriched by
Fox, with no change to ticket or agent volume during qualification.

## Scope

- Run Fox `autonomous-monitor` once per namespace selected by Alloy.
- Keep collectors in `cluster-health-system` with no Kafka credential.
- Disable Fox per-finding publication in the local/internal work image.
- Read Fox state in B1 and rekey pod findings to stable owning workloads.
- Record Fox coverage and corroboration in snapshots.
- Start in shadow mode.

## Non-goals

- Direct Fox-to-Agent or Fox-to-ticket dispatch.
- Automatic remediation.
- Replacing the cluster-level node/capacity probe.
- Treating namespace-owned Fox ConfigMap state as authoritative.
- Deploying from this build session.

## Security and reliability

- No Secret reads, exec, pod mutation, node access, or cluster-wide
  namespaced-resource binding.
- Target namespace administrators do not receive the Kafka identity because
  Fox Deployments remain in the platform namespace.
- A missing or invalid Fox state is visible but cannot block or manufacture
  cluster-health coverage. Namespace-owned ConfigMap evidence is shadow-only.
- Raw finding identity is never used for workflow, snapshot, or ticket identity.
- Namespace scope drift fails verification.

## Migration and rollback

Deploy the mesh with `FOX_MESH_MODE=shadow` and state-only publication.
Rollback by scaling/removing the Fox Deployments and setting the mode to
`disabled`; B1's native Kubernetes collection remains intact. Preserve state
and comparison reports long enough to explain the decision.

## Acceptance criteria

| Criterion | Proof |
|---|---|
| Fox and Alloy select exactly the same namespaces | `fox-mesh/verify.py` |
| One collector is rendered per selected namespace | Render count assertion |
| Fox cannot dispatch per-finding Argo/agent/ticket work | Source tests plus manifest static assertions |
| Pod churn collapses to stable workload identity | B1 unit test with 50 pods |
| Shadow evidence cannot alter domain/gate logic | Mode branch plus unit/policy tests |
| Collector cannot read Secrets or mutate workloads | Generated RBAC inspection |
| Existing package gates remain green | `verify-all.sh` |
| Live readiness, Kafka and parity are not overstated | Offline evidence receipt |

## Open promotion decisions

- Approved immutable image digest and internal mirror.
- Workplace alert-bridge Kafka authentication and NetworkPolicy.
- Missing namespaces in the sanitized Alloy inventory.
- Minimum parity window and acceptable mismatch/false-positive rates before a
  separately authenticated Kafka/state-intake design is considered.
- Whether to retain 22 processes or shard the namespace collectors after
  measuring API, memory and Kafka cost.
