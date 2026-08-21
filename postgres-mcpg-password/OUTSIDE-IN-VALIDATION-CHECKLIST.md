# MCPg password bundle outside-in validation checklist

This checklist is only for the password/Secret-backed MCPg option. It must not
be used to deploy the separate FastMCP/UAMI bundle.

Use this order. Do not start with an Agent question: prove each source layer
before involving the next one. Keep connection strings, passwords, real hosts,
and result rows out of Git, tickets, and shared terminal captures.

## 1. Secret and database path

- [ ] The approved secret system creates `{{POSTGRES_MCP_SECRET_NAME}}` in
  `{{DATA_MCP_NAMESPACE}}` with the key `postgres-url`.
- [ ] The connection uses TLS (`sslmode=require` or the database-owner-required
  stronger setting).
- [ ] The identity is a dedicated non-human reader with only `CONNECT`, schema
  `USAGE`, and `SELECT` on owner-approved views.
- [ ] An AKS disposable client can resolve/reach the private endpoint on 5432
  and run one approved view query.

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{DATA_MCP_NAMESPACE}} \
  get secret {{POSTGRES_MCP_SECRET_NAME}} \
  -o go-template='{{.metadata.name}}{{" keys="}}{{range $key, $_ := .data}}{{$key}}{{" "}}{{end}}{{"\n"}}'
```

Pass: the name and `postgres-url` key exist. This template emits key names
only; never print or decode Secret values in logs.

## 2. MCPg workload

- [ ] `mcpgImage` is the approved internal MCPg v0.7.1 digest, not a tag.
- [ ] The rendered deployment has no `args:` section and no
  `--access-mode=restricted` flag.
- [ ] It sets `MCPG_ACCESS_MODE=read-only` and
  `MCPG_TRANSPORT=streamable-http`.
- [ ] The workload is Ready with no image, DNS, TLS, or database-auth errors.

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} apply --dry-run=server \
  -f {{PRIVATE_RENDERED_DIR}}/mcpg-postgres-mcp.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_RENDERED_DIR}}/mcpg-postgres-mcp.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{DATA_MCP_NAMESPACE}} \
  rollout status deploy/postgres-inventory-mcp --timeout=120s
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{DATA_MCP_NAMESPACE}} \
  logs deploy/postgres-inventory-mcp --tail=100
```

## 3. Direct MCPg discovery — no Agent

- [ ] Apply `direct-mcp-probe.yaml` after private-overlay rendering.
- [ ] `RemoteMCPServer/postgres-inventory-mcpg-direct-probe` is
  `Accepted=True` and discovers tools.
- [ ] Record the exact discovered tools. The first production allowlist must
  remain `list_schemas`, `list_tables`, and `describe_table`.

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} apply --dry-run=server \
  -f {{PRIVATE_RENDERED_DIR}}/direct-mcp-probe.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_RENDERED_DIR}}/direct-mcp-probe.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} wait \
  --for=condition=Accepted=True remotemcpserver/postgres-inventory-mcpg-direct-probe \
  --timeout=120s
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} \
  get remotemcpserver postgres-inventory-mcpg-direct-probe -o yaml
```

Delete this probe before steady state; it deliberately bypasses Agent Gateway.

## 4. Agent Gateway discovery — no Agent

- [ ] Validate the actual Gateway CRD schema and server-dry-run the route.
- [ ] Apply the route and the gateway probe.
- [ ] The route and policy are accepted/attached; the probe is accepted and
  discovers the approved tools.

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} explain agentgatewaybackend.spec.mcp
kubectl --context {{WORK_KUBE_CONTEXT}} explain agentgatewaypolicy.spec.backend.mcp.authorization
kubectl --context {{WORK_KUBE_CONTEXT}} apply --dry-run=server \
  -f {{PRIVATE_RENDERED_DIR}}/agentgateway-route.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_RENDERED_DIR}}/agentgateway-route.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_RENDERED_DIR}}/gateway-mcp-probe.yaml
```

## 5. Schema Agent and steady-state boundary

- [ ] Apply the Kustomize bundle, wait for `postgres-inventory-mcpg` to be
  accepted and `postgres-inventory-schema-agent` to be ready.
- [ ] Confirm the Agent tool list equals the Gateway allowlist exactly.
- [ ] Ask one schema-only question and save its receipt to an owner-only
  evidence location.
- [ ] Delete both probes, then apply `mcp-networkpolicy.yaml` so direct Service
  bypass is no longer possible.

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} apply -k {{PRIVATE_OVERLAY_DIR}}
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} wait \
  --for=condition=Ready=True agent/postgres-inventory-schema-agent --timeout=180s
scripts/kagent-a2a-invoke.sh \
  --context {{WORK_KUBE_CONTEXT}} \
  --agent postgres-inventory-schema-agent \
  --ns {{KAGENT_NAMESPACE}} \
  --text 'List the approved schema names only.' \
  --timeout 120 \
  --receipt-file {{PRIVATE_EVIDENCE_DIR}}/mcpg-schema-a2a.json
```
