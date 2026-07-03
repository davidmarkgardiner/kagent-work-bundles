# Grafana Webhook Payload Proof

## Purpose

This note is for the work agent validating missing Grafana alert fields such as
`pod`, `namespace`, `cluster`, and event context before Vector normalizes the
payload into Kafka.

The home-lab check verified this path:

```text
Grafana-managed alert rule
  -> Grafana webhook contact point
  -> temporary Vector-style HTTP webhook receiver
```

It did not use a synthetic curl payload. The alert was created as a
Grafana-managed alert rule and delivered through a Grafana webhook contact
point.

## Home-Lab Verification Result

Verified on `kind-argo-workflow` using:

- Grafana namespace: `grafana-test`
- Grafana image: Grafana OSS test deployment
- Prometheus service:
  `monitoring-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090`
- Temporary webhook receiver namespace: `vector-payload-test`
- Temporary contact point: `vector-payload-capture`
- Temporary alert rule UID: `vector-payload-proof-pod-labels`

The Grafana alert query was:

```promql
max by (namespace,pod,cluster) (
  label_replace(
    up{namespace="kube-system",pod!="",job="coredns"},
    "cluster",
    "kind-argo-workflow",
    "namespace",
    ".*"
  )
)
```

The fired Grafana alert instances contained the expected labels:

```text
alerts[0].labels.cluster: kind-argo-workflow
alerts[0].labels.namespace: kube-system
alerts[0].labels.pod: coredns-7d764666f9-bslbk

alerts[1].labels.cluster: kind-argo-workflow
alerts[1].labels.namespace: kube-system
alerts[1].labels.pod: coredns-7d764666f9-nqfqc
```

The webhook payload also had shared routing labels:

```text
alerts[].labels.environment: homelab
alerts[].labels.route_to: vector-payload-proof
alerts[].labels.severity: warning
alerts[].labels.source_test: grafana-managed-alert-rule
alerts[].labels.target_agent: aks-sre-triage-agent
```

## Important Finding

Grafana preserved `pod`, `namespace`, and `cluster` when the alert query result
carried those labels.

However, `pod` was not present in `commonLabels` because the notification
contained more than one alert instance and each instance had a different pod
name. That means Vector must read each item in `alerts[]` and must not depend
only on `commonLabels`.

Use this extraction order:

```text
alert.labels.<field>
  -> payload.commonLabels.<field>
  -> receiver/source enrichment
  -> unknown only as a final fallback
```

## Why Work May Be Missing Fields

If the work environment is missing `pod`, `event`, or `cluster`, check these in
order:

1. The Grafana alert query may not return those labels. Grafana will not invent
   `pod`, `namespace`, or `cluster` if the query/expression stripped them.
2. Vector may be reading only `commonLabels`. Per-pod values often exist only in
   `alerts[].labels`.
3. The Grafana notification policy may be grouping multiple alert instances.
   Labels that differ between instances are omitted from `commonLabels`.
4. Prometheus may not have a stable cluster label. Add it through Prometheus
   external labels, the rule labels, a PromQL enrichment, or Vector receiver
   enrichment based on the source.
5. The alert may be based on Kubernetes event/log data that is not present in
   the metric series. For event reason/message/object data, the alert rule must
   query a source that exposes those fields or add them as annotations/labels.
6. A Grafana reduce/math expression may have changed the label set. Confirm the
   final alert instance labels in Grafana before blaming Vector.

## Work-Agent Validation Steps

1. Create a temporary webhook capture endpoint beside Vector or enable a raw
   capture path on the existing Vector receiver.
2. Create or update a Grafana-managed alert rule using the same datasource and
   contact point used by the real flow.
3. Use a query that deliberately returns `cluster`, `namespace`, and `pod`.
4. Fire the alert and capture the raw Grafana webhook payload before Vector
   normalization.
5. Prove the labels exist at `alerts[].labels`.
6. Prove Vector maps each alert instance into the normalized Kafka envelope.
7. Prove the Kafka record consumed by Argo still has the same fields.
8. Clean up the test alert rule, contact point route, capture endpoint, and any
   chaos workload.

Expected evidence:

```text
GRAFANA_ALERT_RULE_UID: {{GRAFANA_ALERT_RULE_UID}}
GRAFANA_CONTACT_POINT: {{GRAFANA_CONTACT_POINT_NAME_OR_UID}}
RAW_WEBHOOK_CAPTURE: captured
RAW_ALERT_LABELS_CLUSTER: present
RAW_ALERT_LABELS_NAMESPACE: present
RAW_ALERT_LABELS_POD: present
COMMON_LABELS_POD: absent_when_multiple_pods_expected
VECTOR_NORMALIZED_CLUSTER: present
VECTOR_NORMALIZED_NAMESPACE: present
VECTOR_NORMALIZED_POD: present
KAFKA_NORMALIZED_EVENT: consumed
ARGO_SENSOR_TRIGGER: verified
CLEANUP: completed
```

## Vector Normalization Guidance

Vector should normalize per alert instance, not per webhook notification group.

Required normalized fields:

```text
source_system: grafana
source_receiver: {{GRAFANA_CONTACT_POINT_NAME_OR_UID}}
alert_name: alert.labels.alertname
cluster: alert.labels.cluster ?? commonLabels.cluster ?? source_enrichment.cluster
namespace: alert.labels.namespace ?? commonLabels.namespace
pod: alert.labels.pod ?? commonLabels.pod
severity: alert.labels.severity ?? commonLabels.severity
status: alert.status
starts_at: alert.startsAt
ends_at: alert.endsAt
summary: alert.annotations.summary
description: alert.annotations.description
dedupe_key: hash(cluster, namespace, pod, alert_name, status)
target_agent: alert.labels.target_agent ?? route_map(alert.labels)
```

If the event is not actionable, Vector should drop it before the actionable
Kafka topic. If fields are missing, route to quarantine or add a
`normalization_gap` marker rather than silently sending weak records to Argo.

## Cleanup Used In Home Lab

The temporary home-lab proof used these cleanup actions:

```bash
curl -u admin:{{GRAFANA_PASSWORD}} \
  -X DELETE \
  {{GRAFANA_URL}}/api/v1/provisioning/alert-rules/vector-payload-proof-pod-labels

curl -u admin:{{GRAFANA_PASSWORD}} \
  -X DELETE \
  {{GRAFANA_URL}}/api/v1/provisioning/contact-points/{{CONTACT_POINT_UID}}

curl -u admin:{{GRAFANA_PASSWORD}} \
  -X DELETE \
  {{GRAFANA_URL}}/api/datasources/uid/real-prometheus-payload-proof

curl -u admin:{{GRAFANA_PASSWORD}} \
  -X DELETE \
  {{GRAFANA_URL}}/api/folders/vector-payload-proof

kubectl --context {{KUBE_CONTEXT}} delete ns vector-payload-test --ignore-not-found
```

## References

- Grafana webhook contact points:
  `https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/`
- Grafana alerting provisioning API:
  `https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/alerting_provisioning/`
- Grafana notification policies:
  `https://grafana.com/docs/grafana/latest/alerting/fundamentals/notifications/notification-policies/`
