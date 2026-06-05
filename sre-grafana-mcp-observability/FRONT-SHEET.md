# SRE Grafana MCP Observability Work-Agent Bundle

Date: 2026-06-05

Purpose: copy this folder into the work agent context and ask it to recreate the
SRE Grafana MCP observability workflow in the approved work environment,
exposed through a cluster-side kagent front door.

This folder is self-contained. The work agent should not need to browse the
home-lab repo to understand the task.

## One-Line Ask

Expose an `observability-work-agent` through kagent UI/A2A so SRE can request
cert-manager observability without installing local MCP servers. The agent
should use the MCP tools already installed in Kubernetes to inspect live Grafana
telemetry, then create or update durable GitOps observability config:
Alloy collection, Grafana dashboards, alert rules, alert-to-triage routing, and
a reviewable GitLab merge request.

## Start Here

Read these files in order:

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/cert-manager-observability-request.yaml`
5. `requests/cert-manager-observability-request.json`
6. `prompts/01-cert-manager-observability.md`
7. `evidence/EVIDENCE-TEMPLATE.md`
8. `payload/docs/observability/sre-grafana-mcp-observability/README.md`
9. `payload/agents/skills/grafana-incident-evidence-pack/SKILL.md`
10. `payload/docs/ai-grafana/shared-grafana-evidence-agent.md`
11. `payload/agents/grafana-evidence-agent/agent.yaml`
12. `payload/agents/kagent-triage/cert-manager-agent.yaml`
13. `payload/observability/grafana/dashboard-registry.yaml`
14. `payload/observability/managed-lgtm-integration/rule-sync/README.md`

## Local Bundle Check

Run this before starting work-side live actions:

```bash
bash scripts/verify-bundle.sh
```

Expected:

```text
SRE_GRAFANA_MCP_OBSERVABILITY_BUNDLE_VERIFY: passed
```

This is a static bundle check only. It does not prove live Grafana MCP, GitLab
MCP, Flux, Alloy, Prometheus/Mimir, Loki, or kagent access.

## Work-Lab Definition Of Done

The work agent must return evidence for:

- Grafana MCP tool discovery.
- kagent UI or A2A exposure plan for `observability-work-agent`.
- Confirmation that SRE does not need local MCP installation for normal use.
- Live datasource discovery.
- Live cert-manager metric and log discovery.
- Existing dashboard and alert inspection.
- Alloy collection decision: existing, patched, or new.
- Dashboard JSON or provisioning change.
- Alert rules and routing labels.
- Alert-to-triage path into kagent or Argo Events.
- GitLab branch and merge request if GitLab MCP is available and approved.
- Validation queries and Grafana deeplinks.

## Safety Rules

- Start read-only with Grafana MCP.
- Keep MCP servers and credentials platform-owned in Kubernetes.
- Do not make local MCP installation a prerequisite for SRE use.
- Do not use write-capable Grafana tools from the default triage agent.
- Put durable dashboard, rule, and Alloy changes through merge request review.
- Keep tokens, internal hostnames, private cluster IPs, tenant IDs,
  subscription IDs, and private project names out of reusable artifacts.
- Use `{{PLACEHOLDER}}` values for environment-specific configuration.
- Do not claim live proof from copied files. Live proof must come from the work
  environment.

## What To Copy Into The Work Repo

The reference material is under:

```text
payload/
```

The work agent should adapt the files, not blindly copy every file. The likely
target areas are:

```text
docs/observability/
docs/ai-grafana/
agents/skills/
agents/grafana-evidence-agent/
agents/kagent-triage/
agents/observability-work-agent/
observability/grafana/
observability/managed-lgtm-integration/
observability/grafana-argo-pipeline/
```

GitLab MCP should create or update the final work-repo files on a reviewable
branch, then open a merge request.
