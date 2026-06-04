# Kagent Triage V2 Overview

## Purpose

Kagent triage v2 is the shared AI SRE flow for controlled incident diagnosis,
evidence gathering, remediation planning, and review. The system is designed so
an SRE can bring an application to the platform, describe expected failure
modes, run approved chaos in a lower environment, and collect evidence that the
right agents detected, explained, and remediated the issue safely.

## Core Flow

1. An alert, operator prompt, or approved chaos event starts the triage flow.
2. A coordinator fans out to specialist agents for Kubernetes, deployment,
   networking, policy, GitOps, Grafana, and knowledge-base lookup.
3. Read-only specialists gather evidence and return bounded findings.
4. The coordinator summarizes the incident, cites evidence, and proposes a
   remediation path.
5. Any non-read-only action pauses for human approval.
6. A write-capable GitOps or remediation specialist acts only after approval.
7. The lifecycle evaluator scores the run and blocks closure if hard gates fail.
8. The report includes the incident summary, evidence links, GitLab activity,
   Grafana panels, and follow-up knowledge-base gaps.

## Agent Roles

| Role | Responsibility | Write access |
|---|---|---|
| SRE front-door agent | Intake, app onboarding, demo planning, and status summaries | No |
| Triage coordinator | Fan-out orchestration and synthesis | No |
| Kubernetes specialist | Pod, event, workload, service, and namespace inspection | No |
| Grafana specialist | Metrics, logs, traces, dashboard lookup, and evidence links | No |
| Knowledge specialist | querydoc lookup and source citation | No |
| GitOps specialist | Branch, file update, merge request, and comment creation | Yes, after approval |
| Remediation specialist | Bounded lower-env remediation through approved workflow path | Yes, after approval |
| Review manager | Eval failure handling and follow-up routing | No direct cluster mutation |

## Safety Rules

- General triage agents must not include delete, exec, broad apply, or
  write-capable GitLab tools.
- GitLab write tools belong to a dedicated GitOps specialist with scoped project
  credentials.
- Remediation must run through GitOps or approved workflow service accounts, not
  direct chat-agent mutation.
- The first work deployment should use a sandbox project and an approved
  non-production namespace.
- Any documentation update should be committed through GitLab MCP as a reviewable
  branch and merge request.

## Evidence Required

Every credible run should include:

- workflow name or agent run ID;
- input alert or chaos event;
- specialist outputs and citations;
- Grafana metrics, logs, or dashboard links;
- GitLab branch or merge request link when GitOps changes were proposed;
- HITL approval identity for any non-read-only action;
- eval score and hard-failure summary;
- final report and knowledge-base gap list.

## Related Documents

- `docs/platform-kb/agents/gitlab-mcp-kb-update-loop.md`
- `docs/platform-kb/agents/querydoc-knowledge-agent.md`
- `docs/platform-kb/agents/triage-agent-kb-lookup.md`
- `docs/platform-kb/runbooks/checkout-api-crashloop.md`
