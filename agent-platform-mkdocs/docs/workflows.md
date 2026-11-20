# Six workflows built with kagent

The platform brings AI into operational and engineering workflows by combining
specialist agents with approved tools, knowledge and skills. These six examples
summarise the capabilities we have built, including a bounded software-delivery
prototype.

| Workflow | MCP / integration | What it does | Presentation |
| --- | --- | --- | --- |
| **AI incident triage and specialist routing** | Kubernetes, Grafana | Picks up alerts or Kubernetes events, routes them to the appropriate specialist agent, gathers evidence and produces a diagnosis and recommended next steps. | [Open deck](workflow-decks/incident-triage.html) |
| **Cluster health checks** | Kubernetes | Checks nodes, workloads, DNS, storage and platform components; investigates failures and produces actionable findings. | [Open deck](workflow-decks/cluster-health.html) |
| **Metrics and log investigation** | Grafana | Queries metrics, logs and dashboards to understand cluster health, investigate incidents and assemble an evidence pack with relevant dashboard links. | [Open deck](workflow-decks/grafana-investigation.html) |
| **ServiceNow incident intake and investigation** | ServiceNow integration, Kubernetes, Grafana | Brings incident context into the agent workflow for investigation and evidence gathering. The gateway intake implementation maps incoming incident JSON into an agent request. | [Open deck](workflow-decks/servicenow-intake.html) |
| **Governed data and compliance investigation** | Denodo / custom data MCPs | Provides controlled access to approved data for inventory, security and compliance investigations, including the owner-confirmed OC6 integration. | [Open deck](workflow-decks/governed-data.html) |
| **Agent-assisted software delivery** | GitLab MCP | A bounded prototype coordinates planning, implementation, testing and review, producing a draft merge request with pipeline evidence for human review. | [Open deck](workflow-decks/software-delivery.html) |

Each deck opens in a browser and includes an interactive flow, code excerpts and an evidence section. The triage deck presents the scheduled application-scanner example.

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

## Scheduled application scanner lab

Use the [Sentinel workplace verification prompt](sentinel-work-agent-prompt.md) to audit the deployed probe and collect receiving-system evidence.

On 19 November 2026, a separate lab build added five-minute polling for
application readiness, controller logs and Kubernetes Warning events. The
scanner requires persistent evidence and reserves at most three dispatches
per application in a rolling day. A scoped MCP tool can record an exact
log or event signature as a proposed ignore rule for operator review.

A disposable Kubernetes cluster exercised the packaged scanner, source
reads, and an assigned issue preview through a fixture ingress. Dated fixture
tests exercise duplicate suppression, the fourth-incident limit, and GitLab
assignment read-back.

The subsequent home-lab run used the actual Agent Gateway and Substrate
agent with Argo scaled to zero. Its durable outcome recorded one assigned
preview after the caller timed out. The recorded follow-up and replay did
not have a matching receipt. The bundle owner later confirmed completion
and testing. Workplace issue creation and assignment still require a
receiving-project read-back. The work handoff includes editable MkDocs
sources and the standalone presentation.
