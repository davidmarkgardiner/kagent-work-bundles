# LGTM Application and Platform Log Alert Examples

## Purpose

This sheet gives one reusable application/controller-log pattern for cert-manager, Kyverno, external-dns, ingress, Flux, CSI, Cilium and application services. It supports the baseline requirement that every application has collected, queryable, correlated and proven logs/events.

It is not a direction to alert on every error line. Build a small number of scoped, high-confidence, owner-routed rules from real application log shapes.

## Collection and onboarding contract

Alloy should attach stable labels:

~~~text
cluster, environment, namespace, pod, container, service/app name, owner/team where available
~~~

Retain structured log bodies and redact secrets before transport. Do not label request IDs, user data, full exception text or other high-cardinality content.

For each application: prove logs arrive, identify owner/service labels, select two or three real failure patterns, test against normal volume, attach an Explore link/runbook, and prove a safe failure/recovery.

## Reusable candidate patterns

~~~logql
# Candidate: ApplicationPanicLogged
sum by (cluster, namespace, service, pod, container) (
  count_over_time({cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}",
    service="{{SERVICE}}"}
    |~ "(?i)panic:|fatal error:|unhandled exception|traceback" [5m])
) > 0

# Candidate: ApplicationErrorBurst; tune to normal volume.
sum by (cluster, namespace, service) (
  count_over_time({cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}",
    service="{{SERVICE}}"} | json | level=~"error|fatal|critical" [5m])
) > {{ERROR_LINES_IN_5M_THRESHOLD}}

# Candidate: DependencyTimeoutBurst
sum by (cluster, namespace, service) (
  count_over_time({cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}",
    service="{{SERVICE}}"}
    |~ "(?i)(timeout|deadline exceeded|connection refused|unavailable)" [10m])
) > {{DEPENDENCY_FAILURE_THRESHOLD}}
~~~

If JSON parsing is not valid for every line, normalize at ingestion or use a narrow text matcher. Never deploy a fleet-wide unqualified error regex.

## Platform application examples

~~~logql
# Candidate: CertManagerIssuanceFailures
sum by (cluster, pod, container) (
  count_over_time({cluster="{{CLUSTER_NAME}}", namespace="cert-manager"}
    |~ "(?i)(issuance|renew|acme|dns|webhook).*(fail|error|denied|timeout)" [10m])
) > {{CERT_MANAGER_ERROR_THRESHOLD}}

# Candidate: KyvernoAdmissionFailures
sum by (cluster, pod, container) (
  count_over_time({cluster="{{CLUSTER_NAME}}", namespace="kyverno"}
    |~ "(?i)(admission|webhook|policy).*(denied|timeout|fail|error)" [5m])
) > {{KYVERNO_ADMISSION_FAILURE_THRESHOLD}}

# Candidate: ExternalDNSProviderOrSyncFailures
sum by (cluster, pod, container) (
  count_over_time({cluster="{{CLUSTER_NAME}}", namespace="external-dns"}
    |~ "(?i)(provider|record|zone|sync|authentication|authorization).*(fail|error|denied|timeout)" [10m])
) > {{EXTERNAL_DNS_FAILURE_THRESHOLD}}
~~~

Pair cert-manager logs with Certificate readiness/expiry metrics; Kyverno webhook/service failure with policy decision context; and external-dns logs with a representative DNS synthetic check. A healthy controller pod does not prove the result has converged.

## Alerting and evidence boundary

Loki Ruler can evaluate these rules and Alertmanager can notify the owner. The same bounded/redacted log can independently travel Alloy -> Vector -> Kafka -> Argo for read-only triage. Alerting establishes notification; the separate path supplies diagnostic context.

Prove each query against normal and failure periods, then repeat this same onboarding pattern for the next platform application.
