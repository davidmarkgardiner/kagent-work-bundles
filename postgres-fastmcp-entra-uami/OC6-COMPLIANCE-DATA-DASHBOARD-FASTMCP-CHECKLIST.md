# OC6 compliance data, dashboard, and FastMCP delivery checklist

## Purpose

Use this checklist to turn the first agreed OC6 questions into a deterministic
compliance data product, a human-readable dashboard, and a bounded
conversational remediation agent.

The design principle is:

```text
policy and data systems evaluate compliance once
  -> PostgreSQL exposes approved findings and summaries
  -> Grafana or Power BI provides fleet visibility
  -> FastMCP retrieves one bounded summary or finding
  -> the agent explains the cause and recommends an approved remediation
```

The agent must not scan the full database, infer the OC6 policy from raw rows,
or aggregate fleet data in model context. PostgreSQL or the upstream compliance
pipeline performs the filtering and aggregation. Large reports remain outside
chat.

## Definition of done

- [ ] The policy owner has approved the OC6 decision rules, scope, evidence
  requirements, reason codes, exemptions, and remediation ownership.
- [ ] The initial user questions and expected answer shapes are agreed.
- [ ] The DB team provides approved current-finding and aggregate views with
  documented grain, freshness, lineage, and read-only access.
- [ ] The reporting team confirms whether an existing Power BI product meets
  the need or delivers an equivalent Grafana dashboard.
- [ ] Engineering exposes only the required typed FastMCP tools with enforced
  row, byte, cell, call, and timeout budgets.
- [ ] A populated OC6 skill maps user language to tools, reason codes, and
  approved remediation playbooks without containing database rows or secrets.
- [ ] A representative end-to-end evaluation proves answer correctness,
  evidence provenance, bounded token use, dashboard drill-down, and safe
  remediation handoff.
- [ ] Production promotion and any resource-changing remediation remain behind
  the workplace review and approval gates.

## Gate 0: agree the questions before building

Treat this catalogue as the MVP. Add, remove, or reprioritize questions with the
policy owner and intended users before finalizing the database contract.

| Priority | User question | Primary interface | Required answer shape |
|---|---|---|---|
| P0 | Show evidence that all production namespaces use encrypted communication. | Dashboard/report first; agent may summarize it. | Complete production denominator; compliant, non-compliant, unknown, exempt, and stale counts; evidence time and source. |
| P0 | Which clusters are non-compliant with OC6? | Dashboard table; bounded MCP list when asked in chat. | Cluster, status, failure count, dominant reason codes, evidence freshness, and drill-down link. |
| P0 | Which applications communicate using unapproved cipher suites? | Dashboard table; bounded application lookup in chat. | Application identity, observed suite, approval status, observation window, affected scope, and evidence reference. |
| P0 | Which namespaces have service mesh disabled? | Dashboard inventory panel; bounded exception lookup in chat. | Cluster, namespace, environment, mesh requirement, observed state, exemption status, and reason code. |
| P0 | Why is namespace X failing OC6 compliance? | Agent using one exact finding. | Deterministic reason codes, relevant facts, evidence age/source, policy citation, and concise explanation. |
| P0 | What remediation is recommended for this issue? | Agent using an approved playbook. | Ordered actions, prerequisites, risk, validation, rollback, owner, and approval boundary. |

For every question:

- [ ] Name the decision the user will make from the answer.
- [ ] Identify the required filters, including environment, cluster, namespace,
  application, time window, and compliance status.
- [ ] Define the maximum useful result size. A fleet-wide list is normally a
  dashboard or export, not a chat response.
- [ ] Define an owner-approved expected answer for at least one compliant, one
  non-compliant, one unknown, and one exempt example.
- [ ] Decide whether the question must use configured state, observed traffic,
  or both.
- [ ] Record terminology and synonyms users are likely to use.

**Gate 0 receipt:** approved question catalogue, priorities, example answers,
and named policy/data/reporting/engineering owners.

## Gate 1: policy owner defines OC6 as a testable contract

