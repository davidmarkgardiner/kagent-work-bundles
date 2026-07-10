# LGTM Integration Problem Statement

## Teams Message

```text
Just to frame the issue as we understand it:

Our agentic triage requirement is not just "send metric alerts to the agent".
We need the triage flow to receive or retrieve useful evidence from the
observability stack: metrics, logs, Kubernetes events, and ideally traces.

The current limitation we are hearing is that the managed LGTM setup is mainly
producing metric-based alerts. Logs may be ingested into Loki for manual
investigation, but they are not currently being used as first-class alert
sources, and Kubernetes events do not appear to be available as alertable
records with useful metadata. We also do not yet have a clear way to
programmatically manage Grafana alert rules/contact points or use API/MCP-style
access to build this out repeatably.

The problem this creates is that the triage agent may receive an alert saying
"pod X is unhealthy" but not the actual reason or evidence, e.g.:
- Kubernetes event reason/message such as FailedScheduling, FailedMount,
  ImagePullBackOff, BackOff, Unhealthy
- application log pattern or sample error line
- timestamp/window for the failure
- Loki/Grafana query or Explore link to fetch the evidence
- labels such as cluster, namespace, workload, pod, source_type,
  reason/error_class

Pod name and cluster name alone are not enough for useful automated triage. The
agent needs either the evidence in the alert payload or enough metadata to query
it from Loki/Grafana.

What we are trying to confirm is whether the managed LGTM service can support
this path:

Application logs -> OTel/Alloy/Promtail -> Loki -> Grafana LogQL alert -> webhook/Alertmanager -> Vector/Kafka -> triage

And:

Kubernetes events -> Alloy or equivalent event collector -> Loki or alertable backend -> Grafana alert -> webhook/Alertmanager -> Vector/Kafka -> triage

We understand OTel/Loki label cardinality constraints, so we are not asking for
every field to become a Loki label. Low-cardinality fields can be labels, and
high-cardinality details can be structured metadata, log body, or alert
annotations. But we do need the data to be queryable, alertable, and routable.

So the key questions are:
1. Can we ingest Kubernetes events into Loki or another alertable backend?
2. Can we create Grafana LogQL alerts over application logs and Kubernetes events?
3. Can those alerts be routed out via webhook/Alertmanager into our existing Vector/Kafka/triage path?
4. Can the alert payload preserve useful labels/annotations: namespace, workload, pod/object, source_type, reason/error_class, message summary, timestamp/window, and ideally a query or Explore link?
5. Can this be managed programmatically or through GitOps/API/Terraform/provisioning rather than manual UI-only setup?

If the answer is yes, then this is likely just configuration work and we can
prove it with smoke tests. If the managed LGTM service cannot support these
capabilities, then it may not be fit for the agentic triage use case and we
need to consider a self-managed Grafana/LGTM path where we control Alloy, Loki,
alert provisioning, notification policies, and API/MCP access.
```

## Short Version

```text
The gap is not alert delivery alone. The gap is source-backed evidence.

Metrics-only alerts can tell the agent that a pod or service is unhealthy, but
they often do not explain why. For agentic triage, the LGTM integration needs
logs and Kubernetes events to be queryable, alertable, and routable into the
same webhook path as metrics.
```
