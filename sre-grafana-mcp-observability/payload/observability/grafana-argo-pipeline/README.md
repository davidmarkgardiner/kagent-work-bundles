# Grafana to Argo Alerting Pipeline

This directory is now a compatibility note for the current alerting path. The
active, maintained implementation is the K-Agent / Agent Gateway observability
bundle under `k8s/observability/`.

## Current Path

```text
Grafana Alerting or Prometheus Alertmanager
  -> Argo Events webhook EventSource
  -> k-agent-alert-triage Sensor
  -> Argo Workflow
  -> K-Agent observability-agent
```

## Use These Files

| Purpose | File |
| --- | --- |
| Work handoff | `docs/observability/caf-style-observability-handoff.md` |
| Alertmanager webhook EventSource | `k8s/observability/k-agent-alertmanager-eventsource.yaml` |
| Alertmanager route | `k8s/observability/k-agent-alertmanager-triage-route.yaml` |
| Argo Sensor and Workflow trigger | `k8s/observability/k-agent-alert-triage-sensor.yaml` |
| Metric alerts | `k8s/observability/k-agent-alerts.yaml` |
| Dashboard | `observability/grafana/dashboards/k-agent-agentgateway-public-ready.json` |
| Verification | `scripts/observability/verify-k-agent-observability.sh` |

## Contact Point Choices

Use a direct webhook contact point when Grafana or Alertmanager can reach the
Argo EventSource service:

```text
http://path-b-alertmanager-webhook-eventsource-svc.argo-events.svc:12000/alertmanager
```

Use the broker-backed package under `observability/confluent-cloud-pipeline/`
when the work environment needs buffering, replay, or network decoupling between
Grafana and Argo Events.

## Verification

Run static checks:

```bash
scripts/observability/verify-k-agent-observability.sh
```

Run live checks:

```bash
scripts/observability/verify-k-agent-observability.sh --context {{KUBE_CONTEXT}}
```

Run the full synthetic route test only in an approved test window:

```bash
scripts/observability/verify-k-agent-observability.sh \
  --context {{KUBE_CONTEXT}} \
  --synthetic-alert
```

The old experimental README referred to `argo/`, `k8s/alerting/`, and
`observability/grafana/provisioning/alerting/` files that are not present in
this checkout. Those references were intentionally removed so this handoff only
points at artifacts that exist in the repo.