The LLM is not the policy decision engine. Encode OC6 as deterministic rules in
the compliance pipeline or approved database transformation.

- [ ] Provide the authoritative OC6 control text and version.
- [ ] Define the in-scope production population and stable resource identity.
- [ ] Define what counts as encrypted communication.
- [ ] Distinguish `encryption_configured` from `encryption_observed`.
- [ ] Define the approved cipher-suite catalogue and its versioning process.
- [ ] Define where service mesh is mandatory, optional, or prohibited.
- [ ] Define permitted exemptions, approver, expiry, and evidence.
- [ ] Define the maximum acceptable evidence age and the behavior for missing or
  stale observations.
- [ ] Confirm that missing evidence becomes `unknown`, not `compliant`.
- [ ] Define stable reason codes such as `OC6_MESH_DISABLED`,
  `OC6_UNAPPROVED_CIPHER`, `OC6_ENCRYPTION_NOT_OBSERVED`, and
  `OC6_EVIDENCE_STALE`; replace these examples with the approved vocabulary.
- [ ] Map every reason code to an owned, versioned remediation playbook.
- [ ] Define the evidence required to prove remediation succeeded.

**Gate 1 receipt:** versioned policy contract, reason-code catalogue, exemption
rules, evidence/freshness rules, and playbook ownership.

## Gate 2: DB team prepares the compliance data product

### Discover what already exists

- [ ] Inventory the current PostgreSQL schemas, approved views, refresh jobs,
  retention, indexes, and read-only roles without copying workplace details to
  this public repository.
- [ ] Identify the source for namespace inventory, application identity,
  environment classification, mesh state, encryption configuration, observed
  traffic/ciphers, exemptions, and evidence timestamps.
- [ ] Determine whether OC6 findings are already evaluated upstream or whether
  the DB team must build a deterministic transformation.
- [ ] Identify any existing Power BI semantic model or dataset and determine
  whether it already provides the required grain and fields.
- [ ] Document source ownership, lineage, refresh cadence, late-arriving data,
  and failure/no-data behavior.

### Agree the logical contract

Provide the equivalent of these approved views; exact workplace names remain in
the private environment.

#### Current finding view

One row represents one control finding for one stable resource at the latest
accepted observation.

| Field | Required meaning |
|---|---|
| `finding_id` | Stable identifier that does not depend on a transient pod name. |
| `control_id` / `control_version` | OC6 identifier and evaluated policy version. |
| `cluster_name`, `environment`, `namespace_name`, `application_name` | Approved resource identity and scope. |
| `compliance_status` | One of `compliant`, `non_compliant`, `unknown`, or `exempt`. |
| `reason_code` | Deterministic reason from the approved catalogue. |
| `reason_summary` | Short, non-sensitive explanation suitable for display. |
| `mesh_required`, `mesh_enabled` | Required and observed/configured mesh states. |
| `encryption_configured`, `encryption_observed` | Separate desired and observed facts. |
| `observed_cipher_suite`, `cipher_approval_status` | Normalized cipher evidence where applicable. |
| `evidence_observed_at`, `evidence_source`, `evidence_reference` | Freshness, provenance, and safe drill-down reference. |
| `exemption_id`, `exemption_expires_at` | Approved exception context without sensitive content. |
| `remediation_playbook_id`, `playbook_version` | Stable link to approved guidance. |

#### Aggregate view

One row represents one bounded group, such as control + environment + cluster +
status + reason code.

- [ ] Include total in-scope resources and counts for compliant,
  non-compliant, unknown, exempt, and stale evidence.
- [ ] Make numerator and denominator definitions explicit.
- [ ] Include evaluation and source freshness timestamps.
- [ ] Support only approved grouping dimensions needed by the question
  catalogue.
- [ ] Consider a materialized view or scheduled summary table if the underlying
  joins are expensive.

### Database safety and acceptance

- [ ] Expose approved views rather than base tables.
- [ ] Grant only `CONNECT`, schema `USAGE`, and `SELECT` on the approved views to
  the existing FastMCP database principal.
