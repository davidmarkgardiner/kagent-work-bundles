# Prompt 07: Chaos Gameday End-to-End Verification

You are the work-side implementation agent. Your task is to prove that the
LGTM-to-agentic-resolution flow works under controlled chaos, not just under a
synthetic happy-path alert.

## Goal

Run a safe gameday that proves:

```text
controlled chaos
  -> LGTM / Grafana alert fires
  -> Alertmanager receives or forwards the firing alert where applicable
  -> Alertmanager or Grafana contact point delivers the event
  -> Kenawa webhook receives the alert
  -> Vector filters noise, removes duplicates, normalizes, and routes the event
  -> only actionable records reach the actionable Kafka topic
  -> Argo EventSource and Sensor trigger the workflow
  -> the correct specialist agent is selected
  -> evidence is collected
  -> GitLab ticket is created or updated with triage/remediation evidence
  -> ServiceNow is used only if the work path requires formal escalation
  -> optional human approval gates remediation
  -> Grafana dashboards show the flow and outcome
```

Do not run destructive chaos against production workloads. Use a designated test
namespace, approved test services, and rollback steps agreed with the platform
owner.

## Preflight

Before injecting chaos, capture:

- `CHAOS_TARGET_NAMESPACE`
- `CHAOS_TARGET_WORKLOAD`
- `CHAOS_SCENARIO_ID`
- Grafana dashboard URL or UID for the relevant LGTM signals
- Alert rule name and contact point name
- Alertmanager route/receiver name if Alertmanager is in the path
- Kenawa webhook endpoint/service name
- Kafka raw topic and normalized topic names
- actionable Kafka topic name
- optional quarantine topic name
- Vector deployment/config name
- Argo EventSource, Sensor, WorkflowTemplate, and workflow namespace
- Target agent route map
- expected ignore/noise policy for this test window
- GitLab or ServiceNow project/queue used for evidence tickets
- Rollback command or GitOps revert path

Do not print secrets, tokens, private URLs, internal IPs, tenant IDs, or real
customer data. Capture names and evidence IDs only where possible.

## Create Grafana Alerts

Create the gameday alert rules before injecting chaos.

Use the example contract:

```text
examples/grafana-chaos-alerts/chaos-alert-rules.yaml
```

Preferred path: use Grafana MCP.

1. Discover the available Grafana MCP tools.
2. Confirm whether the MCP can write folders, alert rules, contact points, and
   notification policies.
3. If write-capable tools exist, create or update the `Kagent Chaos Gameday`
   folder and the alert rules from `chaos-alert-rules.yaml`.
4. Create rules paused first unless the test window is approved.
5. Verify the notification policy routes
   `route_to=kagent-chaos-gameday` to the approved contact point.
6. Record the folder UID, alert rule UIDs, contact point, and policy matcher.

Fallback path: use the Grafana provisioning API script:

```bash
cd work-agent-bundles/vector-kafka-routing-normalization/examples/grafana-chaos-alerts

export GRAFANA_URL="{{GRAFANA_URL}}"
export GRAFANA_USER="{{GRAFANA_USER}}"
export GRAFANA_PASSWORD="{{GRAFANA_PASSWORD}}"
export CHAOS_TARGET_NAMESPACE="{{CHAOS_TARGET_NAMESPACE}}"
export GRAFANA_CREATE_PAUSED="true"

bash create-chaos-alerts-api.sh
```

Only unpause the rules after the alert route, contact point, Vector path, and
rollback are confirmed.

Home-lab replication evidence to aim for:

```text
GRAFANA_CHAOS_ALERT_RULES: created_or_updated
GRAFANA_FOLDER_UID: kagent-chaos-gameday
GRAFANA_RULE_GROUP: kagent-chaos-gameday
GRAFANA_CREATE_PAUSED: true
```

## Scenarios

Run at least three of these scenarios. Prefer the first four for the initial
rollout:

| Scenario | Expected route | Expected evidence |
|---|---|---|
| Pod crashloop or failed readiness | `aks-sre-triage-agent` | pod describe, logs, recent events, deployment rollout state |
| Ingress 5xx or latency | `networking-triage-agent` | ingress/controller logs, service endpoints, DNS/TLS checks, Grafana panel link |
| Cert expiry or TLS failure | `platform-ops-agent` or `cert-manager-agent` | certificate status, issuer events, secret reference, renewal state |
| Policy/security violation | `security-hardening-agent` | policy result, image/advisory evidence, namespace/workload owner |
| DNS/service discovery failure | `networking-triage-agent` | CoreDNS logs, service/endpoints, failing lookup evidence |
| Resource pressure/OOM | `aks-sre-triage-agent` | metrics, limits/requests, OOMKilled evidence, recommendation |

Also run the negative controls below. These prove the pipeline is efficient and
does not create agent work for non-actionable input:

