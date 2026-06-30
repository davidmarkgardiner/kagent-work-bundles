# Front Sheet: Vector Kafka Routing Normalization

## Purpose

Prove and prepare a work-side rollout where Vector normalizes observability
events before Argo creates workflows.

## Current Recommendation

Use Kafka first:

```text
Alertmanager / Grafana / Alloy
  -> raw Kafka topic
  -> Vector normalize / filter / dedupe / route
  -> normalized Kafka topic
  -> Argo EventSource
  -> Argo Sensor
  -> Argo Workflow
  -> selected agent or escalation path
```

If the already-working work path is HTTP webhook based, assess it before
changing it:

```text
Alertmanager / Grafana
  -> webhook
  -> Vector
  -> webhook-to-Kafka proxy
  -> Confluent REST
  -> Argo
```

That path can be valid as a compatibility bridge, but it has more components to
own. The cleaner target is either Kafka-first into Vector or HTTP into Vector
with Vector publishing directly to Kafka.

## Why This Matters

The value is not "more middleware." The value is:

- stable payload contract before Argo
- fewer duplicate workflows
- clearer routing to the right agent
- safer automation gates
- measurable deflection, MTTA, MTTR, and escalation trends

## Production Position

Dev rollout: acceptable after environment preflight and work-side validation.

Production rollout: no-go until the checklist safety items are closed.
