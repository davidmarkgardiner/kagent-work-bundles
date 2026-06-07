# GitLab Ticket Templates

Use these as starting points. Keep real project paths, URLs, namespaces, and
names inside the private work GitLab project only.

## Epic: Kagent Triage V2 SRE Adoption And Game Days

**Goal**

Move Kagent triage v2 from engineering proof into SRE day-to-day usage through
app onboarding, controlled game-day exercises, evidence packs, and a feedback
loop that improves KB docs, skills, dashboards, evals, policies, and workflows.

**Definition of done**

- SRE has onboarded at least one application or namespace.
- At least one controlled lower-env game-day exercise has been completed or
  blocked with clear reason.
- SRE used or reviewed the Kagent workflow directly.
- Feedback was captured and converted into at least one improvement item.
- Adoption metrics/reporting exist or are explicitly marked unavailable.

**Labels**

`kagent-triage-v2`, `sre-adoption`, `game-day`, `platform-reliability`

## Issue 1: Prepare Work-Lab Variables And Access

**Purpose**

Fill the shared variable sheet and confirm the work-side MCP/tooling access
needed by the handover bundles.

**Tasks**

- Fill `SHARED-VARIABLES.md` in the private work context.
- Confirm kagent namespace, model config, and Agent Gateway/model route.
- Confirm GitLab MCP server and scoped project access.
- Confirm Grafana MCP server and datasource UIDs.
- Confirm memory MCP/querydoc/doc2vec path.
- Confirm approval route for HITL remediation.
- Confirm lower-env chaos target constraints.

**Definition of done**

- Shared variables are filled in private context.
- Missing tools are listed as blockers with owners.
- No secrets are committed to public or reusable docs.

## Issue 2: SRE First-Contact Onboarding For One Application

**Purpose**

Select one SRE-owned application or namespace and run the first-contact Kagent
triage v2 onboarding flow.

**Tasks**

- Select app/namespace/workload and SRE owner.
- Capture existing dashboards, alerts, runbooks, and known failure modes.
- Run `sre-adoption-feedback-loop` first-contact prompt.
- Identify 3-5 realistic failure modes.
- Map required agents, MCPs, KB docs, eval cases, Grafana evidence, GitLab
  reporting, memory, HITL, and governance controls.

**Definition of done**

- First-contact output is attached.
- SRE has reviewed or corrected the output.
- Gaps are converted into feedback/improvement items.

## Issue 3: Run First Controlled Game-Day Exercise

**Purpose**

Run one low-risk lower-env game-day exercise so SRE can use the workflow and
provide feedback.

**Tasks**

- Pick a safe failure mode such as pod delete, crashloop, bad config, or missing
  dependency in lower env.
- Validate scope, approval route, and rollback/recovery plan.
- Run or simulate the controlled incident.
- Confirm alert/triage path.
- Collect Grafana metrics/logs/traces or trace fallback.
- Capture SRE interaction and confidence feedback.
- Route any remediation through HITL/GitOps.

**Definition of done**

- Exercise completed or blocker recorded.
- Kagent evidence pack attached.
- Lifecycle eval score or blocker attached.
- SRE feedback captured.

## Issue 4: Create SRE Feedback And Improvement Loop

**Purpose**

Make sure SRE feedback becomes concrete platform improvement, not meeting notes.

**Tasks**

- Create feedback labels/categories.
- Define where feedback issues live.
- Define triage ownership and SLA.
- Convert at least one feedback item into KB, skill, eval, dashboard, policy, or
  workflow improvement.
- Track closed-loop evidence.

**Definition of done**

- Feedback issue/project location exists.
- At least one feedback item is routed and owned.
- Feedback categories match `sre-adoption-feedback-loop/payload/REFERENCE.md`.

## Issue 5: Build Adoption Reporting

**Purpose**

Show whether SRE is actually using the system and whether it is improving
platform reliability.

**Tasks**

- Report first-contact sessions completed.
- Report apps/namespaces onboarded.
- Report game-day exercises requested/completed/blocked.
- Report agent-assisted incidents reviewed by SRE.
- Report feedback items captured and converted to improvements.
- Report eval hard failures and remediation approvals.
- Decide whether this is a Grafana dashboard, GitLab report, or fleet report.

**Definition of done**

- Adoption report exists.
- Metrics source is documented.
- Open blockers and owners are visible.

## Issue 6: Prepare Stakeholder/SRE Handover Session

**Purpose**

Run a short handover session explaining what Kagent triage v2 is, how SRE uses
it, how game days work, and how feedback improves the platform.

**Tasks**

- Review `presentation/kagent-triage-v2-sre-handover.html`.
- Send Teams invite/message.
- Agree first app and first game-day window.
- Capture questions and blockers.
- Assign next actions.

**Definition of done**

- Session held or scheduled.
- Named SRE owner and first app selected.
- Next game-day slot agreed.