- [ ] Confirm base-table reads and every write remain denied.
- [ ] Ensure identifiers used for joins and lookups are indexed and stable.
- [ ] Test the complete production denominator, not only resources with findings.
- [ ] Test duplicate, missing, stale, contradictory, exempt, and late-arriving
  evidence.
- [ ] Publish column definitions, valid values, grain, freshness SLO, lineage,
  sample sanitized rows, and support owner.
- [ ] Provide aggregate and exact-record query examples with expected bounded
  shapes, but no credentials, endpoints, or real production rows.

**Gate 2 receipt:** approved view contract, data dictionary, sanitized fixtures,
access/grant confirmation, refresh SLO, lineage, query plans for expected access
patterns, and named support owner.

## Gate 3: Grafana or Power BI team delivers the human view

Do not create a second dashboard merely because Grafana is available. First
assess the existing Power BI product against the user questions, freshness,
drill-down, operational access, and linkability requirements.

### Reporting-platform decision

- [ ] Identify the intended audience and whether the experience is operational,
  executive/reporting, or both.
- [ ] Confirm whether existing Power BI pages answer every P0 inventory question.
- [ ] Confirm refresh latency, access controls, export controls, ownership, and
  incident-time availability.
- [ ] Confirm whether a filtered view can be linked using control, environment,
  cluster, namespace, application, finding ID, and time window.
- [ ] Choose one authoritative reporting experience where possible. If both are
  retained, document their distinct audiences and common data contract.

### Minimum dashboard contents

- [ ] Fleet summary with compliant, non-compliant, unknown, exempt, and stale
  counts and percentages.
- [ ] Complete production coverage/denominator panel.
- [ ] Non-compliance by cluster and reason code.
- [ ] Namespace mesh-required versus mesh-enabled coverage.
- [ ] Applications and observed unapproved cipher suites.
- [ ] Evidence freshness, no-data, and collector/evaluator health.
- [ ] Filterable findings table with stable finding ID and evidence reference.
- [ ] Drill-down suitable for a selected cluster, namespace, or application.
- [ ] Clear policy version, last refresh time, data owner, and support route.
- [ ] No secrets or sensitive raw payloads in panels, URLs, exports, or annotations.

### Dashboard acceptance

- [ ] Reconcile dashboard totals to the approved database views.
- [ ] Prove that `unknown`, `stale`, and `exempt` cannot be mistaken for pass.
- [ ] Validate role-based access and sharing behavior.
- [ ] Validate performance at production scale and common filter combinations.
- [ ] Provide a stable dashboard identifier and filtered-link contract for the
  FastMCP tool and agent response.

**Gate 3 receipt:** reporting-platform decision, dashboard/report identifier,
screenshots or review evidence, reconciliation results, filter/deep-link
contract, access model, freshness, and owner.

## Gate 4: engineering builds the bounded FastMCP interface

Start only after the P0 questions and approved view contract are stable enough
to implement. Port the change onto the existing workplace deployment; do not
apply this public bundle wholesale or replace workplace authentication,
identity, Gateway, Agent, object names, views, or grants.

### Proposed MVP tools

| Tool | Intended result |
|---|---|
| `get_oc6_summary(environment, cluster?)` | One aggregate compliance summary including denominator and freshness. |
| `list_oc6_findings(status, environment?, cluster?, reason_code?, limit)` | Bounded exception list with stable finding IDs; dashboard/export for the complete list. |
| `get_oc6_namespace_finding(cluster, namespace)` | One namespace's current reasons, facts, provenance, and playbook references. |
| `get_oc6_application_cipher_finding(application, cluster?)` | Bounded current cipher findings for one application. |
| `get_oc6_remediation_playbook(reason_code, playbook_version?)` | Approved remediation summary and durable knowledge reference. |
| `get_oc6_dashboard_link(environment?, cluster?, namespace?, application?, finding_id?)` | Validated filtered link or stable report-navigation metadata. |

Do not add a generic SQL tool. Do not expose schema discovery as the routine
path. Preserve existing tool names when they already satisfy an agreed
contract; treat this table as a proposed interface, not permission to replace
working tools.

