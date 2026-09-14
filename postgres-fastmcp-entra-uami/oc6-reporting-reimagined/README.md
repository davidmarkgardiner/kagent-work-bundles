# Reimagining OC6 reporting and agent-assisted remediation

## Proposal status

This document is a proposal for agreement in principle. It explains why the
current PostgreSQL MCP reporting approach should change, what the replacement
would look like, and which decisions are needed before implementation.

Agreement with this direction is not approval to change the production
database, dashboards, FastMCP deployment, kagent configuration, permissions, or
clusters.

## Executive summary

The initial design allowed the agent to retrieve and reason over too much
PostgreSQL data. Broad queries produced large MCP responses, consumed excessive
model input tokens, exhausted useful context, and prevented the agent from
answering management reporting questions reliably.

The proposed design separates reporting from investigation:

1. PostgreSQL or the upstream compliance pipeline evaluates and aggregates OC6
   data into approved views.
2. Grafana or an existing Power BI product gives management a continuously
   available place to inspect fleet compliance without invoking an agent.
3. FastMCP exposes only small, typed summaries and exact finding lookups needed
   for a conversation.
4. The policy agent explains a selected finding and retrieves an approved
   remediation playbook.
5. When live cluster evidence is required, the policy agent may delegate a
   tightly scoped investigation to a read-only Kubernetes specialist over A2A.

This preserves the useful conversational experience while moving bulk data,
aggregation, and routine reporting out of the model context.

## Where we are now

The workplace already has a PostgreSQL MCP deployment used by kagent as a
reporting interface. Management users want answers to questions such as:

- Are all production namespaces using encrypted communication?
- Which clusters are non-compliant with OC6?
- Which applications use unapproved cipher suites?
- Which namespaces have service mesh disabled?
- Why is a particular namespace failing OC6?
- What remediation is recommended?

The first four questions are principally inventory, aggregation, and reporting
questions. They do not require an LLM to inspect raw records whenever somebody
wants the current position. The final two questions are where an agent adds
more value: interpreting a bounded finding, gathering focused evidence, and
explaining an approved remediation in context.

## Why change the current approach

### The agent sees too much data

A broad database result is serialized into an MCP response and then placed in
the model's input context. Large results can be duplicated by transport/client
serialization, retained across follow-up turns, or fetched again through
retries and paging. The database may handle the query successfully while the
agent still fails because the result is too large to reason over effectively.

### Management reporting is unnecessarily conversational

Users should not need to spend tokens or wait for an agent to reproduce a
fleet-level table or chart. A dashboard is faster, easier to scan, consistently
defined, shareable, and available even when the model or MCP route is degraded.

### A model should not decide policy from raw data

OC6 pass/fail status, exemptions, evidence freshness, and reason codes should be
calculated deterministically from an owner-approved control definition. The
agent may explain the result, but it should not invent or inconsistently
re-evaluate the policy on every turn.

### Compaction alone cannot solve the problem

Conversation compaction can help later turns, but an oversized tool response
has already consumed input context before compaction occurs. The primary
control must be at the data and FastMCP result boundary.

## Proposed high-level design

```text
inventory, configuration, policy, and observed traffic sources
  -> deterministic OC6 evaluation
  -> approved PostgreSQL current-finding and aggregate views
       |
       +-> Grafana or Power BI
       |     -> fleet status, trends, filters, drill-down, evidence freshness
       |
       +-> bounded FastMCP tools
             -> one summary, small exception list, or exact finding
             -> OC6 policy agent
                  -> explanation + approved remediation playbook
                  -> optional focused A2A investigation
                       -> read-only Kubernetes specialist
                       -> selected cluster/namespace evidence only
                  -> human-reviewed recommendation or approved workflow handoff
```

## Responsibilities by layer

### Policy and compliance layer

The policy owner defines the authoritative OC6 version, scope, approved cipher
suites, mesh requirements, exemptions, evidence freshness, reason codes, and
remediation ownership. Missing or stale evidence must be reported as unknown or
stale, not silently counted as compliant.

### PostgreSQL data-product layer

The DB/data team maps existing sources into two narrow contracts:

