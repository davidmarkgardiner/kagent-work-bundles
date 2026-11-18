# Agent platform handbook

## Delivered capability and current work

See [six workflows built with kagent](workflows.md) for a stakeholder summary of incident triage, health checks, Grafana investigation, ServiceNow intake, governed data access and agent-assisted delivery.

The pod lead confirms completed health checks, ServiceNow instance/integrations, triage, task-specific agents, alerting, custom MCP data integration, Denodo security/compliance integration, OC6 integration and self-service agent onboarding. See [historical achievements](historical-achievements.md) for the owner-confirmed record and approximate Q2/Q3 placement. Evaluation and central-registry registration are underway. Q4/Q1 entries describe evolution of these services, including release-specific acceptance.

**Refreshed: 18 November 2026.** This is the working guide for deploying, using and operating our agent platform. It brings the recent isolation, KRO composition, Entra identity, ServiceNow integration, skills/knowledge and delivery-planning work into one portable documentation site.

The platform provides governed agent onboarding and AI-enabled operational workflows, including ServiceNow integration and investigation. Interactive SRE chat is a separate consumer of the same platform.

| Reader | Start with | Outcome |
| --- | --- | --- |
| Product owner or pod lead | [Delivery roadmap](roadmap.md), [achievements](achievements.md) | Delivered outcomes, current focus, next delivery and decisions |
| Platform engineer | [Architecture](architecture.md), [deployment](deploy.md) | Understand ownership and the supported onboarding path |
| Agent author or consumer | [Consumption and the crew](consume.md) | Choose a supported profile and invoke it correctly |
| Security or identity owner | [Isolation](isolation.md), [Entra identity](identity.md) | Review boundaries and the outstanding policy gate |
| Receiving work agent | [Handoff and hosting](handoff.md), [labs](labs.md) | Copy, build, adapt and collect target evidence |

## Current baseline

Use kagent **1.0.1**, with the **1.0.0 Substrate version that its release pins**. The latest standalone Substrate is **1.0.1** and is a separate compatibility-test candidate. agentgateway **1.7.0** is the current gateway target. These are release checks, not a statement about deployed workplace versions. Read the [version matrix](versions.md) before touching an old lab.

## What is ready, and what remains gated

This handbook, its downloadable lab profile and its build process can be reviewed now. Earlier lab receipts retain their original version/environment scope. Fresh kagent 1.0.1 runtime, network denial, token refresh, revocation and workplace acceptance must pass the [lab matrix](labs.md). The policy blocker remains open; a new runtime version does not close it.

The site is source for an internally hosted handbook. Building it does not publish a website. [Hosting instructions](handoff.md) describe the receiving pipeline.
