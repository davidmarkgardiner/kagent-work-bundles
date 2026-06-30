# Vector Kafka Routing Normalization

## TL;DR

This bundle hands a work-side agent the Vector routing rollout: raw Kafka events
are normalized, filtered, deduped, routed, and then delivered to Argo from a
normalized topic.

The public spike proved the pattern, but this is **not production-ready until
the work environment closes the safety gaps** listed in the checklist.

For the intended work run, assume Vector is already running, Confluent
connectivity is already configured, and the Manager/Grafana contact point
already exists. The work agent must discover and confirm those prerequisites
before creating a new Vector instance or applying manifests.

If the work environment already has a working webhook/proxy path, do not break
it. First document it, then prove a cleaner path in parallel:

```text
current possible path:
Alertmanager/Grafana -> webhook -> Vector -> webhook-to-Kafka proxy
  -> Confluent REST -> Kafka -> Argo

clean target path:
Alertmanager/Grafana -> Kafka raw topic -> Vector -> Kafka normalized topic
  -> Argo

clean HTTP fallback:
Alertmanager/Grafana -> Vector HTTP receiver -> Kafka normalized topic -> Argo
```

The design decision is to remove avoidable webhook/proxy services only after the
clean path is verified and rollback is documented.

## What This Feature Does

- Keeps raw Kafka topics for audit and replay.
- Runs Vector as a Kafka consumer and Kafka producer.
- Normalizes Alertmanager, Grafana-native, and Alloy/Kubernetes event shapes.
- Adds route fields such as `target_agent`, `route_key`, `routing_reason`,
  `automation_allowed`, `incident_candidate`, and `dedupe_key`.
- Filters resolved alerts before Argo workflow creation.
- Suppresses duplicates with Vector's count-bounded dedupe cache.
- Uses Argo Events as the Kubernetes-native Workflow trigger boundary.
- Provides a synthetic route-verification workflow that does not call GitLab,
  Teams, Mattermost, ServiceNow, or a real agent.

## Source Artifacts

The implementation reference lives in:

```text
../../observability/vector/
```

Key files:

```text
../../observability/vector/README.md
../../observability/vector/manifests/
../../observability/vector/examples/
../../observability/vector/tests/
../../observability/vector/handoff/
```

## Evidence From Public Spike

Verified in the public/sanitized environment:

```text
alertmanager-events
  -> vector-alertmanager-normalizer
  -> alertmanager-events-triage
  -> vector-alertmanager-triage-kafka EventSource
  -> Argo Sensor
  -> Argo Workflow
```

Also verified:

- app route to `aks-sre-triage-agent`
- platform route to `platform-ops-agent`
- security route to `security-hardening-agent`
- unknown-owner fallback route to `sre-triage-agent`
- three duplicate raw records resulted in one normalized route workflow

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Give `WORK-AGENT-START-PROMPT.md` to the work-side agent.
3. The work agent must run `prompts/01-preflight-env-tools.md` before live
   changes. This must confirm existing Vector image/namespace/config, Confluent
   secret references, Grafana MCP access, and the Manager/Grafana contact point.
4. Use `PREREQS-CHECKLIST.md` as the live building-block inventory before
   creating the new Vector instance/config.
5. Follow the prompts in order.
6. If a webhook/proxy/Confluent REST chain exists, run
   `prompts/06-assess-existing-webhook-proxy-cleanup.md`.
7. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Auth Decision

Preferred: OAuth/OIDC for Confluent Cloud where the work cluster, identity
provider, client library, Vector image, and operations model support it.

Fallback: Confluent Kafka API key/secret using `SASL_SSL` plus `SASL_PLAIN`.
The API key is the SASL username and the API secret is the SASL password. Store
these only in approved secret stores and grant least-privilege topic access.

For Grafana webhook contact points, verify whether Basic Auth, an
`Authorization` header, HMAC signing, mTLS, or network policy is used. If Vector
receives webhooks directly, document and test the receiver protection before
using it outside a test environment.

Reference these primary docs during the work-side check:

- Confluent Cloud client auth:
  `https://docs.confluent.io/cloud/current/client-apps/config-client.html`
- Confluent Cloud OAuth/OIDC:
  `https://docs.confluent.io/cloud/current/security/authenticate/workload-identities/identity-providers/oauth/overview.html`
- Vector Kafka sink:
  `https://vector.dev/docs/reference/configuration/sinks/kafka/`
- Grafana webhook contact point:
  `https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/`

## Definition Of Done

The bundle is complete only when the work environment has proven:

- raw events are retained in raw Kafka topics
- Vector emits normalized `observability.triage.v1` records
- Grafana MCP can fire a safe test alert through the existing Manager/Grafana
  Kafka contact point
- the normalized event triggers the production triage workflow
- the kit/kagent analysis path runs
- a GitLab issue/ticket is created as evidence of the full workflow
- route fields are present and correct
- duplicates are suppressed before Argo workflow creation
- the production triage workflow consumes the full normalized envelope
- write-capable automation is default-deny and gated in Argo
- Kafka credentials are least-privilege
- metrics or evidence exist for route counts, suppression, workflow outcomes,
  MTTA, MTTR, and escalation/deflection
- existing webhook/proxy components are documented and either retained with a
  reason or replaced by a cleaner verified path with rollback
