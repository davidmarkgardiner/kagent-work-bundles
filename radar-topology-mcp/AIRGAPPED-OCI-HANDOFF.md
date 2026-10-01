# Work-agent handoff: air-gapped Radar + existing vector KB

TLDR: mirror the pinned Radar image and chart into the existing internal OCI
snapshot registry; use Radar read-only MCP plus the existing querydoc/vector KB.
Preserve workplace kagent, ModelConfig, credentials, KB ACLs and GitOps delivery.
The lab proves integration, not production acceptance or token savings.

## Before workplace acceptance

1. Exclude expired/unapproved documents during corpus publication. The lab
   Agent flagged expiry but repeated diagnostic content: prompt-only expiry
   handling is PARTIAL. This is the main issue to close.
2. Replace the synthetic runbook with approved workplace documentation carrying
   component, stable workload, namespace applicability, version, revision,
   source and review/expiry dates. Do not promote fictional incident history.
3. Repeat positive, unrelated, wrong-scope, expiry and Pod-churn tests with real
   approved cases; require completed A2A answers, cited sources and tool traces.
   Compare latency and cumulative input/output tokens against the existing
   Agent on identical cases before claiming savings.
4. Confirm installed kagent CRD/runtime compatibility. Tested: 0.10.1 Go.
   Proxmox 0.7.13 exhibited A2A response cleanup failures. Do not blindly upgrade
   workplace kagent; use its approved version and change process.

## Import inventory

| Artifact | Import requirement |
|---|---|
| `ghcr.io/skyhook-io/radar:1.15.0` | Required if Radar is not already mirrored/deployed. OCI index digest: `sha256:0ad9633ca5a5c172969facba30f867ab35b60d878e7749a4edc50fd42aaa8d93`. |
| Radar chart `radar-1.15.0.tgz` | Required for the Radar Helm installation below. Archive SHA256: `7407b294ebb2b52482234e1630d8a111333b6e3c68e9e6bdbba58c474c0e334c`. |
| `ghcr.io/kagent-dev/doc2vec/mcp:2.11.0` | Only if the existing querydoc service is absent or needs this reviewed version. OCI index digest: `sha256:a67a75528544767a76f35f2a24b7ca8e2d8c592e8e6362f2d18132b772742425`. |
| Approved internal doc2vec indexer image | Only if an internal indexing pipeline is absent. Build with doc2vec source pinned to `v2.11.0` (Git SHA `bf8de0ad90ddef87a24fe170c0e7f847181cf0b6`). Bake dependencies into the image. |
| Approved internal embedding service image + model/tokenizer/config weights | Only if no approved reachable embedding endpoint exists. Preserve exactly the same model and vector dimension for indexing and query embedding. Model weights are additional assets, not guaranteed to be inside a server image. |
| `ghcr.io/kagent-dev/kagent/golang-adk:0.10.1` | Reference lab runtime only. Reuse workplace's installed runtime; mirror this only as part of an approved compatible kagent deployment. |

Copy all required node architectures using the organisation's image mirroring
pipeline; verify destination digests and supply internal registry pull access.
Do not substitute the Mac arm64 lab image for an amd64 workplace workload.
No custom guidance MCP image is required. Radar uses an in-memory cache here;
no extra graph database or PostgreSQL is required for this evaluation profile.

Chart source (the Helm package is `.tgz`, not a GitHub source ZIP):
https://github.com/skyhook-io/helm-charts/releases/download/radar-1.15.0/radar-1.15.0.tgz

The upstream chart is published in the standard repository:
https://skyhook-io.github.io/helm-charts

## Connected import machine

These are instructions for the approved import pipeline; they have not been
executed against a workplace registry. Authenticate using existing registry
credentials without placing them in files or commands shown here.

