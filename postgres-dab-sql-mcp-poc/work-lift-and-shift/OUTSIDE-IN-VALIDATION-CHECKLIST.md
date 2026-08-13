# Source-first validation — Azure PostgreSQL MCP

Run this checklist in order. Do **not** deploy an Agent until the direct MCP
and gateway stages pass. This localises a failure to its earliest responsible
layer instead of making a model/prompt failure look like a database problem.

All placeholders are rendered only in the private work overlay. Do not capture
or paste the connection URI, password, token, real hostname, or returned rows
into Git, tickets, or shared logs.

> **Template version:** this checklist currently uses the older
> CrystalDBA/SSE template names. For the current verified MCPg/Streamable HTTP
> candidate, first apply the complete conversion in
> [MCPG-WORK-VARIABLES.md](MCPG-WORK-VARIABLES.md), including the image,
> `MCPG_DATABASE_URL`, `/mcp` route, protocol, and tool names. Do not use this
> checklist unchanged with MCPg.

## 1. Secret delivery — prerequisite, not an Agent test

- [ ] The approved secret system creates `{{POSTGRES_MCP_SECRET_NAME}}` in
  `{{DATA_MCP_NAMESPACE}}` with the key `postgres-url`.
- [ ] The value includes the database endpoint, database name, username,
  password, and required TLS settings; it is never printed.
- [ ] The database identity is a dedicated non-human reader with `CONNECT`,
  schema `USAGE`, and `SELECT` only on approved views.

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{DATA_MCP_NAMESPACE}} \
  get secret {{POSTGRES_MCP_SECRET_NAME}} \
  -o jsonpath='{.metadata.name}{" keys="}{.data}{"\n"}'
```

Pass criterion: the expected Secret name and key are present. Do **not** use
`kubectl get secret -o yaml` or decode the value in an evidence capture.

If this fails, stop with the platform/secrets owner. Do not change the Agent
or MCP configuration.

## 2. Image and MCP workload — test the component nearest the database

- [ ] The internal registry contains the digest-pinned mirror of
  `crystaldba/postgres-mcp`, the exact source image used in the HomeLab/Azure
  proof.
- [ ] Apply the rendered `prebuilt-postgres-mcp.yaml`; wait for its rollout.
- [ ] Confirm the pod has the declared non-root/security settings and
  CPU/memory requests/limits before examining application behaviour.

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} apply --dry-run=server \
  -f {{PRIVATE_RENDERED_DIR}}/prebuilt-postgres-mcp.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_RENDERED_DIR}}/prebuilt-postgres-mcp.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{DATA_MCP_NAMESPACE}} \
  rollout status deploy/postgres-inventory-mcp --timeout=120s
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{DATA_MCP_NAMESPACE}} \
  get pod -l app.kubernetes.io/name=postgres-inventory-mcp -o yaml
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{DATA_MCP_NAMESPACE}} \
  logs deploy/postgres-inventory-mcp --tail=100
```

Pass criterion: one Ready pod, zero unexpected restarts, no image pull,
permission, TLS, DNS, or database-authentication error in the sanitised logs.

If it fails, stop with the image, Secret, private network/DNS, TLS, or database
owner. No Agent or Gateway has been involved yet.

## 3. Direct MCP transport/discovery — no Agent

First confirm that the MCP service exposes its SSE transport. A short timeout
is expected because an SSE connection stays open; `HTTP/1.1 200` is the signal.

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{DATA_MCP_NAMESPACE}} \
  port-forward svc/postgres-inventory-mcp 18000:8000
# In a second terminal, inspect headers only. End it after HTTP 200.
curl -i -N --max-time 5 http://127.0.0.1:18000/sse
```

Then register the rendered [direct probe](direct-mcp-probe.yaml), which has no
Agent, through kagent:

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} apply --dry-run=server \
  -f {{PRIVATE_RENDERED_DIR}}/direct-mcp-probe.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_RENDERED_DIR}}/direct-mcp-probe.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} wait \
  --for=condition=Accepted=True remotemcpserver/postgres-inventory-mcp-direct-probe \
  --timeout=120s
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} \
  get remotemcpserver postgres-inventory-mcp-direct-probe -o yaml
```

Pass criterion: `Accepted=True` and a non-empty
`.status.discoveredTools` list. Save the exact tool names as evidence. This
proves the kagent MCP controller can reach and negotiate with the MCP service;
it intentionally does not involve an Agent, model, or prompt.

Delete this direct probe before proceeding. It is deliberately a temporary
Gateway bypass and must not remain after the network boundary is enabled.

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} \
  delete remotemcpserver postgres-inventory-mcp-direct-probe --ignore-not-found
