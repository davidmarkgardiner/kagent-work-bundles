# LGTM Trace and Network Alert Examples

## Purpose

This sheet covers trace-derived service objectives and Cilium/Hubble network evidence. It addresses the baseline gaps for ingress, DNS, network policy, dropped/denied flows and dependency failures.

First confirm Tempo trace ingestion and whether Cilium/Hubble or ACNS is enabled in each cluster. Do not claim trace/flow coverage where those signals do not exist.

## Signal roles

| Signal | Purpose |
|---|---|
| Distributed trace | Request, latency/error and dependency path evidence. |
| Hubble flow | Cilium-observed flow/policy verdict, DNS and connection evidence. |
| Synthetic probe | User-path availability from an approved network perspective. |
| Cilium/Hubble metrics | Agent/operator/relay health and aggregate flow/drop/DNS objectives. |

A trace/flow is normally evidence, not a page. Alert on bounded user impact, sustained drop/deny anomaly or critical network-component failure.

## Trace-derived service candidates

If the trace backend exports span metrics/service graphs to Mimir, first validate its exact names and labels, then adapt these shapes:

~~~promql
# Candidate: ServiceTraceErrorRate
100 * (
  sum by (cluster, service) (rate({{TRACE_ERROR_COUNTER}}{
    cluster="{{CLUSTER_NAME}}", service="{{SERVICE}}"
  }[5m]))
  /
  clamp_min(sum by (cluster, service) (rate({{TRACE_REQUEST_COUNTER}}{
    cluster="{{CLUSTER_NAME}}", service="{{SERVICE}}"
  }[5m])), 1)
) > {{TRACE_ERROR_PERCENT_THRESHOLD}}

# Candidate: DependencyP95LatencyHigh
histogram_quantile(0.95, sum by (cluster, client_service, server_service, le) (
  rate({{TRACE_LATENCY_HISTOGRAM_BUCKET}}{
    cluster="{{CLUSTER_NAME}}", client_service="{{SERVICE}}",
    server_service="{{DEPENDENCY_SERVICE}}"
  }[5m])
)) > {{DEPENDENCY_P95_SECONDS_THRESHOLD}}
~~~

The trace metric family placeholders are deliberate: they are not literal PromQL until the trace backend contract is confirmed.

## Cilium/Hubble candidates

Enable only required Hubble metric families, such as DNS, drop, TCP, flow and HTTP. Validate names/labels in Explore; these are common metric shapes, not version-independent facts.

~~~promql
# Candidate: CiliumAgentUnavailable
up{cluster="{{CLUSTER_NAME}}", job=~".*cilium.*agent.*"} == 0

# Candidate: HubbleRelayUnavailable
up{cluster="{{CLUSTER_NAME}}", job=~".*hubble.*relay.*"} == 0

# Candidate: SustainedHubbleDrops
sum by (cluster, namespace, direction) (
  rate(hubble_drop_total{cluster="{{CLUSTER_NAME}}"}[5m])
) > {{DROPS_PER_SECOND_THRESHOLD}}

# Candidate: HubbleDNSFailureRate
# rcode is a response-side label: it lives on hubble_dns_responses_total, not
# hubble_dns_queries_total. Querying rcode on the queries metric matches nothing.
# NXDOMAIN is frequently benign (client probing, search-domain expansion); start with
# SERVFAIL|REFUSED and add NXDOMAIN only if a real failure pattern justifies it.
sum by (cluster, namespace) (
  rate(hubble_dns_responses_total{
    cluster="{{CLUSTER_NAME}}", rcode=~"SERVFAIL|REFUSED"
  }[5m])
)
/
clamp_min(sum by (cluster, namespace) (
  rate(hubble_dns_responses_total{cluster="{{CLUSTER_NAME}}"}[5m])
), 1)
> {{DNS_FAILURE_RATE_THRESHOLD}}
~~~

A DROP verdict may be an intentional policy deny. Scope a deny/drop alert to a critical approved source/destination/port contract and correlate it with actual service impact.

## Evidence links and proof

The linked Hubble/flow query should filter by cluster, source workload/namespace, destination service/FQDN, port/protocol, verdict, DNS code and time range. The alert should not put full FQDNs, client IPs or request IDs in labels.

For a failed WHISKEYAPP probe, investigate:

~~~text
probe -> ingress metrics/logs -> endpoint readiness -> Cilium/Hubble DNS/flow/policy
-> application trace/logs
~~~

Test a safe dependency error, DNS failure or approved policy deny. Prove that the alert only fires at the agreed impact threshold and link it to flow, trace, log and event evidence.
