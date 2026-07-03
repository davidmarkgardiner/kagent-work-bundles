# Kafka Topic Design For Vector-Routed Alerts

## Recommendation

Start with a small number of topics and let Vector do the first level of
sorting. Do not create a topic per application on day one.

For the current design, where Alertmanager/Grafana posts to a Vector webhook
receiver and Vector publishes to Kafka, the recommended starting point is:

```text
observability.alerts.actionable.v1
observability.alerts.quarantine.v1      optional
observability.alerts.audit.v1           optional, only if raw retention is required
```

Argo should watch `observability.alerts.actionable.v1` first. Vector should put
only records that an agent should inspect onto that topic.

## Why Start With One Actionable Topic

One actionable topic is the safest first production shape because:

- Vector can filter, dedupe, normalize, and enrich before Kafka.
- Argo has one clean contract to consume.
- Topic ACLs, EventSources, Sensors, dashboards, and retention are simpler.
- Route changes can happen in Vector config without creating new Kafka topics.
- It avoids a topic explosion before the team understands real alert volume.

Use fields in the message to route instead of topics at first:

```text
source_system=alertmanager|grafana|alloy|security|custom
route_domain=application|platform|network|security|compliance|fallback
target_agent=aks-sre-triage-agent|networking-triage-agent|security-hardening-agent
tenant_or_team={{TEAM}}
application={{APP_NAME}}
environment=dev|test|prod
severity=warning|critical
dedupe_key={{STABLE_KEY}}
```

## Suggested Topic Names

Use clear, stable, versioned names:

| Topic | Purpose | Argo consumes? |
|---|---|---|
| `observability.alerts.actionable.v1` | Clean normalized alerts that should create agent work. | Yes |
| `observability.alerts.quarantine.v1` | Malformed, unknown, or suspicious events for inspection. | No |
| `observability.alerts.audit.v1` | Raw or lightly wrapped inbound events if the team needs replay/audit after the webhook receive point. | No |
| `observability.alerts.deadletter.v1` | Events Vector could not publish or downstream systems rejected, if DLQ handling is implemented. | No |

Avoid names tied to a temporary implementation detail, such as a specific
webhook service name. Prefer the business/event contract.

## Message Contract

Every actionable event should include enough routing data for Argo and agents:

```json
{
  "schema_version": "observability.triage.v1",
  "source_system": "alertmanager",
  "event_type": "prometheus-alert",
  "status": "firing",
  "environment": "prod",
  "cluster": "{{CLUSTER_NAME}}",
  "namespace": "{{NAMESPACE}}",
  "application": "{{APP_NAME}}",
  "service": "{{SERVICE_NAME}}",
  "severity": "critical",
  "route_domain": "application",
  "target_agent": "aks-sre-triage-agent",
  "route_key": "{{STABLE_ROUTE_KEY}}",
  "routing_reason": "{{WHY_THIS_ROUTE_WAS_SELECTED}}",
  "dedupe_key": "{{STABLE_DEDUPE_KEY}}",
  "incident_candidate": true,
  "automation_allowed": false,
  "raw_event_ref_or_hash": "{{HASH_OR_REF}}"
}
```

Vector should drop resolved/non-actionable alerts before the actionable topic.
If the team needs visibility into dropped records, emit metrics or write to the
quarantine topic. Argo should not consume quarantine by default.

## When To Split Topics

Split topics only when there is a concrete operational reason.

Good reasons to split:

- Different retention requirements.
- Different ACL/security boundaries.
- Different consumer groups owned by different platform teams.
- High volume from one route is affecting other routes.
- Different SLA or priority handling is required.
- A route needs a separate Argo EventSource/Sensor lifecycle.

Poor reasons to split:

- One topic per application by default.
- One topic per alert rule.
- One topic per agent before volume or ownership is proven.
- Temporary debugging.

## Expansion Model

If one actionable topic becomes too broad, split by route domain first:

```text
observability.alerts.application.v1
observability.alerts.platform.v1
observability.alerts.network.v1
observability.alerts.security.v1
observability.alerts.compliance.v1
observability.alerts.fallback.v1
```

Only split application traffic further if there is a clear ownership or volume
reason:

```text
observability.alerts.application.payments.v1
observability.alerts.application.digital.v1
observability.alerts.application.shared-services.v1
```

Do not create per-service topics unless the service is high-volume, high-risk,
or has separate access/retention requirements.

## Multiple Webhooks vs One Webhook

Prefer one protected Vector webhook receiver for the initial rollout:

```text
Alertmanager / Grafana / other sources
  -> Vector webhook receiver
  -> Vector source detection + normalization
  -> Vector filtering / dedupe / route selection
  -> Kafka actionable topic(s)
```

Use multiple webhooks only when they create a real control boundary:

| Pattern | Use when | Tradeoff |
|---|---|---|
| One webhook, Vector routes internally | Default path. Same auth/network boundary and common schema. | Simple to operate; Vector config must identify sources reliably. |
| Webhook per source type | Alertmanager, Grafana, security scanner, and custom app events need different auth or payload handling. | More endpoints and contact points to manage. |
| Webhook per tenant/team | Teams need hard isolation or separate credentials. | Higher operational overhead and more failure points. |
| Webhook per critical app | Only for high-risk/high-volume apps with separate support model. | Can become unmanageable if used broadly. |

The webhook should not be the main routing primitive. Vector should be.

## Source Types

This topic design can handle more than Alertmanager:

| Source | Suggested handling |
|---|---|
| Alertmanager / Grafana alerts | Normalize to `observability.triage.v1`; route by labels, namespace, app, severity, and environment. |
| Alloy / Kubernetes events | Normalize into the same envelope where the event is actionable; otherwise drop/quarantine. |
| Security scanner / advisory feed | Route to `security` or `compliance` domain; usually lower automation by default. |
| Application custom events | Require an owner, app name, environment, and severity before allowing into actionable topics. |
| Synthetic chaos/gameday alerts | Add `chaos_scenario`, `test_run_id`, and cleanup markers; keep them distinguishable in dashboards. |

## Recommended First Implementation

Use this first:

```text
Vector webhook receiver
  -> normalize all supported source shapes
  -> filter resolved/noisy/malformed events
  -> compute route_domain, target_agent, route_key, dedupe_key
  -> suppress duplicates
  -> publish to observability.alerts.actionable.v1
  -> optionally publish rejects to observability.alerts.quarantine.v1
```

Argo:

```text
Kafka EventSource watches observability.alerts.actionable.v1
  -> Sensor creates one generic triage workflow
  -> Workflow reads target_agent and route_domain
  -> Agent can hand off to specialists
```

Review after the first few weeks of real data:

- alert count by source
- alert count by route domain
- duplicate suppression count
- quarantine count and reason
- workflow count by route
- ticket outcome by app/team
- noisy applications or labels

Only then decide whether to split into domain or team topics.

## Naming Rules

- Use lowercase dot-separated names.
- Include the event family: `observability.alerts`.
- Include the contract or route: `actionable`, `quarantine`, `application`.
- Include a version suffix: `.v1`.
- Avoid environment in the topic name unless clusters share the same Kafka
  cluster and require hard separation. Prefer an `environment` field in the
  payload.
- Avoid app names until the team has a proven need.

## Decision Summary

Start with:

```text
observability.alerts.actionable.v1
observability.alerts.quarantine.v1
```

Optional:

```text
observability.alerts.audit.v1
```

Let Vector decide what is actionable, which agent should look at it, and whether
it should be dropped, quarantined, or published. Split topics later by route
domain or ownership only when volume, ACLs, retention, or operational ownership
make it worth the extra moving parts.