| Negative control | Expected result |
|---|---|
| Duplicate firing notification for the same alert | one actionable Kafka record and one Argo workflow inside the dedupe window |
| Resolved notification for the same alert | no new actionable Kafka record and no new Argo workflow |
| Ignored severity or configured noisy label | dropped or quarantined, no Argo workflow |
| Malformed or incomplete alert payload | dropped or quarantined, no Argo workflow |

## Execution Steps

1. Confirm the alert rule is enabled and routed to the intended contact point.
2. Confirm the rules were created through Grafana MCP or the API fallback.
3. Confirm Vector and Argo are healthy before the test.
4. Start a timestamped evidence log.
5. Inject one controlled chaos scenario.
6. Wait for the Grafana/LGTM alert to fire.
7. Confirm Alertmanager receives or forwards the alert where applicable.
8. Confirm the Kenawa webhook receives the alert.
9. Confirm delivery into the raw path:
   - Kafka-first: event appears on the raw topic.
   - Direct Vector: Vector receives the webhook.
10. Confirm Vector emits a normalized `observability.triage.v1` record only for
   the actionable firing alert.
11. Confirm the normalized event includes:
   - `schema_version`
   - `source_system`
   - `alert_uid`
   - `fingerprint`
   - `target_agent`
   - `route_domain`
   - `route_key`
   - `routing_reason`
   - `dedupe_key`
   - `incident_candidate`
   - `automation_allowed`
   - `raw_event_ref_or_hash`
12. Confirm duplicates, resolved notifications, ignored severities, ignored
    labels, and malformed events do not create actionable records or workflows.
13. Confirm Argo creates the triage workflow for the actionable record only.
14. Confirm the selected specialist agent is correct for the scenario.
15. Confirm the GitLab ticket is created or updated and includes:
    - original alert name and fingerprint
    - affected namespace/workload/service
    - selected specialist agent
    - triage summary
    - evidence links or captured evidence
    - remediation recommendation or action taken
    - automation approval state
    - final status: triaged, remediated, escalated, or blocked
16. If remediation is enabled, confirm human approval is required before any
    write-capable action.
17. Roll back the chaos condition.
18. Confirm alert recovery/resolution is observed and does not create a new
    actionable agent task.
19. Capture final dashboard screenshots or panel links showing the lifecycle.

## Daily Scheduled Gameday

Propose, but do not enable without approval, a daily low-risk verification job:

```text
CronWorkflow or scheduled CI job
  -> create safe test fault in a dedicated namespace
  -> assert alert fired
  -> assert normalized event created
  -> assert route selected
  -> assert ticket/evidence created
  -> clean up test fault
  -> publish daily result metric
```

The daily job must:

- run only in an approved test namespace
- use a unique `chaos_scenario_id`
- include at least one negative control for duplicate or resolved alert
- clean up after itself
- fail closed if alerting or remediation safety gates are unavailable
- never perform production remediation automatically
- emit a single pass/fail result for dashboards

## Grafana Dashboards

Create or update dashboards that show:

- alerts received by source
- raw events vs normalized events
- normalized actionable events vs dropped/quarantined events
- Vector route counts by `target_agent` and `route_domain`
- duplicate suppression count
- noise suppression count by reason
- Argo workflow count and status
- ticket created count
- ticket avoided or deflected count
- MTTA and MTTR trends
- chaos gameday pass/fail history
- manual approval count and outcome
- remediation success/failure count

The dashboard must let a stakeholder follow one scenario from alert to ticket
without needing terminal access.

## Success Markers

Append these markers to the evidence file:

```text
CHAOS_PREFLIGHT: passed
GRAFANA_MCP_ALERT_WRITE: used_or_blocked
GRAFANA_CHAOS_ALERT_RULES: created_or_updated
CHAOS_SCENARIO: injected
GRAFANA_ALERT_FIRED: verified
EVENT_DELIVERY: verified
VECTOR_NORMALIZED_EVENT: verified
ACTIONABLE_TOPIC_CLEAN: verified
NEGATIVE_CONTROLS: verified
NOISE_FILTER: verified
DEDUPE_BEFORE_ARGO: verified
VECTOR_ROUTE_AGENT: verified
ARGO_WORKFLOW_CREATED: verified
SPECIALIST_AGENT_SELECTED: verified
EVIDENCE_PACK_CREATED: verified
TICKET_CREATED_OR_UPDATED: verified
GITLAB_TICKET_TRIAGE_OR_REMEDIATION: verified
REMEDIATION_GATE: verified_or_not_enabled
CHAOS_ROLLBACK: verified
ALERT_RESOLUTION: verified
GRAFANA_DASHBOARD: updated
DAILY_GAMEDAY_PROPOSAL: captured
OUTPUT_SANITIZED: yes
```

If any marker cannot be completed, stop and record:

- what failed
- exact component boundary
- evidence captured
- rollback state
- next action

Do not claim the process is production-ready until this gameday passes for at
least one application scenario, one platform scenario, and one networking or
security scenario.
