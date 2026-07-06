# Fair-Fight Handoff: Grafana Alerting To Kagent Triage

Give the work agent this folder:

```text
work-agent-bundles/vector-kafka-routing-normalization/
```

The folder is self-contained for the replication task. It includes:

- `FAIR-FIGHT-HANDOFF.md` - start here.
- `payload/observability-vector/manifests/01-vector-alertmanager-normalizer.yaml` - Vector normalizer to deploy/adapt.
- `payload/observability-vector/tests/run-vector-example-tests.sh` - local Vector contract test.
- `payload/observability-vector/tests/vector-example-test.yaml` - local Vector test config.
- `payload/observability-vector/examples/grafana-alertmanager-rich.json` - Grafana-managed Alerting fixture with rich context.
- `GITLAB-TICKET.md` - ticket body/acceptance criteria.
- `evidence/EVIDENCE-TEMPLATE.md` - evidence form to return.
- `prompts/04-run-grafana-mcp-end-to-end.md` - live end-to-end work prompt.

## Goal

Prove a fair fight for the agent:

Grafana-managed Alerting fires the alert, Vector preserves the rich context, Argo
receives the rich payload, and the GitLab ticket contains enough context for the
kagent triage agent to start with the best possible evidence.

Do not count it as success if the agent has to rediscover `cluster`,
`event_reason`, kubectl commands, or log queries later through Grafana MCP.

## Required Live Path

Use the real work path:

```text
Grafana managed alert rule
  -> Grafana contact point
  -> raw Kafka/webhook path
  -> Vector normalizer
  -> alertmanager-events-triage
  -> Argo sensor/workflow
  -> kagent triage agent
  -> GitLab ticket
```

Do not bypass Grafana Alerting with a direct synthetic Argo payload for the final
proof. Synthetic payloads are only allowed for local contract tests.

## Alert Contract

The Grafana alert must include these labels where available:

```text
cluster
namespace
pod or service
severity
environment
event_name
event_reason
reason
kagent_path=webhook
route_to=triage
```

The Grafana alert must include these annotations where available:

```text
summary
description
event_context
suggested_kubectl
suggested_log_query
grafana_panel_url or dashboard_url
runbook_url
```

The sample fixture is:

```text
payload/observability-vector/examples/grafana-alertmanager-rich.json
```

## Local Contract Test

From inside this bundle:

```bash
cd payload/observability-vector
bash tests/run-vector-example-tests.sh
```

Expected result:

```text
PASS Vector example tests
```

The test proves the bundled Vector config preserves:

```text
cluster=aks-dev-01
event_reason=BackOff
event_context=event_name=CheckoutApiWarningEvent; event_reason=BackOff; ...
suggested_kubectl=kubectl -n payments describe pod checkout-api-...
suggested_log_query={namespace="payments", pod="checkout-api-..."} |= "Back-off"
alerts[0].labels.cluster=aks-dev-01
alerts[0].labels.event_reason=BackOff
alerts[0].annotations.suggested_kubectl=kubectl -n payments describe pod ...
```

## Live Evidence Required

Return `evidence/EVIDENCE-TEMPLATE.md` filled in with real work evidence. Redact
tokens, private hostnames, internal URLs, tenant IDs, subscription IDs, and
private cluster names unless the target work system explicitly allows them.

The same alert fingerprint or dedupe key must be visible across all checkpoints:

1. Grafana alert fired
   - rule name/UID
   - alert state
   - fingerprint or group key
   - contact point delivery evidence

2. Vector normalized record consumed
   - topic, partition, offset
   - `source=grafana`
   - `event_type=grafana-managed-alert`
   - `cluster`
   - `event_reason`
   - `event_context`
   - `suggested_kubectl`
   - `suggested_log_query`
   - `target_agent`
   - `route_key`
   - `dedupe_key`

3. Argo sensor/workflow received rich payload
   - workflow name
   - workflow parameter or logged payload excerpt
   - `alerts[0].labels.cluster`
   - `alerts[0].labels.event_reason`
   - `alerts[0].annotations.event_context`
   - `alerts[0].annotations.suggested_kubectl`
   - `alerts[0].annotations.suggested_log_query`

4. GitLab ticket is triage-ready
   - issue URL or ID
   - redacted ticket body excerpt
   - same `cluster`
   - same `event_reason`
   - suggested kubectl command
   - suggested log query
   - dashboard link
   - runbook link

## Ready Gate

Mark the run ready only when all of these are true:

```text
NORMALIZED_KAFKA_RECORD_HAS_CLUSTER: verified
NORMALIZED_KAFKA_RECORD_HAS_EVENT_REASON: verified
NORMALIZED_KAFKA_RECORD_HAS_RICH_CONTEXT: verified
ARGO_SENSOR_PAYLOAD_HAS_CLUSTER: verified
ARGO_SENSOR_PAYLOAD_HAS_EVENT_REASON: verified
ARGO_SENSOR_PAYLOAD_HAS_RICH_CONTEXT: verified
GITLAB_TICKET_INCLUDES_CLUSTER: verified
GITLAB_TICKET_INCLUDES_EVENT_REASON: verified
GITLAB_TICKET_INCLUDES_RICH_CONTEXT: verified
```

If any field is missing, `unknown`, blank, or only rediscovered after the agent
calls Grafana MCP, mark the run not ready and record the gap.

## Work Agent Start Prompt

```text
Use this folder as the source of truth:
work-agent-bundles/vector-kafka-routing-normalization/

Start with FAIR-FIGHT-HANDOFF.md. Run the local Vector contract test from
payload/observability-vector. Then perform the live fair-fight proof using the
real Grafana managed alerting contact point, Vector, alertmanager-events-triage,
Argo, kagent, and GitLab ticket path.

Return evidence/EVIDENCE-TEMPLATE.md filled in. Do not claim ready unless the
normalized Kafka record, Argo payload, and GitLab ticket all contain cluster,
event_reason, event_context, suggested_kubectl, and suggested_log_query.
```
