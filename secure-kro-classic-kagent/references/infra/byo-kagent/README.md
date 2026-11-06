# BYO-KAgent — Platform Architecture

Self-service onboarding of kagent Agents and MCP tool servers onto the shared platform via Flux GitOps.

---

## Problem this solves

Before BYO-KAgent, every new agent was hand-authored YAML applied manually with no consistent tool-grant model, no per-team budget enforcement, no MCP tool safety verification, and no multi-cluster Flux story. Each deployment was a one-off.

BYO-KAgent gives teams a repeatable, auditable, GitOps-native path to ship their own agents and tools while the platform enforces security at admission time (Kyverno) rather than at review time.

---

## Architecture overview

```
  Agent Owner                    Platform                           Cluster
  ──────────                     ────────                           ───────

  1. Copy _template/             
     Fill request.yaml           
     Open PR labelled            
     'byo-kagent'   ──────────►  Argo Events Sensor
                                  │
                                  ▼
                                 byo-kagent-onboarding-template (Argo Workflows)
                                  │  parse request.yaml
                                  │  validate schema
                                  │  resolve ToolCatalogEntry refs
                                  │  call byo-kagent-orchestrator via A2A
                                  │    ├─ render Kustomize tree
                                  │    ├─ kyverno dry-run
                                  │    ├─ yaml-lint
                                  │    └─ post diff + checklist to PR
                                  │
  2. Review comment  ◄────────────┘
     Fix / merge

                                 Flux (management cluster)
                                  │  reconciles apps/04-applications/agents/
                                  │  postBuild substitution → target cluster
                                  ▼
                                 Flux (worker cluster)
                                  │
                                  ▼
                                 Kyverno admission
                                  ├─ Agent has ToolGrants? ✓
                                  ├─ ToolGrants resolve catalog? ✓
                                  ├─ ToolGrants not expired? ✓
                                  └─ ModelConfig via agentgateway? ✓
                                  │
                                  ▼
                                 kagent controller spins up Agent pod
                                  │
                                  ▼
  3. Post-deploy A2A  ◄──────────  kagent-validate smoke test → comment on merged PR
     smoke test result
```

---

## Components

### Platform infrastructure (`infra-stack/byo-kagent/`)

| Directory | Contents | Purpose |
|---|---|---|
| `crds/` | `ToolCatalogEntry` CRD, `ToolGrant` CRD | Two new Kubernetes CRDs that form the authorization model |
| `kyverno-policies/` | 6 `ClusterPolicy` CRs | Admission enforcement — see below |
| `bootstrap-catalog/` | 6 initial `ToolCatalogEntry` CRs + status patch commands | One-time platform bootstrap |

### Orchestrator (`ai-platform/kagent-agents/byo-kagent-orchestrator/`)

| File | Purpose |
|---|---|
| `namespace.yaml` | `kagent-platform` namespace — platform trust root, exempt from tenant policies |
| `agent.yaml` | `byo-kagent-orchestrator` kagent Agent CR — reviews PRs, renders manifests, never applies live resources |
| `remotemcpservers.yaml` | 5 tool servers the orchestrator uses (`gitlab-mcp`, `kagent-introspect-mcp`, `kyverno-cli-mcp`, `yaml-lint-mcp`, `kagent-tool-server-platform`) |
| `tool-grants.yaml` | 5 `ToolGrant` CRs authorizing the orchestrator to use its own tools |
| `rbac.yaml` | ClusterRoles + RoleBindings: read `ToolCatalogEntry`, write `ToolCatalogEntry/status`, read `gitlab-token` Secret |
| `modelconfig.yaml` | `gpt-4o-platform` — orchestrator's LLM config (platform cost bucket) |
| `team-charter-example.yaml` | `TeamCharter` ConfigMap — defines per-team cluster targeting authorization |

### Argo Workflows (`application-stack/core/argo-workflows/`)

| File | Purpose |
|---|---|
| `byo-kagent-onboarding-template.yaml` | WorkflowTemplate — orchestrates agent PR review and post-merge smoke test |
| `mcp-onboarding-template.yaml` | WorkflowTemplate — quarantine → introspect → scan → promote MCP tool servers |
| `byo-kagent-sensor.yaml` | Argo Events Sensor + EventSource — webhook listener routing PRs to the right workflow |
| `byo-kagent-rbac.yaml` | ServiceAccount + RBAC for workflow pods + `mcp-quarantine` Namespace |

### Shared model pool (`apps/03-platform/kagent-shared/`)

Three shared `ModelConfig` CRs routed through agentgateway for cost attribution:

