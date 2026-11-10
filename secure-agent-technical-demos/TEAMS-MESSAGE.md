Thanks for the questions following the onboarding presentation. I've put together three technical demos we can walk through from the terminal:

1. **Onboarding and deployment.** Submit an agent request, watch the controllers create the resources, inspect the generated YAML and hardening, and verify the protected API.
2. **Security and application access.** Inspect the gateway policies, show accepted and rejected callers, and walk through the tool identity's permissions.
3. **Runtime and observability.** Follow a real read-only tool request through the agent, gateway, and MCP server using terminal output and the OTel view.

The demo menu and command sheets are here:
https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/secure-agent-technical-demos

The onboarding implementation and presentation are here:
https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/secure-kro-classic-kagent

The platform uses the open-source KRO, kagent, and agentgateway projects. Much of the technical detail is in the resource definitions, policies, reconciliation, and runtime behaviour. We can inspect the controller source or the smaller verifier and tool-adapter code if that is the depth you're looking for. Your application code can stay in your existing ADO repository; we can focus on its endpoint, identity, and gateway-policy integration.

These demos cover a different use case from the documentation assistant we discussed, which focuses on retrieving guidance and answering questions. Here the focus is agents invoking approved tools against operational systems. The first live tool example would be a bounded Kubernetes read. Changes to systems or repositories require the relevant permissions and approval flow.

Which demo would be most useful, and is there a particular integration or failure case you want to see? I'd suggest combining onboarding and security first, then adding observability if that is your main interest. We'll rehearse the selected live path in the target environment before the session.

For the question about "Copilot harness in production", could you share the product or framework you mean, and whether you're asking about execution, hosting, security, or operational support?
