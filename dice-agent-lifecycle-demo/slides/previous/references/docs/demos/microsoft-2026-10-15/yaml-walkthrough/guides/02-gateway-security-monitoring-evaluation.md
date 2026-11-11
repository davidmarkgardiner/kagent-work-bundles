# Gateway identity, security and evaluation walkthrough

Use this as a technical reference alongside the numbered YAML walkthrough. These are sanitized examples, not evidence of deployment into the Microsoft/customer tenant. The local gateway policy schema was checked against the sibling upstream checkout at `4ae9c32`. The installed controller, CRDs and data plane must support the selected fields, especially `Require`, `traffic.timeouts` and `frontend` telemetry. Existing repo examples use older shapes; identical `v1alpha1` API strings do not guarantee identical fields.

## Microsoft access tokens and JWT mean different things about the same token

For these registered A2A and MCP APIs, we use **Microsoft Entra-issued OAuth access tokens in signed JWT format**. Entra is the issuer, access token is the purpose, and JWT is the format. The policy field `jwtAuthentication` configures validation of that Entra token using the tenant issuer and trusted signing keys. It does not require a second, separately minted gateway token.

The client presents its access token in the Authorization header. The gateway validates the signature, issuer, audience and time validity, then checks the verified caller/child identity and role. An ID token for sign-in is not the API access token. A token issued for Microsoft Graph is not a token for our A2A or MCP API. Clients should treat access tokens as opaque; validation is the responsibility of the API/gateway receiving them. These examples deliberately require v2 custom-API tokens; token version and claim names must match the registered resource API.

Source: [Microsoft access-token documentation](https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens).

## The two permission boundaries

| Hop | Token acquisition | Gateway checks | Remaining enforcement |
| --- | --- | --- | --- |
| Application → SRE agent | Caller ServiceAccount federates to caller UAMI; request an A2A API access token | Tenant issuer/signature/expiry, exact A2A audience, caller `azp` + `oid`, `sre.chat.invoke`, named route | Agent destination and task permissions; authorized tools remain separate |
| Running SRE agent → Kubernetes MCP | Selected token-holder ServiceAccount federates directly to a dedicated blueprint; runtime acquires a child Agent ID token for the MCP API | Tenant issuer/signature/expiry, separate MCP audience, exact child `azp` + `oid`, `sre.kubernetes.read`, listed tools | MCP input/resource restrictions and downstream Kubernetes RBAC |

The blueprint holds credential configuration and defines the agent family. Its child Agent ID is the permission and audit identity. Record an accountable sponsor and owner. For this bounded example, assign the MCP API app role directly to the named child. If using inherited blueprint permissions, review that shared grant boundary separately and retain exact-child restrictions at the gateway. Use separate blueprints when their children must belong to independent trust domains.

The two incoming tokens have different audiences and roles. Forwarding the caller's token does not create a child token or delegate its permissions. Configure both protected APIs to issue v2 access tokens and verify their actual issuer/audience claims. The examples use app-only Entra v2 tokens: `azp` identifies the calling application, `oid` identifies its principal. For an autonomous Agent ID, Microsoft documents that the child object ID and app ID are the same. Delegated user flows require their own `scp`, user and authorization contract.

Use `xms_par_app_azp` to record the parent blueprint in audit context. Microsoft advises against authorizing solely by this claim because it can grant broad access to many children. Identity claims must come from a verified token, never caller-supplied headers.

