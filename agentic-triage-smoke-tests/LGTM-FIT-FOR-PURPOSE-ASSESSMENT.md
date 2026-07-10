# LGTM Fit-For-Purpose Assessment For Agentic Triage

## Position

The agentic triage requirement is reasonable: operational incidents should be
detectable from metrics, logs, Kubernetes events, and traces where available.
A platform that only emits metric threshold alerts, without a supported way to
alert on logs/events or enrich metric alerts with nearby evidence, is not
sufficient for this use case.

Using OpenTelemetry for log ingestion does not make the requirement invalid.
It changes where metadata should live:

- Low-cardinality routing keys should be Loki labels.
- High-cardinality details should be structured metadata, log attributes, or
  the log body.
- Alert annotations should carry triage summaries and Explore/deeplink context.

The key test is not whether every useful field can become a Loki index label.
That would be bad Loki practice. The key test is whether the LGTM service can
preserve and query enough metadata to create reliable Grafana alerts and route
those alerts into the triage pipeline.

## Required Managed LGTM Capabilities

The work LGTM service needs to provide or allow the platform team to configure:

1. **Application logs in Loki**
   - Pod stdout/stderr reaches Loki.
   - Logs can be queried by stable Kubernetes/service keys.
   - Known error markers can be found in Grafana Explore and used in LogQL
     alert rules.

2. **Kubernetes events in Loki or another alertable backend**
   - Kubernetes events are collected, for example via Alloy
     `loki.source.kubernetes_events` or an equivalent approved collector.
   - Warning events such as `FailedScheduling`, `BackOff`, `FailedMount`,
     `ErrImagePull`, `ImagePullBackOff`, and `Unhealthy` can be queried.
   - Event alerts preserve namespace, workload/object, reason, and message.

3. **Grafana LogQL alerting**
   - Grafana can create managed alert rules over Loki queries.
   - Rules can be scoped by namespace/workload and tagged with labels such as
     `source_type=logs` or `source_type=events`.
   - Alert annotations can include useful context and links back to Loki.

4. **Webhook or Alertmanager routing**
   - Fired alerts can be sent to the existing webhook path.
   - If Vector/Kafka sits between Grafana and triage, it must preserve the
     join keys required for scoring and investigation.

5. **Programmatic or GitOps control**
   - The team needs a supported way to create, update, export, and review alert
     rules, contact points, and notification policies.
   - This can be Grafana API, Terraform/provider, provisioning files, Grafana
     MCP, or another controlled automation interface.
   - A UI-only managed service is a poor fit for repeatable smoke tests and
     agentic triage rollout.

## OTel And Loki Metadata Guidance

OpenTelemetry ingestion commonly maps selected resource attributes to Loki
labels and stores the rest as structured metadata. That is expected.

Use labels for low-cardinality fields:

```text
cluster
namespace
service_name
service_namespace
k8s_deployment_name
k8s_statefulset_name
k8s_daemonset_name
k8s_job_name
source_type
severity
event_reason when low-cardinality
```

Use structured metadata, log attributes, or log body for high-cardinality
fields:

```text
pod
container_id
trace_id
span_id
run_id
fingerprint
event_uid
exact error text
full Kubernetes event message
```

The service does not need to index every field. It does need to let us query
and alert reliably, using a combination of labels, structured metadata, parsed
fields, and log body filters.

## Minimum Proof Required From The LGTM Team

Before declaring the managed LGTM path fit for purpose, ask the team to prove
the following in a dev cluster:

1. **Log alert proof**
   - Emit a known application log marker from a pod.
   - Show the marker in Loki/Grafana Explore.
   - Create a Grafana LogQL alert over that marker.
   - Route the fired alert to the triage webhook path.
   - Confirm the triage payload contains source type, namespace, workload, pod
     or service, and a link/query back to the evidence.

2. **Kubernetes event alert proof**
   - Create a safe failure such as an unschedulable pod.
   - Show the Kubernetes event in Loki or another alertable backend.
   - Create a Grafana alert for that event reason.
   - Route the fired alert to the triage webhook path.
   - Confirm the triage payload contains source type, namespace, object,
     reason, message, and evidence link/query.

3. **Metric enrichment proof**
   - Fire a normal Prometheus/Mimir metric alert.
   - Show how the triage workflow can query nearby Loki logs/events using the
     metric alert labels and time window.
   - If enrichment is not available, document that metric alerts remain
     evidence-light and cannot by themselves satisfy full triage.

4. **Automation proof**
   - Demonstrate how these alert rules and routes can be created and versioned
     programmatically.
   - If API/MCP/Terraform/provisioning access is blocked, document the managed
     service limitation explicitly.

## Go / No-Go Criteria

### Go

Proceed with the managed LGTM service if all of these are true:

- logs and Kubernetes events are ingested and queryable;
- Grafana LogQL alerts can be created for log and event sources;
- alerts can be routed to the triage webhook path;
- required labels/metadata survive into Vector/Kafka and the triage workflow;
- alert rules and routes can be managed programmatically or through an
  approved GitOps/provisioning flow;
- periodic smoke tests can prove the path continuously.

### No-Go

Treat the managed LGTM service as not fit for purpose for agentic triage if any
of these are permanent limitations:

- Kubernetes events cannot be ingested into an alertable backend;
- application logs cannot be queried in Loki with useful Kubernetes/service
  metadata;
- Grafana LogQL alert rules are not available or cannot be routed out;
- webhook/contact-point routing is blocked or too restricted;
- alert labels/annotations are stripped before reaching triage;
- there is no supported API, MCP, Terraform, or provisioning route for alert
  configuration;
- the service only supports metric alerts and manual log investigation.

If these limitations are confirmed and cannot be remediated by the LGTM team,
the fallback is to host or operate our own Grafana/LGTM path where we control
Alloy, Loki/Tempo/Prometheus configuration, alert provisioning, notification
policies, and API/MCP access.

## References

- Grafana Loki OpenTelemetry ingestion:
  https://grafana.com/docs/loki/latest/send-data/otel/
- Grafana Loki structured metadata:
  https://grafana.com/docs/loki/latest/get-started/labels/structured-metadata/
- Grafana Alloy Loki exporter and OTel label hints:
  https://grafana.com/docs/alloy/latest/reference/components/otelcol/otelcol.exporter.loki/
- Grafana Alloy Kubernetes attributes processor:
  https://grafana.com/docs/alloy/latest/reference/components/otelcol/otelcol.processor.k8sattributes/
- OpenTelemetry Kubernetes semantic conventions:
  https://opentelemetry.io/docs/specs/semconv/resource/k8s/