| Name | Model | Cost tier |
|---|---|---|
| `gpt-4o` | GPT-4o | Standard |
| `claude-sonnet` | Claude Sonnet 4.6 | Premium |
| `azure-gpt-4o-uksouth` | GPT-4o, UK South data residency | Standard |

### Owner-facing template (`apps/04-applications/agents/_template/`)

| File | Purpose |
|---|---|
| `request.yaml` | Schema skeleton — agent owners fill this in |
| `README.md` | Step-by-step owner journey |

---

## The two new CRDs

### `ToolCatalogEntry` (cluster-scoped)

The verified tool registry. Each entry represents one version of an MCP tool server that the platform has quarantined, introspected, and scanned.

```yaml
apiVersion: platform.kagent.dev/v1alpha1
kind: ToolCatalogEntry
metadata:
  name: aks-mcp-v0-0-12
spec:
  name: aks-mcp
  version: v0.0.12
  description: "AKS MCP server — Azure-aware Kubernetes tools"
  source:
    url: http://aks-mcp.aks-mcp.svc.cluster.local:8000/mcp
    protocol: STREAMABLE_HTTP
status:
  verifiedAt: "2026-05-07T00:00:00Z"
  verifiedBy: byo-kagent-orchestrator
  toolCount: 8
  verifiedTools:
    - name: k8s_get_resources
      verbClassification: read
      dangerous: false
    # ...
```

**Key rules:**
- `status.verifiedAt` is immutable once set (Kyverno `protect-catalog-status` policy)
- Only `byo-kagent-orchestrator` ServiceAccount may write `/status`
- Version bumps require a new entry (e.g. `aks-mcp-v0-0-13`) — no in-place edits
- Cluster-scoped so all tenant namespaces can reference it

### `ToolGrant` (namespaced)

Per-agent authorization linking an Agent to specific tools from a verified catalog entry. Lives in the same namespace as the Agent.

```yaml
apiVersion: platform.kagent.dev/v1alpha1
kind: ToolGrant
metadata:
  name: my-agent-aks-mcp
  namespace: webx
spec:
  agentRef:
    name: frontend-debugger
  toolCatalogRef: "aks-mcp@v0.0.12"       # must match a ToolCatalogEntry name
  allowedToolNames:
    - k8s_get_resources
    - k8s_get_pod_logs
  expiresAt: "2027-01-01T00:00:00Z"        # optional
  reason: "Frontend debugging — read-only pod inspection"
```

**Why not just use `RemoteMCPServer.allowedNamespaces`?**  
`allowedNamespaces` controls which namespaces can *connect* to the MCP server — it can't express "agent X may use tool A but not tool B from the same server." `ToolGrant` adds per-agent, per-tool-name, expiry-aware authorization. The audit trail lives in the grant CR.

---

## Kyverno policies

All 6 policies run in `Enforce` mode with `background: true`. They share one carve-out: `excludeNamespaces: [kagent-platform]` (the platform trust root).

| Policy | What it blocks |
|---|---|
| `validate-agent-tool-grants` | Agent CRs with no matching `ToolGrant` for each MCP tool ref |
| `mcp-dangerous-verb` | `RemoteMCPServer` CRs leaving quarantine with `delete/exec/apply/drop/admin` tool names |
| `agent-tenant-defaults` | Tenant namespaces missing PSS restricted label, team/cost-center labels, or using ClusterRoleBinding |
| `protect-catalog-status` | Any principal other than `byo-kagent-orchestrator` writing `ToolCatalogEntry/status`; also blocks mutation of `verifiedAt` |
| `validate-modelconfig-via-litellm` | `ModelConfig` CRs not pointing at the agentgateway (unless `platform.kagent.dev/byo-model-approved=true`) |
| `validate-agent-cluster-target` | Agents without `team`/`cost-center` labels or without resource limits |

**Flux + Kyverno:** Flux applies with field manager `kustomize-controller`. None of the policies exclude this field manager — Flux gets the same enforcement as kubectl.

---

## Security model

```
Internet / tenant
       │
       │  PR to git repo (only entry point)
       ▼
  GitLab/GitHub
       │  webhook
       ▼
  Argo Events → Argo Workflows
  (parse + validate + call orchestrator — no live mutations)
       │
       │  orchestrator posts diff to PR
       ▼
  Human approves PR → git merge
       │
       ▼
  Flux reconciles → Kyverno admission
  (no ToolGrant = admission denied)
       │
       ▼
  Agent pod in tenant namespace
  ├─ PSS restricted (no root, no hostNetwork)
  ├─ NetworkPolicy: deny-all egress
  │   allow: DNS, litellm, granted MCP namespaces only
  ├─ Namespaced RBAC only (no ClusterRoleBinding)
  └─ ResourceQuota from request.yaml.budget
```

