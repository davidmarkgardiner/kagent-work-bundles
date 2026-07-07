# K Agent Agentic Cluster Delivery Checklist

Planning assumptions:
- Today is Tuesday 2026-07-07.
- The new agentic cluster is expected Thursday 2026-07-09.
- The target is a dev-ready operating position by Friday 2026-07-31, with a repeatable path for pre-prod and prod.

## This Week: Cluster Bring-Up

- [ ] Confirm the new agentic cluster is online, reachable, and has the expected ingress, DNS, TLS, namespaces, storage class, and egress.
- [ ] Create the UAMI for the kagent runtime and record the client ID, object ID, resource ID, and owning scope.
- [ ] Configure workload identity or the approved equivalent so the kagent runtime uses UAMI-backed access, not static Azure secrets.
- [ ] Assign the first-pass RBAC across the management group and target clusters. Start read-first, then explicitly approve any write permissions.
- [ ] Deploy only the minimum viable kagent control path first: kagent harness, required environment values, Agent Gateway, and A2A endpoint.
- [ ] Prove one real A2A request completes through the controller and agent path. Do not count service presence as readiness.
- [ ] Hold broader integrations until the single-call path is healthy. Do not wire live alert traffic, broad tools, or write-capable agents before this proof.
- [ ] Prepare the Alertmanager receiver/webhook change, but only point live alert flow once the minimum viable kagent path is healthy.
- [ ] Confirm the Teams alerting model: target Team, channel, owning group, on-call responders, and escalation expectations.
- [ ] Set up the Teams notification receiver/webhook or out-of-box Teams integration for the alert route.
- [ ] Send a basic ping/test notification into the Teams channel before wiring real alert traffic.

## Next Week: Alert Triage and Guardrails

- [ ] Point only a narrow Alertmanager route or synthetic receiver at the new kagent intake.
- [ ] Point Teams notifications at the same narrow/synthetic alert route so engineers see test alerts in the expected channel.
- [ ] Fire synthetic alerts and prove the alert reaches kagent, is enriched, and creates a traceable triage run.
- [ ] Prove the Teams message includes enough context to act: alert name, severity, cluster, namespace/service, kagent run ID, dashboard/evidence link, and ticket link when available.
- [ ] Implement grouping, deduplication, and rate limits before broad alert routing.
- [ ] Run a repeated-alert storm test and confirm it creates one incident thread with updates rather than ticket spam.
- [ ] Confirm Teams notification spam controls: grouped updates, severity filters, quiet hours/on-call routing if applicable, and a clear stop/disable path.
- [ ] Configure workflow TTL/retention and a cleanup runbook for stale Argo/jobs/workflows.
- [ ] Add monitoring for alert intake, triage completion, failures, stale workflows, HITL pauses, ticket creation, and latency.
- [ ] Install or enable only the core specialist agents needed for dev proof: Kubernetes/AKS, Azure estate, Grafana evidence, remediation planner, and ticketing.
- [ ] Prove one agent-to-agent handover from the triage agent to a specialist agent and back.

## Week Three: Operating Model Proof

- [ ] Prove the human loop for risky remediation: pause, named approval, timeout, resume, and decline.
- [ ] Prove GitLab ticket or MR creation from triage output, including alert summary, evidence, owner, run ID, and links.
- [ ] Confirm Teams, GitLab, and kagent triage stay correlated through a shared alert fingerprint/run ID.
- [ ] Define the SRE queue ownership rota: named daily or weekly owners responsible for reviewing kagent triage, remediation suggestions, unresolved alerts, and queue health.
- [ ] Define the daily queue review ritual: inspect new triage runs, stuck runs, missed routing, low-confidence answers, failed tool calls, duplicate alerts, and remediation recommendations.
- [ ] Define the weekly improvement ritual: review what the agents missed, what they over-escalated, what they could not prove, and what should become a skill, prompt, runbook, tool, alert change, or backlog ticket.
- [ ] Create a gap-capture path: every repeated miss or weak triage result should become either a skill/runbook update, an alert enrichment fix, a routing change, or a tracked engineering ticket.
- [ ] Define who can update kagent skills/prompts/runbooks, how changes are reviewed, and how they are regression-tested against recent incidents.
- [ ] Decide whether ServiceNow is a July pilot or an August/backlog item. Do not let it block the core GitLab path.
- [ ] Complete the security review for UAMI scope, MCP tools, prompt boundaries, audit logging, and data retention.
- [ ] Run alert-like A2A capacity smoke tests at 1, 5, 10, and 20 concurrent requests after the single-call path is healthy.
- [ ] Define the first knowledge-base and memory backlog: approved sources, freshness labels, privacy rules, and retention.
- [ ] Define the bring-your-own-agent onboarding bar: capability declaration, identity, allowed tools, audit, tests, and kill switch.
- [ ] Define the value metrics captured from daily use: time to analyze, time to remediate, confidence score, human touches, avoided escalation, ticket quality, and repeat-incident reduction.

