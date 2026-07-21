# Alloy k8s-event raw capture — container field investigation

**Date:** 2026-07-21 · **Cluster:** `red` · **Method:** `vector tap alloy_otlp.logs`
(the OTLP record exactly as Vector receives it from Alloy, before any Vector VRL).

## Question

Did the Alloy Kubernetes-event path ever produce a non-empty `container` field?
The bundle's `PAYLOAD-FIELD-PROOF.md` line 27 shows a `kubernetes-event` record
carrying `"container":"checkout-api"` and calls container a "dropped" field. Was
that ever real Alloy output, or a fixture?

## Answer: it was a fixture. Alloy never emitted container on the event path.

A live `BackOff` event captured immediately as Vector receives it:

```json
{
  "attributes": {
    "cluster": "red", "environment": "lab", "event_reason": "BackOff",
    "instance": "loki.source.kubernetes_events.events", "job": "kubernetes-events",
    "loki.attribute.labels": "job,instance,namespace,event_reason,environment,source_type,cluster",
    "namespace": "agentic-triage-proof", "source_type": "kubernetes-event"
  },
  "message": "{\"count\":1,\"eventRV\":\"106146677\",\"kind\":\"Pod\",\"msg\":\"Back-off restarting failed container tap3-marker-container in pod reason-check-tap3-0721_agentic-triage-proof(d0e1add3-1a14-47f4-865c-b8fde04fb595)\",\"name\":\"reason-check-tap3-0721\",\"objectAPIversion\":\"v1\",\"objectRV\":\"106146585\",\"reason\":\"BackOff\",\"reportingcontroller\":\"kubelet\",\"reportinginstance\":\"homelab-control-plane\",\"sourcecomponent\":\"kubelet\",\"sourcehost\":\"homelab-control-plane\",\"type\":\"Warning\"}"
}
```

Structured findings from that record:

| Check | Result |
|---|---|
| OTLP attribute keys | `cluster, environment, event_reason, instance, job, namespace, source_type` |
| Event body keys (`message`, parsed) | `count, eventRV, kind, msg, name, objectAPIversion, objectRV, reason, reportingcontroller, reportinginstance, sourcecomponent, sourcehost, type` |
| `involvedObject` object present? | **No** |
| `involvedObject.fieldPath` present anywhere? | **No** |
| top-level `container` field present? | **No** |
| container name present in `msg` text? | **Yes** (`...failed container tap3-marker-container in pod...`) |

## Why the previous approaches could not work

`loki.source.kubernetes_events` with `log_format = "json"` emits a **flattened**
event, not the raw Kubernetes Event object. Consequences:

- `pod = "involvedObject.name"` and `namespace = "involvedObject.namespace"` in
  `01-alloy.yaml` extract **nothing** — there is no `involvedObject`. `namespace`
  is labelled anyway by the events source's own namespace watch; `pod` is the
  top-level `name` key. `event_reason = "reason"` works because `reason` is a
  real top-level key.
- The `involvedObject.fieldPath → spec.containers{<name>}` regex approach (the
  earlier uncommitted patch) targets a field that does not exist here, so it
  always produced empty. Reverted.

## The fix that works (proven)

Container name is only in `msg`. Parse it in Vector, mirroring the existing
`.pod = event.name` rescue. Proven live: GitLab ticket **#508** shows
`Container | the-failing-container` on an event-path ticket — the first event
ticket ever to carry a non-empty container. See `02-vector.yaml` `normalize`.

Coverage is best-effort by design: `msg` names the container for crashloop-class
events (`BackOff`, container-kill). Probe failures (`Unhealthy`) and pod-scoped
events (`FailedScheduling`, `Evicted`) do not name a container in `msg`, so those
stay empty — correct, not a defect.