**Prompt injection mitigation:** The orchestrator string-substitutes `prompt.systemMessage` verbatim into the rendered `Agent.spec.declarative.systemMessage` — it never executes or interprets the content. The rendered diff is posted to the PR for human review before any cluster state changes.

---

## Tool verification pipeline (MCP onboarding)

When a team submits a new MCP tool server:

```
PR (label: byo-mcp-tool)
  apps/04-applications/mcp-tools/_quarantine/{vendor}/{tool}/
       │
       ▼
  mcp-onboarding-template (Argo Workflow)
       │
       ├─ 1. Deploy RemoteMCPServer in mcp-quarantine namespace
       │       allowedNamespaces: mcp-quarantine only
       │
       ├─ 2. Poll status.discoveredTools[] (kagent auto-introspects via MCP protocol)
       │
       ├─ 3. Dangerous-verb scan (Python regex: delete/exec/apply/drop/admin)
       │       FAIL → post warning, require platform-team manual review
       │
       ├─ 4. byo-kagent-orchestrator generates ToolCatalogEntry YAML via A2A
       │
       ├─ 5. Orchestrator opens follow-up PR moving to _verified/
       │       adds annotation: platform.kagent.dev/promoted-from-quarantine=true
       │
       └─ 6. Cleanup: delete quarantine RemoteMCPServer (onExit handler)
```

MCP tools needing real credentials for introspection (e.g. `aks-mcp` needs Azure identity) should use a verifier-only Azure subscription with read-only IAM via Workload Identity.

---

## Multi-cluster targeting

The existing `FluxGitOps` RGD (`infra-stack/kro-stack/definitions/uk8sfluxgitops.yaml`) is used unchanged. Agent manifests live at `apps/04-applications/agents/` (layer 04). Per-cluster overlays use `postBuild.substituteFrom` with `${CLUSTER_NAME}`:

```
apps/04-applications/agents/webx/frontend-debugger/
  base/           ← single base, cluster-agnostic
  overlays/
    red-cluster/  ← patches: replicas, resource limits
    example-cluster-prod/
```

The `FluxGitOps` CR for each cluster already has `ownerCluster` pointing at the right target. Adding a new cluster overlay is a git-only operation.

---

## Bootstrap procedure (one-time platform setup)

Run these steps in order — see the sequencing rationale in the plan file.

```bash
# 1. Install CRDs
kubectl apply -f infra-stack/byo-kagent/crds/

# 2. Install Kyverno policies (carve-out for kagent-platform built-in)
kubectl apply -f infra-stack/byo-kagent/kyverno-policies/

# 3. Apply shared ModelConfig pool (depends on agentgateway already running)
kubectl apply -k apps/03-platform/kagent-shared/

# 4. Apply bootstrap ToolCatalogEntry CRs
kubectl apply -f infra-stack/byo-kagent/bootstrap-catalog/

# 5. Patch status on bootstrap catalog entries (one-time exception)
#    See infra-stack/byo-kagent/bootstrap-catalog/BOOTSTRAP-STATUS.md
bash infra-stack/byo-kagent/bootstrap-catalog/BOOTSTRAP-STATUS.md  # contains patch commands

# 6. Create gitlab-token Secret in kagent-platform namespace
kubectl create secret generic gitlab-token \
  -n kagent-platform \
  --from-literal=token=<gitlab-api-token>

# 7. Deploy orchestrator (depends on bootstrap catalog being in place)
kubectl apply -k ai-platform/kagent-agents/byo-kagent-orchestrator/

# 8. Deploy Argo Workflows templates + RBAC + sensor
kubectl apply -f application-stack/core/argo-workflows/byo-kagent-rbac.yaml
kubectl apply -f application-stack/core/argo-workflows/byo-kagent-onboarding-template.yaml
kubectl apply -f application-stack/core/argo-workflows/mcp-onboarding-template.yaml
kubectl apply -f application-stack/core/argo-workflows/byo-kagent-sensor.yaml

# 9. Configure GitLab webhook
#    URL: http://<argo-events-ingress>/byo-kagent-webhook
#    Secret: matches byo-kagent-webhook-secret in argo-events namespace
#    Events: Merge Request events
```

**Three bootstrap exceptions** that must never be widened after go-live:
- `excludeNamespaces: [kagent-platform]` in all tenant policies
- Hand-authored `status.verifiedTools` on the 6 bootstrap catalog entries
- `byo-kagent-orchestrator` SA with `patch` on `toolcatalogentries/status`

---

## Day 2 operations

### Add a new team