### Adapter checklist

- [ ] Inspect the deployed source, image digest, FastMCP version,
  authentication mode, approved views, Gateway policy, Agent allowlist, and
  rollback digest.
- [ ] Use fixed parameterized queries against approved views and compose
  identifiers safely.
- [ ] Use read-only transactions and a bounded PostgreSQL statement timeout.
- [ ] Replace unbounded retrieval with `fetchmany(max_rows + 1)`.
- [ ] Apply server-side row, byte, and per-cell limits and return explicit
  truncation metadata.
- [ ] Begin with the proven defaults of 50 rows, 32 KiB, 512 characters per
  cell, and a five-second statement timeout; lower them per tool where useful.
  Do not exceed the compiled ceilings documented in the existing handoff.
- [ ] Use scalar/one-row limits for summaries and exact findings; use a small
  explicit top-N limit for exception lists.
- [ ] Return dashboard or governed-export references for larger results; do not
  automatically fetch the referenced artifact into model context.
- [ ] Preserve password or Workload Identity/UAMI authentication exactly as
  discovered unless a separate identity change is approved.
- [ ] Keep the FastMCP Agent read-only. Resource changes belong to an approved
  Argo/GitOps workflow service account.

### FastMCP acceptance

- [ ] Unit tests cover every tool's parameters, approved query, result shape,
  truncation, empty result, unknown/stale evidence, and database error behavior.
- [ ] A source query matching thousands of rows returns only the configured
  bounded result with `truncated: true`.
- [ ] Complete Streamable HTTP envelopes are measured, including any structured
  content duplicated into text.
- [ ] Tool and Gateway allowlists contain only the approved read-only tools.
- [ ] Direct database, MCP transport, Gateway discovery, and kagent A2A checks
  pass using sanitized marker-only evidence.
- [ ] Base-table access, writes, unsupported dimensions, invalid limits, and
  attempts to page an export fail closed.

**Gate 4 receipt:** reviewed delta, immutable image digest, tests, scans,
signature, dry-run, direct/transport/Gateway/A2A evidence, result-envelope
measurements, and rollback inputs.

## Gate 5: engineering builds the OC6 policy skill and agent behavior

Copy and populate
`token-efficient-query-skill-template/postgres-domain-query-template/`; do not
install the generic template or public POC skill unchanged.

- [ ] Record the OC6 scope, policy version, logical grain, freshness, statuses,
  dimensions, synonyms, and ambiguity rules.
- [ ] Map every P0 question to one preferred typed tool and expected result
  shape.
- [ ] Map every approved reason code to an owned remediation playbook.
- [ ] Keep playbooks versioned and reviewable; the agent explains and adapts
  them but does not invent the governing policy or required control.
- [ ] Require the agent to state scope, evidence time/source, status, reason
  codes, and uncertainty.
- [ ] Require the agent to stop on truncation and direct the user to the
  dashboard or governed export.
- [ ] Require focused lookup for "namespace X" rather than a preceding fleet
  dump.
- [ ] Keep the agent read-only for diagnosis and recommendation.
- [ ] For requested changes, produce a bounded plan with prerequisites, risk,
  validation, rollback, and owner, then use the approved HITL/GitOps workflow.
- [ ] Add at least ten sanitized evaluations covering the six P0 questions,
  ambiguity, missing data, stale evidence, exemptions, truncation, forbidden
  requests, dashboard routing, follow-up questions, and remediation safety.

**Gate 5 receipt:** immutable skill artifact, populated semantic contract,
playbook mapping, evaluation set/results, Agent delta, and rollback inputs.

## Gate 6: end-to-end canary and decision

Run the same representative questions before and after the change.

- [ ] Confirm dashboard totals match the approved database views.
- [ ] Confirm FastMCP summaries and exact findings match owner-approved expected
  answers.
- [ ] Confirm the agent reports `unknown`, stale evidence, exemptions, and
  truncation correctly.