- a current-finding view with one deterministic finding for one stable
  resource, including status, reason, evidence provenance, freshness, and
  playbook reference; and
- an aggregate view containing the complete in-scope denominator and bounded
  group counts for dashboards and summary tools.

Existing source tables do not need to be exposed to the agent. Expensive joins
or calculations can be handled through materialized views or a scheduled
transformation where appropriate.

### Dashboard and reporting layer

The Grafana and reporting teams first determine whether an existing Power BI
product already meets the agreed questions, freshness, drill-down, access, and
operational availability requirements. The goal is one authoritative human
view where possible, not duplicate dashboards by default.

The selected view should show:

- the complete production population;
- compliant, non-compliant, unknown, exempt, and stale counts;
- failures by cluster and deterministic reason code;
- mesh-required versus mesh-enabled coverage;
- applications observed using unapproved cipher suites;
- evidence freshness and collector/evaluator health; and
- filtered drill-down by finding, cluster, namespace, and application.

### FastMCP layer

Engineering adds or adapts a small typed interface over the approved views. The
likely MVP operations are:

- get an OC6 fleet or cluster summary;
- list a bounded number of current findings;
- get one namespace finding;
- get one application's cipher finding;
- retrieve an approved playbook by reason code; and
- return a filtered dashboard or report link.

The implementation must use fixed parameterized queries, read-only database
permissions, statement timeouts, and enforced row, byte, and cell limits. It
must not expose generic SQL, the full schema, base tables, automatic paging, or
bulk result reconstruction in chat.

### OC6 policy-agent layer

The agent routes each question to one bounded tool, explains deterministic
reason codes, reports evidence source and age, and retrieves the matching
approved remediation playbook. It remains read-only for diagnosis and
recommendation.

The agent should direct fleet-wide browsing to the dashboard. A focused
question such as "Why is namespace X failing OC6?" should retrieve only the
exact finding for that namespace rather than first loading a fleet-wide result.

### Optional Kubernetes A2A investigation

Some findings may need evidence that PostgreSQL does not contain or that must
be checked against current cluster state. In that case, the OC6 policy agent can
delegate to an existing read-only Kubernetes specialist through A2A.

The handoff should contain only the minimum scope:

```yaml
controlId: OC6
findingId: "{{FINDING_ID}}"
cluster: "{{CLUSTER_NAME}}"
namespace: "{{NAMESPACE}}"
reasonCodes:
  - "{{REASON_CODE}}"
requestedChecks:
  - "{{APPROVED_READ_ONLY_CHECK}}"
```

The Kubernetes specialist inspects only the named cluster and namespace with
approved read-only tools and returns a bounded evidence summary. It does not
receive the full compliance dataset and does not mutate the cluster.

If a change is requested, the agents produce a proposed plan with risk,
validation, and rollback. Any execution goes through the existing approved
GitOps/Argo and human-approval path, using a separately permissioned workflow
service account.

## Intended user journeys

### Management reporting

1. A user opens the authoritative Grafana or Power BI view.
2. They see the current fleet position and evidence freshness immediately.
3. They filter by control, environment, cluster, namespace, application, or
   reason without invoking an LLM.
4. If an issue needs interpretation, they copy or select its stable finding ID
   and ask the agent for an explanation.

### Focused investigation and remediation guidance

1. The user asks why a selected namespace or application is failing.
2. FastMCP returns one bounded finding from the approved view.
3. The policy agent explains the reason codes and obtains the approved
   playbook.
4. If necessary, it delegates a narrowly scoped live check to the Kubernetes
   specialist over A2A.
5. The agent returns evidence, recommendations, risks, validation, rollback,
   and a filtered dashboard link.
6. Remediation stops at recommendation unless the user enters the approved
   human-governed execution workflow.

## What this should solve

- Management receives a faster, consistent, always-available reporting view.
- Routine reporting no longer consumes model tokens.
- PostgreSQL performs filtering and aggregation where it is efficient and
  auditable.
- FastMCP returns only the data necessary for the current conversation.
- The agent retains context for explanation, follow-up questions, and
  remediation reasoning.
