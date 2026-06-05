# Managed LGTM Rule Sync With Alloy

This README explains the rule-sync pattern proved on a local validation cluster
and how to lift it into a managed LGTM target.

The goal is to manage alert and recording rules as Kubernetes YAML instead of
clicking every rule into the Grafana UI.

## What This Solves

If the target environment exposes a Mimir Ruler endpoint, Alloy can watch labelled
`PrometheusRule` CRs in Kubernetes and push them into managed Mimir:

```text
PrometheusRule YAML
  -> Kubernetes API
  -> Alloy mimir.rules.kubernetes
  -> managed Mimir Ruler API
  -> Grafana Alerting UI shows/evaluates the rule
  -> existing Alertmanager/Grafana routing sends notifications
```

This lets us programmatically create and update many alert rules through GitOps
or `kubectl apply`.

It does **not** replace notification routing. The alert still needs an existing
Grafana/Alertmanager notification policy, contact point, or webhook route that
matches rule labels such as:

```yaml
labels:
  route_to: triage
  team: ai-platform
  severity: warning
```

If the target environment already has a route like
`route_to=triage -> Argo EventSource/TRIAS`, then new synced rules only need to
carry the right labels.

## What It Does Not Manage

`mimir.rules.kubernetes` manages Mimir/Prometheus-compatible rules only:

- alerting rules using PromQL
- recording rules using PromQL

It does **not** manage:

- Grafana dashboards
- Grafana-managed alert rules
- contact points
- notification policies
- Alertmanager routes
- folders, teams, or permissions
- Loki/LogQL rules

For Loki/LogQL rules, use the separate Alloy component
`loki.rules.kubernetes` and a Loki Ruler endpoint.

Official docs:

- <https://grafana.com/docs/alloy/latest/reference/components/mimir/mimir.rules.kubernetes/>
- <https://grafana.com/docs/alloy/latest/reference/components/loki/loki.rules.kubernetes/>

## What We Proved On A Local Validation Cluster

The original local validation cluster `k-agent-alloy` deployment did **not**
have rule sync enabled. It only shipped metrics and logs.

We then enabled an isolated proof:

- `monitoring/mimir-rule-sync-proof` - local Mimir Ruler target
- `monitoring/alloy-rule-sync-proof` - separate Alloy rule-sync instance
- `monitoring/managed-rule-sync-smoke` - labelled smoke `PrometheusRule`
- Grafana datasource `Mimir Rule Sync Proof`

Evidence:

- Alloy loaded `mimir.rules.kubernetes.proof`.
- Alloy logged `added rule group`.
- Alloy metrics showed:

```text
mimir_rules_mimir_client_request_duration_seconds_count{
  operation="POST /prometheus/config/v1/rules/<namespace>",
  status_code="202"
} 1
```

- Mimir Ruler API returned the synced rule.
- Grafana datasource proxy returned:

```json
{
  "name": "ManagedRuleSyncSmoke",
  "query": "vector(1)",
  "state": "firing",
  "labels": {
    "route_to": "triage",
    "severity": "info"
  },
  "health": "ok"
}
```

Proof manifest:

```text
k8s/observability/mimir-rule-sync-proof.yaml
```

Evidence write-up:

```text
docs/observability/mimir-rule-sync-evidence.md
```

## Target Environment Prerequisites

The target environment must provide:

1. Mimir Ruler URL, not just remote-write URL.
2. Tenant ID, if the backend is multi-tenant.
3. Service account token, bearer token, basic auth, or OAuth details with
   permission to write ruler config.
4. Confirmation of the existing routing labels. Example:
   `route_to=triage`, `team=ai-platform`, `severity=warning`.
5. For log-based alerts, a Loki Ruler URL and credentials as well.

Important: this pattern avoids manual UI rule creation, but Alloy still needs
API credentials to the Ruler backend.

## Alloy Mimir Rule Sync

Use this shape for metric/PromQL rules:

```alloy
mimir.rules.kubernetes "managed" {
  address   = sys.env("MIMIR_RULER_URL")
  tenant_id = sys.env("MIMIR_TENANT_ID")

  bearer_token = sys.env("MIMIR_RULER_BEARER_TOKEN")

  rule_selector {
    match_labels = {
      "shipto.lgtm" = "true",
      "lgtm.tenant" = sys.env("TENANT"),
    }

    match_expression {
      key      = "lgtm.engine"
      operator = "NotIn"
      values   = ["loki"]
    }
  }

  sync_interval = "1m"
}
```

Use `rule_namespace_selector` only if the Kubernetes Namespace itself is
labelled for tenant isolation. For most target environments, match tenant
labels on the `PrometheusRule` CR via `rule_selector`.

## Alloy Loki Rule Sync

Use this only if the target environment exposes a Loki Ruler endpoint:

```alloy
loki.rules.kubernetes "managed" {
  address   = sys.env("LOKI_RULER_URL")
  tenant_id = sys.env("LOKI_TENANT_ID")

  bearer_token = sys.env("LOKI_RULER_BEARER_TOKEN")

  rule_selector {
    match_labels = {
      "shipto.lgtm" = "true",
      "lgtm.tenant" = sys.env("TENANT"),
      "lgtm.engine" = "loki",
    }
  }

  sync_interval = "1m"
}
```

## RBAC

Alloy needs to read namespaces and `PrometheusRule` CRs:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: alloy-rule-sync
rules:
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["monitoring.coreos.com"]
    resources: ["prometheusrules"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: alloy-rule-sync
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: alloy-rule-sync
subjects:
  - kind: ServiceAccount
    name: alloy
    namespace: monitoring
```

## Example: Cert-Manager Metric Alert

Use Mimir rule sync for metric-based certificate alerts. This is the best option
if the target environment only gives us a Mimir endpoint.

This example fires when a certificate expires within 14 days. It assumes
cert-manager metrics or kube-state-metrics custom resource metrics are present
in Mimir.

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: cert-manager-certificate-alerts
  namespace: monitoring
  labels:
    shipto.lgtm: "true"
    lgtm.tenant: platform
    route_to: triage
spec:
  groups:
    - name: cert-manager.certificates
      interval: 1m
      rules:
        - alert: CertManagerCertificateExpiringSoon
          expr: |
            (certmanager_certificate_expiration_timestamp_seconds - time()) < 14 * 24 * 60 * 60
          for: 15m
          labels:
            severity: warning
            team: platform
            route_to: triage
          annotations:
            summary: "Certificate {{ $labels.name }} expires within 14 days"
            description: "Certificate {{ $labels.namespace }}/{{ $labels.name }} is approaching expiry. Check Certificate, CertificateRequest, Order, and Challenge status."
```

If the exact metric name differs in the target environment, discover available
series first:

```promql
{__name__=~".*cert.*"}
```

or search in Grafana Explore for:

```text
certmanager_certificate
kube_certmanager
certificate_expiration
```

## Example: Cert-Manager Log Alert

Use Loki rule sync for log-pattern alerts. This is only available if the target
environment exposes a Loki Ruler endpoint.

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: cert-manager-log-alerts
  namespace: monitoring
  labels:
    shipto.lgtm: "true"
    lgtm.tenant: platform
    lgtm.engine: loki
    route_to: triage
spec:
  groups:
    - name: cert-manager.logs
      interval: 1m
      rules:
        - alert: CertManagerCertificateErrorLogs
          expr: |
            sum by (cluster, namespace, pod) (
              count_over_time({namespace="cert-manager"} |~ "(?i)(error|failed|denied|certificate|issuer|challenge|order)" [10m])
            ) > 0
          for: 5m
          labels:
            severity: warning
            team: platform
            route_to: triage
          annotations:
            summary: "cert-manager certificate error logs detected"
            description: "cert-manager emitted certificate, issuer, order, or challenge error logs. Check pod logs and Certificate/CertificateRequest/Order/Challenge resources."
```

This is a good option for broad operational coverage, but it depends on logs
being shipped to Loki and on having Loki Ruler API access.

## Verification

Check Alloy component health:

```bash
kubectl -n monitoring logs deploy/alloy-rule-sync --tail=200 | \
  egrep 'mimir.rules.kubernetes|loki.rules.kubernetes|added rule group|error'
```

Check Alloy metrics:

```bash
kubectl -n monitoring port-forward svc/alloy-rule-sync 12345:12345
curl -fsS http://127.0.0.1:12345/metrics | egrep 'mimir_rules_|loki_rules_'
```

Expected for Mimir:

```text
mimir_rules_events_total{type="sync-mimir"} > 0
mimir_rules_mimir_client_request_duration_seconds_count{operation="POST /prometheus/config/v1/rules/<namespace>",status_code="202"} > 0
```

Check the Ruler API directly:

```bash
curl -fsS \
  -H "Authorization: Bearer ${MIMIR_RULER_BEARER_TOKEN}" \
  -H "X-Scope-OrgID: ${MIMIR_TENANT_ID}" \
  "${MIMIR_RULER_URL}/prometheus/config/v1/rules"
```

Check Grafana:

1. Open Grafana Alerting.
2. Filter by rule name or label.
3. Confirm the rule appears under the managed Mimir/Loki datasource.
4. Confirm firing alerts match an existing notification policy.

## Practical Answer

Yes, if the target environment gives us the Mimir Ruler endpoint and
credentials, we can programmatically create many metric-based alerting rules
without using the UI.

For cert-manager log events specifically, that requires Loki Ruler, not Mimir.
If the target environment only gives us Mimir, use cert-manager metrics
instead. If the target environment gives us both Mimir and Loki Ruler
endpoints, we can manage both PromQL metric alerts and LogQL log alerts the
same way.
