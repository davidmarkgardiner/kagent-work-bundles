# Work agent request: review encryption across the agent platform

## Objective

Inspect the **actual workplace AKS deployment** of our secure KRO-managed agent solution and report how traffic is protected between each component. Use the real deployed route, including the Istio VirtualService exposing the Agent Gateway. The architecture and sequence diagrams describe intent; verify what is actually running and identify any differences.

Give David a clear answer for each component and connection: what is encrypted, where encryption starts and terminates, whether the destination is authenticated, what is known from configuration, what is confirmed by existing runtime evidence, and what remains unknown.

## Boundaries

- Use approved **read-only** access to the target cluster, GitOps repositories, platform configuration and existing telemetry. First identify the intended cluster/context, environment, namespaces, collection time and component versions.
- Do not change manifests, policies, secrets, Istio settings, workloads or infrastructure. Do not restart, deploy, upgrade, port-forward, invoke agents or tools, generate model requests, inject traffic, run packet captures, or perform active or negative tests without separate authorisation.
- Do not read or print Secret data, access tokens, private keys, credentials, prompt bodies or tool results. Inspect metadata and non-secret configuration only. Keep private endpoints and evidence in an approved private location; redact them in any public report.
- Treat access failures as evidence gaps. If you cannot identify the environment, a hop, its configuration or runtime evidence, mark it **UNKNOWN** and state exactly what is needed. Never substitute a lab result, documentation, a `Ready` status or an authenticated response for workplace transport evidence.
- Recommendations are proposals; do not implement them as part of this request.

## 1. Map the real path

Identify a representative application and secure KRO-managed agent, and resolve the deployed objects and destinations. Record differences for other agents, MCP servers or model routes when their transport configuration differs. Follow the actual implementation rather than assuming every hop passes through the same gateway.

```text
Application → load balancer / Istio ingress → Agent Gateway → agent
                                                       agent → gateway → MCP → backend
                                                       agent → model gateway → model provider
                                                       agent → other agent, if used
                                      components → collector / Alloy → LGTM backends
```

Document any additional proxies, external services, private endpoints, TLS termination and re-origination points, direct paths, and callbacks. Record which paths do not exist and which could not be assessed. Responses normally use the same connection, but inspect any separate asynchronous or callback connection.

## 2. Review each component

| Component | What to inspect | Questions to answer |
|---|---|---|
| **Application / caller** | The actual agent API URL, client TLS and trust configuration, identity method, any proxy or upstream load balancer. | Does it use HTTPS? What certificate and hostname are validated? Where does its connection terminate? Is client mTLS used? |
| **Istio ingress Gateway and VirtualService** | Effective Gateway listener, TLS mode, certificate metadata, associated VirtualService, host/path routing and actual destination. Include upstream termination if present. | Does ingress terminate or pass through TLS? What is the next hop? Is that hop separately protected? A VirtualService routes traffic; it does not by itself prove TLS or authentication. |
| **Agent Gateway** | Deployed version, listeners, AgentgatewayPolicies and their actual targets, routes and backend references, inbound and outbound TLS, certificate/CA validation and service identity. | Which caller, MCP and model routes exist? Which connections use TLS or mTLS, where do they terminate, and what peer is authenticated? |
| **KRO and secure agent resources** | The KRO owner/graph and generated Agent, Service, route and relevant policies. Review generated objects as well as source templates. | Which resources are actually generated for this agent? Are references and policies attached and effective? KRO composition and a Ready status do not prove transport encryption. |
| **Agent runtime** | Actual pod/deployment or runtime form, service endpoints, mesh participation, model and MCP references, connection settings and effective policies. | How does the agent receive calls and make outbound model, MCP and A2A calls? Are any connections direct? Are its sidecar or ambient paths active where expected? |
| **Istio mesh** | Installed revision and mesh defaults, workload participation and effective `PeerAuthentication` and `DestinationRule` policies, including selectors, namespaces, port overrides and applicable gateway/egress settings. | Where is mesh mTLS used? Is inbound traffic `STRICT` or `PERMISSIVE` at the effective scope? Which workloads or ports are outside the mesh? |
| **ModelConfig and model path** | Agent's actual ModelConfig reference and non-secret endpoint fields; model gateway route and provider configuration, TLS origination and trust. | What endpoint does the agent call, and how is each subsequent connection protected? `ModelConfig` is configuration, not a network hop. Inspect the agent → model gateway and gateway/garden → provider separately. |
| **MCP and its backend** | Actual RemoteMCPServer endpoints and protocol, gateway policies, MCP workload and service, and the MCP server's connection to its backend. | Are agent → gateway, gateway → MCP, and MCP → backend protected? Is certificate validation enabled? Record differences across Kubernetes, database and other tools. |
| **Agent-to-agent** | Actual A2A routes, callers, intermediaries, destinations and participating workloads, if used. | Is each delegation or callback connection encrypted and authenticated? If A2A is not deployed, say so. |
| **Identity and token services** | Relevant non-secret workload identity, issuer and token acquisition endpoint configuration, and the connections used to obtain or validate identity. | Which network calls carry assertions or tokens, and what transport protects them? JWTs and workload identity authenticate or authorise; they do not encrypt traffic. |
| **Observability** | Effective OTLP/log/metric producers, collector or Alloy receivers, and exporters to Loki, Tempo, Mimir or other services. | Is each telemetry connection encrypted? What content can be retained, who can access it, and what retention is configured if readily available? |
| **Shared infrastructure and dependencies** | Actual DNS, Kubernetes API, data stores, registries or other dependencies used by these paths where in scope. | Identify material unassessed connections and owners; avoid assuming all traffic in AKS is covered by the mesh. |

