# SRE Grafana MCP Observability Workflow

This note shows how SRE can use Grafana MCP, Alloy, GitLab MCP, and kagent
triage agents to build observability for a Kubernetes component such as
cert-manager.

The preferred operating model is a cluster-side kagent front door that is
read-first and GitOps-backed:

```text
SRE in kagent UI, A2A, or curl
  -> observability-work-agent
  -> installed in-cluster MCP tools
  -> live Prometheus/Mimir, Loki, dashboards, and alert metadata
  -> proposed Alloy, dashboard, alert, and triage routing changes
  -> GitLab MR
  -> merge to main
  -> Flux / rule sync / Grafana sidecar reconciliation
```

## TLDR

SRE can hand an agent a focused request such as "add cert-manager
observability". The agent should inspect live Grafana data first, then produce
durable repo changes for Alloy collection, Grafana dashboards, alert rules, and
triage routing. The final answer should include dashboard links, alert names,
files changed, validation queries, and any gaps.

SRE should not need to install Grafana MCP, GitLab MCP, AKS-MCP, tokens, or
local images on their laptop. The platform should expose this as a kagent-backed
workflow through the kagent UI and A2A endpoint. Local MCP setup is a platform
engineering development path, not the normal SRE operating path.

Grafana MCP should be treated as the live evidence path. Alloy is still the
collector. Git remains the durable source of truth.

## Why This Helps

- SRE gets a fast way to inspect current telemetry without manually building
  every PromQL and LogQL query.
- Dashboards and alerts can be generated from live metric evidence instead of
  guessed metric names.
- Triage agents can reuse the same Grafana evidence during incidents.
- Temporary investigation work can become durable by raising a GitLab MR.
- The default path can remain read-only while write-capable changes go through
  review.
- The platform team owns MCP versions, service accounts, network access, and
  tool grants centrally instead of pushing that setup to every SRE laptop.

## Recommended Integration Path

Expose a dedicated kagent, for example `observability-work-agent`, as the SRE
front door:

```text
SRE
  -> kagent UI or A2A/curl request
  -> observability-work-agent
  -> Grafana MCP read tools
  -> GitLab MCP branch/MR tools, only if approved
  -> shared grafana-evidence-agent
  -> domain agent such as cert-manager-agent
  -> GitOps MR and validation evidence
```

The `observability-work-agent` should load or reference:

- `agents/skills/grafana-incident-evidence-pack/SKILL.md`
- the cert-manager request contract
- the shared Grafana evidence-agent contract
- dashboard and alert authoring guardrails
- the GitOps/MR closeout format

SRE interaction should be simple:

```text
Add cert-manager observability for {{CLUSTER_NAME}} / {{ENVIRONMENT}}.
Use the installed Grafana MCP tools, validate live metrics and logs, and open a
GitLab MR for any durable config changes.
```

For automation, the same request can be sent to the kagent A2A endpoint:

```bash
curl -fsS -X POST "{{KAGENT_A2A_ENDPOINT}}" \
  -H "Content-Type: application/json" \
  -d @requests/cert-manager-observability-request.json
```

The exact A2A payload shape should match the installed kagent version and work
gateway conventions. Keep endpoint URLs and auth values out of reusable docs.

## Agent Responsibilities

`observability-work-agent` owns the workflow:

- accept SRE requests from UI or A2A
- call installed MCP tools from inside the cluster
- decide whether the request is debug-only or durable GitOps work
- coordinate with `grafana-evidence-agent` and domain agents
- prepare or open GitLab MRs for durable changes
- return a concise SRE handoff

`grafana-evidence-agent` owns live Grafana evidence:

- datasource discovery
- dashboard discovery and panel query inspection
- PromQL and LogQL evidence
- Grafana deeplinks
- alert metadata inspection when read access is available

Domain agents such as `cert-manager-agent` own component reasoning:

- certificate, issuer, order, challenge, webhook, and controller context
- likely causes and remediation options
- whether a remediation should be proposed through GitOps or HITL

## Work-Agent Deliverables

When this is handed to the work-side agent, the expected output is not a local
MCP package for each SRE. The expected output is a cluster-side integration:

1. `observability-work-agent` is defined or updated in the work repo.
2. The agent can use the already-installed Grafana MCP tools.
3. Optional GitLab MCP write tools are scoped to branch/MR operations and review.
4. The agent is reachable through kagent UI or the approved A2A endpoint.
5. The cert-manager request JSON can be submitted through UI or `curl`.
6. The agent returns dashboard, Alloy, alert, triage-route, MR, and validation
   evidence.
7. Documentation states that local MCP installation is not required for normal
   SRE use.

## Two Operating Modes

### Fast Debug Mode

Use this when SRE wants quick evidence for an active question.

The agent should:

1. Discover datasources and relevant dashboards with Grafana MCP.
2. Query Prometheus or Mimir for live metrics.
3. Query Loki for recent component logs.
4. Inspect current alert rules and routing if the token permits read access.
5. Return a concise evidence pack with Grafana deeplinks, PromQL, LogQL, and
   uncertainty.

This mode should not mutate Grafana, Kubernetes, or Git.

### Durable GitOps Mode

Use this when SRE wants the observability configuration to remain after the
investigation.

The agent should:

1. Start with the same live Grafana MCP discovery.
2. Add or patch Alloy scrape and log collection only where telemetry is missing.
3. Add dashboard JSON or provisioning ConfigMaps.
4. Add Prometheus/Mimir and Loki alert rules.
5. Route alerts into the existing Argo Events / kagent triage path.
6. Open a GitLab MR if GitLab MCP is available.
7. Return the MR, expected dashboard UID, alert names, validation queries, and
   completion gaps.

