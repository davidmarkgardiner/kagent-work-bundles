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

## Where to copy each profile

The profile blocks below describe values that must stay aligned in three
places. Do not update only one of them:

1. **Vector decision:** in `config/02-vector.yaml`, edit the
   `transforms.incident_signals.condition` line. Replace the event-reason regex
   with `eventReasons`, and replace the log regex with `logPattern`.
2. **Argo admission:** in `config/03-argo.yaml`, edit the
   `red-event-triage` Sensor filter at `body.reason`. Replace its list with the
   same `eventReasons` list. This is the management-plane backstop.
3. **Worker collection scope:** in `config/01-alloy.yaml`, update both the
   pod-log namespace `regex` and the Kubernetes-events `namespaces` list with
   the approved worker namespaces. Set the worker's `cluster` static label in
   the same file to `{{CLUSTER_NAME}}`.

The profiles below are ready to copy as policy values, but they have **not yet
been live-smoke-tested against GitLab labels**. The bundle has passed Kustomize
rendering and Kubernetes server-side dry-run; run one controlled smoke fixture
after each profile change and check both the ticket labels and the ticket count.

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
