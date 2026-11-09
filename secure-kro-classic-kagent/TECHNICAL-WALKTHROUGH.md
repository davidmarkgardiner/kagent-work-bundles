# Demonstrate how the platform runs and constrains an agent

Proposed follow-up to the onboarding demonstration. Allow 25 minutes. Use a terminal beside the OTel activity map, then open an original trace when the audience wants detail.

The technical story is how a small declarative request becomes a running agent with controlled access. KRO reconciles the resource graph, kagent runs the agent, and agentgateway applies the configured traffic policies. The customer writes less orchestration code; the platform still has concrete schemas, runtime configuration, identity checks, permissions, and operational evidence to inspect.

## Walk through the execution and its evidence

| Time | Show | Explain and verify |
| --- | --- | --- |
| 0–3 min | Today's single-file onboarding dashboard, then its YAML | The HTML demonstrates the user journey. Its API handoff is simulated. The YAML captures intent; the platform owns the resource graph and security configuration. |
| 3–8 min | The installed KRO graph and an approved demo instance reconciling | Watch the owner, Agent, Deployment, Pods, Golden Job, and protected route. Inspect the actual objects. If the agent is already running, describe this as an existing deployment rather than replaying a fictitious startup. |
| 8–13 min | Missing JWT, wrong identity, and wrong audience | Send the console's fixed, bodyless negative requests. Compare actual HTTP results with the expected policy decision. Inspect matching Gateway evidence where exported. These tests exercise the caller boundary without sending model prompts. |
| 13–20 min | One authenticated, bounded Kubernetes MCP read | Use the protected agent endpoint. Show the returned answer and native task/context IDs. Follow the received runtime, model, Gateway, and MCP spans for that same request. Inspect the actual tool operation and compare its result with an independent Kubernetes read. |
| 20–23 min | A forbidden operation or cross-resource access check | Inspect effective backend permissions. If a separately rehearsed MCP isolation probe is available, show its rejection and zero protected-backend request delta. A model saying “I cannot do that” is not an authorization test. |
| 23–25 min | Trace details, configuration ownership, and lifecycle | Show latency and reported usage where available. Explain how a reviewed change triggers fresh verification. Optionally remove the one approved demo instance and observe its captured resources disappear while shared services remain. |

Use [TERMINAL-COMMANDS.md](TERMINAL-COMMANDS.md) for the presenter commands. Use [TEAMS-MESSAGE.md](TEAMS-MESSAGE.md) to agree the next session's emphasis with the team.

## Prepare one coherent live path

- Choose the receiving context, installed API/runtime versions, dedicated demo slot, protected HTTPS endpoint, approved model, and one real read-only MCP tool. Rehearse before offering the live demonstration.
- Reuse existing models, identity configuration, tool adapters, and telemetry destinations. Do not change shared controllers or broaden permissions to make the demo work.
- Confirm the OTel deployment's effective mode. The bundle defaults include fixtures, and genuine runtime spans can still describe simulated model or tool data. Select real backends for a live-data claim.
- Connect the viewer to received telemetry from the selected agent, Gateway, model path, and instrumented MCP server. Preserve existing exports. A read-only viewer observes requests invoked through the approved client; it does not become another invocation front door.
- Correlate by actual trace/parent IDs and native task/context identity. The classic query helper does not inject `traceparent`; verify runtime correlation during rehearsal. Do not associate unrelated activity by timing alone.
- Keep prompts, tokens, headers, and tool-result bodies out of the OTel projection. Display bounded operational metadata. Keep private configuration and receipts outside the public repository.

The classic reference uses kagent 0.10.4, KRO 0.9.4, and agentgateway 1.7.0. The OTel bundle also contains newer native/Substrate paths. Its existing-agent Substrate verifier is not an acceptance test for an arbitrary classic Agent. Use the compatible observation path and validate it against the receiving versions. Do not switch runtimes for this presentation.

## State what each observation establishes

| Observation | What it establishes |
| --- | --- |
| Current owner, ready Agent/runtime, and matching Golden receipt | This instance reconciled and completed the verifier's model check. It does not establish a successful MCP operation. |
| Rejected request plus the native Gateway policy decision | This request was denied at the named caller boundary. It does not establish that every direct Service or controller route is blocked. |
| Client tool span | The agent attempted the operation. Backend completion needs corresponding server or audit evidence. |
| Matching completed MCP server/handler evidence, bounded result, and independent read-back | The approved tool executed against the demonstrated target. Keep an unset span status distinct from reported success. |
| `auth can-i` result | An authorization decision for that subject and scope. It does not itself prove the running adapter uses that identity or that network traffic is blocked. |
| Actual approved and denied traffic from reviewed probe identities | Enforcement on the tested paths. A NetworkPolicy manifest alone establishes configured intent. |
| Mounted skill or skill selected in YAML | Configured guidance. Claim skill loading or execution only when corresponding runtime evidence exists. |

If classic onboarding and real-tool OTel execution cannot be connected in time, present them as two named demonstrations. Say which runtime and request each uses. Keep missing evidence marked UNKNOWN rather than presenting them as one end-to-end run.

## Offer code depth when useful

There is useful Python to inspect: the Golden verifier, the protected A2A client, and bounded MCP adapters. Show one small function and its acceptance evidence if the team wants it. Custom tool integration is the appropriate place for a code-focused follow-up; a large bespoke Python orchestration framework is not required for the configuration-led onboarding flow.

## Existing material

- Onboarding dashboard from today's demonstration: https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/secure-kro-classic-kagent/onboarding-dashboard.html
- Classic terminal walkthrough: https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/secure-kro-classic-kagent/TERMINAL-DEMO.md
- Connect the OTel demo to existing agents: https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/otel-agent-flow/LIVE-INTEGRATION.md
- Workplace OTel prerequisites and evidence: https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/otel-agent-flow/LIVE-WORKPLACE-ONE-SHEET.md
- Real Kubernetes and GitLab tool-flow example: https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/otel-agent-flow/LIVE-HOMELAB.md
- Separate identity-isolation probes: https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/otel-agent-flow/ENTRA-ISOLATION-DEMO.md

Prepared from the repository sources and current published guides on 9 November 2026. No cluster commands, model requests, probes, configuration changes, or deployments were executed while preparing this walkthrough. Receiving-environment readiness remains to be checked.