## Cert-Manager Example

A useful cert-manager observability bundle should normally cover:

- cert-manager controller, cainjector, and webhook availability
- certificate expiry windows
- certificate renewal failures
- ACME order and challenge failures
- webhook request errors and latency
- controller reconcile and workqueue health
- pod restarts and crash loops
- relevant cert-manager logs

The agent must discover the actual metric names and labels in the target
environment before writing final PromQL. Do not assume every cert-manager
install exposes the same metrics or labels.

## Alert To Triage Flow

The recommended path is:

```text
Grafana Alerting or Prometheus Alertmanager
  -> Argo Events EventSource
  -> Argo Sensor
  -> Argo Workflow
  -> cert-manager expert agent
  -> shared Grafana evidence agent
  -> Grafana MCP
  -> evidence, verdict, and remediation plan
```

The contact point should deliver the original alert payload. It should not run
the investigation itself.

The cert-manager expert should own the domain reasoning. The shared Grafana
evidence agent should own dashboard discovery, PromQL, LogQL, deeplinks, and
live verification queries.

## Guardrails

- Do not require SREs to install MCP servers locally for normal use.
- Keep MCP servers and tokens platform-owned in Kubernetes.
- Keep default Grafana MCP access read-only.
- Use a dedicated Grafana service account for any write-capable workflow.
- Keep dashboard writes, alert-rule writes, annotations, plugin installs, and
  incident creation out of default SRE triage agents.
- Put durable changes through GitLab MR review and Flux reconciliation.
- Do not commit Grafana tokens, private URLs, cluster IPs, internal hostnames,
  or tenant/subscription identifiers.
- Use `{{PLACEHOLDER}}` values for environment-specific configuration.
- Validate dashboard panels against live series before calling the dashboard
  complete.
- Validate alert rules against the rule engine used by the target environment.
- If GitLab MCP is unavailable, return a patch plan or branch instructions
  instead of claiming durable GitOps completion.

## Agent Prompt

```text
Use `agents/skills/grafana-incident-evidence-pack/SKILL.md`.

You are running as the cluster-side kagent observability-work-agent. Use the
installed in-cluster MCP tools. Do not ask the SRE to install local MCP servers.

Goal: add cert-manager observability for {{CLUSTER_NAME}} / {{ENVIRONMENT}}.

Use Grafana MCP first to inspect existing datasources, dashboards, alert rules,
and live Prometheus/Loki data. Discover the actual cert-manager metric names and
labels before writing queries.

Then produce a durable GitOps change set:
- Alloy scrape/log config if telemetry is missing
- Grafana dashboard JSON for cert-manager health
- alert rules for expiry, renewal failure, ACME/order/challenge failure,
  controller/webhook errors, and missing cert-manager metrics
- alert routing into the kagent triage path, targeting the cert-manager expert
  agent
- validation commands and live Grafana MCP proof queries

Open an MR using GitLab MCP if available. Do not commit secrets or internal
hostnames. Use placeholders where needed.

Return:
- dashboard URL or expected dashboard UID
- alert names and routing labels
- files changed
- MR link
- Grafana MCP queries used as proof
- assumptions or gaps
```

## Example SRE Request

```json
{
  "component": "cert-manager",
  "namespace": "cert-manager",
  "cluster": "{{CLUSTER_NAME}}",
  "environment": "{{ENVIRONMENT}}",
  "mode": "durable-gitops",
  "request": "Add or update cert-manager observability. Use installed Grafana MCP tools to validate live metrics and logs first. Open a GitLab MR for durable Alloy, dashboard, alert, and triage-route changes if GitLab MCP is available."
}
```

## Expected Agent Closeout

The agent should finish with a short handoff:

```text
Dashboard:
- {{GRAFANA_DASHBOARD_URL_OR_UID}}

Configured:
- Alloy: {{FILES_OR_NOT_REQUIRED}}
- Dashboard: {{FILES}}
- Alerts: {{ALERT_NAMES}}
- Triage route: {{ROUTING_LABELS_OR_WORKFLOW}}

Validation:
- PromQL: {{QUERY}}
- LogQL: {{QUERY}}
- Grafana MCP tools used: {{TOOLS}}

Git:
- MR: {{GITLAB_MR_URL}}

Gaps:
- {{KNOWN_GAPS_OR_NONE}}
```

## Teams Message

```text
FYI: now that we have Grafana MCP connected to our Grafana API, SRE can use an
agent-assisted workflow for observability work through kagent. SRE should not
need to install MCP servers locally; the agent can use the MCP tools already
installed in Kubernetes.

Example: "add cert-manager observability". The agent can inspect live Grafana
data first, check Prometheus/Loki queries, identify missing Alloy collection,
generate dashboards and alert rules, and optionally raise a GitLab MR so the
config is kept through GitOps rather than being a one-off Grafana change.

This should help with fast debugging, but also with the triage agents: alerts
can route into the kagent workflow, and the cert-manager expert can use Grafana
evidence directly when producing remediation guidance.

Key guardrail: default path should be read-first via Grafana MCP. Durable
dashboard/rule changes should go through MR/review/Flux, with write-capable
Grafana/GitLab access scoped separately.

The intended UX is kagent UI or a simple A2A/curl request to the
observability-work-agent.
```

## Related Repo Material

- `docs/observability/grafana-mcp-home-lab.md`
- `docs/ai-grafana/README.md`
- `docs/observability/k-agent-alloy-grafana.md`
- `observability/managed-lgtm-integration/`
- `observability/grafana-argo-pipeline/`
