# OTel agent workflow demo

Start at [FRONT-SHEET.md](FRONT-SHEET.md). Download this repository from GitHub and hand the `otel-agent-flow` folder to the work agent with [WORK-AGENT-PROMPT.md](WORK-AGENT-PROMPT.md).

The app has prompt entry on the left and switchable workflow/log views on the right. Received OTel drives the map. Native Substrate identity correlates worker restore, actor execution, checkpoint, and suspend.

Use [WORK-BUNDLE-README.md](WORK-BUNDLE-README.md) to deploy. Use [LIVE-INTEGRATION.md](LIVE-INTEGRATION.md) to reuse the existing agentgateway, agents, Kubernetes MCP tools, and skills. AKS serves the app through an Istio VirtualService and the existing HTTPS Gateway.

The current single-cluster rehearsal passed six fixture workflows, including triage, SDLC review, and simulated identity isolation. An earlier live-model workflow used simulated tools. The existing-agent work profile has offline manifest checks. Actual workplace integrations still require target receipts.

Build the backend container from the Dockerfile in work CI. No separate ZIP or image archive is needed. See [IMAGE-IMPORT.md](IMAGE-IMPORT.md).

Use [DEMO-SCENARIOS.md](DEMO-SCENARIOS.md) for triage and SDLC examples. Use [ENTRA-ISOLATION-DEMO.md](ENTRA-ISOLATION-DEMO.md) for the separate identity allow/deny demonstration and its evidence requirements.