```bash
helm pull radar --repo https://skyhook-io.github.io/helm-charts --version 1.15.0
sha256sum radar-1.15.0.tgz
helm push radar-1.15.0.tgz oci://{{SNAPSHOT_REGISTRY}}/{{HELM_REPOSITORY_PATH}}
```

`helm push` infers `radar:1.15.0` from the package. The push destination omits
`/radar`; pull/install references include it. Record the resulting OCI chart
manifest digest. The archive checksum above is NOT the OCI manifest digest.

Mirror the image separately into
`{{SNAPSHOT_REGISTRY}}/{{IMAGE_REPOSITORY_PATH}}/radar:1.15.0` using the existing
organisation pipeline. Importing a Helm chart does not import its container image.

## Inside the air gap

1. Fill the bundle configuration with existing namespaces/ModelConfig and the
   internal Radar image repository. Render with `scripts/render.py`. Its stock
   Flux template points to the public HelmRepository: replace that with your
   existing internal OCI source/delivery pattern before committing it.
2. Apply the reviewed namespace, selected inventory ServiceAccount/RBAC and
   NetworkPolicy manifests through the existing delivery flow. The values use
   `rbac.create=false` and `serviceAccount.create=false`, so these are prerequisites.
3. Pull/render the chart from the internal OCI registry, run server dry-run on
   the generated Kubernetes manifests, then deliver the pinned chart:

   ```bash
   helm pull oci://{{SNAPSHOT_REGISTRY}}/{{HELM_REPOSITORY_PATH}}/radar --version 1.15.0
   helm upgrade --install radar-topology \
     oci://{{SNAPSHOT_REGISTRY}}/{{HELM_REPOSITORY_PATH}}/radar \
     --version 1.15.0 --namespace {{RADAR_NAMESPACE}} \
     --kube-context {{APPROVED_CONTEXT}} -f generated/values.yaml --wait --timeout 5m
   ```

   Use the organisation's immutable OCI digest pinning where supported. The
   rendered values disable cloud reporting, external ingress and timeline DB
   persistence, and use the internal container repository. Review registry trust,
   pull credentials and NetworkPolicy with workplace conventions.
4. Wire the existing kagent Agent to Radar's internal Service endpoint
   `/mcp-readonly`. Use `knowledge/render.py` for the separate read-only Agent
   delta pointing to the existing Radar and querydoc RemoteMCPServer names. The
   two exposed tools are `get_neighborhood` and `query_documentation`.
5. Reuse the existing KB service. If deploying querydoc afresh, adapt
   `ai-platform/kagent-knowledge-base/k8s` into the workplace's standard manifest
   or internal Helm packaging. This bundle does not provide an independently
   verified upstream querydoc Helm chart. Serve an approved indexed database;
   configure an internal embedding endpoint, not the temporary Mac lab server.
6. Verify readiness, read-only RBAC denials, enforced ingress restrictions,
   actual MCP calls, ordered Radar-response-before-KB-search traces and completed
   A2A artifacts. Run the representative case set above.

## Air-gap dependency trap

Mirroring `node:20-bookworm` alone does NOT make the example indexer offline.
Its CronJob clones public GitHub repositories and runs npm install. Replace that
with a prebuilt internal indexer containing pinned doc2vec/npm dependencies,
internal Git documentation sources and an approved internal embedding endpoint;
or use the existing internal indexing pipeline to publish the database. Keep
scheduling suspended until this path works with public egress blocked.

The lab's small MiniLM model and Python endpoint are reproducibility fixtures,
not a requirement to install another service at work. Prefer the existing
approved embedding service. Index and query vectors must match; switching model
or dimension requires rebuilding the DB. Check actual stored chunk/document
counts; a nonempty DB file and successful-looking logs are insufficient.

See [KNOWLEDGE-INTEGRATION.md](KNOWLEDGE-INTEGRATION.md) and the
[live evaluation receipt](KNOWLEDGE-VERIFICATION-2026-10-01.md).

Official OCI command semantics: https://helm.sh/docs/topics/registries/
