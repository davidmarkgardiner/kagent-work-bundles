# OTel agent workflow demo

Start at [FRONT-SHEET.md](FRONT-SHEET.md). Download this repository from GitHub and hand the `otel-agent-flow` folder to the work agent with [WORK-AGENT-PROMPT.md](WORK-AGENT-PROMPT.md).

The app has prompt entry on the left and switchable workflow/log views on the right. Received OTel drives the map. Native Substrate identity correlates worker restore, actor execution, checkpoint, and suspend.

Use [WORK-BUNDLE-README.md](WORK-BUNDLE-README.md) to deploy. Use [LIVE-INTEGRATION.md](LIVE-INTEGRATION.md) to reuse the existing agentgateway, agents, Kubernetes MCP tools, and skills. AKS serves the app through an Istio VirtualService and the existing HTTPS Gateway.

The local single-cluster rehearsal passed three fixture workflows and one live-model workflow with simulated tools. The existing-agent work profile has offline manifest checks. Actual workplace integrations still require target receipts.

Build the backend container from the Dockerfile in work CI. No separate ZIP or image archive is needed. See [IMAGE-IMPORT.md](IMAGE-IMPORT.md).
