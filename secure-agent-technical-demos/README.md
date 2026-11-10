# Choose a technical agent demonstration

Three terminal walkthroughs show what runs behind the onboarding form. Choose one for a focused session, or combine onboarding and security in about 25 minutes. Observability adds about 15 minutes once a real tool and its telemetry are connected.

| Demo | What the audience sees | Preparation |
| --- | --- | --- |
| [1. Onboard an agent](01-ONBOARD-AN-AGENT.md) | One request becomes an Agent, workload, protected route, policies, and a verification Job. Inspect the deployed objects and get a real response. | Compatible installed controllers, an empty approved demo slot, approved model, and HTTPS route. |
| [2. Inspect and test security](02-TEST-SECURITY.md) | Inspect hardening and identity policies. Compare an authenticated request with rejected callers. Query the tool identity's effective permissions. | An existing approved demo agent, caller-test permissions, and the actual MCP identity for the optional RBAC checks. |
| [3. Follow a tool call through OTel](03-FOLLOW-A-TOOL-CALL.md) | Make one bounded read-only tool request. Inspect its trace, tool operation, latency, and reported usage from the terminal and OTel viewer. | A real tool-enabled agent, instrumented backend, and existing telemetry exports correlated to that request. |

The [Teams message](TEAMS-MESSAGE.md) is ready to copy. The [technical overview](TECHNICAL-WALKTHROUGH.md) explains the architecture and the [shared command sheet](TERMINAL-COMMANDS.md) prepares the shells.

## Use the existing implementation

This folder contains presenter guides. It uses the existing CLIs and adds no deployment framework.

- Classic onboarding implementation and presentation: https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/secure-kro-classic-kagent
- Single-file onboarding simulation: https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/secure-kro-classic-kagent/onboarding-dashboard.html
- OTel implementation and integration notes: https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/otel-agent-flow

Download or clone `kagent-work-bundles` with those sibling folders. In the source monorepo, the equivalent root is `work-agent-bundles/`. The published classic implementation is the command reference even where it is absent from the source repository's `main` branch.

## Configuration

Use the variables in [TERMINAL-COMMANDS.md](TERMINAL-COMMANDS.md). Resolve every `{{PLACEHOLDER}}` privately. The classic examples deliberately use `classic-agents/demo`. Their paths, resource names, audience, and installed catalogs must match the selected environment. Do not transplant these names into an unrelated workplace deployment.

## Verification status

Prepared on 10 November 2026. Commands and JSON fields were checked against the published implementation. Shell examples and links were checked offline. These guides are not a new live rehearsal or proof of workplace readiness. The classic bundle's preflight and recorded validation identify its pinned versions. Discover the receiving versions before use.

The onboarding dashboard is synthetic. A real request can also use fixture tools. Demo 3 requires a real backend for a live-data claim. Missing spans or untested controls remain UNKNOWN.
