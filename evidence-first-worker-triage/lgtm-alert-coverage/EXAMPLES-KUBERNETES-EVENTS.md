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
  job_name   = "kubernetes-events"
  log_format = "json"
  forward_to = [loki.process.parse_event.receiver]
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
  forward_to = [/* your loki.write or downstream receiver */]
}
~~~

`forward_to` is required on both components — without it the config fails to
load. The `involvedObject.*` JSON paths are not a guess: the pilot's
red-cluster config extracts `involvedObject.namespace` and `involvedObject.name`
this way and is recorded as proven (`EVENT_EVIDENCE_PATH_PROVEN`). See
`../next-phase-end-to-end/reference-config/01-alloy.yaml`.

Add static cluster and environment labels. Keep the event JSON body; do not label message, UID, image name or other high-cardinality fields. The collector needs read-only Event API access in its approved scope.

**Label names must be agreed before either path is built on.** The proven
red-cluster config promotes these same fields under *different* label names —
`namespace` and `pod`, and it does not promote `type` at all. This sheet uses
`obj_namespace`/`obj_kind`/`event_type`. Both are defensible; they cannot both
be live. Every LogQL query below selects `event_type="Warning"`, so if the
deployed pipeline does not promote `type` to a label, every rule here returns
nothing and reports as a healthy cluster. Pick one label model, apply it to the
alerting and triage pipelines together, and confirm the promoted label set in
Explore before deploying any rule — grouping by a label that was extracted but
never promoted silently returns nothing.

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
# ErrImagePull and ImagePullBackOff are container *status* reasons, not Event
# reasons — selecting them here matches nothing and the rule never fires. The
# kubelet reports image-pull failure as Event reason=Failed ("Failed to pull
# image ...") and reason=BackOff ("Back-off pulling image ..."). The line filter
# is mandatory: Failed is also emitted for container start, probe and mount
# failures.
sum by (cluster, obj_namespace) (
  count_over_time({cluster="{{CLUSTER_NAME}}", event_type="Warning",
    event_reason=~"Failed|BackOff"}
    |~ "(?i)(pull(ing)? image|ErrImagePull|ImagePullBackOff)" [10m])
) > 0

# Candidate: VolumeAttachFailures
sum by (cluster, obj_namespace) (
  count_over_time({cluster="{{CLUSTER_NAME}}", event_type="Warning",
    event_reason="FailedAttachVolume"}[10m])
) > 0

# Candidate: VolumeMountFailures — must NOT use > 0.
# FailedMount is emitted routinely during healthy pod startup whenever CSI
# attach exceeds the mount timeout, and on every node reboot and reschedule.
# At > 0 this pages constantly, and an alert that always fires is ignored.
# Tune the threshold to observed normal volume and attach a `for:`.
sum by (cluster, obj_namespace) (
  count_over_time({cluster="{{CLUSTER_NAME}}", event_type="Warning",
    event_reason="FailedMount"}[10m])
) > {{FAILED_MOUNT_THRESHOLD}}

# Candidate: NetworkSandboxFailures
sum by (cluster, obj_namespace) (
  count_over_time({cluster="{{CLUSTER_NAME}}", event_type="Warning",
    event_reason=~"FailedCreatePodSandBox|NetworkNotReady"}[10m])
) > 0
~~~

This sheet is the single owner of the `PodFailedScheduling` and `PodEvicted`
rule definitions. The node auto-provisioning sheet interprets those same events
for scheduling and capacity, but must not redefine them — one objective, one
rule, one page.

Use a named critical-workload objective as well as a fleet summary. An Evicted event is a symptom, not proof that memory pressure was its cause; link node conditions, requests/limits and the event message for triage.

Every rule here fails open: `count_over_time(...) > 0` cannot distinguish "no
Warning events occurred" from "Alloy stopped shipping events". Silence is the
healthy state and also the broken state. Give the event pipeline its own
liveness objective — a scrape/health rule on the collector, or an expected-volume
floor on total events per cluster — so a dead collector pages rather than
presenting as a quiet cluster.

## Alert/triage contract

Retain cluster, object namespace, object kind and event reason on the alert. Use Warning events as alert input; Normal events are context and must not page. Dedupe/group alert notifications by event class and target, but do not suppress the first evidence record.

## Proof

- Trigger a controlled Warning event and verify fields/labels in Loki.
- Run the exact LogQL in Explore and prove Loki Ruler plus Alertmanager routing.
- Independently verify the corresponding Alloy -> Vector -> Kafka -> Argo triage record.
- Test grouping/rate limiting and confirm Normal events do not page.
- Record all four baseline gates in the coverage inventory.

See [Node auto-provisioning, scheduling and eviction](EXAMPLES-NODE-AUTOPROVISIONING.md) for the scheduling-specific event contract.
