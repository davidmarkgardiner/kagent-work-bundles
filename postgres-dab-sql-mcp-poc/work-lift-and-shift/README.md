# Azure PostgreSQL data MCP — work lift-and-shift bundle

This is a **non-production, placeholder-safe deployment bundle** for the next
AKS proof with the database team:

```text
kagent inventory Agent
  -> RemoteMCPServer (explicit tool allowlist)
  -> Agent Gateway route (optional policy and telemetry boundary)
  -> pre-built PostgreSQL MCP service (restricted mode)
  -> Azure PostgreSQL endpoint over approved private network/TLS
```

The database identity belongs only to the MCP workload. The kagent Agent and
`RemoteMCPServer` must never receive a database connection string, password,
or Entra access token.

## Status and honest boundary

| Claim | Status | Evidence / decision |
|---|---|---|
| kagent can discover explicit tools from the pre-built PostgreSQL MCP and return synthetic PostgreSQL facts | **Verified current capability** | [Azure run record](../evidence/AZURE-FLEXIBLE-SERVER-PREBUILT-MCP-POC-2026-08-13.md) proves `list_objects`, `get_object_details`, and `execute_sql` receipts. |
| kagent can consume an MCP route through Agent Gateway | **Verified current capability** | Proven for the separate GitLab MCP route in this repository; it is not a live Azure-PostgreSQL route proof. |
| This bundle's Agent Gateway route works with the installed work release | **Unknown / requires validation** | Validate the work CRDs with server dry-run before applying. |
| Pre-built generic MCP is safe for routine governed production questions | **Proposed design** | It has a broad `execute_sql` tool. The real boundary is a database role limited to approved views; a thin parameterised MCP is the preferred later hardening. |
| Username/password bootstrap works | **Proposed design** | The tested image consumes `DATABASE_URI`; work credentials and network/TLS remain environment-owned. |
| UAMI/AKS Workload Identity authenticates the selected image to PostgreSQL | **Unknown / requires validation** | Workload Identity alone does not teach a generic image how to acquire an Entra token or construct a PostgreSQL connection. Validate image support or use a small approved adapter. |

## Files

| File | Purpose |
|---|---|
| [prebuilt-postgres-mcp.yaml](prebuilt-postgres-mcp.yaml) | MCP Deployment and internal Service. Uses a Secret reference only; no connection material is committed. |
| [agentgateway-route.yaml](agentgateway-route.yaml) | Gateway backend, route, and exact tool policy template. Apply only after server-side schema validation. |
| [kagent-agent.yaml](kagent-agent.yaml) | `RemoteMCPServer` pointing at the gateway and two least-privilege Agent examples. |
| [direct-mcp-probe.yaml](direct-mcp-probe.yaml) | No-Agent direct MCP registration probe: isolates the MCP service before Gateway and Agent wiring. |
| [gateway-mcp-probe.yaml](gateway-mcp-probe.yaml) | No-Agent gateway registration probe: isolates the route/policy before Agent wiring. |
| [OUTSIDE-IN-VALIDATION-CHECKLIST.md](OUTSIDE-IN-VALIDATION-CHECKLIST.md) | Ordered source-first tests and expected evidence/failure ownership. |
| [WORK-LIFT-AND-SHIFT-CRITIQUE-PROMPT.md](WORK-LIFT-AND-SHIFT-CRITIQUE-PROMPT.md) | Read-only review prompt for a second agent. |

The supplied Deployment deliberately references the **same source image used in
the HomeLab and Azure proof**: `crystaldba/postgres-mcp`, with the same
`--access-mode=restricted --transport=sse` arguments. The lab ran its mutable
`latest` tag; work must resolve that tested source to an immutable digest,
scan/sign it, and mirror it as
`{{INTERNAL_REGISTRY}}/third-party/crystaldba/postgres-mcp@{{IMAGE_DIGEST}}`.
Do not substitute an image called `crystaldba-postgres-mcp`—that would not be
the same repository.

## Inputs required before any work deployment

The supplied table/column spreadsheet is enough to begin tool and view design.
It is not by itself enough to run a safe cluster proof. Record these values in
the work change record or approved secret store—not in Git:

