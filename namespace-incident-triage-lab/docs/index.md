# Scheduled application incident triage

A Kubernetes CronJob checks one application's Deployment readiness, controller
logs and related events every five minutes. Fresh evidence across two or
more scans qualifies an incident after at least five minutes. Kubernetes
ConfigMaps hold the active incident and a rolling 24-hour budget of three
dispatch reservations per application.

The direct path is **CronJob → Istio VirtualService → Agent Gateway → kagent
on Substrate → MCP → GitLab**. Agent Gateway wraps the incident as A2A 1.0.
MCP reads source evidence and records the ticket outcome. A durable receipt
can confirm the handoff if the gateway response is delayed or times out.

Application owners choose which objects and unusual log patterns to monitor
and which exact signatures to ignore. The agent can record a proposed ignore
rule for review. The application's policy changes when an operator adopts the
rule.

- [Interactive presentation](presentation.html) with scenario walkthroughs and actual code.
- [Office adoption](office-adoption.md) for target bindings and rollback.
- [Validation and evidence](validation.md) for the home-lab record and office canary.
- [Documentation maintenance](maintain.md) for editing and building this site.
