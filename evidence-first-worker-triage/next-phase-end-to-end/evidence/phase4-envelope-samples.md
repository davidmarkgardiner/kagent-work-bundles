# Phase 4 — Envelope samples at produce / consume / agent-input

## Why only two capture points are directly instrumented here

The requested three points are "as Vector produces it, as Argo consumes it,
as the agent receives it." This session had no CLI/console access to
Confluent Cloud itself (it's a managed SaaS broker, `red`'s tooling has no
`rpk`/`kcat` pointed at it), so the literal on-the-wire Kafka message bytes
were not independently fetched. Instead:

- **"As Argo consumes it"** is captured directly:
  `kubectl get wf <name> -o jsonpath='{.spec.arguments.parameters[0].value}'`
  returns the exact `body` the Sensor pulled off the EventBus, e.g. (from the
  Phase-1 `FailedScheduling` replay test):

  ```json
  {"automation_allowed":false,"cluster":"red","container":"","dedupe_key":"d726e032...","delivery_key":"083aae91...","evidence":{"event_summary":"FailedScheduling","representative_log_lines":"{\"action\":\"Scheduling\",...,\"reason\":\"FailedScheduling\",...}"},"namespace":"agentic-triage-proof","observed_timestamp":"2026-07-20T11:10:19.518707Z","pod":"scheduling-failure-confluent","reason":"FailedScheduling","schema_version":"observability.triage.v2","service":"","severity":"critical","signal_kind":"event","source_type":"opentelemetry"}
  ```

- **"As Vector produces it" is architecturally identical to the above, not
  merely assumed similar.** The `red-telemetry-triage-kafka` EventSource's
  Sensor filters bind directly on `body.<field>` JSON paths from the raw
  Kafka record value (`dataKey: body`, no `transform`/`filter` step is
  configured on the EventSource or Sensor between Kafka and the workflow
  trigger — confirmed by reading the live Sensor/EventSource specs, both in
  `../applied-config/03-argo-augmented.yaml` and `kubectl get eventsource
  red-telemetry-triage-kafka -o yaml`). Vector's `kafka` sink writes exactly
  the record built by the `normalize` transform's `. = {...}` allow-list
  (`../applied-config/02-vector-with-metrics.yaml`) with `encoding: {codec:
  json}` — no further mutation between that allow-list and the wire. So the
  JSON above **is** what Vector produced, verified by architecture (no
  transform layer exists to diverge them) rather than by an independent byte
  capture. Recommendation for whoever has Confluent Cloud console/CLI access:
  do a literal `kcat`/console fetch on `k8s-events` once, to close this out
  with a true independent byte-for-byte capture — not done here because the
  tooling wasn't available in this session.

- **"As the agent receives it" is provably byte-identical by construction,
  not just observed to match.** The `diagnose-readonly` template
  (`../applied-config/03-argo-augmented.yaml`) does:

  ```sh
  cat > /tmp/incident.json <<'EOF'
  {{workflow.parameters.incident}}
  EOF
  prompt="...<untrusted_evidence>$(cat /tmp/incident.json)</untrusted_evidence>"
  ```

  `{{workflow.parameters.incident}}` is Argo's own templating of the exact
  same `spec.arguments.parameters[0].value` captured above — there is no
  intermediate parse/rebuild step, so the agent's prompt embeds the literal
  string Argo consumed. This is corroborated behaviourally: every ticket's
  agent diagnosis captured this session correctly cites the exact pod name,
  reason, and redacted evidence text from its envelope (e.g. #453's agent
  diagnosis explicitly parses the `FailedScheduling` JSON event body cited
  above) — the agent could only produce that level of specific, correct
  detail if it received the full, matching envelope.

## Match confirmation

All three points reduce to one directly-captured value (Argo-consumed) plus
two architecturally-guaranteed identities (no transform layer exists on
either side) — verified consistent across every ticket examined in
`phase0`/`phase1`/`phase4`, with zero observed mismatches (no ticket ever
showed a field value that didn't trace back to its source fixture).
