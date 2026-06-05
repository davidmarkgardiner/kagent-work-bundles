# K-Agent and agentgateway Observability

This plan proves the end-to-end LGTM path for kagent and agentgateway:

1. Alloy tails kagent and agentgateway logs from Kubernetes.
2. Alloy scrapes annotated kagent/agentgateway Prometheus endpoints plus kubelet cAdvisor container metrics.
3. Alloy writes logs to Loki and metrics to Prometheus or Mimir.
4. Grafana provisions the K-Agent dashboard against those data sources.
5. Prometheus/Loki rules alert on token spikes, gateway errors, missing metrics, kagent restarts, and suspicious log patterns.

All environment-specific values must stay outside Git. Use `k-agent-alloy-endpoints` for endpoint overrides and use secret-backed Alloy auth blocks if the target LGTM stack requires tokens.

## Preconditions

- Kubernetes cluster with kagent in `kagent` and agentgateway/AI gateway pods in `kgateway-system`.
- Grafana Alloy can authenticate to the Kubernetes API and has `pods/log` access for log tailing.
- A Loki push endpoint and a Mimir or Prometheus remote-write endpoint are available.
- kube-state-metrics is installed if you want the dashboard panels and alerts based on `kube_pod_status_phase`, `kube_pod_container_status_restarts_total`, and `kube_deployment_status_replicas_available`.
- Gateway pods expose Prometheus scrape annotations, including `prometheus.io/scrape: "true"`, `prometheus.io/port`, and `prometheus.io/path`.
- The Alloy log parser uses `stage.cri`, so it assumes containerd or CRI-O formatted pod logs.
- The kubelet cAdvisor scrape uses `insecure_skip_verify: true` by default. If the work cluster has a valid kubelet CA chain, tighten this before production rollout.

## Files

| File | Purpose |
|---|---|
| `k8s/observability/k-agent-alloy.yaml` | Alloy Deployment, RBAC, log collection, metric scrape, remote write |
| `k8s/observability/k-agent-alerts.yaml` | Token usage, gateway, kagent, and log alert rules |
| `observability/grafana/provisioning/datasources/k-agent-lgtm.yaml` | Grafana datasource provisioning template |
| `observability/grafana/provisioning/dashboards/k-agent-dashboards.yaml` | Grafana dashboard provider |
| `observability/grafana/dashboards/k-agent-metrics.json` | Dashboard for token usage, gateway rates, kagent health, and logs |
| `docs/observability/k-agent-observability-playbook.html` | Visual HTML playbook for verification, queries, and alerts |
| `scripts/observability/verify-k-agent-observability.sh` | Static and optional live validation |

## Deployment Plan

1. Confirm the LGTM endpoints:

   ```bash
   curl -fsS "${LOKI_PUSH_URL%/loki/api/v1/push}/ready"
   curl -fsS "${PROMETHEUS_REMOTE_WRITE_URL%/api/v1/push}/-/ready"
   ```

   For a raw Prometheus target, the server must have remote write receiver enabled and expose `/api/v1/write`. Mimir normally uses `/api/v1/push`.

2. Apply the Alloy bundle:

   ```bash
   kubectl apply -f k8s/observability/k-agent-alloy.yaml
   kubectl -n monitoring set env deployment/k-agent-alloy \
     CLUSTER_NAME="{{CLUSTER_NAME}}" \
     LOKI_PUSH_URL="http://{{LOKI_HOST}}/loki/api/v1/push" \
     PROMETHEUS_REMOTE_WRITE_URL="http://{{MIMIR_OR_PROMETHEUS_REMOTE_WRITE_URL}}"
   kubectl -n monitoring rollout status deployment/k-agent-alloy
   ```

3. Apply alert rules where Prometheus Operator CRDs are installed:

   ```bash
   kubectl apply -f k8s/observability/k-agent-alerts.yaml
   ```

4. Provision Grafana by mounting:

   ```text
   observability/grafana/provisioning/datasources/k-agent-lgtm.yaml
   observability/grafana/provisioning/dashboards/k-agent-dashboards.yaml
   observability/grafana/dashboards/k-agent-metrics.json
   ```

   Set `PROMETHEUS_URL` and `LOKI_URL` in the Grafana environment.
   If the work LGTM stack is multi-tenant or authenticated, add the required
   `X-Scope-OrgID`, `Authorization`, basic auth, or Grafana Cloud credentials
   to the datasource provisioning before rollout.

## Proof Queries

Use these in Grafana Explore or any Prometheus/Loki query UI after Alloy is
running and the Grafana data sources point at the same LGTM backends.

PromQL:

