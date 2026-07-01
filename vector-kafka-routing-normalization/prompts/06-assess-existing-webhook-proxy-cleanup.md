# Prompt 06: Assess Existing Webhook/Proxy Chain And Clean Cutover

The work environment may already have a working alert path that looks like this:

```text
Alertmanager or Grafana contact point
  -> Kenawa webhook / HTTP webhook POST
  -> Vector HTTP receiver
  -> Grafana webhook Kafka proxy service
  -> Kafka topic
  -> Argo EventSource
  -> Argo Sensor
  -> Argo Workflow
```

This is now the proven work baseline from the previous test run. This prompt is
not permission to remove anything. Your job is to document the current chain,
preserve it, improve Vector filtering/dedupe/routing around it, prove whether a
cleaner chain can replace it later, and return a safe cutover recommendation.

## Target Cleaner Chains

Prefer this when the source can publish directly to Kafka:

```text
Alertmanager / Grafana
  -> Confluent Kafka raw topic
  -> Vector Kafka source
  -> normalize / filter / dedupe / route
  -> Confluent Kafka normalized topic
  -> Argo EventSource
```

Use this when the source can only send HTTP webhooks:

```text
Alertmanager / Grafana
  -> Vector HTTP receiver
  -> normalize / filter / dedupe / route
  -> Confluent Kafka normalized topic
  -> Argo EventSource
```

Avoid this unless there is a proven blocker:

```text
Alertmanager / Grafana
  -> Kenawa webhook
  -> Vector
  -> webhook-to-Kafka proxy
  -> Argo
```

For the current work run, this avoided path is still the control path because it
has already been proven end to end. Do not remove it until the cleaner path has
passed the same test evidence.

## Authentication Decision

Verify what is supported in the work environment. Do not print secret values.

Preferred:

- OAuth/OIDC for Confluent Cloud if the cluster, identity provider, client
  library, and operations team support it.
- Use `SASL_OAUTHBEARER` only after proving the selected client path supports
  it end to end.

Fallback:

- Confluent Kafka API key and secret using `SASL_SSL` plus `SASL_PLAIN`.
- Treat the API key as the username and the API secret as the password.
- Scope the principal to the smallest required topic permissions.

Webhook-side options:

- Grafana webhook contact points can send HTTP `POST` or `PUT` JSON payloads.
- Confirm whether the current webhook endpoint uses Basic Auth, an
  `Authorization` header, HMAC signing, mTLS, or network policy only.
- If Vector receives webhook traffic directly, document exactly how the
  receiver is protected.

Vector-side options:

- For standard Kafka API key/secret auth, use Vector Kafka SASL settings with
  `PLAIN`, TLS enabled, and secret-backed username/password values.
- For OAuth/OIDC, verify the installed Vector image and librdkafka support.
  If the required settings are not exposed through Vector's normal `sasl.*`
  block, test `librdkafka_options` in a temporary environment before proposing
  production use.

Primary docs to check during the work-side run:

- Confluent Cloud client auth:
  `https://docs.confluent.io/cloud/current/client-apps/config-client.html`
- Confluent Cloud OAuth/OIDC:
  `https://docs.confluent.io/cloud/current/security/authenticate/workload-identities/identity-providers/oauth/overview.html`
- Vector Kafka sink:
  `https://vector.dev/docs/reference/configuration/sinks/kafka/`
- Grafana webhook contact point:
  `https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/`

Home-lab reference YAML to compare against:

- `payload/observability-vector/homelab/vector-http-receiver-to-kafka.yaml`
- `payload/observability-vector/homelab/vector-kafka-raw-to-normalized.yaml`

## Work To Perform

1. Map the currently working path from source to Argo.
2. Identify every workload, service, contact point, topic, secret reference,
   and namespace in that path.
3. Capture a sanitized current-state diagram.
4. Confirm the Kenawa webhook endpoint/service and how it is protected.
5. Confirm which component performs normalization today.
6. Confirm which component publishes to Kafka today.
7. Confirm whether the proxy service is only translating HTTP to Kafka
   or whether it has any extra required logic.
8. Confirm Vector performs or will perform filtering, dedupe, route enrichment,
   and actionable-topic cleanup before Argo sees the event.
9. Test the cleaner direct Vector-to-Kafka path in parallel using safe topics.
10. If available, test a Kafka-first source path in parallel using safe topics.
11. Compare both paths with the same safe test alert payload.
12. Confirm Argo receives the normalized event from the cleaner path.
13. Capture a rollback plan before proposing any removal.

## Home-Lab Demonstration

Create a sanitized demonstration plan that can be reproduced outside work:

```text
compatibility demo:
  webhook sender -> Vector HTTP receiver -> local webhook-to-Kafka proxy stub
  -> Kafka/Confluent-compatible topic -> Argo-style consumer

clean demo:
  webhook sender -> Vector HTTP receiver -> Kafka topic -> Argo-style consumer
```

The demo should show:

- same input alert
- same normalized envelope
- fewer components in the clean path
- which failure modes disappear when the proxy is removed
- which failure modes remain in Vector, Kafka, and Argo

## Return

```text
CURRENT_CHAIN: documented | blocked
KENAWA_WEBHOOK: verified | blocked
CLEAN_CHAIN: proposed | verified | blocked
AUTH_OPTIONS: verified | blocked
OAUTH_DECISION: supported | blocked | not_available
API_KEY_FALLBACK: documented | blocked
VECTOR_DIRECT_KAFKA: verified | blocked
KAFKA_FIRST_SOURCE: verified | blocked | not_applicable
PROXY_SERVICE_ROLE: translation_only | extra_logic | unknown
BASELINE_PRESERVED: yes | no
PROXY_REMOVAL_DECISION: remove | keep | blocked
ROLLBACK_PLAN: captured | blocked
HOME_LAB_REPLICATION: planned | implemented | not_requested
EVIDENCE:
RISKS:
NEXT_ACTION:
```

Hard stop: do not delete, scale down, or disable the working webhook/proxy path
until the cleaner path has produced a normalized event, Argo has consumed it,
and rollback is documented.
