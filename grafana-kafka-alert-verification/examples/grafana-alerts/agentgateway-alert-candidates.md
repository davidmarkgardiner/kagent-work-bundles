# Agent Gateway Alert Candidates

These queries are starting points for the work agent. Validate metric names and
labels against the target Grafana/Prometheus/Loki datasources before creating
durable alert rules.

## Prometheus Metric Discovery

Run these first:

```promql
agentgateway_requests_total
```

```promql
agentgateway_request_duration_seconds_count
```

```promql
agentgateway_gen_ai_server_request_duration_count
```

```promql
grafana_alerting_notification_requests_total
```

Expected useful `agentgateway_requests_total` labels:

```text
namespace
pod
route
backend
method
protocol
status
reason
gateway
listener
```

## Agent Gateway 429s

Use this when the gateway exposes HTTP status on `agentgateway_requests_total`:

```promql
sum by (cluster, namespace, route, backend, status) (
  increase(agentgateway_requests_total{
    namespace="agentgateway-system",
    status="429"
  }[5m])
) > 0
```

Suggested labels:

```text
severity = warning
route_to = confluent-kafka-rest
component = agentgateway
signal = http-429
```

## Agent Gateway 5xx / Upstream Errors

```promql
sum by (cluster, namespace, route, backend, status, reason) (
  increase(agentgateway_requests_total{
    namespace="agentgateway-system",
    status=~"5.."
  }[5m])
) > 0
```

Suggested labels:

```text
severity = critical
route_to = confluent-kafka-rest
component = agentgateway
signal = http-5xx
```

## Agent Gateway Request Volume Drop

Use only after establishing a real baseline:

```promql
sum(rate(agentgateway_gen_ai_server_request_duration_count{
  namespace="agentgateway-system"
}[5m])) == 0
```

Suggested labels:

```text
severity = warning
route_to = confluent-kafka-rest
component = agentgateway
signal = no-llm-traffic
```

## Grafana Kafka Notification Proof

Use this to prove Grafana is attempting Kafka notifications:

```promql
increase(grafana_alerting_notification_requests_total{
  integration="kafka"
}[15m]) > 0
```

Use this for notification failures:

```promql
increase(grafana_alerting_notification_requests_failed_total{
  integration="kafka"
}[15m]) > 0
```

## Loki: Agent Gateway 429 Logs

```logql
count_over_time(
  {namespace="agentgateway-system"} |= "429" [30m]
) > 0
```

Suggested labels:

```text
severity = warning
route_to = confluent-kafka-rest
component = agentgateway
signal = log-429
```

## Loki: Agent Gateway Error Logs

```logql
count_over_time(
  {namespace="agentgateway-system"} |~ "(?i)(error|failed|timeout|rate.?limit)" [15m]
) > 0
```

Suggested labels:

```text
severity = warning
route_to = confluent-kafka-rest
component = agentgateway
signal = log-error
```

## Work-Agent Validation Rule

Before creating durable alert rules, the work agent must record:

```text
metric/log query:
datasource UID:
current result:
labels present:
alert threshold:
notification route:
Kafka evidence:
cleanup or GitOps MR:
```