```

If it fails after stage 2 passed, stop with the MCP transport/configuration or
kagent RemoteMCPServer owner. Do not debug Agent YAML.

## 4. Gateway path — still no Agent

- [ ] Server-side dry-run the rendered `agentgateway-route.yaml` against the
  installed work CRDs.
- [ ] Confirm the actual Gateway pod labels, render and apply
  `mcp-networkpolicy.yaml`, then apply the Gateway route and rendered
  [gateway probe](gateway-mcp-probe.yaml). Do not apply either Agent yet.

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} apply --dry-run=server \
  -f {{PRIVATE_RENDERED_DIR}}/agentgateway-route.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} apply --dry-run=server \
  -f {{PRIVATE_RENDERED_DIR}}/mcp-networkpolicy.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_RENDERED_DIR}}/mcp-networkpolicy.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_RENDERED_DIR}}/agentgateway-route.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_RENDERED_DIR}}/gateway-mcp-probe.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} wait \
  --for=condition=Accepted=True remotemcpserver/postgres-inventory-mcp-gateway-probe \
  --timeout=120s
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} \
  get remotemcpserver postgres-inventory-mcp-gateway-probe -o yaml
```

Pass criterion: the gateway-fronted `RemoteMCPServer` is `Accepted=True` and
discovers the expected tool set. Compare it with the direct-probe tool list;
unexpected omissions/additions are a Gateway policy/routing issue.

The expected first-route reconciliation is: permit `list_schemas`,
`list_objects`, `get_object_details`, and `execute_sql`; deny
`explain_query`, `analyze_workload_indexes`, `analyze_query_indexes`,
`analyze_db_health`, and `get_top_queries`. Record both lists. The final Agent
allowlists are narrower than the Gateway list by design.

If it fails while stage 3 passed, stop with the Agent Gateway owner. Do not
change database credentials or Agent prompts.

## 5. Model-egress approval — before any Agent receives a query result

- [ ] Inspect the selected `{{KAGENT_MODEL_CONFIG}}` and identify its model
  provider/destination, prompt/completion retention, training policy, and who
  can access the relevant logs.
- [ ] Obtain data-owner confirmation that the approved view's classification
  permits result rows to travel to that destination.
- [ ] Record the approval reference without copying rows, hostnames, tokens,
  or provider credentials into this bundle.

Pass criterion: the destination and handling of query result data are known and
approved. An unknown or unapproved model-egress path blocks the query Agent.

## 6. Agent binding and one approved query — final integration test

Only now apply the two Agent documents. Start with the schema Agent; review the
discovered names and tool allowlists before applying the query Agent.

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_RENDERED_DIR}}/kagent-agent.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} wait \
  --for=condition=Ready=True agent/postgres-inventory-schema-agent \
  --timeout=180s
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} wait \
  --for=condition=Ready=True agent/postgres-inventory-query-agent \
  --timeout=180s
```

Ask one owner-approved, redacted question with a known expected result. Save
the A2A receipt privately. This is the first stage that proves an actual SQL
tool execution through the complete route. If it fails after stages 1–4 passed,
the fault is constrained to kagent Agent configuration, model routing, prompt,
or the approved query/view contract.

## 7. Negative and handoff checks

- [ ] An unapproved table/view is denied by PostgreSQL grants.
- [ ] A write request is refused; do not execute DML as a test.
- [ ] The schema Agent cannot call `execute_sql`.
- [ ] The query Agent has only the discovered/approved tools.
- [ ] Evidence includes rendered redacted manifests, readiness/status, exact
  discovered tools, sanitised logs, one receipt, database audit/query ID, and
  image digest/scan record.
- [ ] Delete the temporary gateway probe after the final route passes:

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} \
  delete remotemcpserver postgres-inventory-mcp-direct-probe --ignore-not-found
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} \
  delete remotemcpserver postgres-inventory-mcp-gateway-probe --ignore-not-found
```

## Failure ownership at a glance

| First failed stage | Likely responsible layer | Do not change first |
|---|---|---|
| 1 | secret delivery or database-role owner | Agent/Gateway YAML |
| 2 | image, Secret reference, network/DNS, TLS, database authentication | Agent/Gateway YAML |
| 3 | MCP service/SSE or kagent RemoteMCPServer | Agent prompt/model |
| 4 | Agent Gateway CRD/route/policy | database credentials/grants |
| 5 | ModelConfig/model provider, data-owner egress approval | prior passing infrastructure |
| 6 | Agent allowlist, model route, prompt, approved query/view | prior passing infrastructure |
