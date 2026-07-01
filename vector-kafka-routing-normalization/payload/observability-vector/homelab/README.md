# Vector Home-Lab Reference

This folder gives the work agent concrete YAML for comparing the two cleaner
paths without copying the current webhook-to-Kafka proxy pattern.

The goal is to prove which components can be removed at work:

1. HTTP receiver option:

   ```text
   Grafana / Alertmanager webhook
     -> Vector HTTP receiver
     -> normalized Kafka topic
     -> Argo EventSource
   ```

2. Kafka-first option:

   ```text
   Grafana / Alertmanager Kafka contact point
     -> raw Kafka topic
     -> Vector Kafka source
     -> normalized Kafka topic
     -> Argo EventSource
   ```

## Files

| File | Purpose |
|---|---|
| `vector-http-receiver-to-kafka.yaml` | Reference Kubernetes YAML for direct webhook-to-Vector ingress. |
| `vector-kafka-raw-to-normalized.yaml` | Reference Kubernetes YAML for raw-topic ingestion and normalized-topic output. |

## Required Secrets

Create these in the target namespace before applying either YAML. Use real
values only in the private/home-lab cluster, never in this repo.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: confluent-credentials
  namespace: argo-events
type: Opaque
stringData:
  bootstrap: "{{CONFLUENT_BOOTSTRAP_SERVER}}"
  key: "{{CONFLUENT_KAFKA_API_KEY}}"
  secret: "{{CONFLUENT_KAFKA_API_SECRET}}"
```

For Confluent API-key auth, Vector uses:

```text
security.protocol=sasl_ssl
sasl.mechanism=PLAIN
sasl.username=${CONFLUENT_SA_KEY}
sasl.password=${CONFLUENT_SA_SECRET}
```

OAuth/OIDC is preferred where available, but only use it after proving the
installed Vector image and librdkafka options support the chosen
`SASL_OAUTHBEARER` configuration end to end.

## Option 1: HTTP Receiver

Apply the reference YAML:

```bash
kubectl -n argo-events apply -f observability/vector/homelab/vector-http-receiver-to-kafka.yaml
kubectl -n argo-events rollout status deploy/vector-alert-webhook-normalizer
```

Port-forward for a simple home-lab test:

```bash
kubectl -n argo-events port-forward svc/vector-alert-webhook-normalizer 8080:8080
```

Send a synthetic alert:

```bash
curl -sS -X POST http://127.0.0.1:8080/alerts \
  -H 'content-type: application/json' \
  --data @observability/vector/examples/alertmanager-raw.json
```

Expected result:

- Vector receives the webhook directly.
- Vector normalizes, filters, and dedupes the event.
- Vector writes to `alertmanager-events-triage`.
- Argo can consume the normalized topic.

This removes the extra webhook-to-Kafka proxy if direct Kafka source publishing
is not available.

Verified home-lab result:

```text
Raw Alertmanager webhook
  -> vector-alert-webhook-normalizer /alerts
  -> alertmanager-events-triage
  -> vector-alertmanager-triage-kafka EventSource
  -> vector-alertmanager-triage Sensor
  -> alert-triage-vector-rpwvn
```

The direct HTTP receiver returned HTTP `200`, Argo consumed the normalized Kafka
record, and the workflow completed successfully.

Direct receiver constraints:

- Protect the Vector HTTP endpoint before using it outside a private lab.
- Prefer cluster-internal networking, NetworkPolicy, TLS, and an explicit auth
  mechanism in front of Vector.
- Alertmanager delivery now depends on Vector being reachable at receive time.
- There is no raw Kafka replay point before Vector in this pattern.
- Vector still needs valid Confluent Kafka produce credentials for
  `alertmanager-events-triage`.

## Option 2: Kafka-First

Apply the reference YAML:

```bash
kubectl -n argo-events apply -f observability/vector/homelab/vector-kafka-raw-to-normalized.yaml
kubectl -n argo-events rollout status deploy/vector-alert-kafka-normalizer
```

Produce a synthetic raw event using the approved Kafka client for the lab:

```bash
confluent kafka topic produce alertmanager-events \
  --parse-key \
  --delimiter ':' < /tmp/vector-routing-test-record.jsonl
```

Expected result:

- Grafana or Alertmanager writes to `alertmanager-events`.
- Vector consumes from `alertmanager-events`.
- Vector writes to `alertmanager-events-triage`.
- Argo consumes only the normalized topic.

This is the preferred clean design because Kafka buffers raw events if Vector is
down and preserves an audit/replay topic.

Verified home-lab result:

```text
Alertmanager-style payload
  -> alertmanager-confluent-bridge /alertmanager
  -> alertmanager-events
  -> vector-alertmanager-normalizer
  -> alertmanager-events-triage
  -> vector-alertmanager-triage-kafka EventSource
  -> vector-alertmanager-triage Sensor
  -> alert-triage-vector-jnpz9
```

The bridge returned HTTP `202`, Vector consumed the raw Kafka topic and produced
the normalized topic, Argo consumed the normalized record, and the workflow
completed successfully.

Kafka-first constraints:

- The producer into `alertmanager-events` needs approved Kafka or bridge auth.
- Vector needs Confluent Kafka consume credentials for `alertmanager-events`.
- Vector needs Confluent Kafka produce credentials for
  `alertmanager-events-triage`.
- Argo Events needs Confluent Kafka consume credentials for
  `alertmanager-events-triage`.
- If Kafka credentials are changed in Kubernetes Secrets, restart Vector pods so
  environment variables refresh.

## Work-Agent Decision

Use this comparison:

| Question | Prefer Kafka-first | Prefer HTTP receiver |
|---|---|---|
| Can Grafana/Alertmanager publish directly to Kafka with approved auth? | Yes | No |
| Do we need raw replay before Vector? | Yes | No or lower priority |
| Is the only current blocker the proxy translating webhook to Kafka? | Maybe | Yes |
| Can Vector publish directly to Confluent Kafka? | Required | Required |

Do not remove the work proxy path until the chosen clean path has produced a
normalized record, Argo has consumed it, and rollback is documented.