Sources: [Agent identities](https://learn.microsoft.com/en-us/entra/agent-id/agent-identities), [token claims](https://learn.microsoft.com/en-us/entra/agent-id/agent-token-claims), [autonomous agent protocol](https://learn.microsoft.com/en-us/entra/agent-id/autonomous-agent-authentication-authorization-flow).

## What the identity setup actually needs

1. Identity administrators create the blueprint, accountable sponsor/owner and child Agent ID. They configure the protected A2A and MCP APIs and their app roles, and approve each role assignment.
2. Create the exact blueprint FIC using [blueprint-federated-credential.json](../identity/README.md). It is a Microsoft Graph request body for `POST /v1.0/applications/{{BLUEPRINT_CLIENT_ID}}/federatedIdentityCredentials`, not a Kubernetes resource. The OIDC issuer, ServiceAccount subject and exchange audience must match. The API identifier and permissions must be confirmed against the tenant's supported Agent ID API.
3. [File 11](../11-blueprint-token-holder.yaml) binds the selected token component to that blueprint. Its Pod needs the Workload Identity label and ServiceAccount assignment. Keep the identity within the authority of administrators who control that namespace.
4. The runtime acquires the blueprint exchange token, selecting the child with `fmi_path`, then uses that token as the assertion for a child access token with the MCP API scope. It must refresh before expiry. The exact protocol is in the Microsoft autonomous-agent documentation above. Use supported Agent ID libraries or a reviewed implementation; ordinary `DefaultAzureCredential`/webhook injection alone is not proof of this child exchange.
5. Configure authenticated requests to the gateway's named MCP endpoint. MCP OAuth discovery can advertise the resource; it does not mint or refresh the runtime's child token.

The repository ownership brief records a disposable pilot using a direct child grant and manual token update/restart. It does not provide current end-to-end proof of the requested workplace caller-UAMI/inherited-grant/automatic-refresh chain. The separate ServiceAccount → UAMI → blueprint middle-hop attempt was not the successful outbound design. This walkthrough uses direct ServiceAccount → blueprint federation.

Source: [Create a blueprint](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/create-blueprint), repository `platform/agentgateway/CLAVES-ADR-MEETING-BRIEF.md` and `ENTRA-AGENT-ID-REQUEST-OWNERSHIP.html`.

## The concrete gateway controls

| File | What it demonstrates |
| --- | --- |
| [12 application policy](../12-application-to-agent-policy.yaml) | Strict Entra JWT and mandatory caller/tenant/role checks on `sre-chat-a2a` |
| [13 agent/MCP policy](../13-agent-to-mcp-policy.yaml) | Separate audience, exact child identity, role and mandatory MCP tool list |
| [10 trusted JWKS backend](../10-entra-jwks.yaml) | Entra key retrieval using a TLS-validated backend |
| [11 token-holder identity](../11-blueprint-token-holder.yaml) | Kubernetes ServiceAccount annotation; separate FIC and runtime exchange requirements |
| [15 traffic limits](../15-model-traffic-limits.yaml) | Request timeout plus local requests/minute and tokens/minute on the model route |
| [16 model data guard](../16-model-content-guards.yaml) | Selected request PII rejection and response masking |
| [17 audit and traces](../17-gateway-observability.yaml) | Verified identity audit attributes and OTLP traces on the Gateway |
| [18 proxy monitor](../18-gateway-podmonitor.yaml) | Prometheus Operator scraping the native proxy metrics |
| [19 alerts](../19-gateway-alerts.yaml) | Missing metrics, denial activity, 5xx ratio, input tokens and separate evaluation alerts |
| [20 agent evaluation](../20-agent-evaluation-case.yaml) | Local deterministic scorer case with tool, namespace, trace and budget gates |
| [14 destination ingress](../14-mcp-network-boundary.yaml) | MCP ingress from only the named gateway pods; enforcing CNI and additive-policy audit required |

`Require` makes each expression mandatory. `Allow` expressions are OR alternatives; splitting identity and role into two `Allow` entries would permit either one. Multiple policy objects can merge or override fields according to their attachment level. Inspect effective configuration, `Accepted`/`Attached` status, and negative behavior, not only the YAML. Platform administrators own shared routes, policies, credentials, grants and destination controls.

`ReferenceGrant` permits a typed cross-namespace reference; it does not authenticate the caller. Agent `toolNames` limits model-visible operations; the gateway policy independently constrains actual calls. Neither tool-name check enforces resource arguments. Keep typed/bounded adapters, approved data views, read-only grants, and explicit human-controlled change paths at the destination.

Local limits apply per proxy and per selected route. They are not a coordinated per-agent spending cap. Tokens are counted after completion, so in-flight work can overshoot. A gateway request timeout does not bound an entire task. Coordinated quotas require a configured global service and reliable identity attribution. PII regexes are limited pattern matching and need false-positive, streaming and structured-output tests.

Sources: [Authorization](https://agentgateway.dev/docs/kubernetes/latest/documentation/security/authorization/), [policy targeting and merging](https://agentgateway.dev/docs/kubernetes/latest/documentation/about/policies/overview/), [regex guards](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/guardrails/regex/).

## What to put in Grafana

The proxy defaults to `:15020/metrics`; the controller defaults to `:9092/metrics`. Verify actual ports, selected pods/services and the emitted metric labels. Do not copy Envoy metric names into a native Rust gateway dashboard without observing them.

| Panel | Native PromQL |
| --- | --- |
| Request rate | `sum(rate(agentgateway_requests_total{job="agentgateway-demo"}[5m]))` |
| 401/403 activity | `sum by (status) (rate(agentgateway_requests_total{job="agentgateway-demo",status=~"401|403"}[5m]))` |
| Tool call rate | `sum by (server, resource) (rate(agentgateway_mcp_requests_total{job="agentgateway-demo",method="tools/call"}[5m]))` |
| Input/output tokens per minute | `sum by (gen_ai_request_model,gen_ai_token_type) (rate(agentgateway_gen_ai_client_token_usage_sum{job="agentgateway-demo"}[5m])) * 60` |
| Model response p95 seconds | `histogram_quantile(0.95, sum by (le,gen_ai_request_model) (rate(agentgateway_gen_ai_server_request_duration_bucket{job="agentgateway-demo"}[5m])))` |
| Scrape health | `up{job="agentgateway-demo"}` |

A 401/403 response is a signal to inspect, not definitive attribution to a particular gateway policy; upstream applications can also return it. Tool errors can be encoded in a successful HTTP MCP response, so combine HTTP metrics with MCP results and agent traces. A healthy HTTP response does not prove correct diagnosis or safe remediation.

Keep team/environment/model dimensions in metric labels. Keep child IDs, user IDs, sessions and trace IDs in protected logs/traces to avoid unbounded metric cardinality. Native model aggregates do not prove per-agent token attribution. Capture the agent's full client-visible envelope and correlated per-call telemetry when measuring transport/token improvements. Missing token series are missing evidence, not zero consumption.

Add controller/config rejection monitoring and policy/route acceptance to the platform dashboard. Confirm these metric names on the installed release instead of guessing them. Correlate Entra sign-in/audit entries with child identity/time and gateway/kagent trace context. Do not store raw tokens or unrestricted prompts, tool results and data rows in routine logs.

Sources: [Metrics scraping](https://agentgateway.dev/docs/kubernetes/latest/documentation/observability/metrics/overview/), [native metric reference](https://agentgateway.dev/docs/kubernetes/latest/documentation/observability/metrics/dataplane/), [access logs](https://agentgateway.dev/docs/kubernetes/latest/documentation/observability/access-logs/view/), [traces](https://agentgateway.dev/docs/kubernetes/latest/documentation/observability/traces/setup/).

## Evaluate behavior and access separately

The gateway enforces access and observes traffic. Our local `observability/agent-evals` scorer evaluates captured agent and incident results. [File 20](../20-agent-evaluation-case.yaml) is scorer input, not a Kubernetes or gateway CRD. It checks diagnosis/evidence terms, selected/forbidden tool use, namespace, response sections and budgets. Safety failures override a high numeric score. Exported `agent_eval_*` and `agent_lifecycle_eval_*` metrics come from the evaluator, not natively from the gateway.

Use captured positive and negative cases before promotion. Require complete tool arguments/results, trace receipts and token/latency telemetry for the dimensions being assessed. `requireTrace` requires an ID; a placeholder or arbitrary ID alone is not trace proof. Missing latency/token dimensions otherwise become `not_scored`, so a promotion process must reject incomplete evidence separately. The deterministic term scorer is not a semantic correctness guarantee; add reviewed datasets and optional judge/human review for more nuanced quality checks.

The lifecycle case separately verifies approval before remediation, post-change verification and ticket update. Evaluation never confers execution authority.

The existing offline demo can be run without a cluster:

```sh
cd "{{REPOSITORY_ROOT}}"
python3 observability/agent-evals/scripts/score-agent-run.py \
  --case observability/agent-evals/cases/crashloop-wrong-env-var.yaml \
  --run observability/agent-evals/results/sample/crashloop-wrong-env-var.run.json \
  --output-dir /tmp/microsoft-gateway-evaluation
```

This uses a retained sample, not a freshly observed agent. The sample and the strict attached case serve different purposes; do not substitute the sample for a target-environment canary.

## Rehearsal and proof matrix

| Probe | Expected evidence |
| --- | --- |
| Approved caller + A2A token + invoke role | Named agent reached, with correlated request and response |
| Missing/expired token or wrong audience | Authentication rejected; no agent invocation |
| Valid token, wrong caller or missing invoke role | Authorization rejected; no agent invocation |
| Approved child + MCP token + role + listed read tool | Named MCP operation succeeds within approved resource scope |
| A sibling child from the same blueprint | Rejected despite having a valid issuer or shared grant |
| A2A token replayed to MCP | Rejected for audience/permission mismatch |
| Approved child tries apply/delete/exec | Rejected at tool enforcement; no downstream side effect |
| Allowed tool with forbidden namespace/resource | Rejected by the MCP/resource authorization layer |
| Caller tries direct MCP Service access | Network/destination enforcement blocks bypass |
| Token expires during a multi-call task | Reviewed refresh path continues with a valid child token; no permissive fallback |
| Telemetry collector unavailable | Access enforcement remains intact; loss of observability is detected |
| Wrong namespace, forbidden tool or action before approval | Evaluator hard failure blocks promotion independently of numeric score |

JWT failures typically produce HTTP 401 and authorization failures 403; record the installed implementation's actual HTTP/JSON-RPC outcome and downstream invocation count. A forbidden MCP operation can be represented by a protocol error rather than only an HTTP status. Inspect complete results and effects.

Read-only inspection commands, after explicitly selecting the intended context privately:

```sh
kubectl --context "$DEMO_CONTEXT" -n platform-gateway get agentgatewaypolicy \
  application-to-sre-chat agent-to-kubernetes-mcp -o yaml
kubectl --context "$DEMO_CONTEXT" -n platform-gateway get httproute \
  sre-chat-a2a kubernetes-mcp -o yaml
kubectl --context "$DEMO_CONTEXT" -n platform-gateway get pods \
  -l gateway.networking.k8s.io/gateway-name=agent-gateway -o wide
```

Do not display raw Entra tokens, live object IDs or private endpoints on a shared screen. Use the sanitized examples for the YAML walkthrough. No cluster commands were run as part of creating this pack.
