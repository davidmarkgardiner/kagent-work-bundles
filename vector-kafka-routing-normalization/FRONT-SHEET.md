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
