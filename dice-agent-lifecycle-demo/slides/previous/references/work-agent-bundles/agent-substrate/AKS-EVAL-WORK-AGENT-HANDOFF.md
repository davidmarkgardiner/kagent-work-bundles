# AKS gVisor evaluation: work-agent handoff (7 October 2026)

## Live result

Two separate, disposable Azure Linux 3.0 AKS runs used **gVisor**, with no
microVM WorkerPool:

| Run | AKS | Agent Substrate | kagent | Result |
| --- | --- | --- | --- | --- |
| Baseline | 1.35.8 | 0.0.9 | 0.10 (patch 1) | Stock and internal-asset `SandboxAgent`s Ready; three extra fresh-actor cycles passed. |
| Comparison | 1.37.0 **preview** | 0.4.0-alpha1 | 1.0.0-alpha8 | `Agent` Ready with a golden Substrate template; three fresh-actor cycles passed. |

Each recorded cycle resumed from golden, did Full pause/restore and Data
commit/restore, and returned an HTTP 200 agent card that matched across both
restores. The 0.0.9 test forced a standalone `runsc` cache miss and verified the
repopulated SHA-256. The 0.4.0-alpha1 `atelet` logged a cold cache miss and
completed download for the internally served `gvisor.tar.zstd` archive. The
internal-bucket source patches in both versions passed focused tests proving
that the anonymous GCS client was not called for that bucket. Both patches are
lab deltas, not upstream releases.

The operator's private `aks-substrate-eval` evidence folder holds timestamped
inventory, chart/archive checksums, patch files, command receipts, agent cards,
asset upload/fetch receipts, and the two live reports. Keep its kubeconfigs,
Helm values, CA pools, and Azure identifiers out of Git and chat. No live UI
screenshots were captured; JSON and lifecycle command receipts are primary.

These runs do **not** prove an air gap: the clusters were Internet connected,
most images came from public registries, no public-egress deny or packet capture
was used, and no model, MCP, or chat call was made. They do not diagnose the
separate workplace `fscheckpoint` exit 128 or prove `/data` mutation survives
a restore. A `/state` request against the old kagent agent hit its A2A handler,
so it could not serve as the standalone state fixture.

After both runs, Azure confirmed the dedicated evaluation resource group and
the AKS managed node resource group were absent. The evaluation cluster and
private registry are deleted; private deletion receipts were saved.

## Exact 1.37 lessons

- UK South exposed AKS 1.37.0 as **preview** on the evaluation date. Verify the
  region and support status anew with `az aks get-versions --location
  {{AZURE_REGION}}`; require the node's `kubeletVersion` to be 1.37 and
  `osImage` to be Microsoft Azure Linux 3.0 before installation.
- This node served `certificates.k8s.io/v1` PodCertificateRequest and
  ClusterTrustBundle. The pinned Substrate controller discovers v1 and uses it.
- Substrate 0.4.0-alpha1 needs bootstrap CA pool Secrets and an API
  authentication ConfigMap that the Helm chart does not create. From the exact
  pinned Substrate source, use `ate-setup --kubeconfig {{PRIVATE_KUBECONFIG}}
  --no-dev-env create` for: `jwt-authority-pool`, `actor-id-ca-pool`,
  `actor-id-ca-certs`, `egress-mitm-ca-pool`,
  `podcertificate-controller-cas`, and `api-authentication-config`. Keep these
  Secrets private. Without them, PodCertificateRequests remain pending and
  certificate volumes cannot mount. Generate the pools before a Helm `--wait`
  install or expect to rerun the release after bootstrap.
- kagent 1.0.0-alpha8 uses `api.kagent.dev/v1alpha3 Agent` with an inline or
  referenced `Harness`. It no longer ships the old `SandboxAgent` CRD. The
  `Harness` selects a gVisor WorkerPool and a snapshot policy. Pin its Go ADK
  workload image by digest; it is not in the Helm image render. A sanitized
  [Agent example](examples/agent-v1-gvisor.yaml) shows the required shape. The kagent
  controller image tag is `1.0.0-alpha8` without a `v` prefix.
- A loopback dummy model URL failed the 1.x compatibility check for credential
  routing. Use an exact internal DNS hostname for the approved model endpoint;
  keep any credential in a Kubernetes Secret. A DNS-shaped dummy URL only
  establishes lifecycle readiness, not model connectivity.
- Substrate 0.4 ingress selects the Actor through the
  `ate-target-actor: <atespace>/<actor>` request header. The 0.0.9 Host-based
  probe returned 404 on this version.
- The pinned 0.4.0-alpha1 chart's AMD64 gVisor asset is
  `gvisor.tar.zstd`, SHA-256
  `d547d81401461fd1c679c5c4fa0a6c2b8ef7dc3c22ce23c9e25dcc4c69cfd06f`.
  The old 0.0.9 standalone `runsc` binary and patch cannot be copied across
  unchanged. Mirror the exact asset to `{{INTERNAL_BUCKET}}`, render the
  `SandboxConfig` URL to that key, and use a reviewed internal-only fetch path.

## Workplace acceptance path

1. Choose a compatible kagent/Substrate pair and validate its CRDs, chart
   archive checksums, image digests, node kernel and AKS version on a dedicated
   approved node pool. Keep the install declarative in Flux. Use the bundle's
   [air-gap guide](AIRGAPPED-AKS-README.md) for image and policy inventory.
2. Mirror **all** rendered images and the generated agent workload image into
   `{{INTERNAL_REGISTRY}}` by digest. Mirror charts and the runtime asset into
   approved internal stores. Keep CA material, model credentials, and any
   registry credentials out of Git.
3. Bootstrap CA pools, then reconcile Substrate CRDs/control plane before
   kagent CRDs/controller and its gVisor WorkerPool. Confirm the pools and
   PodCertificateRequests are healthy. Apply one disposable `Agent` with a
   digest-pinned workload and approved internal model DNS endpoint.
4. Capture Ready conditions, generated golden template, WorkerPool class and
   image, a cold internal asset fetch with matching checksum, HTTP agent-card
   response, Full pause/restore, and Data commit/restore. Use a separate state
   fixture to mutate `/data` and assert its contents across both restores.
5. Deny public egress during the cold-start run or capture equivalent flow/DNS
   evidence. Test a real harmless request through the approved internal model
   route if model integration is in scope. Keep diagnosis read-only; give
   resource-changing permissions to workflow service accounts, not chat agents.
6. If a workplace checkpoint fails, capture the first fatal `atelet`/`ateom`
   stderr, exact operation, chart/image digests, node OS/kernel, snapshot mode,
   and private actor/snapshot IDs. Do not infer workplace success from this lab.

The repository's [0.x verifier](scripts/verify-aks-substrate.sh) now uses
`WorkerPool.spec.replicas` and finds generated ActorTemplates by owner label.
It passed on the 1.35.8 run; it assumes `SandboxAgent` and is not a 1.x check.

Official references:

- https://learn.microsoft.com/en-us/azure/aks/supported-kubernetes-versions
- https://kagent.dev/docs/kagent/0.x/examples/agent-substrate/
- https://kagent.dev/docs/kagent/1.x/operations/tune-agent-substrate/
- https://www.kagent.dev/docs/kagent/1.x/setup/installation/
