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
6. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

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
