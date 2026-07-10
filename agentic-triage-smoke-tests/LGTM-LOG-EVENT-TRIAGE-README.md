# LGTM Log And Event Triage Position

## Teams Reply

```text
TL;DR: I think this is doable with LGTM, but it needs to be configured as first-class log/event alerting, not treated as automatic context attached to metric alerts.

What we need is:

Kubernetes events -> Alloy -> Loki -> Grafana LogQL alert -> Alertmanager/Grafana webhook -> Vector/Kafka -> triage system

And similarly:

Application logs -> Alloy/Promtail -> Loki -> Grafana LogQL alert -> Alertmanager/Grafana webhook -> Vector/Kafka -> triage system

So the key requirement is that LGTM lets us:
1. ingest Kubernetes events into Loki, ideally via Alloy loki.source.kubernetes_events;
2. query those events/logs in Loki with the right labels;
3. create Grafana LogQL alert rules over those records;
4. route those alerts through the existing webhook path into Vector/Kafka/triage;
5. preserve labels like namespace, workload, pod, reason, source_type, run_id/fingerprint.

This does not require a new custom tool in principle. It is mostly Alloy/Loki/Grafana alerting configuration.

The important distinction is that metric alerts will not automatically include related logs/events unless we add enrichment, e.g. the triage agent querying Loki/Tempo around the alert time window. But logs and Kubernetes events can still become their own Grafana alerts and enter the same triage pipeline.

If the current managed LGTM setup cannot support Loki alert rules, Kubernetes event ingestion, or webhook routing with the labels we need, then it is probably not fit for this agentic triage use case as-is. In that case we should look at either extending the current LGTM setup or hosting/operating our own Grafana/LGTM path where we control Alloy, Loki alerting, notification policies, and webhook delivery.
```

## Implementation Shape

The work-side replication path is configuration-first:

- Alloy or Promtail must send application pod logs to Loki.
- Alloy should send Kubernetes events to Loki with `loki.source.kubernetes_events`
  or an approved equivalent.
- Grafana needs LogQL alert rules for log and event sources.
- Alertmanager or Grafana notification policies need to route those alerts into
  the same webhook path as metric alerts.
- Vector/Kafka, if used, must preserve the triage join keys:
  `run_id`, `fingerprint`, `alertname`, `namespace`, `workload`,
  `source_type`, and `severity`.

Metric alerts remain useful, but they are not enough by themselves. If a metric
alert needs related logs/events, the triage agent or an enrichment service must
query Loki around the alert time window.

For the fuller work-team assessment, including OTel/Loki label guidance and
go/no-go criteria for managed LGTM versus self-hosted Grafana/LGTM, see
`LGTM-FIT-FOR-PURPOSE-ASSESSMENT.md`.
