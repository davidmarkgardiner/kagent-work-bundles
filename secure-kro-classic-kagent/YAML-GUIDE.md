# Explain each YAML in the secure agent demonstration

The customer applies one [instance](examples/agent-demo.yaml). The platform
installs the [RGD](examples/resourcegraphdefinition.yaml) and
[Gateway baseline](examples/platform.yaml) once. KRO applies resource templates;
kagent separately creates the native Deployment, Service and configuration Secret.

The split files below are generated from compose.py. They are graph templates
containing CEL, not a second set of customer files to apply individually.
The catalog variant is under demo/yaml/catalog. For actual cluster output, run
the corresponding demo.py show command in [the walkthrough](DEMO-WALKTHROUGH.md).

| Graph resource | What it does and why | Inspect live |
| --- | --- | --- |
| [Runtime identity](demo/yaml/model/01-runtimeAccount.yaml) | No Kubernetes API token is automounted into the native agent. Backend permissions remain separate from chat access. | `show runtimeAccount` |
| [Golden identity](demo/yaml/model/02-verifierAccount.yaml) | The verifier gets only an audience-specific, short-lived projected JWT. It has no Role or RoleBinding to the Kubernetes API. | `show verifierAccount` |
| [Caller identity](demo/yaml/model/03-callerAccount.yaml) | Only the exact demo-caller subject is accepted on the caller listener. Minting its JWT requires the operator token-request permission. | `show callerAccount` |
| [Native kagent Agent](demo/yaml/model/04-agent.yaml) | KRO passes the system prompt, existing ModelConfig name and selected MCP operations to the normal declarative Agent. kagent creates the Deployment, Service and generated configuration Secret. | `show agent` |
| [Agent network boundary](demo/yaml/model/05-network.yaml) | Ingress is limited to the approved Gateway pods. Egress permits only the resolved DNS, model, controller and reviewed tool paths. DNS and backend permissions are still separate controls. | `show network` |
| [Verifier route policy](demo/yaml/model/06-verifierPolicy.yaml) | Strict JWT validation checks issuer and audience. Authorization requires the verifier service-account subject. | `show verifierPolicy` |
| [AgentCard policy](demo/yaml/model/07-cardPolicy.yaml) | The Golden identity can inspect the native AgentCard. Anonymous callers and malformed tokens are denied. | `show cardPolicy` |
| [Caller route policy](demo/yaml/model/08-callerPolicy.yaml) | Strict JWT validation and exact caller subject protect invocation. This policy does not give the caller Kubernetes or MCP execution permissions. | `show callerPolicy` |
| [Golden invocation route](demo/yaml/model/09-verifyRoute.yaml) | The verifier-only listener rewrites the exact verification path to the native A2A endpoint. It is distinct from the customer invocation route. | `show verifyRoute` |
| [AgentCard route](demo/yaml/model/10-cardRoute.yaml) | Only the verification listener exposes the exact AgentCard path. Route status must report Accepted and ResolvedRefs. | `show cardRoute` |
| [Golden ConfigMap](demo/yaml/model/11-goldenConfig.yaml) | Fixed URLs, expected agent name, owner UID and token file path bind the Job to this instance. It contains no provider key or JWT value. The token is projected at runtime. | `show goldenConfig` |
| [Verifier network boundary](demo/yaml/model/12-verifierNetwork.yaml) | All verifier ingress is denied. Its only egress paths are DNS and the two Gateway listeners, including the caller lane used for a negative control. | `show verifierNetwork` |
| [Golden verification Job](demo/yaml/model/13-golden.yaml) | After the Agent and verifier routes are ready, the Job checks the card and denied requests, then makes one real model request for PONG. It requires completed native assistant output. backoffLimit is zero. | `show golden` |
| [Customer invocation route](demo/yaml/model/14-callerRoute.yaml) | The annotation references the Golden Job. KRO waits for that Job to succeed before creating the caller route. A successful Job is a recorded gate, not continuous reapproval or revocation. | `show callerRoute` |

## The front door and Golden configuration

In this non-Substrate version the front door is agentgateway itself. Its Gateway,
listener policies, route policies and HTTPRoutes replace the other bundle's
custom front-door adapter and ConfigMap. There is no front-door ConfigMap in
this composition. Do not copy that adapter configuration into this bundle.

The Golden ConfigMap is different. It stores fixed verifier/caller URLs, the
expected agent name, owner UID, timeout and projected token file path. It does
not store a JWT value, model key, system prompt or mutable approval lease. The
Job mounts this configuration and its verifier token. Its successful completion
is the KRO dependency that permits caller-route creation. A completed Job is
recorded verification, not continuous revocation after dependencies change.

## Backend references and native controller output

- [ModelConfig](demo/yaml/model.yaml) is a reference example for an existing approved model. Resolve its provider fields against the installed CRD. The customer chooses its name; credentials stay in the approved Secret or model Gateway.
- [RemoteMCPServer](demo/yaml/remoteMCP.yaml) is a reference example. Catalog operation names, endpoints, authentication and egress must match the receiving tool server.
- [Recorded native Deployment](demo/recorded-native-deployment.yaml) is sanitized controller output from 2026-11-04. It uses the normal Go runtime, not a Substrate worker. It is dated evidence, not live cluster state.
- [Native Service](demo/yaml/nativeService.yaml) shows the controller-owned Service structure. The actual receiving output is available with `demo.py show service`.
- The generated native configuration Secret is controller-owned. Inspect its reference and ownership without exposing credential-bearing contents. It is not another customer ConfigMap.

## JWTs and privileges

| Identity | Credential and boundary |
| --- | --- |
| Native runtime | Dedicated ServiceAccount with Kubernetes token automount disabled. kagent separately projects a one-hour token with audience `kagent` for its controller API; the recorded Deployment shows it. Its model/MCP permissions remain backend-specific. |
| Golden verifier | Projected 10-minute Kubernetes JWT with audience `secure-agent-classic`. Exact verifier subject on the verifier listener. No Kubernetes API Role or RoleBinding. |
| Caller | Authorized operator requests a 10-minute demo-caller JWT. Exact caller subject on the caller listener. This is not yet per-human or UAMI login. |

The strict listener policies exist before customer instance creation. Per-route
policies add route-specific JWT and subject requirements. Missing or invalid
tokens are denied. The recorded post-route controls show HTTP 401 for no caller
JWT and HTTP 403 when the verifier attempts caller access. JWT enforcement does
not confer Kubernetes RBAC or MCP backend permissions.

## ReferenceGrant is conditional

The [optional example](demo/yaml/referenceGrant.yaml) is not installed. Every
route and backend Service in this graph is in classic-agents, so no grant is
required. A reviewed cross-namespace variant needs a grant in the backend
namespace allowing HTTPRoute references from the approved route namespace to
only Service/demo. The grant does not authenticate callers or authorize tool
operations. Control who may create routes in that trusted namespace.

## What the verification proves

The dated [live receipt](evidence/live-classic-0.10.4-2026-11-04.json) proves native
model PONG, separate caller PONG and JWT denial controls on the reference version.
The presentation does not claim a fresh run on 2026-11-05, when the lab was
unreachable. It does not prove skill fetching, MCP backend operations, or denied
network traffic. NetworkPolicy enforcement requires a supporting receiving CNI
and explicit ingress/egress traffic tests. Show those results separately before
claiming that the agent cannot reach an unapproved destination.

The native Kubernetes container is the containment boundary here. No Substrate
sandbox, continuous approval lease, Entra/UAMI login or automatic dependency
revocation is supplied by this demonstration.