- OC6 results become deterministic, versioned, and reconcilable between the
  dashboard and agent.
- Focused Kubernetes investigation remains available without granting the
  reporting agent broad fleet access.
- Dashboard, database, MCP, model, and cluster permissions remain separable.

## What this does not claim yet

- The current workplace database schema has not been mapped in this public
  proposal.
- It is not yet known whether Power BI already satisfies the reporting need.
- The exact OC6 policy contract, data sources, evidence coverage, and
  remediation playbooks still require owner approval.
- The proposed FastMCP tool names and result shapes are not final contracts.
- The sanitized lab evidence proves that large results can be bounded; it does
  not yet prove workplace token savings or answer quality.
- A2A delegation must be validated against the installed kagent version,
  current agent identities, tool permissions, and cluster-access boundaries.
- No production database, dashboard, agent, Gateway, or cluster change is
  authorized by this document.

## Agreement in principle requested

Before asking teams to implement the design, confirm agreement on the following:

- [ ] The initial broad database-interrogation approach is not suitable for
  routine management reporting.
- [ ] Fleet status and standard compliance breakdowns should be available in an
  owned dashboard or report without invoking an agent.
- [ ] OC6 compliance must be evaluated deterministically outside the LLM.
- [ ] PostgreSQL should expose approved current-finding and aggregate views
  rather than broad source-table access.
- [ ] FastMCP should expose only question-driven, typed, read-only, bounded
  operations.
- [ ] The agent's primary value is focused explanation, evidence correlation,
  conversational follow-up, and approved remediation guidance.
- [ ] A read-only Kubernetes specialist may be used over A2A for narrowly scoped
  live evidence where the database finding is insufficient.
- [ ] Remediation execution remains behind the existing human approval and
  workflow permission boundary.
- [ ] The DB, policy, reporting, engineering, and SRE owners will jointly define
  the first questions and expected answers before schemas or tools are finalized.
- [ ] A representative canary must demonstrate correctness, bounded transport,
  reduced per-call and cumulative token use, dashboard reconciliation, and
  rollback before wider adoption.

## Decisions needed at the agreement meeting

1. Are these the right user journeys and responsibilities?
2. What are the first five to ten questions the solution must answer?
3. Who owns the authoritative OC6 policy and expected answers?
4. Does the required data already exist as evaluated findings or only as raw
   evidence?
5. Is an existing Power BI product sufficient, or is an operational Grafana
   dashboard required?
6. Which reporting experience will be authoritative, and can it provide stable
   filtered links?
7. Which existing workplace FastMCP tools, authentication, objects, and routes
   must be preserved?
8. Which live checks, if any, require A2A delegation to a Kubernetes specialist?
9. Where will the approved remediation playbooks live, and who signs them off?
10. What correctness, freshness, response-size, token, latency, and rollback
    evidence is required for the canary?

## Next step after agreement

If the direction is accepted, use
[`../OC6-COMPLIANCE-DATA-DASHBOARD-FASTMCP-CHECKLIST.md`](../OC6-COMPLIANCE-DATA-DASHBOARD-FASTMCP-CHECKLIST.md)
to assign the detailed policy, DB, Grafana/Power BI, FastMCP, skill, A2A,
evaluation, and rollout work. Begin with the question catalogue and policy
contract; do not start by changing manifests or granting broader database
access.

Supporting context:

- [`../WORK-AGENT-TOKEN-EFFICIENCY-HANDOFF.md`](../WORK-AGENT-TOKEN-EFFICIENCY-HANDOFF.md)
  describes the delta-only workplace FastMCP upgrade.
- [`../AGENTIC-DATABASE-TOKEN-EFFICIENCY-RESEARCH.md`](../AGENTIC-DATABASE-TOKEN-EFFICIENCY-RESEARCH.md)
  explains the bounded-tool and out-of-band analysis decision.
- [`../../../docs/ai-grafana/shared-grafana-evidence-agent.md`](../../../docs/ai-grafana/shared-grafana-evidence-agent.md)
  describes the existing focused dashboard-evidence and specialist handoff
  pattern.
