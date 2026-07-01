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

## Work Baseline To Preserve

The work environment has already proven an end-to-end path. Treat this as the
baseline, not as theory:

```text
Alertmanager / Grafana alert
  -> Kenawa webhook
  -> Vector
  -> webhook-to-Kafka proxy
  -> Kafka
  -> Argo EventSource / Sensor
  -> Argo Workflow
```

The next work-side agent should iterate over this working path. Do not replace,
delete, or bypass the Kenawa webhook, Vector deployment, proxy, Kafka topic, or
Argo trigger until the current chain is documented, rollback is captured, and a
cleaner path has been proven in parallel.

The immediate improvement is signal quality:

- Vector should filter resolved/non-actionable/noisy alerts.
- Vector should suppress duplicates before the actionable Kafka topic.
- Only actionable alerts should reach the Kafka topic consumed by Argo.
- Argo should trust the normalized/actionable topic and avoid carrying the main
  cleanup logic.

If the work environment later wants to simplify the chain, compare the existing
baseline with cleaner candidate paths in parallel:

```text
verified current path:
Alertmanager/Grafana -> Kenawa webhook -> Vector -> webhook-to-Kafka proxy
  -> Kafka -> Argo

clean target path:
Alertmanager/Grafana -> Kafka raw topic -> Vector -> Kafka normalized topic
  -> Argo

clean HTTP fallback:
Alertmanager/Grafana -> Vector HTTP receiver -> Kafka normalized topic -> Argo
```

The design decision is to remove avoidable webhook/proxy services only after the
clean path is verified and rollback is documented. Until then, the working path
is the control path.

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

## Copy / Upload Folder

Copy this single folder to the work agent:

```text
work-agent-bundles/vector-kafka-routing-normalization/
```

It now includes the prompt, checklists, chaos examples, dashboard example, and
the relevant Vector reference manifests under `payload/observability-vector/`.
You should not need to copy the wider repo for this handoff.

Start the other agent with:

```text
WORK-AGENT-START-PROMPT.md
```

## Source Artifacts

The implementation reference is bundled locally in:

```text
payload/observability-vector/
```

Key files:

```text
payload/observability-vector/README.md
payload/observability-vector/manifests/
payload/observability-vector/homelab/
payload/observability-vector/tests/
payload/observability-vector/handoff/
```

Home-lab reference YAML for the two cleanup options lives in:

```text
payload/observability-vector/homelab/vector-http-receiver-to-kafka.yaml
payload/observability-vector/homelab/vector-kafka-raw-to-normalized.yaml
```

Use these as implementation references when deciding whether work can remove the
webhook-to-Kafka proxy service.

Grafana chaos alert examples for the gameday prompt live in:

```text
examples/grafana-chaos-alerts/chaos-alert-rules.yaml
examples/grafana-chaos-alerts/create-chaos-alerts-api.sh
examples/grafana-dashboards/lgtm-agentic-resolution-showcase.json
examples/daily-gameday/cronworkflow.yaml
```

Use Grafana MCP first. Use the API script as the fallback and home-lab
replication path.

Use [`SHOWCASE-RUNBOOK.md`](SHOWCASE-RUNBOOK.md) as the single stakeholder demo
path. Use [`scenarios/SCENARIO-PACK.md`](scenarios/SCENARIO-PACK.md),
[`TICKET-QUALITY-CONTRACT.md`](TICKET-QUALITY-CONTRACT.md),
[`FAILURE-MODE-TESTS.md`](FAILURE-MODE-TESTS.md), and
[`PROMOTION-GATE.md`](PROMOTION-GATE.md) before rollout.

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
7. After the flow is working, run
   `prompts/07-chaos-gameday-end-to-end.md` to prove real alerting, routing,
   ticket/evidence creation, rollback, and dashboard visibility under
   controlled chaos.
8. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

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

- the existing Kenawa webhook -> Vector -> proxy -> Kafka -> Argo path is
  documented and preserved until a replacement is proven
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
- at least one controlled chaos scenario has proven the full flow from
  Grafana/LGTM alert to GitLab or ServiceNow evidence
- Grafana MCP or the approved API fallback has created the chaos alert rules
  from `examples/grafana-chaos-alerts/chaos-alert-rules.yaml`
- Grafana dashboards show route counts, dedupe, workflow outcomes, ticket
  outcomes, MTTA/MTTR, and daily gameday pass/fail history
- a daily low-risk gameday proposal exists before any scheduled chaos is enabled
