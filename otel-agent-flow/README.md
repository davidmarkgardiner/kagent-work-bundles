# OTel agent workflow demo

Start at [FRONT-SHEET.md](FRONT-SHEET.md). Download this repository from GitHub and hand the `otel-agent-flow` folder to the work agent with [WORK-AGENT-PROMPT.md](WORK-AGENT-PROMPT.md).

The app has prompt entry on the left and switchable workflow/log views on the right. Received OTel drives the map. Native Substrate identity correlates worker restore, actor execution, checkpoint, and suspend.

Use [WORK-BUNDLE-README.md](WORK-BUNDLE-README.md) to deploy. Use [LIVE-INTEGRATION.md](LIVE-INTEGRATION.md) to reuse the existing agentgateway, agents, Kubernetes MCP tools, and skills. AKS serves the app through an Istio VirtualService and the existing HTTPS Gateway.

The current single-cluster rehearsal passed six fixture workflows, including triage, SDLC review, and simulated identity isolation. An earlier live-model workflow used simulated tools. The existing-agent work profile has offline manifest checks. Actual workplace integrations still require target receipts.

Build the backend container from the Dockerfile in work CI. No separate ZIP or image archive is needed. See [IMAGE-IMPORT.md](IMAGE-IMPORT.md).

Use [DEMO-SCENARIOS.md](DEMO-SCENARIOS.md) for triage and SDLC examples. Use [ENTRA-ISOLATION-DEMO.md](ENTRA-ISOLATION-DEMO.md) for the separate identity allow/deny demonstration and its evidence requirements.

For the real-model example with live Kubernetes and GitLab reads, use [LIVE-HOMELAB.md](LIVE-HOMELAB.md). It includes the server scopes, live values, multi-server verifier, and credential lifecycle boundary.

Live mode also offers Kubernetes-only, GitLab-only, and combined presets. Separate MCP panels identify and highlight the tool that actually ran from received execution spans. Kubernetes currently exports tool spans; GitLab additionally exports OTel logs.

Use [RUNTIME-COMPARISON.md](RUNTIME-COMPARISON.md) for the paired demonstrations. The runtime picker selects a normal native kagent ADK Deployment or a Substrate actor. Standalone-only mode creates no kagent/Substrate custom resources and does not require their platform installation.

Use [NATIVE-KAGENT-OTEL.md](NATIVE-KAGENT-OTEL.md) for the separate KAgent 1.x
documentation-agent viewer, native skill/knowledge spans, bounded request
retention, and observation-only mode.
