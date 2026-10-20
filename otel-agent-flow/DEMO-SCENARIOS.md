# Present the live workflow and agent-isolation demos

Use the same HTTPS UI for each example. Keep the prompt on the left and the activity map on the right. Select Logs to inspect API calls, tool names, error states, and original trace IDs. The observed-operation cards appear only when corresponding OTel spans arrive. A selected scenario never fabricates a span.

## Rehearse without work credentials

Select a scenario in bundled fixture mode and send the prompt. The fixture model and all returned business and identity data are simulated. Real kagent sessions, Substrate sandboxes, gateway/model HTTP traffic, MCP requests, and OTel exports run on the cluster.

| Scenario | Tool sequence | What to explain |
| --- | --- | --- |
| Simulated incident triage | Kubernetes workload conditions, Grafana alert summary, GitLab issue lookup | Correlate an ImagePullBackOff fixture with its alert and existing incident. No issue is created. |
| Simulated SDLC review | GitLab issue, GitLab pipeline status, change review | Explain a failed validation and human-review decision. No pipeline, repository, or deployment is changed. |
| Simulated identity isolation | Agent A reads team A, agent A is denied team B, agent B reads team B | Show distinct subject/resource aliases and the intentional denial error span. No Entra token is issued or validated. |

The map groups MCP traffic under its MCP component. The cards identify each received tool operation and its reported system. Fixture system labels are metadata on the fixture tool service, not proof of three separately deployed MCP servers. Selecting a card opens its original span. The UI displays a fixed set of component roles and does not pretend to be automatic discovery of every service.

## Demonstrate real incident triage

Use the existing-agent profile from LIVE-INTEGRATION.md. Select an approved read-only specialist that already has the required Kubernetes, Grafana, and GitLab tools. Do not add write permissions to make the example more dramatic.

Prepare a private prompt using the actual allowlisted tool names, target namespace, and incident reference:

> Inspect the designated demo workload's readiness and warning conditions using Kubernetes MCP. Query its relevant alert and recent error-rate summary using Grafana MCP. Read the existing GitLab incident and pipeline status. Correlate the evidence, cite the tool results, and propose a next step. Do not modify resources, create issues, trigger pipelines, or commit changes.

Ask one tool at a time during the first rehearsal if needed to make each hop clear. The UI shows completed spans as the exporters deliver them, so it does not guarantee animation during every in-flight call. Native actor resume, restore, checkpoint, and suspend remain visible beside the tool sequence.

The connected verifier accepts repeated `--expect-mcp SERVICE:TOOL` pairs for multiple servers. See LIVE-HOMELAB.md for the actual Kubernetes and GitLab example. Grafana needs its own live source and receipt before adding it to that claim. Keep server evidence separate from client tool-attempt evidence. Missing OTel stays unknown. Record reported token usage and explicit price estimates only.

## Demonstrate real SDLC inspection

Ask the approved specialist to read an existing GitLab issue, inspect a designated pipeline and failed job summary, compare with the approved deployment's Kubernetes status, and explain a review plan. Use the existing Grafana dashboard only for the named workload. The initial demo is read-only. Branch creation, commits, merge requests, approvals, and deployments need their own authorized execution flow and receipts.

If the agent uses an existing triage or SDLC skill, show the resulting tool calls. A mounted skill file does not prove that the agent used it. Explicit skill execution requires native runtime instrumentation as described in LIVE-INTEGRATION.md.

## Present the isolation example

Use ENTRA-ISOLATION-DEMO.md. Show allowed and denied calls through the policy front door, then inspect the matching native gateway span and backend request counter. Explain Entra identity, gateway authorization, Kubernetes access policy, and Substrate sandbox isolation as separate controls. A green actor lifecycle is not proof of Entra authorization.

## Live read-only scenarios

With `tools.mode: live`, the picker offers Kubernetes workload health, GitLab pipeline review, and a combined inspection. These use real MCP/API reads; fixture presets stay in fixture mode. Separate MCP activity panels highlight completed MCP execution spans and identify the exact tool. See [LIVE-HOMELAB.md](LIVE-HOMELAB.md) for the evidence and logging boundaries.
