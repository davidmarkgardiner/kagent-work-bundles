# Teams message draft

Draft for David to review and send. No message has been sent.

---

Hi all, I've pulled together a handoff covering the remaining demo evidence and a proposal for agent registration.

For the demo, I'd like us to follow the same main Go Agent through deployment, both authenticated Gateway hops, actual tool execution and correlated Grafana evidence. The runtime deny/restore test should use a real Agent task as well as credential probes. Please also add a synthetic confidential-data request that the Gateway blocks, with a correlated OTel decision and proof the backend was not read. Keep the data itself out of telemetry.

On registration, could we approve the accountable service/profile, identity and permitted capabilities, then automatically record tasks and temporary workers within that scope? Agents could adapt their plans to new problems without a fresh manual registration for each composition. Broader access or higher-risk behaviour would still need review. Tool permissions are central, alongside controls on code execution, data, credentials and outputs.

The proposed model keeps ownership and auditability while avoiding the need to predict every future problem. Could we agree what "agent registration" covers and which changes need renewed approval?

Work-agent handoff:
https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/dice-gateway-auth-otel/WORK-AGENT-README.md

Registration discussion:
https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/dice-gateway-auth-otel/AGENT-REGISTRATION-DISCUSSION.md
