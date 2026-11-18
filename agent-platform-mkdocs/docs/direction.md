# North Star and delivery

## Delivery builds on existing capabilities

The [historical record](historical-achievements.md) captures delivered operational and integration capabilities confirmed by the pod lead. The current focus is evaluation and registry-based reuse of agents, skills and tools. The earlier proposal below is planning context; existing triage, ServiceNow integration, specialists and onboarding are delivered foundations rather than new first-time builds. The [calendar](roadmap.md) is the maintained status reference.

**North Star:** teams can deploy an accountable, observable agent through a reviewed platform contract, and people or event workflows can consume it with access limited to their task. Useful operational results carry evidence; changes follow owned approval and execution paths.

The platform combines kagent, Agent Substrate, agentgateway, KRO and approved MCP backends. Its value is repeatable onboarding, isolated execution, controlled identity and useful investigation outcomes. Counts of agents or demos alone are insufficient measures.

## Shared platform, separate consumers

ServiceNow processing owns durable incident execution. The SRE chatbot owns interactive exploration and user sessions. Both reuse specialists, reviewed knowledge, model routes and telemetry, with distinct caller identities and permissions. Incident handling must continue if the chatbot is unavailable.

The specialist crew is a set of bounded capabilities selected per incident: Kubernetes, network, observability, knowledge and GitOps/change guidance. Fan out only when evidence calls for that specialist. No new agent, tool or permission is created from ticket text.

## Proposed milestones

Use the [delivery roadmap](roadmap.md) for the maintained Q4/Q1 outcome sequence and [achievements archive](achievements.md) for fortnightly evidence. These sections describe horizons and dependencies; the roadmap is maintained without promised delivery dates.

The 17 November pod direction is a proposal for one tech lead and three engineers. These dates and targets remain planning assumptions, pending product-owner agreement and the policy/identity dependencies.

| Window | Deliverable | Acceptance and accountable role |
| --- | --- | --- |
| Remaining Q4 2026 | Extend onboarding with Entra / 1.0 acceptance | Platform engineer: one pod-owned agent, approved read, caller/tool denials, revocation and correlated traces |
| Remaining Q4 2026 | Expand the ServiceNow incident contract | Integration engineer with SRE: one queue, 2–3 patterns, trusted target mapping, payload/update contracts and replay fixtures |
| Q1 2027 | Harden and extend existing investigation workflows | Integration engineer: durable state, duplicate handling, explicit failure/handoff and reviewed ticket updates |
| Q1 2027 | Registry-based reuse and second-team adoption | Pod lead: a second team onboards through the same contract; versioned knowledge and evaluation releases serve both consumers |

Identity/security owners approve grants and exceptions. Service owners own runbook correctness and incident decisions. The pod lead owns architecture, scope and acceptance; the product owner sets priority. Engineers verify AI-assisted implementation and reviews.

## Measures and progression

Proposed pilot measures from the direction document are acknowledgement within one minute, useful triage within five minutes for supported cases, and at least 80% of results accepted without material correction. They are **unmeasured targets**, not SLOs. Establish the manual baseline, sample size, incident mix, exclusions, timeouts and cost per useful result before claiming improvement.

Start with read-only investigation. Later increments can draft a reviewed GitLab change or request a fixed workflow. Production remediation, arbitrary BYO runtimes, wider catalog growth and ownership of the chatbot require their own prioritisation and acceptance.

The six-month modernisation statement remains strategic context: KRO/ASO lifecycle, Flux delivery, progressive fleet changes and Argo workflows. Its older path names and “working/near-production” labels are historical assertions; use current source links and receiving receipts before treating them as readiness evidence. See [sources](sources.md).
