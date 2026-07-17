# LGTM Kubernetes Event Alert Examples

## Purpose

This sheet shows how Kubernetes Warning events can be collected by Alloy, queried in Loki with LogQL, and evaluated by Loki Ruler and Alertmanager. It complements the independent evidence-first path:

~~~text
Alloy events -> Loki -> Loki Ruler -> Alertmanager -> human page
Alloy events -> Vector -> Kafka -> Argo -> read-only triage
~~~

The alert can identify cluster, namespace, object and event class even if Alertmanager does not forward the full reason/message. Loki and the Vector/Kafka/Argo record retain the bounded event detail for investigation.

## Required Alloy event shape

The existing bundle already uses this pattern:

~~~alloy
loki.source.kubernetes_events "events" {
  namespaces = [] // or an approved explicit namespace list
  log_format = "json"
}
loki.process "parse_event" {
  stage.json {
    expressions = {
      event_type = "type",
      event_reason = "reason",
      obj_kind = "involvedObject.kind",
      obj_namespace = "involvedObject.namespace",
      obj_name = "involvedObject.name",
    }
  }
  stage.labels {
    values = { event_type = "", event_reason = "", obj_kind = "", obj_namespace = "" }
  }
}
~~~

Add static cluster and environment labels. Keep the event JSON body; do not label message, UID, image name or other high-cardinality fields. The collector needs read-only Event API access in its approved scope.

## Candidate LogQL alerts

~~~logql
# Candidate: PodFailedScheduling
sum by (cluster, obj_namespace, obj_kind) (
  count_over_time({cluster="{{CLUSTER_NAME}}", event_type="Warning",
    event_reason="FailedScheduling"}[10m])
) > {{FAILED_SCHEDULING_THRESHOLD}}

# Candidate: PodEvicted
sum by (cluster, obj_namespace) (
  count_over_time({cluster="{{CLUSTER_NAME}}", event_type="Warning",
    event_reason="Evicted"}[5m])
) > 0

# Candidate: ImagePullFailures
sum by (cluster, obj_namespace) (
  count_over_time({cluster="{{CLUSTER_NAME}}", event_type="Warning",
    event_reason=~"ErrImagePull|ImagePullBackOff"}[10m])
) > 0

# Candidate: VolumeMountOrAttachFailures
sum by (cluster, obj_namespace) (
  count_over_time({cluster="{{CLUSTER_NAME}}", event_type="Warning",
    event_reason=~"FailedMount|FailedAttachVolume"}[10m])
) > 0

# Candidate: NetworkSandboxFailures
sum by (cluster, obj_namespace) (
  count_over_time({cluster="{{CLUSTER_NAME}}", event_type="Warning",
    event_reason=~"FailedCreatePodSandBox|NetworkNotReady"}[10m])
) > 0
~~~

Use a named critical-workload objective as well as a fleet summary. An Evicted event is a symptom, not proof that memory pressure was its cause; link node conditions, requests/limits and the event message for triage.

## Alert/triage contract

Retain cluster, object namespace, object kind and event reason on the alert. Use Warning events as alert input; Normal events are context and must not page. Dedupe/group alert notifications by event class and target, but do not suppress the first evidence record.

## Proof

- Trigger a controlled Warning event and verify fields/labels in Loki.
- Run the exact LogQL in Explore and prove Loki Ruler plus Alertmanager routing.
- Independently verify the corresponding Alloy -> Vector -> Kafka -> Argo triage record.
- Test grouping/rate limiting and confirm Normal events do not page.
- Record all four baseline gates in the coverage inventory.

See [Node auto-provisioning, scheduling and eviction](LGTM-NODE-AUTOPROVISIONING-SCHEDULING-EXAMPLES.md) for the scheduling-specific event contract.