- [ ] Confirm the agent's remediation matches the approved playbook and does not
  imply that it changed production.
- [ ] Confirm filtered dashboard links open at the intended scope and respect
  access controls.
- [ ] Measure PostgreSQL rows scanned versus rows returned.
- [ ] Measure adapter payload and complete client-visible MCP envelope bytes.
- [ ] Measure MCP calls/retries and per-call/cumulative model input and output
  tokens.
- [ ] Measure p50/p95 latency, correctness, and failure rate.
- [ ] Confirm the common questions normally use one bounded tool call.
- [ ] Test session compaction below the model limit, while retaining
  server-side result limits as the primary control.
- [ ] Record the previous image/skill/Agent state and prove rollback in the
  canary environment.
- [ ] Stop for review before wider or production promotion.

**Gate 6 receipt:** question-by-question results, reconciliation, token and
transport comparison, latency, correctness review, security review, rollback
proof, and explicit promotion decision.

## Team handoff summary

| Team | Needs from others | Delivers | Blocks |
|---|---|---|---|
| Policy/security owner | User questions and source capabilities | OC6 rules, reason codes, evidence/freshness rules, exemptions, playbook ownership | Final database contract and agent correctness |
| DB/data team | Approved OC6 contract and source access | Current-finding and aggregate views, dictionary, lineage, fixtures, grants, freshness SLO | Dashboard and FastMCP implementation |
| Grafana/Power BI team | Approved views and user/audience needs | Platform decision, fleet dashboard/report, reconciliation, filtered-link contract | Agent dashboard navigation and human self-service |
| Engineering | Approved views, questions, reason codes, playbooks, dashboard link contract | Bounded FastMCP tools, OC6 skill, read-only agent, tests, telemetry, rollback | End-to-end canary |
| SRE/application owners | Findings and approved playbooks | Usability review, remediation feedback, HITL decisions, verification evidence | Production adoption |

## Open decisions log

- [ ] Who owns the authoritative OC6 policy and its version lifecycle?
- [ ] What exact resources form the production denominator?
- [ ] Is the source evidence configuration, observed traffic, or both?
- [ ] Where is the approved cipher catalogue maintained?
- [ ] Which namespaces may be exempt from service mesh, and for how long?
- [ ] What freshness threshold changes a status to `unknown` or `stale`?
- [ ] Does PostgreSQL already hold evaluated findings, or only raw evidence?
- [ ] Does an existing Power BI product already answer the P0 questions?
- [ ] Which reporting platform is authoritative for operational users?
- [ ] Can the selected platform provide stable, access-controlled filtered links?
- [ ] What existing FastMCP tools and workplace object names must be preserved?
- [ ] Where will versioned remediation playbooks live and who approves them?
- [ ] Which actions, if any, may be submitted to an approved remediation
  workflow after human confirmation?
- [ ] What token, response-byte, latency, and correctness thresholds define a
  successful canary?

## Related implementation references

- [`WORK-AGENT-TOKEN-EFFICIENCY-HANDOFF.md`](WORK-AGENT-TOKEN-EFFICIENCY-HANDOFF.md)
  for the delta-only workplace rollout and evidence gates.
- [`AGENTIC-DATABASE-TOKEN-EFFICIENCY-RESEARCH.md`](AGENTIC-DATABASE-TOKEN-EFFICIENCY-RESEARCH.md)
  for the bounded MCP versus analytical-job decision.
- [`token-efficient-query-skill-template/postgres-domain-query-template/`](token-efficient-query-skill-template/postgres-domain-query-template/)
  for the copy-and-populate semantic and tool-routing template.
- [`../POSTGRES-MCP-WORK-START-HERE.md`](../POSTGRES-MCP-WORK-START-HERE.md)
  for the PostgreSQL MCP bundle entrypoint and authentication paths.
- [`../../docs/ai-grafana/agent-dashboard-evidence-pattern.md`](../../docs/ai-grafana/agent-dashboard-evidence-pattern.md)
  for agent home dashboards, focused evidence dashboards, and verification
  links.