1. PostgreSQL hostname, port, database name, CA/TLS mode, and AKS private DNS/
   Private Endpoint reachability.
2. The `{{POSTGRES_MCP_SECRET_NAME}}` Secret created by the approved secret
   delivery mechanism, containing only `postgres-url`. Its value is a TLS
   connection URI for a dedicated non-human reader. Do not paste it into a
   manifest, issue, terminal capture, or Agent prompt.
3. A dedicated database role with `CONNECT`, schema `USAGE`, and `SELECT` only
   on the owner-approved views—not tables, functions, DDL, or DML.
4. Exact lower-case table/view names, primary keys and join relationships, data
   classification/masking rules, and five initial questions with expected
   redacted answers.
5. An internal, scanned and signed image mirror plus immutable digest for the
   tested MCP image. `latest` is prohibited.
6. Approved work namespace, kagent `ModelConfig`, Agent Gateway service name,
   and a non-production change window/rollback owner.

For the first proof, create views that expose only the minimum inventory facts,
for example a namespace inventory view joining `aks_estate`, `uk8s_namespaces`,
and (when justified) `uk8s_appdir`. Give the reader role access to those views
only. The view and database grants, not the agent instruction, are the security
boundary for a generic SQL tool.

## Deployment sequence

1. **Preflight the path.** Confirm the AKS workload subnet can resolve and
   reach the PostgreSQL private endpoint on 5432, TLS validates using the
   approved CA, and the reader role can run one approved `SELECT` from a
   disposable client. Confirm that no production data is in the initial view.
2. **Mirror the image.** Pull the exact tested image in an approved connected
   environment, scan/sign it, push it to the internal registry, record its
   digest, and replace `{{INTERNAL_REGISTRY}}` and `{{IMAGE_DIGEST}}` only in
   the private work overlay.
3. **Deliver the password Secret out of band.** Use the approved secret-store
   integration (for example, a SecretProviderClass or ExternalSecret). It must
   materialise `postgres-url` in `{{POSTGRES_MCP_SECRET_NAME}}` in
   `{{DATA_MCP_NAMESPACE}}`; do not create a literal Secret manifest from this
   repository.
4. **Apply the MCP service.** Render and apply
   `prebuilt-postgres-mcp.yaml`. It was live-tested with
   `--access-mode=restricted --transport=sse`; restricted mode is not a
   substitute for database grants. The template supplies a non-root pod and
   container security context, RuntimeDefault seccomp, dropped Linux
   capabilities, disabled privilege escalation, and CPU/memory requests and
   limits. Both generated kagent Agent pods carry the same baseline controls
   and their own CPU/memory requests and limits. Smoke-test the digest-pinned
   image and generated Agent pods under these contexts before relying on them;
   only then consider `readOnlyRootFilesystem: true` if compatible.
5. **Put the service behind Agent Gateway when the work CRDs accept it.** Run
   the schema gate below, render `agentgateway-route.yaml`, then use the gateway
   URL from `kagent-agent.yaml`. If the gateway CRDs do not accept the template,
   stop: use the direct internal `RemoteMCPServer` URL only for a separately
   approved limited proof, and open a gateway compatibility task. Do not
   improvise an older CRD shape.
6. **Register tools, then bind Agents.** Apply `kagent-agent.yaml`, wait for
   `RemoteMCPServer` discovery, and replace the example `toolNames` with the
   exact names in `.status.discoveredTools`. Start the schema Agent first.
   Grant the query Agent only after the view, database grants, and test cases
   are approved.
7. **Run the acceptance and negative tests.** Record the artefacts below, then
   remove temporary Agents/route and revoke temporary reader access if this is
   a one-off proof.

For the safer source-first order requested for work, use the dedicated
[outside-in validation checklist](OUTSIDE-IN-VALIDATION-CHECKLIST.md) instead
of starting with an Agent question.

### Agent Gateway schema gate