```promql
# Is Alloy remote_write landing gateway metrics?
count({__name__=~"envoy_cluster_external_upstream_rq.*", namespace="kgateway-system"})

# Tokens per minute by model and token type
sum by (gen_ai_request_model, gen_ai_token_type) (
  rate(agentgateway_gen_ai_client_token_usage_sum[5m]) * 60
)

# Gateway request rate by upstream and response class
sum by (envoy_cluster_name, envoy_response_code_class) (
  rate(envoy_cluster_external_upstream_rq_xx[5m])
)

# kagent container restarts in the last hour
sum by (namespace, pod, container) (
  increase(kube_pod_container_status_restarts_total{namespace="kagent"}[1h])
)

# kagent pod CPU by pod
sum by (pod) (
  rate(container_cpu_usage_seconds_total{namespace="kagent", container!="", container!="POD"}[5m])
)

# kagent memory working set by pod
sum by (pod) (
  container_memory_working_set_bytes{namespace="kagent", container!="", container!="POD"}
)
```

LogQL:

```logql
# Recent kagent API/A2A logs
{namespace="kagent"} | json | line_format "{{.level}} {{.logger}} {{.path}} status={{.status}} {{.msg}}"

# Suspicious gateway log patterns
{namespace="kgateway-system"} |~ "(?i)(error|reset|timeout|token|model|upstream)"

# Token fields from structured kagent logs, if present
sum by (agent, model) (
  sum_over_time({namespace="kagent"} | json | unwrap total_tokens [5m])
)
```

## Work Verification Checklist

### Visual check in Grafana

1. Open the `K-Agent and agentgateway Observability` dashboard.
2. Confirm these panels are non-empty over `Last 6 hours`:
   - `agentgateway Upstream Response Rate`
   - `Running kagent Pods`
   - `kagent Restarts Last Hour`
   - `kagent API and A2A Logs`
   - `agentgateway Suspicious Logs`
3. If `agentgateway Tokens Per Minute` is blank, run the token query in
   Grafana Explore. A blank result means either no model calls have happened in
   the selected time window or this gateway build is not emitting
   `agentgateway_gen_ai_client_token_usage_*`.
4. Click a metric panel data point and pivot to a Loki query using the same
   `cluster`, `namespace`, and `pod` labels where available.

### Query check in Grafana Explore

Run one PromQL and one LogQL query:

```promql
sum by (envoy_cluster_name, envoy_response_code_class) (
  rate(envoy_cluster_external_upstream_rq_xx[5m])
)
```

```logql
{namespace="kagent"} | json | line_format "{{.level}} {{.logger}} {{.path}} status={{.status}}"
```

Expected result: PromQL returns gateway time series and LogQL returns recent
kagent API/A2A lines. If PromQL is empty but the live gateway exposes metrics,
Alloy remote_write or the metric backend endpoint is the issue. If LogQL is
empty, check Alloy `loki.write` delivery and label relabeling.

### Alert check

Apply the alert bundle:

```bash
kubectl apply -f k8s/observability/k-agent-alerts.yaml
kubectl -n monitoring get prometheusrule k-agent-agentgateway-alerts k-agent-log-alerts
```

Verify rule discovery:

```bash
kubectl -n monitoring get prometheusrule k-agent-agentgateway-alerts -o yaml \
  | rg 'AgentgatewayRunawayInputTokens|AgentgatewayHigh5xxRate|KagentControllerDown'
```

In Grafana or Prometheus, check that the rules appear under the active rules
view. If the work environment uses managed Mimir/Loki rulers, ensure the labels
`shipto.lgtm: "true"` and `route_to: triage` match the platform team's rule
sync and Alertmanager routing selectors.

The `k-agent-log-alerts` object contains LogQL expressions in a
`PrometheusRule` shape for environments where Alloy or the managed LGTM stack
syncs labelled rules to a Loki ruler. Do not select that object with a vanilla
Prometheus rule selector unless your platform explicitly supports LogQL rules
from `PrometheusRule` resources.

### Scenario checks

Use these low-risk scenarios:

1. Generate a normal kagent request and confirm new kagent log lines appear in
   Loki within a few minutes.
2. Send one agentgateway-backed model request and confirm gateway request rate
   increases.
3. If token metrics are supported, confirm `agentgateway Tokens Per Minute`
   increases after the request.
4. Temporarily lower an alert threshold in a non-production namespace or test
   branch, confirm the rule fires, then revert the threshold.

## Live Lab Findings From 2026-05-13

Read-only checks on the lab Kubernetes context showed:

- `kagent` namespace is running the controller, tools, UI, and agent pods.
- `kgateway-system` is running `ai-gateway` and `kgateway`; `ai-gateway` exposes Prometheus annotations on port `9091`.
- Existing Alloy in `monitoring` is running and tails kagent/agentgateway pod logs.
- Loki is reachable at the current lab endpoint and reports ready; a Loki `query_range` for `{namespace="kagent"}` returned live kagent log streams.
- agentgateway metrics are available from the live gateway pod; `envoy_cluster_external_upstream_rq*` samples were returned from port `9091`.
- Existing Alloy remote write was pointed at an HTTP app that returns HTML/405 for remote write. Correct that endpoint to a Prometheus remote-write receiver or Mimir push URL before considering metrics delivery proven.

The repo bundle above makes the endpoint choice explicit and repeatable, so the same proof can be replayed without committing private hostnames.
