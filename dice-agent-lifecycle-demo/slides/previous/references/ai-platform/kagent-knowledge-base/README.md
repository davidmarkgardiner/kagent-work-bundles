# Kagent Platform Knowledge Base POC

This proof of concept wires platform documentation into kagent using the upstream `doc2vec` + `querydoc` MCP pattern.

It replaces the custom FastAPI retrieval service idea with the kagent-native path:

```text
docs/platform-kb
  -> doc2vec indexer
  -> platform-kb.db
  -> querydoc MCP server
  -> RemoteMCPServer
  -> platform-knowledge-agent
```

## What Is Included

| Path | Purpose |
|---|---|
| `../../docs/platform-kb/` | Seed platform documentation corpus and `INDEX.md` |
| `config/doc2vec-platform-kb.yaml` | Local doc2vec config for the platform docs |
| `k8s/` | Kustomize manifests for the indexer, querydoc MCP service, RemoteMCPServer, and kagent Agent |
| `scripts/build-platform-kb-db.sh` | Build `platform-kb.db` locally or on a homelab host |
| `scripts/smoke-querydoc-local.sh` | Run a local querydoc container against a generated DB |
| `scripts/deploy-poc-demo.sh` | Apply the POC, seed the PVC with `platform-kb.db`, and verify the rollout |
| `scripts/validate.sh` | Static validation and safe render checks |
| `evidence/` | Captured validation and connectivity evidence |
| `EMBEDDING-OPTIONS.md` | Direct OpenAI, Azure OpenAI, and local OpenAI-compatible embedding options |
| `OPENAI-EMBEDDING-SETUP.md` | OpenAI model/key setup commands for the demo |
| `platform-kb-poc-presentation.html` | Static HTML presentation for review walkthroughs |

## Safety

The manifests do not create Azure resources. They create Kubernetes resources only in the `kagent` namespace:

- `PersistentVolumeClaim`
- `CronJob`
- `Deployment`
- `Service`
- `RemoteMCPServer`
- `Agent`

Do not apply these manifests to the `kind-argo-workflow` management cluster unless you intentionally want to deploy the POC there. These resources do not contain ASO `ManagedCluster`, `ResourceGroup`, or KRO AKS cluster instances.

## Quick Local Validation

Prerequisites:

- `bash`, `git`, `node`, and `npm` for local DB builds.
- `kustomize` or `kubectl` for manifest rendering.
- `rg` or `grep` for the validation safety scan.

```bash
cd ai-platform/kagent-knowledge-base
./scripts/validate.sh
```

This checks:

- scripts parse with `bash -n`;
- platform KB seed docs exist;
- doc2vec config references the expected source and database path;
- Kustomize renders all resources;
- rendered manifests do not contain known Azure-provisioning resource kinds.

## Build the Vector DB

`doc2vec` requires an embedding provider. For OpenAI:

```bash
export OPENAI_API_KEY="<key>"
cd ai-platform/kagent-knowledge-base
./scripts/build-platform-kb-db.sh
```

The script writes:

```text
dist/platform-kb.db
dist/platform-kb-manifest.json
dist/doc2vec-build.log
```

The script refuses to publish `platform-kb.db` if `doc2vec` logs embedding failures. This matters because `doc2vec` can leave a non-empty SQLite file behind even when the upstream embedding API rejected the request.

For Azure OpenAI embeddings:

```bash
export EMBEDDING_PROVIDER=azure
export AZURE_OPENAI_KEY="<key>"
export AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com"
export AZURE_OPENAI_DEPLOYMENT_NAME="text-embedding-3-large"
export AZURE_OPENAI_API_VERSION="2024-10-21"
./scripts/build-platform-kb-db.sh
```

## Run querydoc Locally

After the DB exists:

```bash
export OPENAI_API_KEY="<key>"
./scripts/smoke-querydoc-local.sh
```

This starts `ghcr.io/kagent-dev/doc2vec/mcp:2.11.0` with `dist/platform-kb.db` mounted at `/data/platform-kb.db` and checks `/health`.

## Kubernetes Deployment Flow

Prerequisites:

- kagent is already installed in the target cluster.
- The `kagent-builtin-prompts` ConfigMap exists in the `kagent` namespace.
- The target cluster can pull `node:20-bookworm` and `ghcr.io/kagent-dev/doc2vec/mcp:2.11.0`.
- The default StorageClass can bind the `platform-kb-data` `ReadWriteOnce` PVC. On multi-node or zonal clusters, keep the indexer Job and querydoc pod schedulable on the same storage topology, or switch to RWX/object-storage handoff for production.

Render only:

```bash
kustomize build k8s
```

Apply, when you intentionally want to deploy to a safe cluster:

```bash
kubectl --context <safe-context> apply -k k8s
```

Create the dedicated POC secret before the indexer, querydoc pod, or demo agent runs:

```bash
kubectl --context <safe-context> -n kagent create secret generic platform-kb-openai \
  --from-literal=OPENAI_API_KEY="<key>"
```

The POC uses a dedicated `platform-kb-openai` secret and `platform-kb-openai` `ModelConfig` so it does not depend on the shared cluster `default-model-config` or shared LiteLLM credentials.

The cluster-side indexer and querydoc pods read embedding settings from `platform-kb-embedding-config`. The default is direct OpenAI:

```yaml
EMBEDDING_PROVIDER: openai
EMBEDDING_DIMENSION: "3072"
OPENAI_MODEL: text-embedding-3-large
OPENAI_BASE_URL: https://api.openai.com/v1
```

For Azure OpenAI embeddings, patch the ConfigMap and add the Azure key to the same secret before enabling the indexer:

```bash
kubectl --context <safe-context> -n kagent patch configmap platform-kb-embedding-config \
  --type merge \
  -p '{"data":{"EMBEDDING_PROVIDER":"azure","AZURE_OPENAI_ENDPOINT":"https://{{AZURE_OPENAI_RESOURCE}}.openai.azure.com","AZURE_OPENAI_DEPLOYMENT_NAME":"text-embedding-3-large","AZURE_OPENAI_API_VERSION":"2024-10-21"}}'

kubectl --context <safe-context> -n kagent create secret generic platform-kb-openai \
  --from-literal=OPENAI_API_KEY="<chat-model-key>" \
  --from-literal=AZURE_OPENAI_KEY="<embedding-key>" \
  --dry-run=client -o yaml | kubectl --context <safe-context> apply -f -
```

Trigger an index rebuild manually:

```bash
kubectl --context <safe-context> -n kagent create job \
  --from=cronjob/platform-kb-indexer platform-kb-indexer-manual
```

The CronJob is rendered with `suspend: true` by default so it cannot start nightly embedding jobs until you intentionally enable it:

```bash
kubectl --context <safe-context> -n kagent patch cronjob platform-kb-indexer \
  --type merge -p '{"spec":{"suspend":false}}'
```

## Agent Query Contract

The `platform-knowledge-agent` should call `query_documentation` before answering platform documentation questions. Its prompt instructs it to use:

- `productName: platform-kb`
- `version: current`
- `dbName: platform-kb.db`

Answers should cite source paths. If the docs do not answer the question, the agent should say so and route the user to the platform ticket path.

The chat agent is read-only. It must not create Azure resources, modify Kubernetes resources, or push to Git. If documentation is stale or missing, it should summarize the gap and route that to the approved stale-doc PR workflow.