Run these commands against the intended cluster before applying the route:

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} api-resources | rg -i 'agentgateway|httproute'
kubectl --context {{WORK_KUBE_CONTEXT}} explain agentgatewaybackend.spec.mcp
kubectl --context {{WORK_KUBE_CONTEXT}} explain agentgatewaypolicy.spec.backend.mcp.authorization
kubectl --context {{WORK_KUBE_CONTEXT}} apply --dry-run=server -f agentgateway-route.yaml
```

The expected capabilities are a static Streamable HTTP MCP backend, an
`HTTPRoute`, and a tool-name authorization policy. A server-side dry-run is the
gate because Agent Gateway schemas change across releases.

### Read-only verification commands

Run these after the private overlay has been rendered and applied. They require
cluster read access only; save any A2A receipt in an owner-only evidence store,
not this public repository.

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{DATA_MCP_NAMESPACE}} \
  rollout status deploy/postgres-inventory-mcp --timeout=120s
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} \
  get remotemcpserver postgres-inventory-mcp -o yaml
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} \
  get agent postgres-inventory-schema-agent postgres-inventory-query-agent -o yaml

# After confirming the exact discovered tool names, run one approved question.
# The helper owns the correct A2A envelope and trailing slash.
scripts/kagent-a2a-invoke.sh \
  --context {{WORK_KUBE_CONTEXT}} \
  --agent postgres-inventory-query-agent \
  --ns {{KAGENT_NAMESPACE}} \
  --text 'List the approved namespace inventory fields only.' \
  --timeout 120 \
  --receipt-file {{PRIVATE_EVIDENCE_DIR}}/postgres-inventory-a2a.json
```

Before calling the query Agent, inspect
`RemoteMCPServer.status.discoveredTools` in the YAML output and confirm that
the Agent's `toolNames` exactly match the approved final names. The helper uses
`jq`; include it in the verifier image or install it before invoking.

## Password bootstrap, then UAMI migration

**Bootstrap now:** The pre-built MCP reads `DATABASE_URI` from a namespaced
Kubernetes Secret supplied by the approved secret system. The database team
issues a short-lived, least-privilege reader username/password. Rotate it after
the proof. This is the shortest path to reproduce the live integration.

**Target identity later:** AKS Workload Identity is a sound target shape:

```text
MCP ServiceAccount -> AKS federated credential -> UAMI
  -> Entra PostgreSQL token -> PostgreSQL role mapped to that identity
```

That migration requires all of the following: a UAMI and federated credential,
an annotated ServiceAccount/workload label, Azure PostgreSQL Entra
administrator/role mapping, private network/DNS, and an MCP image or approved
sidecar that obtains and refreshes the correct database token. Do not remove
the password bootstrap until an independent live test proves this complete
chain. Agent Gateway can protect and observe MCP traffic; it does not replace
the database authentication mechanism.

## First proof acceptance and evidence contract

The initial proof passes only if all of these are true:

- `postgres-inventory-mcp` is Ready with zero unexpected restarts; it contains
  no credential value in its rendered pod spec or logs.
- `RemoteMCPServer` is `Accepted=True`; capture its exact discovered tool list.
- Both applicable kagent Agents are `Accepted=True, Ready=True` and each mounts
  only its explicit permitted tools.
- A conversational request produces the expected redacted answer, accompanied
  by a sanitised MCP tool receipt/query audit record.
- An out-of-scope table/view, a write attempt, and a request for credentials
  are denied or absent from the permitted surface. Do not test DML against a
  shared database.
- A read-only verifier can reproduce the status/tool checks and conclude pass
  or fail without access to the password.

Attach these to the work card: rendered manifests with Secret values redacted,
`kubectl get/describe` status, relevant MCP/controller logs with secrets
redacted, `RemoteMCPServer.status.discoveredTools`, agent/controller history,
sanitised answer/tool receipt, database audit/query identifier, changed-file
list, image digest/scan evidence, and cleanup or handover receipt.

## Known limitations and next decision

- The Microsoft DAB PostgreSQL experiment in the parent POC was partial; it is
  not selected as this work candidate.
- The pre-built server exposes a generic query tool. For sustained use, choose
  either data-owner-approved curated views plus strong DB grants, or replace it
  with a thin parameterised MCP that exposes only named business functions.
- Do not claim row-level security, UAMI authentication, Agent Gateway policy
  enforcement, or production-data readiness until each is live-proven in work.

Use the supplied [critique prompt](WORK-LIFT-AND-SHIFT-CRITIQUE-PROMPT.md)
before implementation to obtain an independent GO / NO-GO assessment.
