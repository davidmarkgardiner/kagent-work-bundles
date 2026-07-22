# GitLab Issue: Evaluate kagent SandboxAgent / Agent Substrate on Air-Gapped AKS

## What this is for

Evaluate whether Agent Substrate can run kagent `SandboxAgent` workloads on a
dedicated non-production AKS node pool in an air-gapped environment.

This is **not** required for the initial evidence-first triage agent. A normal
read-only kagent `Agent` can run without Agent Substrate. This evaluation is for
the optional gVisor actor runtime, where idle Go declarative agents suspend to
snapshots and resume on demand.

```text
SandboxAgent -> kagent controller -> Agent Substrate WorkerPool -> gVisor actor
```

## Benefits if successful

- Stronger runtime isolation for agent code through gVisor actors.
- Lower idle cost: agents can suspend rather than retain one always-on pod each.
- Higher density for intermittent workloads such as triage, investigations and
  team-specific assistants.
- Fast resume with preserved session/scratch state through snapshots.
- Kubernetes-native lifecycle: WorkerPools and agent declarations remain
  GitOps-managed resources.

## Scope

- One dedicated non-production AKS node pool; tainted and labelled for
  Substrate only.
- One test `SandboxAgent` using the Go declarative runtime.
- One approved internal model/provider route.
- End-to-end proof: Ready -> request -> suspend -> restore.
- No production migration, no production workload, and no conversion of the
  existing evidence-first triage agent in this issue.

## Helm charts to mirror and deploy

Mirror pinned, tested compatible versions into `{{INTERNAL_REGISTRY}}`. Do not
use unpinned or `latest` versions.

```text
oci://ghcr.io/kagent-dev/substrate/helm/substrate-crds
oci://ghcr.io/kagent-dev/substrate/helm/substrate
oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds
oci://ghcr.io/kagent-dev/kagent/helm/kagent
```

Flux deployment order:

```text
1. substrate-crds
2. substrate control/data plane in ate-system
3. kagent-crds
4. kagent upgrade with controller.substrate.enabled=true
   and substrateWorkerPool.create=true
5. test SandboxAgent
```

`SandboxAgent` is a kagent CRD, but it needs the separately deployed Agent
Substrate WorkerPool/runtime to execute. Upgrading kagent alone is insufficient.

## Air-gapped artifact and image requirements

- Download, checksum and mirror all four OCI chart archives.
- Render the exact Helm values before the installation and mirror **every image
  reference by digest**, including:
  - Agent Substrate API/controller/network/node components;
  - gVisor worker (`ateom`) image;
  - bundled or approved replacement Valkey and snapshot/object-storage images;
  - kagent controller, UI, tools and Go agent-runtime images; and
  - selected model/provider sidecar or route dependencies, if any.
- **Go ADK agent-runtime image is not in the Helm render.** The controller injects
  it at runtime into the `ActorTemplate`, pinned to
  `cr.kagent.dev/kagent-dev/kagent/golang-adk@sha256:<digest>` — which in kagent
  0.9.9 does not resolve. Mirror that digest **from GHCR**
  (`ghcr.io/kagent-dev/kagent/golang-adk`) and add a cluster-wide image-rewrite /
  registry-mirror policy for `cr.kagent.dev/*`. Without it, actors never boot.
- Configure internal registry CA trust and image-pull identity.
- Use a Secret reference for model credentials; do not store credentials in
  Helm values, Git, manifests, shell history or issue comments.
- Capture the final chart/image digest inventory as issue evidence.

Reference image-discovery command, run against the exact pinned internal chart
and values:

```bash
helm template substrate {{INTERNAL_REGISTRY}}/substrate/helm/substrate \
  --version {{SUBSTRATE_VERSION}} --namespace ate-system \
  -f substrate-values.yaml > substrate.rendered.yaml

helm template kagent {{INTERNAL_REGISTRY}}/kagent/helm/kagent \
  --version {{KAGENT_VERSION}} --namespace kagent \
  -f kagent-substrate-values.yaml > kagent.rendered.yaml

rg '^\s*image:' *.rendered.yaml
```

## AKS prerequisites and gates

- Approved Kyverno/admission-policy exception scoped only to `ate-system` and
  the WorkerPool namespace for required gVisor/checkpoint-restore privileges.
- Approved Pod Security Admission labels for those namespaces.
- Dedicated recent Ubuntu node pool with required kernel checkpoint/restore
  support, proved before broader use.
- No regular workloads scheduled on the Substrate node pool.
- Approved snapshot/object-storage, encryption and retention design.
- Approved internal model endpoint reachable from the actor network path.
- No external registry or public model endpoint dependency after deployment.

## Quick operational checks

After Flux reconciles the charts and the test agent, run:

```bash
bash work-agent-bundles/agent-substrate/scripts/verify-aks-substrate.sh \
  --context {{KUBE_CONTEXT}} \
  --sandboxagent hello-substrate
```

Expected final marker:

```text
AKS_SUBSTRATE_VERIFY: PASS
```

This is a read-only check. It verifies the required CRDs, `ate-system` rollout,
WorkerPool, kagent controller, SandboxAgent Ready condition and generated
ActorTemplate. It does not replace the final suspend/restore proof.

## Acceptance criteria

- [ ] Charts and every rendered image are mirrored, checksum/digest recorded,
  and pulled from the internal registry only.
- [ ] Go ADK agent-runtime image mirrored from GHCR and `cr.kagent.dev/*`
  rewrite/mirror policy in place; a test actor boots (golden snapshot ready).
- [ ] Flux reconciles the four Helm releases in dependency order.
- [ ] `ate-system` control/data-plane components are healthy on the dedicated
  node pool.
- [ ] kagent controller is healthy with Substrate integration enabled.
- [ ] Test `SandboxAgent` is `Ready=True` and has an ActorTemplate/WorkerPool.
- [ ] Test request reaches the approved internal model route.
- [ ] Actor suspends, restores with state intact, and evidence is attached.
- [ ] Admission, image-pull, model-route and checkpoint/restore failure paths
  are documented with rollback steps.
- [ ] No secrets, private endpoints or internal identifiers are committed.

## Decision at close

Close with one of:

- **Proceed to limited platform pilot** — only after all acceptance criteria
  pass and an owner accepts the privileged-runtime risk.
- **Keep as lab-only** — runtime works but cost, policy or operational overhead
  is not justified.
- **Do not adopt** — one or more AKS gates cannot be satisfied safely.

## Supporting material

- `work-agent-bundles/agent-substrate/AIRGAPPED-AKS-README.md`
- `work-agent-bundles/agent-substrate/WORK-CLUSTER-ADAPTATION.md`
- `work-agent-bundles/agent-substrate/scripts/verify-aks-substrate.sh`
