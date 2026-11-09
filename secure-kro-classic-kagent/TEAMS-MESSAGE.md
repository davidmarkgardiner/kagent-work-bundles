Thanks for the feedback today. I've attached the onboarding demo we walked through.

For the next session, I suggest going a level deeper into what happens after the YAML is submitted. We could watch the agent resources come online, inspect the generated configuration and security policies, demonstrate allowed and denied requests, and follow a real read-only tool call through the OTel view to the agent's response.

The approach is configuration-led, using kagent, KRO and agentgateway, so there is relatively little bespoke Python orchestration to walk through. The technical detail sits in the resource definitions, identity and permission boundaries, reconciliation, and runtime behaviour. There are also small verifier and tool-adapter components we can inspect if code integration is the part you're most interested in.

Which emphasis would be most useful for the next demo?

1. **Security and access**: caller identity, allowed/denied requests, tool permissions, and the evidence that the controls are enforced.
2. **Runtime and observability**: the agent coming online, model and tool calls, traces, latency, and reported usage.
3. **Integration and extension**: how your application calls the agent, how models/skills/tools are configured, and where custom adapter code fits.

My recommendation is a 25-minute terminal-and-OTel walkthrough combining the first two. We would rehearse the selected live path in advance and make clear which application-binding capabilities are still proposed. If you have a particular integration or failure case in mind, send it over and we can shape the session around that.
