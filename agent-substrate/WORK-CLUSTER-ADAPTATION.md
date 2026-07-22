# Running Agent Substrate on the Work Cluster (AKS)

Answers the practical question: *we don't want kind or GKE — can we run this on our AKS
clusters, and how?* Short answer: **the install is portable, the gVisor requirement is the
gate.**

---

## It is open-source and not tied to Google

Agent Substrate is Apache-licensed and self-hostable
(https://github.com/agent-substrate/substrate). It ships as **generic OCI Helm charts**:

```
oci://ghcr.io/kagent-dev/substrate/helm/substrate-crds   # CRDs
oci://ghcr.io/kagent-dev/substrate/helm/substrate        # control + data plane
oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds         # kagent CRDs (>= 0.9.7)
oci://ghcr.io/kagent-dev/kagent/helm/kagent              # kagent + substrate flags
```

The `kind` and `GKE` paths in the upstream docs are only **cluster-bootstrap convenience**
(`hack/create-kind-cluster.sh`, `tools/setup-gcp bootstrap`). The runtime itself is these
charts — which is exactly what [`scripts/install-substrate.sh`](scripts/install-substrate.sh)
runs. Those charts install on **any conformant Kubernetes cluster, including AKS**.

## The real gate: gVisor checkpoint/restore

Substrate's suspend/resume needs gVisor (`runsc`) checkpoint/restore (CRIU):

- **GKE is first-class** because **GKE Sandbox provides managed gVisor**. AKS has **no
  managed gVisor equivalent**.
- Substrate ships its own gVisor userspace **inside the `ateom-gvisor` pod** (gVisor-in-pod,
  not a node `RuntimeClass`), so AKS does **not** need a special node runtime.
- But checkpoint/restore still requires **privileged / elevated pod capabilities** and a
  **node kernel** that supports the C/R syscalls.

So on AKS the question is not "will the charts install" (they will) — it's **"will admission
control let privileged gVisor actor pods run, and does the node kernel support C/R."**

## AKS blockers to clear first

1. **Admission policy (the #1 blocker).** Our work AKS clusters run **Kyverno** (seen on the
   `uk8s-tsshared-*` contexts). Privileged pods, `SYS_ADMIN`/`SYS_PTRACE` capabilities, and
   host access will be **denied** by default. You need policy exceptions scoped to
   `ate-system` + the worker pool namespace, or a `PolicyException`/exclusion.
2. **Pod Security Admission.** Namespaces default to `restricted`. `ate-system` and the
   worker-pool namespace must be labelled `pod-security.kubernetes.io/enforce: privileged`.
3. **Node kernel / node pool.** Use a recent Ubuntu node image. Deep C/R can need
   `SeccompDefault` relaxed and kernel features present; validate on a **dedicated,
   tainted node pool** you can label for substrate workers — don't co-schedule with normal
   app pods.
4. **Egress / model reachability.** The actor makes the LLM call from inside the cluster. On
   AKS point `default-model-config` at either the in-cluster AI gateway (as `red` does) or an
   approved egress endpoint (Azure OpenAI). See
   [`examples/modelconfig-openrouter.yaml`](examples/modelconfig-openrouter.yaml) for the
   shape.
5. **Image pull.** Mirror `ghcr.io/kagent-dev/substrate/*` into ACR if GHCR egress is
   restricted.

## Recommended AKS rollout path

Do **not** graft this onto a shared prod cluster first.

1. **Prove on kind (done in this bundle).** Baseline evidence in [`evidence/`](evidence/).
2. **Dedicated AKS dev cluster or dedicated node pool.** Isolated, tainted, labelled for
   substrate; nothing else scheduled there.
3. **Clear the 5 blockers above** — the Kyverno exception is the long pole; engage whoever
   owns policy early.
4. **Install through the air-gapped GitOps path.** Follow
   [`AIRGAPPED-AKS-README.md`](AIRGAPPED-AKS-README.md): mirror pinned charts and images,
   reconcile the four Helm releases through Flux, then run its read-only verifier. Do not
   adapt `scripts/install-substrate.sh` for AKS; it is intentionally a kind-only demo
   installer with demo credential handling and a version-specific workaround.
5. **Validate the actual property**, not just "pods Running": confirm an actor goes
   `Suspended`, holds ~0 RAM, then **restores with state intact**. If C/R fails on the AKS
   kernel, this is where it shows — capture the `ateom-gvisor` logs.

## Honest verdict for AKS

- **Feasible?** Yes — charts are portable; gVisor is in-pod so no managed runtime needed.
- **Easy?** No. The privileged-pod + Kyverno exception on locked-down AKS is real work, and
  node-kernel C/R support must be validated, not assumed.
- **Worth it now?** Only if you have a **large fleet of idle Go-ADK agents**. Two blockers cap
  near-term value on our estate: (a) substrate is **Go ADK only** while our existing agents
  are `runtime: python`, and (b) it's **v0.0.x pre-production**. Recommended as a **platform
  readiness / evaluation** track, not a prod migration yet.

## If AKS policy is a hard no

Fallbacks that still deliver the capability:
- **Dedicated GKE Sandbox cluster** — least-friction managed gVisor, first-class support.
- **Self-managed cluster** (kubeadm on VMs you own) where you control admission + kernel —
  what the Geekom kind run effectively is, scaled up.