## Final Week: Dev Acceptance and Replication

- [ ] Run a full dev acceptance scenario: synthetic alert -> Alertmanager -> kagent triage -> specialist agent -> HITL/ticket -> Grafana/dashboard evidence.
- [ ] Include Teams in the dev acceptance scenario: synthetic alert -> Teams notification -> kagent triage -> specialist/HITL/ticket/dashboard evidence.
- [ ] Capture a single evidence index with run IDs, commands, screenshots/links, ticket/MR links, and dashboard queries.
- [ ] Run a real SRE queue rehearsal: assign an owner, review the queue, classify agent misses, open/update gap tickets, and update at least one skill/runbook/prompt from the findings.
- [ ] Prove the value loop on at least one incident or synthetic incident: baseline analysis/remediation time, agent-assisted analysis/remediation time, confidence, human review outcome, and follow-up improvement item.
- [ ] Package the dev install as a lift-and-shift baseline: environment values, secret placeholders, UAMI/RBAC matrix, runbooks, smoke tests, and rollback steps.
- [ ] Identify which engineering integrations are reusable as-is and which require environment-specific changes before pre-prod.
- [ ] Create prod readiness gates: identity approval, alert routing approval, dashboard coverage, support ownership, rollback, and comms.
- [ ] Decide what moves to August: ServiceNow depth, richer memory, BYO agent onboarding, broader remediation writes, and production rollout hardening.

## SRE Queue Operating Model

- [ ] Assign a named SRE owner daily or weekly to manage the kagent queue and keep the system in active use.
- [ ] Review new and open triage runs at least once per working day.
- [ ] Check whether the right key agent picked up each issue. If not, record the missing signal, routing gap, missing skill, missing tool, or missing runbook.
- [ ] Review agent triage quality: evidence used, confidence, root-cause quality, hallucination risk, and whether the answer was actionable.
- [ ] Review remediation recommendations: safety, approval requirement, blast radius, rollback, and whether the recommendation should become an approved runbook path.
- [ ] Open a gap ticket for repeated misses, weak evidence, bad routing, missing data enrichment, failed tools, or unclear ownership.
- [ ] Update skills, prompts, runbooks, alert labels, or routing rules when the fix is small and owned; otherwise create a backlog ticket with evidence.
- [ ] Track value for every reviewed incident where possible: time to analyze, time to remediate, confidence, avoided escalation, manual steps saved, and whether the agent reduced repeat work.
- [ ] Review weekly trends with engineering: top misses, top successful automations, noisy alerts, missing enrichment, tool failures, and the highest-value next improvements.
- [ ] Treat usage as part of the process: if SRE does not use and review the queue daily, the system will not improve and value will not be measurable.

## Definition of Ready for Development

- [ ] kagent harness is deployed on the new agentic cluster.
- [ ] UAMI-backed MCP access works across the approved management group and cluster scopes.
- [ ] Alertmanager can send a synthetic alert into the system and get a traceable triage run.
- [ ] Teams receives ping/test alerts and synthetic incident alerts in the agreed channel with useful context and no uncontrolled spam.
- [ ] Deduplication and spam controls are tested.
- [ ] Workflows are cleaned up and monitored.
- [ ] Specialist agents are visible, owned, and can complete at least one handover.
- [ ] Human approval works for risky remediation.
- [ ] GitLab ticket/MR creation works from triage output.
- [ ] Daily or weekly SRE queue ownership is assigned and rehearsed.
- [ ] Agent misses and weak triage results have a clear gap-ticket or skill-update path.
- [ ] Value metrics are captured from actual use: analysis time, remediation time, confidence, human touches, and repeat-incident reduction.
- [ ] Grafana shows intake, completion, failures, HITL, ticketing, and latency signals.
- [ ] Pre-prod/prod replication can be driven by values, runbooks, and smoke tests rather than manual reconstruction.
