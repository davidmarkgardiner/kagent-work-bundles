# Architecture talk track

Use these paragraphs with `index.html` before the live terminal walkthrough. They describe the proposed integrated design. Use receiving-system receipts when describing a control as implemented.

## Architecture overview

> In this design, a team consumes an agent through a protected API. Entra supplies the identity and destination token. Our ingress or application validates that token, and Agent Gateway enforces the configured route policy. The agent runs in Kubernetes alongside separately controlled MCP services. Skills come from reviewed GitLab releases. The agent, its skills and the MCP services have central registry records describing their owners, versions and approved connections. Model requests go through the Gateway to the existing model garden and its approved LLM endpoints.

> The registry, identity system, gateway and Kubernetes controls have different jobs. The registry records the intended service. Identity and destination policy determine who can use it. Runtime and network controls constrain the actual access paths. The deployment and acceptance receipts tell us which checks passed.

## Authentication flow

> There are two separate paths here. First, the application uses its UAMI to obtain a token for the agent API. A human uses an approved interactive client, or signs in to an application that authorizes that user before invoking the agent. The receiving API checks the token and permission for the selected agent.

> Second, the running agent needs its own authority to call a tool. Its trusted credential adapter binds it to the approved Agent ID or assigned agent identity and obtains a token for the MCP destination. Gateway checks that identity, audience and tool permission. The MCP service enforces the bounded operation and uses its own backend identity. We keep the caller, agent and tool identities separate.

## Evaluation and observability

> Observability shows the operations we received. Evaluation assesses the required behavior and policy checks. We bind release evaluations to the exact agent, skill, MCP, model and policy versions before promotion through the existing approval and GitOps flow. Runtime evaluations sit beside OTel and LGTM with their own approved data access and permissions. Their verdicts and the underlying evidence join the registry's release record. This lets us explain both what happened and whether the reviewed candidate met its acceptance criteria.
