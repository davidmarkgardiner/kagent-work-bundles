# Agent Gateway policies we can demonstrate

Agent Gateway can check identity, restrict access, inspect content, limit traffic, and record decisions between applications, agents, tools, and models. These controls surround the existing declarative kagent Agent. They do not require a custom Go agent.

This is a capability guide, not a statement that every control is deployed. Field names below were checked against the [official agentgateway v1.7.0 policy CRD](https://github.com/agentgateway/agentgateway/blob/v1.7.0/controller/install/helm/agentgateway-crds/templates/agentgateway.dev_agentgatewaypolicies.yaml). Check the receiving installation and effective configuration before using them.

## Put the policy on the right hop

```text
Application -> Gateway -> Agent -> Gateway -> MCP -> backend resource
                            |
                            +----> Gateway -> model provider
```

Caller authentication belongs on the Agent's front door. Tool access belongs on the MCP path. Model prompt guards belong on the model path. A guard on one hop does not automatically inspect another hop's payload.

Kubernetes uses the `AgentgatewayPolicy` resource with these sections. [Policy overview](https://agentgateway.dev/docs/kubernetes/latest/documentation/about/policies/overview/).

| Section | What it controls | Common placement |
| --- | --- | --- |
| `frontend` | Connections, TLS settings, logs, traces, and metrics. | The Gateway, with supported listener or port scoping. |
| `traffic` | Authentication, route access, request limits, headers, and request handling. | The Gateway, listener, or route. |
| `backend` | Destination credentials, TLS, AI guards, and MCP controls. | The appropriate route or supported backend resource. |

## Choose the control for the requirement

Paths below start under `AgentgatewayPolicy.spec`. A schema field shows an available configuration interface; it does not establish successful enforcement.

| Requirement | Policy area | Example to talk through |
| --- | --- | --- |
| Authenticate the caller or Agent | `traffic.jwtAuthentication`, `apiKeyAuthentication`, or `basicAuthentication`; `backend.mcp.authentication` for MCP-specific auth. | An unsigned or expired credential is rejected before the protected service runs. Use separate identities for each hop. |
| Authorise a valid identity | `traffic.authorization`, `backend.authorization`, or `traffic.extAuth`. | Both identities authenticate, but only the approved application or role may invoke this Agent. CEL expressions can evaluate verified claims; an external authoriser can consult an existing access service. |
| Restrict tools | `backend.mcp.authorization`. | Permit a read tool and deny another tool for the same authenticated Agent. MCP-aware authorisation can also filter discovery. |
| Inspect MCP arguments or results | `backend.mcp.guardrails`. | Reject a synthetic restricted target before a tool runs, or filter a synthetic result before returning it. Request denial and response filtering have different evidence requirements. |
| Block recognised personal data going to a model | `backend.ai.promptGuard.request`. | Reject card numbers, email addresses, phone numbers, US SSNs, or Canadian SINs. This bundle includes a template with all five enabled. |
| Detect an organisation-specific pattern | Custom regex under `backend.ai.promptGuard`, or an approved guard webhook. | Match a synthetic internal record identifier. UK National Insurance numbers, IBANs, and sort codes are not separate built-ins in the five-type list below. |
| Mask or reject sensitive model output | `backend.ai.promptGuard.response`. | A controlled response contains synthetic personal data. The Gateway masks it in a buffered response or rejects it under the configured response guard. |
| Use a content-safety or DLP service | Prompt-guard `webhook`, `openAIModeration`, `bedrockGuardrails`, or `googleModelArmor`; `traffic.extProc` for supported HTTP processing. | An approved service supplies a content verdict. Verify what content it receives, its supported scope, and its failure behaviour. |
| Limit request volume | `traffic.rateLimit.local` or `.global`. | A bounded burst exceeds the demo quota and returns a rate-limit response. Per-identity limits require appropriate keys or descriptors; they are not implied by a route-wide limit. |
| Bound latency and failure handling | `traffic.timeouts`, `traffic.retry`, `backend.http`, or `backend.health`. | A controlled slow dependency times out. Retry only operations safe to repeat; a repeated write-capable tool call can duplicate an action. |
| Control model request settings | `backend.ai.defaults`, `.overrides`, `.transformations`, or `.prompt`. | Apply an approved provider parameter or system instruction. A generation-length cap is not a complete financial budget or an authorisation rule. |
| Use the correct destination credential | `backend.auth`, including Secret references, supported cloud auth, or supported token exchange; `backend.tls` for upstream trust and client certificates. | The Agent's caller token is not blindly reused as the tool or model provider credential. Identity-provider setup and destination permissions still apply. |
| Control headers and browser access | `traffic.headerModifiers`, `.cors`, or `.csrf`. | Remove an unneeded forwarded header or restrict browser origins. CORS does not authenticate a calling service. |
| Control connections and source networks | `frontend.tls`, `.tcp`, `.http`, or `.networkAuthorization`. | Apply TLS/connection limits or source-network admission. These controls do not prevent a pod from taking a separate direct path. |
| Record the decision | `frontend.accessLog`, `.tracing`, or `.metrics`. | Follow an exact task to the Gateway decision in LGTM/Grafana using safe identifiers. Do not record the sensitive content that triggered a guard. |

For implementation details, see [JWT authentication](https://agentgateway.dev/docs/kubernetes/latest/documentation/security/jwt/setup/), [CEL and external authorisation](https://agentgateway.dev/docs/kubernetes/latest/documentation/security/authorization/), [MCP tool access](https://agentgateway.dev/docs/kubernetes/latest/documentation/mcp/tool-access/), and [MCP guardrail processors](https://agentgateway.dev/docs/kubernetes/latest/documentation/mcp/guardrails/processors/).

Content filtering has distinct actions. `Reject` blocks matching content. `Mask` rewrites supported content. `Audit` records a verdict while permitting the request; it is not a blocking control. Response masking requires buffered output. Do not assume it protects a streamed response; inspect the separate streaming settings and rejection behaviour. [Guardrail actions and streaming](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/guardrails/overview/), [regex filters](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/guardrails/regex/).

Further references cover [MCP rate limits](https://agentgateway.dev/docs/kubernetes/latest/documentation/mcp/rate-limit/), [resiliency](https://agentgateway.dev/docs/kubernetes/latest/documentation/resiliency/), and [safe access-log configuration](https://agentgateway.dev/docs/kubernetes/latest/documentation/observability/access-logs/view/). Model/provider routing and failover also involve `HTTPRoute` and `AgentgatewayBackend` configuration; they are not all standalone policy switches. Protect every applicable destination path.

## Explain the five built-in detectors

These match recognised data formats, not the literal words "credit card", "email", or "phone number".

| Built-in | Detects |
| --- | --- |
| `CreditCard` | Credit card numbers. |
| `Email` | Email addresses. |
| `PhoneNumber` | Phone numbers. |
| `Ssn` | US Social Security numbers. |
| `CaSin` | Canadian Social Insurance Numbers. |

The [existing YAML](examples/credit-card-prompt-guard.yaml) now enables all five with `action: Reject` and a constant HTTP 403 response. It scans system prompts, messages, tool outputs, and tool inputs present in the model request. The [demo guide](CREDIT-CARD-PROMPT-GUARD-DEMO.md) retains the card-number example and requires a separate synthetic fixture for each other detector. Enabling these patterns is not proof of general confidential-data classification or resistance to every encoded format.

## Keep our current evidence explicit

| Control | Bundle evidence |
| --- | --- |
| Two authenticated Gateway hops and direct-path restrictions | Dated Python home-lab proof in [VALIDATION.md](VALIDATION.md). It is not workplace or current-runtime proof. |
| Five-type personal-data request rejection | Template checked offline against the v1.7.0 schema. Not deployed or live-tested. |
| MCP confidential-resource denial | [Proposed scene](CONFIDENTIAL-DATA-DEMO.md). No new runtime proof. |
| The other capabilities in this guide | Available configuration areas to evaluate. No additional controls are installed by this README. |

For the next rehearsal, follow the same existing Agent through caller authentication, a permitted tool call, a denied identity, and the model prompt guard. Add rate-limit, response-filtering, or MCP resource-access demonstrations only with their own scoped configuration and receipts. Show the received policy decision and an independent downstream audit; an HTTP status or missing span alone does not prove where enforcement occurred.

## Review attachment and remaining boundaries

Keep a policy in the namespace of its target. `frontend` targets a Gateway; an AI guard must target a supported model route/backend rather than a generic Service or the Agent A2A route. Inspect existing policy ownership before adding another attachment. Do not assume two prompt-guard lists concatenate. Conflicting fields can select one effective value, and an accepted policy can still lose a field to precedence. Verify the data-plane result. [Targeting and merging rules](https://agentgateway.dev/docs/kubernetes/latest/documentation/about/policies/target-merge/).

The Gateway controls traffic it handles. Kubernetes NetworkPolicy or equivalent network enforcement closes direct bypass paths. Backend IAM and database grants enforce resource permissions. Pod security, admission, runtime containment, code/image provenance, and human approval for higher-risk execution remain separate platform controls. Gateway policies complement those controls; they do not replace them or make an arbitrary agent production-ready.
