# Consume agents and the specialist crew

## Existing agents and current acceptance

Task-specific specialist agents and the triage system are confirmed delivered by the pod lead. The [historical record](historical-achievements.md) captures that capability; the following runtime/tool gates apply to new releases and expanded profiles. Existing delivery is not reset to planned because a new-release test remains open.

## Choose the entry point

| Consumer | Contract | Session/lifecycle owner |
| --- | --- | --- |
| SRE or application chat | Authenticated UI/API invokes a named Agent | Chat application with user-scoped access |
| ServiceNow event | Validated incident -> durable workflow -> gateway -> Agent | Incident workflow, with dedupe/retry state |
| Specialist calling another agent | Approved `subAgent` binding and destination policy | Parent workflow/agent with a bounded delegation budget |
| MCP-capable client | Approved agent-as-tool interface | Client plus platform identity policy; verify 1.0 transport |

Callers select the **Agent**, not its AgentTemplate, Harness, Worker or Actor. Use a fresh session for each independent incident. Reuse a `contextId` only to continue that incident/user conversation; knowledge shared across incidents is a separately governed service.

## Current A2A contract

The 1.0 HTTP JSON-RPC endpoint is `/agents/{namespace}/{name}` and its card is at `/agents/{namespace}/{name}/.well-known/agent-card.json`. gRPC uses `tenant` as `namespace/name`. Read the advertised card and pin the client protocol; the 1.0 shape and role/part fields differ from legacy examples.

For a deliberate, approved local canary, port-forward only the controller service on loopback and use a matching 1.0 client. The [gRPC request example](downloads/a2a-request.json) omits `contextId` to start a new session. It requests a simple answer and performs no tool call. The [official A2A guide](https://kagent.dev/docs/kagent/latest/examples/a2a-agents/) gives transport and task retrieval details.

Record task ID, context ID, terminal task state, artifacts and receiving/backend receipts. A transport HTTP 200 is not completion. Authentication tests must prove denied calls cause no agent execution or backend tool activity.

## The crew's operating contract

| Specialist | Input | Output and permission boundary |
| --- | --- | --- |
| Kubernetes | Trusted cluster/namespace/workload mapping | Bounded read observations and next checks |
| Network | Named route/service and allowed scope | Policy/DNS/connectivity evidence, no arbitrary destinations |
| Observability | Approved datasource/query window | Bounded metrics/logs with source and timestamps |
| Knowledge | Issue signature and caller entitlement | Reviewed, cited guidance with applicability/version |
| GitOps/change guidance | Findings and approved repository scope | Draft recommendation/change or fixed workflow request |

The coordinator chooses only necessary specialists, bounds recursion/time/tokens and returns disagreements or missing evidence explicitly. An agent's prose cannot grant another agent tools, impersonate an identity or approve remediation. Ticket text, log lines, repository content and tool results are untrusted data.

For independent sessions, verify no cross-context history, filesystem markers or artifacts leak. Sharing a worker over time is an implementation detail; it does not authorise shared conversation state. See [labs](labs.md).


## Kubernetes specialist acceptance

For the next reviewed release, the Kubernetes specialist uses the supported read-only capability contract. Approval and runtime acceptance are recorded per intended environment. Verify the configured tool allowlist, actual backend identity, allowed namespace/workload read, denied out-of-scope read and correlated task/tool receipts. Record the date, release/revision, operation, result and evidence scope in the controlled evidence store. The documentation and offline profile checks do not establish a completed Kubernetes tool invocation. Mark this milestone delivered only when its owner accepts those receiving-system receipts.
