# SRE Grafana MCP Observability Checklist

Use this checklist for the work-side cert-manager observability implementation.

## Intake

- [ ] Confirm the approved work repo and target branch.
- [ ] Confirm the approved cluster, namespace, and environment.
- [ ] Confirm the installed kagent UI or A2A endpoint SRE will use.
- [ ] Confirm SRE does not need local MCP server installation for normal use.
- [ ] Confirm whether GitLab MCP is available for branch, file, MR, and comment
  operations.
- [ ] Confirm whether Grafana MCP is read-only or write-capable.
- [ ] Confirm the expected GitOps reconciliation path.

## Kagent Front Door

- [ ] Define or update `observability-work-agent`.
- [ ] Load or reference `agents/skills/grafana-incident-evidence-pack/SKILL.md`.
- [ ] Grant Grafana MCP read tools through installed cluster MCP services.
- [ ] Grant GitLab MCP branch/MR tools only if approved.
- [ ] Keep write-capable Grafana tools out of the default agent.
- [ ] Expose the agent through kagent UI or A2A.
- [ ] Add an example SRE request for cert-manager observability.
- [ ] Document the curl or UI path using placeholders.

## Grafana MCP Discovery

- [ ] List available Grafana MCP tools through the cluster-side agent/tool path.
- [ ] List datasources.
- [ ] Identify Prometheus or Mimir datasource UID.
- [ ] Identify Loki datasource UID.
- [ ] Inspect current cert-manager dashboards.
- [ ] Inspect current cert-manager alert rules and routing.
- [ ] Record Grafana deeplinks for relevant dashboards or Explore queries.

## Live Telemetry Discovery

- [ ] Discover cert-manager metric names and labels.
- [ ] Query controller, webhook, and cainjector health.
- [ ] Query certificate expiry and renewal health where metrics exist.
- [ ] Query ACME order and challenge health where metrics exist.
- [ ] Query pod restarts and missing metrics.
- [ ] Query recent cert-manager logs.
- [ ] Confirm whether log labels include `namespace`, `pod`, `container`, and
  `cluster`.

## Alloy

- [ ] Check whether Alloy already scrapes cert-manager metrics.
- [ ] Check whether Alloy already tails cert-manager logs.
- [ ] Add or patch Alloy config only for missing telemetry.
- [ ] Keep endpoints, tenant IDs, tokens, and hostnames as placeholders.
- [ ] Validate Alloy config using the work environment's supported workflow.

## Dashboards

- [ ] Reuse existing dashboard conventions where possible.
- [ ] Add dashboard panels only after live series are confirmed.
- [ ] Include controller, webhook, cainjector, certificate expiry, renewals,
  ACME errors, logs, restarts, and recovery signal where data is present.
- [ ] Return dashboard UID or expected URL.

## Alerts

- [ ] Add certificate expiry warnings.
- [ ] Add renewal failure alerts.
- [ ] Add ACME order and challenge failure alerts.
- [ ] Add controller/webhook/cainjector down or missing-metrics alerts.
- [ ] Add cert-manager log error alerts only if Loki ruler support exists.
- [ ] Add routing labels for the triage path.
- [ ] Validate rule syntax with the work rule engine.

## Triage Route

- [ ] Route alerts through Grafana Alerting or Alertmanager.
- [ ] Deliver alert payload into Argo Events or the approved triage entry point.
- [ ] Target the cert-manager expert agent.
- [ ] Delegate Grafana evidence to the shared Grafana evidence agent.
- [ ] Keep Kubernetes mutation out of the Grafana evidence agent.

## GitLab MCP

- [ ] Create a source branch if write access is approved.
- [ ] Create or update files through GitLab MCP.
- [ ] Open a merge request.
- [ ] Add an evidence comment with validation queries and gaps.
- [ ] Do not include secrets or private endpoints in the MR.

## Closeout

- [ ] Return required evidence markers.
- [ ] Confirm `KAGENT_FRONT_DOOR`.
- [ ] Confirm `LOCAL_MCP_REQUIRED_FOR_SRE: no`.
- [ ] Separate live proof from proposed config.
- [ ] List assumptions and blocked items.
- [ ] Provide next action for any blocked write, review, or runtime path.
