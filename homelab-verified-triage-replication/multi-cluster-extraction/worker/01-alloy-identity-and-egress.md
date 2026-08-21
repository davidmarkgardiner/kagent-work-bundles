# Worker overlay changes

Replace the baseline's `cluster = "red"`, proof namespace values, and
cluster-local Vector endpoint with rendered worker values:

```hcl
stage.static_labels {
  values = { cluster = "{{CLUSTER_NAME}}", environment = "{{ENVIRONMENT}}" }
}
rule {
  source_labels = ["__meta_kubernetes_namespace"]
  regex = "{{NAMESPACE_REGEX}}"
  action = "keep"
}
otelcol.exporter.otlphttp "management_vector" {
  client { endpoint = "https://{{MANAGEMENT_VECTOR_HOST}}" }
}
```

Use mutual TLS or a unique per-worker credential. The label is metadata, not
the identity proof.
