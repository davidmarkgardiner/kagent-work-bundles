# Kafka Payload Replay Sheet — prove Argo can parse the incident now

**Purpose:** validate the exact incident contract while Kafka access is pending,
then replay the *same JSON* through Kafka when the producer ACL arrives. This
does not change the alerting path, invoke remediation, or require live worker
cluster access.

## The contract to test

The Kafka value is one JSON object. Argo Events exposes it as `body`; both
Sensors filter on `body.schema_version`, `body.automation_allowed`, and
`body.signal_kind`, then copy `body` verbatim to the Workflow parameter named
`incident`. Do **not** wrap the JSON in `{ "body": ... }`, quote it as a JSON
string, or send the raw Alloy record — any of those tests a different shape.

Use a fresh `observed_timestamp` whenever testing the deployed workflow: the
current validation template quarantines records more than 24 hours old.

```json
{
  "schema_version": "observability.triage.v2",
  "cluster": "{{WORKER_CLUSTER_CONTEXT}}",
  "namespace": "payments",
  "node": "{{WORKER_NODE}}",
  "pod": "checkout-api-payload-replay",
  "container": "checkout-api",
  "service": "checkout-api",
  "reason": "BackOff",
  "severity": "warning",
  "signal_kind": "event",
  "object_kind": "Pod",
  "event_count": 3,
  "reporting_component": "kubelet",
  "source_type": "opentelemetry",
  "observed_timestamp": "{{CURRENT_UTC_RFC3339}}",
  "dedupe_key": "{{SHA256_OF_CLUSTER_NAMESPACE_POD}}",
  "delivery_key": "{{SHA256_OF_DEDUPE_KEY_AND_REASON}}",
  "automation_allowed": false,
  "evidence": {
    "event_summary": "BackOff",
    "representative_log_lines": "Back-off restarting failed container checkout-api"
  }
}
```

Use the `log` variant only to test the log Sensor: set `signal_kind` to `log`,
`reason` to `log-error-signature`, `severity` to `error` or `critical`, and use
a redacted log line. Keep `schema_version` and `automation_allowed: false`.

## Route A — prove Argo parsing before Kafka access

This bypasses Kafka deliberately and submits the exact `incident` value that a
Sensor would put into the `red-agentic-triage` WorkflowTemplate. It proves the
Workflow parameter accepts valid JSON and exercises schema/DLQ validation. Do
this in the isolated proof namespace/cluster only; it can continue to the
configured read-only agent and ticket backend if those are live.

1. Save the JSON above as a **sanitized** `incident.json`, replacing every
   placeholder and generating `dedupe_key` / `delivery_key` with the same
   Vector rules. Keep the resulting file out of Git if it contains real names.
2. In the isolated proof environment, submit it as the workflow parameter. The
   equivalent Argo CLI shape is below; obtain approval first if this environment
   has the real ticket backend enabled, because a valid replay can create a
   triage ticket.

   ```bash
   argo submit -n argo-events --from workflowtemplate/red-agentic-triage \
     -p "incident=$(jq -c . incident.json)"
   ```

   An automation path may instead construct a `Workflow` that references
   `red-agentic-triage` and sets `spec.arguments.parameters[name=incident]` to
   this compact JSON text.
3. Inspect the submitted Workflow and verify its resolved `incident` parameter
   is byte-for-byte equivalent after JSON canonicalisation:

   ```bash
   jq -S . incident.json > /tmp/expected.json
   # Extract the resolved workflow parameter using the local Argo/kubectl method.
   # jq -S . /tmp/actual-incident.json > /tmp/actual.json
   diff -u /tmp/expected.json /tmp/actual.json
   ```

4. Record the result: accepted path must reach `validate-schema` with
   `valid=true`; malformed, unexpected-cluster, unsupported-schema, and
   stale-timestamp controls must be quarantined, not triaged.

## Route B — replay the identical value through Kafka after access arrives

First confirm the topic, bootstrap endpoint, TLS/SASL settings, and producer
identity from the approved Kafka onboarding. Then publish **the contents of
`incident.json` as the message value**, with no schema registry wrapper unless
the topic contract explicitly requires one.

```bash
# Example only: use the approved client and secret injection; never paste
# credentials or broker addresses into this sheet, Git, or workflow logs.
kcat -P -b "{{KAFKA_BROKER}}" -t "{{TRIAGE_TOPIC}}" \
  -k "payload-replay-{{UNIQUE_ID}}" < incident.json
```

Consume the same key from a separate temporary, approved consumer group and
canonicalise it with `jq -S` before comparing it with `/tmp/expected.json`.
Then verify exactly one matching Sensor/Workflow appears. Use a new unique key
and a new pod value for each replay; the 24-hour claim and delivery suppression
can otherwise make a correct second test look silent.

## Evidence and acceptance

Attach one small sanitized record to `../evidence/` with: producer JSON hash,
Kafka-consumed JSON hash, resolved Workflow-parameter JSON hash, workflow name,
Sensor route (`log` or `event`), and accepted/quarantined outcome. Hashes must
match after canonicalisation; timestamps may differ only if the test explicitly
regenerates the entire record.

Pass when all are true:

```text
ARGO_DIRECT_CONTRACT_PARSE: yes
KAFKA_VALUE_EQUALS_PRODUCED_ENVELOPE: yes
SENSOR_FILTER_ROUTE_PROVEN: yes
WORKFLOW_INCIDENT_EQUALS_KAFKA_BODY: yes
VALID_RECORD_ACCEPTED: yes
INVALID_CONTROLS_QUARANTINED: yes
NO_SECRET_OR_RAW_UNREDACTED_EVIDENCE: yes
```

**Current config anchors:** `reference-config/03-argo.yaml` (`body` filters and
`dataKey: body` → `incident`); `reference-config/02-vector.yaml` (allow-listed
`observability.triage.v2` envelope); `PAYLOAD-FIELD-PROOF.md` (field-level
consumer and redaction evidence). The canonical source remains Vector: do not
add fields in the replay fixture that Vector would drop.