Edit `ai-platform/kagent-agents/byo-kagent-orchestrator/team-charter-example.yaml`, add the team entry, open a PR with `@platform-team` approval.

### Revoke an agent

```bash
git rm -r apps/04-applications/agents/<team>/<agent-name>/
# Open PR — Flux prune deletes Agent + ToolGrants + Namespace + ExternalSecret on merge
```

Active A2A sessions are torn down by the kagent controller on Agent CR deletion. ESO `deletionPolicy: Delete` removes the synced K8s Secret.

### Revoke a tool

```bash
git rm apps/04-applications/mcp-tools/_verified/<vendor>/<tool>/toolcatalogentry.yaml
# Kyverno then blocks any Agent referencing it on next reconcile
```

Note: Kyverno background scans will flag existing Agents within one scan cycle (default 1h). Remove the agent's `ToolGrant` first if you want immediate enforcement.

### Rotate a tool version

Create a new `ToolCatalogEntry` (e.g. `aks-mcp@v0.0.13`) via the mcp-onboarding workflow. Update `ToolGrant.spec.toolCatalogRef` in the agent's PR. The old entry remains in the catalog for auditability — do not delete it until all grants are migrated.

### BYO model

Agent owner adds to `request.yaml`:

```yaml
model:
  inline:
    provider: OpenAI
    modelName: gpt-4o-mini
    secretRef: my-openai-key
```

This triggers a second approval label requirement (`infra-approved`) in the orchestrator's PR checklist and renders an `ExternalSecret` CR in the agent's base.

---

## Observability

| Signal | Where |
|---|---|
| Agent stdout/stderr | Alloy → Loki (existing LGTM stack) |
| A2A request traces | OTel collector → Tempo |
| LLM spend per team | agentgateway dashboard (`team` label on each `ModelConfig`) |
| Workflow execution history | Argo Workflows UI |
| Kyverno policy violations | `kubectl get policyreport -A` |
| Tool catalog status | `kubectl get toolcatalogentries` |
| Active ToolGrants | `kubectl get toolgrants -A` |

---

## File map

```
infra-stack/byo-kagent/
├── README.md                              ← this file
├── crds/
│   ├── toolcatalogentry-crd.yaml          ← ToolCatalogEntry CRD (cluster-scoped)
│   ├── toolgrant-crd.yaml                 ← ToolGrant CRD (namespaced)
│   └── kustomization.yaml
├── kyverno-policies/
│   ├── validate-agent-tool-grants.yaml
│   ├── mcp-dangerous-verb.yaml
│   ├── agent-tenant-defaults.yaml
│   ├── protect-catalog-status.yaml
│   ├── validate-modelconfig-via-litellm.yaml
│   ├── validate-agent-cluster-target.yaml
│   └── kustomization.yaml
└── bootstrap-catalog/
    ├── BOOTSTRAP-STATUS.md                ← kubectl patch commands for initial status
    ├── toolcatalogentry-aks-mcp.yaml
    ├── toolcatalogentry-kagent-tool-server.yaml
    ├── toolcatalogentry-gitlab-mcp.yaml
    ├── toolcatalogentry-kagent-introspect.yaml
    ├── toolcatalogentry-kyverno-cli.yaml
    ├── toolcatalogentry-yaml-lint.yaml
    └── kustomization.yaml

ai-platform/kagent-agents/byo-kagent-orchestrator/
├── namespace.yaml                         ← kagent-platform namespace
├── agent.yaml                             ← byo-kagent-orchestrator Agent CR
├── remotemcpservers.yaml                  ← 5 orchestrator tool servers
├── tool-grants.yaml                       ← 5 ToolGrant CRs
├── rbac.yaml                              ← ClusterRoles + Bindings
├── modelconfig.yaml                       ← gpt-4o-platform ModelConfig
├── team-charter-example.yaml              ← TeamCharter ConfigMap (edit to add teams)
└── kustomization.yaml

application-stack/core/argo-workflows/
├── byo-kagent-onboarding-template.yaml    ← WorkflowTemplate: agent PR review
├── mcp-onboarding-template.yaml           ← WorkflowTemplate: MCP tool quarantine
├── byo-kagent-sensor.yaml                 ← Argo Events Sensor + EventSource
└── byo-kagent-rbac.yaml                   ← Workflow SA + mcp-quarantine Namespace

apps/03-platform/kagent-shared/
├── modelconfig-gpt-4o.yaml
├── modelconfig-claude-sonnet.yaml
├── modelconfig-azure-uksouth.yaml
└── kustomization.yaml

apps/04-applications/agents/
└── _template/
    ├── request.yaml                        ← schema skeleton for agent owners
    └── README.md                           ← owner-facing submission guide
```
