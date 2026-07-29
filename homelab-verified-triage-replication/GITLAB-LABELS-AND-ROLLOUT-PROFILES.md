# Labels and rollout profiles

Create project labels once, then the workflow attaches their names. Suggested
colours: `severity::critical` red, `severity::error` orange,
`severity::warning` yellow, `signal-log` blue, `signal-event` purple,
`triage::automated` grey, and `triage::agent-unavailable` dark red.

New tickets carry `triage::automated`, `source::alloy-vector-kafka`,
`route::non-lgtm`, a signal label, severity, `cluster::...`, `namespace::...`,
and the fingerprint. A later correlated signal adds `signal-log` or
`signal-event`; both remain visible.

## Three rollout policies

Each worker supplies `{{CLUSTER_NAME}}` and an explicit list of
`{{NAMESPACE_NAME}}` values. The management side must allow exactly those
cluster/namespace pairs; never accept a wildcard identity from worker payloads.
Use per-cluster credentials or mTLS before accepting many workers on shared
OTLP ingress.

```yaml
# critical-only.yaml — start here
cluster: "{{CLUSTER_NAME}}"
namespaces: ["{{NAMESPACE_NAME}}"]
logPattern: '(?i)(fatal|panic|critical|out of memory|segfault)'
eventReasons: [OOMKilled, OOMKilling, FailedScheduling, Evicted, NodeNotReady, NetworkNotReady, FailedCreatePodSandBox]
```

```yaml
# priority.yaml — add actionable application errors
cluster: "{{CLUSTER_NAME}}"
namespaces: ["{{NAMESPACE_NAME}}"]
logPattern: '(?i)(error|exception|fatal|panic|failed|timeout|unavailable|denied|forbidden|out of memory)'
eventReasons: [OOMKilled, FailedScheduling, Evicted, NodeNotReady, NetworkNotReady, FailedMount, FailedAttachVolume, ErrImagePull, ImagePullBackOff, Unhealthy]
```

```yaml
# broad-warning-review.yaml — only after volume review
cluster: "{{CLUSTER_NAME}}"
namespaces: ["{{NAMESPACE_NAME}}"]
logPattern: '(?i)(warn|warning|error|exception|fatal|panic|failed|timeout|unavailable|denied|forbidden|out of memory)'
eventReasons: [BackOff, Failed, FailedScheduling, OOMKilled, OOMKilling, Unhealthy, Evicted, FailedMount, FailedAttachVolume, FailedCreatePodSandBox, NetworkNotReady, SpotEviction, ErrImagePull, ImagePullBackOff, NodeNotReady, Preempted, ProbeWarning, FailedSync, FailedKillPod, FailedCreate]
```
