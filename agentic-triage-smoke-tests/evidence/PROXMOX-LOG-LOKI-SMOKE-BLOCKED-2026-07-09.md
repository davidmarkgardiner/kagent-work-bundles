# Proxmox Loki Log Smoke Blocked - 2026-07-09

## Verdict

```text
source_type=logs
status=not_proven
reason=application log marker emitted, but log shipping to Loki did not ingest it during the smoke window
```

## What Was Tested

Created a short-lived smoke pod:

```text
namespace={{LOG_SMOKE_NAMESPACE}}
pod=log-errorburst-smoke
run_id=loki-log-20260709
```

The pod emitted five log lines:

```text
AGENTIC_TRIAGE_SMOKE_ERROR run_id=loki-log-20260709 smoke=log-errorburst failure=synthetic_error_burst seq=1
...
AGENTIC_TRIAGE_SMOKE_ERROR run_id=loki-log-20260709 smoke=log-errorburst failure=synthetic_error_burst seq=5
```

`kubectl logs` confirmed the application log marker existed.

## Loki Query Attempt

Queried Loki repeatedly with:

```logql
{namespace="{{LOG_SMOKE_NAMESPACE}}", pod="log-errorburst-smoke"}
|= "AGENTIC_TRIAGE_SMOKE_ERROR"
|= "loki-log-20260709"
```

Result:

```text
attempt=1 count=0
...
attempt=12 count=0
```

Loki label check showed `{{EVENT_SMOKE_NAMESPACE}}` existed, but
`{{LOG_SMOKE_NAMESPACE}}` did not appear under namespace labels during the
test window.

## Blocking Evidence

Promtail was Ready, but its recent logs showed push failures to the Loki
gateway:

```text
error sending batch, will retry ... context deadline exceeded
error sending batch, will retry ... 502 Bad Gateway
```

Because the log marker did not reach Loki, no Grafana Loki log alert was
created for this run and no log-source smart-triage workflow was claimed.

## Cleanup

Deleted the smoke pod and namespace:

```text
kubectl delete namespace {{LOG_SMOKE_NAMESPACE}}
```

## Required Fix

Before marking logs as proven:

- fix Promtail or replace it with an Alloy application-log pipeline;
- prove the emitted marker is queryable in Loki;
- create a Grafana LogQL alert over that marker;
- verify the alert posts to the smart-triage webhook;
- capture the resulting workflow and lifecycle score.
