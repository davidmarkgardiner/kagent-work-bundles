# Work-agent handoff: reproduce the Substrate 0.0.9 gVisor result

> **Decision in one sentence:** the public Substrate 0.0.9 + kagent 0.10
> (patch 1)
> pairing completed the gVisor actor lifecycle on a disposable **AKS 1.35.8**
> AMD64 Azure Linux node. This is a useful baseline, not proof that the bank's
> private builds, node, binary delivery, or failing workload are identical.

## Correct the target first

The 7 October 2026 evaluation had two different AKS runs. Substrate **0.0.9**
with kagent **0.10 (patch 1)** ran on Kubernetes **1.35.8**. Kubernetes **1.37.0
preview** was tested with Substrate **0.4.0-alpha1** and kagent
**1.0.0-alpha8**; that release uses a `gvisor.tar.zstd` asset and a different
Agent API. Do not attribute the 1.37 result to Substrate 0.0.9 or copy its asset
and manifests into a 0.0.9 deployment.

The work target is **AKS**, as confirmed by the operator. The disposable
evaluation node was deleted, so the work node cannot be the same physical
node. The work agent must compare its Kubernetes version, Azure Linux image,
kernel, architecture, VM SKU, container runtime and admission policy with the
tested node. A matching Kubernetes version alone is insufficient.

## Tested public baseline to compare against

| Item | Disposable 0.0.9 AKS evidence |
| --- | --- |
| Cluster/node | AKS 1.35.8; one Ready `Standard_D8s_v3` AMD64 node; Microsoft Azure Linux 3.0; kernel `6.6.150.1-1.azl3` |
| Agent stack | Substrate charts/CRDs 0.0.9; kagent charts/CRDs 0.10 (patch 1); gVisor WorkerPool with one replica; generated `SandboxAgent`/immutable `ActorTemplate` |
| Worker runtime | `ateom-gvisor`; `atelet` built from pinned 0.0.9 source with a **lab-only internal-asset fetch patch**; all deployed image digests recorded in private receipts |
| `runsc` | AMD64 `release-20260622.0`; SHA-256 `f18a948bf9c8bbb54eb998549a3a8d719a1c7de2efbe8fdd2ff0ee5fecd06f19`; 129,078,244 bytes |
| Binary delivery | `SandboxConfig/gvisor-default` referenced `gs://{{INTERNAL_BUCKET}}/assets/runsc-amd64-release-20260622.0`; patched `atelet` fetched through the configured internal object-store client into its content-addressed node cache. After deliberate cache eviction, a new agent caused a fresh fetch and the cached binary checksum matched. The observed cached path shape was `/host/static-files/runsc-<sha256>`. This was **not a Kubernetes hostPath mount of a preinstalled `runsc` executable**. |
| Snapshot contract | Generated template used `onPause: Full`, `onCommit: Data`, durable `/data` and an agent-card readiness probe. In this release Full uses `runsc checkpoint`; Data uses `runsc fscheckpoint`. Golden creation uses `onCommit` and therefore exercises Data. |
| Observed result | Stock and internal-asset generated agents became Ready. Golden restore, Full pause/restore and Data commit/restore returned matching HTTP 200 agent cards. Three further fresh actors repeated the sequence. No exit 128 appeared in these AKS runs. |

The internal asset fetch patch was tested for *zero anonymous Google Storage
client calls* for the configured internal bucket. It was not an upstream
release. The AKS cluster remained Internet-connected, and most images came
from public registries; this was not a strict air-gap or packet-level egress
test. No model/MCP/chat request or changed `/data` survival assertion ran.
The disposable cluster and registry were deleted after evidence capture.

Public receipts: [AKS evaluation handoff](AKS-EVAL-WORK-AGENT-HANDOFF.md),
[air-gap asset guide](AIRGAPPED-AKS-README.md), and
[checkpoint diagnostic handoff](../runsc-checkpoint-investigation/WORK-AGENT-HANDOFF.md).
The operator's private AKS report and patch are separate evidence; do not put
its kubeconfig, Helm values, CA material, resource IDs or raw logs in this repo.

## Instructions for the work agent

**Start with read-only discovery on the explicitly named non-production target.**
Save raw output only in the bank's approved private evidence location. Return a
sanitized comparison and exact file/receipt pointers. Do not replace images,
change `SandboxConfig`, evict a cache, restart a pod or create an actor during
the discovery phase.

1. **Identify the AKS node.** Confirm the target cluster and node pool from
   approved AKS inventory and the selected node's `spec.providerID`. Record
   the Kubernetes and kubelet versions, architecture, Azure Linux OS image and
   version, kernel, container runtime, VM SKU, node-pool labels and taints,
   relevant Pod Security/Kyverno policy, and worker pod placement. Compare
   every field to the table above. Record `match`, `different`, or `unknown`
   for each; do not infer equality from `1.37`, `amd64` or a chart tag.
2. **Pin the actual installed pair.** Record Helm chart versions and archive
   digests, Substrate and kagent source commits, CRD schemas, every deployed
   image reference and running `imageID`, including `atelet`, `ateom-gvisor`,
   controller and generated Go ADK workload. The prior workplace references
   were private SNAPSHOT builds based on Substrate 0.0.9 and kagent 0.10
   (patch 1); their suffixes do **not** prove equivalence to the public
   releases. Obtain their matching source and a component-by-
   component diff before saying the runtime is the same.
3. **Trace the executable actually used.** Capture the live
   `SandboxConfig/gvisor-default` AMD64 asset URL/checksum, `atelet` image and
   asset-source settings, configured object-store endpoint and CA trust,
   node-cache path and cached-file SHA-256/size, and the `runsc_path` sent to
   `ateom-gvisor` during checkpoint. Inspect the worker pod mounts and OCI
   mount/config shape. State explicitly whether work uses internal fetch,
   cache seeding, a preinstalled host mount, or another method. A matching
   `runsc` hash proves binary identity, not an identical delivery path or
   identical Substrate source.
