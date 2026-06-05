# Prompt: Correct Scope To Process, Not One Dashboard

Use this when a work-side agent has focused on building one cert-manager
dashboard or alert bundle and missed the broader objective.

```text
You are not being asked to build cert-manager dashboards and alerts as the
primary deliverable.

The goal is to build and prove the reusable SRE observability workflow:

SRE request
  -> kagent UI or A2A/curl front door
  -> observability-work-agent
  -> installed in-cluster MCP tools
  -> live Grafana evidence
  -> proposed or generated Alloy/dashboard/alert/triage config
  -> GitLab MR for durable changes
  -> SRE-facing closeout

Use the bundle `work-agent-bundles/sre-grafana-mcp-observability` as the
instruction pack.

Your deliverable is the process and agent integration, not just one
cert-manager dashboard.

Do this in order:

1. Read:
   - FRONT-SHEET.md
   - WORK-AGENT-START-PROMPT.md
   - CHECKLIST.md
   - payload/docs/observability/sre-grafana-mcp-observability/README.md
   - payload/agents/skills/grafana-incident-evidence-pack/SKILL.md

2. Confirm or design the kagent front door:
   - agent name: `observability-work-agent`
   - accessible through kagent UI and/or A2A/curl
   - SRE does not need local MCP install
   - agent uses installed Kubernetes-hosted MCP tools

3. Confirm tool wiring:
   - Grafana MCP read tools available to the agent
   - GitLab MCP branch/MR tools available only if approved
   - no default write-capable Grafana mutation tools
   - no direct Kubernetes mutation unless explicitly approved

4. Define the reusable request contract:
   - component name
   - namespace
   - cluster/environment
   - mode: debug-only or durable-gitops
   - expected outputs: Alloy, dashboard, alerts, triage route, MR, validation
     queries

5. Use cert-manager only as the example test case:
   - show how an SRE would request "add cert-manager observability"
   - prove the agent can use Grafana MCP to discover live metrics/logs if
     available
   - show what dashboard/alert config it would create or propose
   - open an MR only if GitLab MCP is available and approved

6. Return the process proof, not just component config.

Required final answer format:

STATUS: PASS | PARTIAL | BLOCKED

KAGENT_FRONT_DOOR:
- UI path:
- A2A/curl path:
- Agent name:
- Local MCP required for SRE: no

TOOLS:
- Grafana MCP tools discovered:
- GitLab MCP tools discovered:
- Write-capable tools excluded or gated:

REUSABLE_WORKFLOW:
- Request contract:
- Agent steps:
- GitOps/MR path:
- SRE closeout format:

CERT_MANAGER_EXAMPLE:
- Request used:
- Live Grafana evidence:
- Proposed or created files:
- Dashboard:
- Alerts:
- Triage route:
- MR:

VALIDATION:
- Bundle verifier:
- MCP proof:
- UI/A2A proof:
- GitLab MR proof:
- Gaps:

Do not stop after building dashboard JSON. If you created dashboards or alerts,
treat them as the cert-manager example only. The actual objective is the
reusable kagent-based SRE observability workflow.
```
