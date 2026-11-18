# Six workflows built with kagent

The platform brings AI into operational and engineering workflows by combining
specialist agents with approved tools, knowledge and skills. These six examples
summarise the capabilities we have built, including a bounded software-delivery
prototype.

| Workflow | MCP / integration | What it does |
| --- | --- | --- |
| **AI incident triage and specialist routing** | Kubernetes, Grafana | Picks up alerts or Kubernetes events, routes them to the appropriate specialist agent, gathers evidence and produces a diagnosis and recommended next steps. |
| **Cluster health checks** | Kubernetes | Checks nodes, workloads, DNS, storage and platform components; investigates failures and produces actionable findings. |
| **Metrics and log investigation** | Grafana | Queries metrics, logs and dashboards to understand cluster health, investigate incidents and assemble an evidence pack with relevant dashboard links. |
| **ServiceNow incident intake and investigation** | ServiceNow integration, Kubernetes, Grafana | Brings incident context into the agent workflow for investigation and evidence gathering. The gateway intake implementation maps incoming incident JSON into an agent request. |
| **Governed data and compliance investigation** | Denodo / custom data MCPs | Provides controlled access to approved data for inventory, security and compliance investigations, including the owner-confirmed OC6 integration. |
| **Agent-assisted software delivery** | GitLab MCP | A bounded prototype coordinates planning, implementation, testing and review, producing a draft merge request with pipeline evidence for human review. |

## Integration scope

The documented integrations include Grafana, Kubernetes, ServiceNow, Denodo,
GitLab and PostgreSQL. This is a capability summary, not a complete inventory of
currently deployed MCP servers. ServiceNow incident intake can use the gateway
directly without an MCP.

The data integration is named **Denodo** in the documentation. **SDLC** names the
software-delivery workflow above; a separate workflow named STOC has not been
identified in the reviewed documentation.

## Delivery and evidence

The [historical achievements](historical-achievements.md) record the pod lead's
confirmation of completed health checks, triage, specialist agents, alerting,
ServiceNow and custom data integrations, Denodo security/compliance work and OC6
integration. Exact delivery dates and receiving-service acceptance remain with
the capability owners.

The latest gateway intake proof establishes incident payload mapping and agent
receipt. It does not establish autonomous incident resolution or the complete
ServiceNow incident lifecycle. The software-delivery workflow remains a bounded
prototype with human review before merge. Investigation permissions and approved
resource-changing workflows remain separate.

For each workflow, useful outcomes depend on the agent having the right tool
permissions, relevant knowledge and skills, and clear acceptance criteria.
Successful incident delivery alone does not establish that capability.