4. **Compare the generated workload.** Record `SandboxAgent`, generated
   immutable ActorTemplate UID/spec and golden status; command, container
   count/names, image digest, readiness probe, mounts, durable-directory
   annotations, `/data` file types/permissions, `onPause` and `onCommit`.
   Compare the failing private agent with a public Go ADK canary. Do not mutate
   an existing immutable template to make it match.
5. **Diagnose the existing failure first.** For the reported golden-suspend
   `fscheckpoint` exit 128, identify the failing RPC, snapshot scope, actor and
   worker, and capture the **first fatal `runsc` stderr line** from current and
   previous worker logs around the timestamp. Check path/permissions/disk,
   OCI mounts and unusual files or open descriptors under `/data`. In stock
   0.0.9 a golden suspend selects Data; exit 128 alone does not identify its
   cause. Keep private paths and identities out of the returned summary.

**Cross-check gate:** finish steps 1–5 and return the comparison table before
repeating an installation or lifecycle test. Resolve or explicitly account for
every material difference in source commits, image digests, node properties,
generated template, `runsc` bytes/delivery, storage and trust. Record the first
fatal stderr from the current failure. If a field is unknown, mark it unknown;
do not call the configuration identical. Preserve the current failure evidence
for comparison with the new installation.

6. **Prepare the repeat installation.** In version-controlled configuration
   for an approved non-production AKS test scope, render the exact four pinned
   charts and all images for the bank's internal registry. Include the
   generated Go ADK image, checked AMD64 `runsc`, approved snapshot store,
   CA trust, image pulls,
   namespace privileges and network policy. If internal fetch is required,
   review/port the lab `atelet` change against the *exact private source* or
   select a compatible upstream internal-only mechanism. Preserve the chosen
   asset URL/image settings in Flux desired state. A URL change alone is not
   enough: stock 0.0.9 attempts anonymous public Google Storage first.
7. **Repeat the installation and retain receipts.** Reconcile through the
   bank's GitOps path in this order: Substrate CRDs, Substrate control/data
   plane, kagent CRDs, then kagent controller and gVisor WorkerPool. Confirm
   actual running image digests, healthy control-plane pods, WorkerPool
   placement, `SandboxConfig` and internal storage/CA reachability before
   creating an agent. Use a separate test cluster or another supported
   isolated scope whose releases and cluster-scoped CRDs do not conflict with
   the existing installation. Retain its failure logs for comparison.
8. **Run the lifecycle canary and retain receipts.** Use a fresh disposable
   Go ADK `SandboxAgent` and a separately named state fixture. Require Ready
   conditions and golden readiness, an uncached internal asset fetch on the
   new test node with a verified cache checksum and public egress denied,
   then golden restore, Full pause/restore, **resume before** Data
   commit/restore, and matching agent-card responses. Mutate `/data` in the
   state fixture and assert it survives the
   documented transitions. Record the template UID/spec and golden identity
   before and after. Test a harmless real model/MCP request separately if
   integration is in scope. The older release can fail a direct
   pause-to-suspend transition with `no active worker`; do not mistake that
   for the `fscheckpoint` failure.

Read-only starting commands, with placeholders replaced locally:

```bash
WORK_CONTEXT='{{WORK_CONTEXT}}'
WORK_NODE='{{WORK_NODE}}'
kubectl --context "$WORK_CONTEXT" get node "$WORK_NODE" -o json
kubectl --context "$WORK_CONTEXT" get pods -A -o wide
kubectl --context "$WORK_CONTEXT" get sandboxconfig gvisor-default -o yaml
kubectl --context "$WORK_CONTEXT" get workerpool.ate.dev -A -o yaml
kubectl --context "$WORK_CONTEXT" get sandboxagent -A -o yaml
helm --kube-context "$WORK_CONTEXT" list -A -o json
```

These outputs can contain private identifiers, URLs and configuration. Keep
the raw files inside the approved bank location and provide only a sanitized
summary for review. For a confirmed 0.x AKS install, the repository's
[`verify-aks-substrate.sh`](scripts/verify-aks-substrate.sh) checks CRDs,
rollouts, WorkerPool replicas and generated template readiness; it does not
prove checkpoint/restore or agent calls. Do not run it as a 1.x verifier.

## Return format and decision gate

Return one table with `item | public AKS 0.0.9 | bank observed | same/different/unknown | receipt` for:
platform; node OS/kernel/arch/SKU/container runtime; Kubernetes version;
Substrate/kagent source and charts; all running image digests; WorkerPool and
generated template; `runsc` bytes/hash/cache/mount/fetch path; storage/CA;
Full/Data snapshot settings; first fatal stderr; and actual canary lifecycle.
Then state **one** of:

- `MATCHED AND WORKING CANARY`: the exact bank build and path passed the
  approved canary, including cold internal asset fetch and state assertions.
- `DIFFERENT BUT WORKING CANARY`: the bank path passed, but list each material
  difference from the public baseline.
- `BLOCKED`: name the earliest failed gate and the next evidence or compatible
  change needed. A Ready CR, matching `runsc` hash, or public AKS pass cannot
  upgrade a failed bank canary to success.

The goal is a working bank canary. Matching the known inputs increases the
chance of reproducing the public result, but the public result cannot promise
it: the private build, AKS node and failing workload may expose a difference
that the public canary did not exercise.
The bank's reported private `fscheckpoint` failure remains unresolved until
its own fatal stderr and an exact-build lifecycle establish the cause and fix.