## 3. Establish the evidence

For each hop, separate the following:

1. **Effective configuration:** deployed endpoint, route, listener and policy, including applicable selectors, overrides and installed version. Record what the settings require or allow.
2. **Existing runtime observation:** already available access logs, proxy telemetry, connection metadata or approved traces that identify the connection, transport, peer and time. Do not generate traffic merely to obtain evidence.
3. **Peer and certificate validation:** whether the actual client verifies the expected server identity and trust chain; for mTLS, identify what is known about both peers. An encrypted connection alone does not prove validation.
4. **Enforcement:** whether plaintext is rejected by the effective policy. A scoped `STRICT` policy supports a configuration finding for the covered inbound traffic; proof of a rejection requires suitable existing evidence or a separately authorised test.

Use these distinctions when interpreting evidence:

- An application `http://` URL may be protected between participating Istio proxies. It does not prove the network hop is plaintext. Equally, an injected sidecar or a `STRICT` policy elsewhere does not prove a particular connection used mTLS.
- Istio `PERMISSIVE` can accept both mTLS and plaintext. Auto mTLS, namespace defaults and route policies must be resolved against the actual source and destination.
- Private networking, NetworkPolicy, JWTs, OAuth, port 443 and successful authorisation do not independently prove transport encryption.
- TLS termination means the terminating component can access plaintext. Verify whether a new protected connection is established for the next hop.
- Do not infer an unencrypted connection solely from missing evidence. Report **UNKNOWN** unless affirmative evidence establishes plaintext.

## 4. Return the findings

Start with a short executive summary in plain language: what is observed encrypted, what is configured or expected but unverified, what is confirmed plaintext, and the most important unknowns. Include the target, date and scope. Do not calculate a percentage unless all in-scope flows are inventoried and the denominator is meaningful.

Complete one row **per actual connection**, including distinct outbound and callback paths when applicable. Expand the table as needed.

| Source → destination | Purpose and endpoint/port | App protocol | TLS termination / re-origination | Transport and peer validation | Effective configuration evidence | Existing runtime evidence and time | Status, owner and exact next check |
|---|---|---|---|---|---|---|---|
| Application → ingress | To investigate | Unknown | Unknown | Unknown | Pending | Pending | UNKNOWN |
| Ingress → Agent Gateway | To investigate | Unknown | Unknown | Unknown | Pending | Pending | UNKNOWN |
| Agent Gateway → agent | To investigate | Unknown | Unknown | Unknown | Pending | Pending | UNKNOWN |
| Agent → Gateway → MCP | Split into actual connections | Unknown | Unknown | Unknown | Pending | Pending | UNKNOWN |
| MCP → backend | One row per distinct backend | Unknown | Unknown | Unknown | Pending | Pending | UNKNOWN |
| Agent → model gateway → provider | Split into actual connections | Unknown | Unknown | Unknown | Pending | Pending | UNKNOWN |
| A2A and telemetry | One row per actual path | Unknown | Unknown | Unknown | Pending | Pending | UNKNOWN |

Use **OBSERVED** for an attributable runtime observation; **CONFIGURED / EXPECTED** where configuration supports the claim but no runtime observation was found; **PLAINTEXT CONFIRMED** only with affirmative evidence; **UNKNOWN** for insufficient evidence; and **NOT APPLICABLE** only when the path does not exist. State the observation's time and scope. A connection may need separate statuses for encryption, peer validation and plaintext rejection.

Then provide:

- A component-by-component summary, including version, role, effective security settings and any gaps.
- Prioritised findings with impact, owner, smallest proposed remediation and exact next verification. Do not make changes.
- An evidence inventory with private references, timestamps, permissions and missing access. Redact sensitive details for public sharing.
- An explanation of what can see plaintext at termination points, and whether observability can retain prompts, tool outputs or tokens. Separate transit encryption from storage encryption, retention and access controls.
- Any separately authorised runtime tests that would close remaining gaps, described as proposals only.

## References

Use the workplace-owned architecture and deployed GitOps configuration as the primary sources. The companion [HTML handoff](index.html) provides a visual overview.

- Istio TLS configuration: https://istio.io/latest/docs/ops/configuration/traffic-management/tls-configuration/
- Istio mTLS migration: https://istio.io/latest/docs/tasks/security/authentication/mtls-migration/
- AKS Istio secure ingress: https://learn.microsoft.com/en-us/azure/aks/istio-secure-gateway
