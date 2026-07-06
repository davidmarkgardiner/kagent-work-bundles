# Alert Data Enrichment Front Sheet

Hand this file to the work agent when the only goal is improving the alert data
presented to the kagent triage agent.

## Goal

Make the alert context from Grafana as rich and useful as possible before it is
handed to the agent.

The agent should not have to rediscover basic facts like cluster, event reason,
pod, suggested kubectl command, or log query after the handoff. Those fields
should already be present in the alert payload that reaches the agent.

## Scope

Focus only on the data path:

```text
Grafana managed alert
  -> Grafana contact point
  -> Vector normalization/enrichment
  -> alertmanager-events-triage payload
  -> Argo sensor/workflow payload
  -> kagent triage prompt/context
```

Out of scope for this pass:

- remediation
- workflow approval gates
- dashboard design
- GitLab workflow automation, except proving the ticket/context would contain
  the enriched fields if a ticket is created
- agent reasoning quality after the payload is handed over

## Data The Agent Must Receive

At minimum, the final agent-facing alert context should contain:

```text
alert_name
severity
cluster
namespace
pod or service
environment
event_name
event_reason
event_context
suggested_kubectl
suggested_log_query
dashboard_url or grafana_panel_url
runbook_url
dedupe_key
route_key
target_agent
```

If any of these are missing from the source alert, record whether Vector can
derive them safely or whether the Grafana alert rule/contact point must be fixed.

## Source Alert Requirements

The Grafana alert should provide these labels:

```text
cluster
namespace
pod
service
environment
severity
event_name
event_reason
reason
kagent_path=webhook
route_to=triage
```

The Grafana alert should provide these annotations:

```text
summary
description
event_context
suggested_kubectl
suggested_log_query
grafana_panel_url
runbook_url
```

Use this local fixture as the reference shape:

```text
payload/observability-vector/examples/grafana-alertmanager-rich.json
```

## What Vector Must Do

Vector should normalize the alert into `observability.triage.v1` and preserve
the rich fields in two places:

1. Top-level normalized fields for routing and evidence:

```text
cluster
event_name
event_reason
reason
event_context
suggested_kubectl
suggested_log_query
runbook_url
dashboard_url
target_agent
route_key
dedupe_key
```

2. Argo-compatible Alertmanager-style fields:

```text
alerts[0].labels.cluster
alerts[0].labels.event_name
alerts[0].labels.event_reason
alerts[0].annotations.event_context
alerts[0].annotations.suggested_kubectl
alerts[0].annotations.suggested_log_query
alerts[0].annotations.runbook_url
alerts[0].annotations.dashboard_url
```

The relevant bundled file is:

```text
payload/observability-vector/manifests/01-vector-alertmanager-normalizer.yaml
```

## What Argo Must Pass To The Agent

The Argo sensor/workflow should not collapse the payload to only alert name,
severity, namespace, and summary.

Before invoking the agent, confirm the prompt or request body includes:

```text
Cluster
Event name
Event reason
Event context
Suggested kubectl
Suggested log query
Runbook URL
Dashboard URL
Full alert payload or enough structured payload to recover the above
```

The repo-side reference file is:

```text
k8s/observability/k-agent-alert-triage-sensor.yaml
```

## Local Contract Test

From inside the bundle:

```bash
cd payload/observability-vector
bash tests/run-vector-example-tests.sh
```

This must pass before attempting the live work-environment proof.

The important assertion is the Grafana-managed rich-context fixture. It proves:

```text
cluster=aks-dev-01
event_reason=BackOff
event_context is preserved
suggested_kubectl is preserved
suggested_log_query is preserved
alerts[0].labels.cluster is preserved
alerts[0].labels.event_reason is preserved
alerts[0].annotations.suggested_kubectl is preserved
```

## Live Proof Required

Use one real Grafana-managed alert and follow the same event through the path.
Capture the same fingerprint, group key, or dedupe key at each stage.

Return evidence for:

1. Grafana fired the alert.
2. Vector produced a normalized Kafka record with the enriched fields.
3. Argo received those enriched fields in its workflow payload.
4. The agent-facing prompt/request includes those enriched fields.
5. If a GitLab ticket is produced, it includes the same enriched context.

## Ready Gate

Ready means all of these are true:

```text
GRAFANA_ALERT_HAS_CLUSTER: verified
GRAFANA_ALERT_HAS_EVENT_REASON: verified
GRAFANA_ALERT_HAS_RICH_CONTEXT: verified
VECTOR_NORMALIZED_CLUSTER: verified
VECTOR_NORMALIZED_EVENT_REASON: verified
VECTOR_NORMALIZED_RICH_CONTEXT: verified
ARGO_PAYLOAD_HAS_CLUSTER: verified
ARGO_PAYLOAD_HAS_EVENT_REASON: verified
ARGO_PAYLOAD_HAS_RICH_CONTEXT: verified
AGENT_CONTEXT_HAS_CLUSTER: verified
AGENT_CONTEXT_HAS_EVENT_REASON: verified
AGENT_CONTEXT_HAS_RICH_CONTEXT: verified
```

Not ready if the fields are missing, blank, `unknown`, or only found later by
the agent calling Grafana MCP.

## Work Agent Prompt

```text
Use this front sheet as the source of truth:
work-agent-bundles/vector-kafka-routing-normalization/ALERT-DATA-ENRICHMENT-FRONT-SHEET.md

Concentrate only on alert data enrichment and the data flow from Grafana into
the kagent triage context.

Prove that the Grafana alert, Vector normalized record, Argo workflow payload,
and final agent-facing context all include cluster, event_reason, event_context,
suggested_kubectl, and suggested_log_query.

Do not mark ready if the agent has to rediscover those fields after handoff.
Return concise evidence for each checkpoint and list any missing fields.
```
