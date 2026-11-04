# Use a dedicated DeepSeek model route

The optional [model bridge template](../examples/deepseek-model-gateway.yaml) connects the standalone profile to DeepSeek through the existing Agent Gateway 1.7 image. It keeps the provider credential in the platform model namespace. The agent runtime receives neither the key nor direct provider access.

## Prepare the platform route

1. Confirm authorization for the target model, a bounded scenario, and the selected account. Use the protected credential process to provision an Opaque Secret named `standalone-deepseek-model` in the model namespace, with field `api-key`. Keep the key out of owner YAML, prompts, shell arguments, source files, and receipts.
2. Confirm authentication and availability with the provider's [model list](https://api-docs.deepseek.com/api/list-models/) and [balance API](https://api-docs.deepseek.com/api/get-user-balance/). A listed model and available balance are prerequisites, not a successful scenario.
3. Fill the template placeholders privately. Reuse the approved digest-pinned Agent Gateway image. The model namespace must differ from both the standalone and central Gateway namespaces. This template expects the existing OTel collector in the model namespace with Pod label `app: flow-collector`; adapt and verify that network path if the target differs.
4. Apply through the platform owner and verify the Deployment and Service. The bridge's fixed upstream is `api.deepseek.com` over TLS. Its ingress policy permits only the standalone facade. It has no Kubernetes API token mount. Egress permits provider HTTPS, cluster DNS, and the configured collector path.
5. Perform one bounded real model smoke check through the bridge. A successful `PONG` establishes model transport only. It does not activate an agent.

The template forces `thinking: {type: disabled}` through the platform-owned AI override. DeepSeek enables thinking by default and requires reasoning fields to be preserved across thinking-mode tool calls. The current bounded worker uses the provider's [documented non-thinking tool flow](https://api-docs.deepseek.com/guides/tool_calls/). This setting permits that flow without changing the adapter or its security checks.

## Select the bridge in the protected profile

Set these fields in a private settings file before rendering:

```json
{
  "model": {
    "name": "deepseek-flash",
    "upstreamURL": "http://standalone-deepseek-model.{{MODEL_NAMESPACE}}.svc.cluster.local:8081/v1/chat/completions",
    "podLabels": {"app": "standalone-deepseek-model"}
  }
}
```

This is part of `settings.example.json`, not an owner-CR field. Render the platform and graph using [the runbook](../RUNBOOK.md). The owner still submits one approved profile plus instructions. This route does not establish native kagent `ModelConfig` integration.

## Change an existing immutable profile safely

Use an approved maintenance window with no active requests. Preserve prior owners, UIDs, approval states, Jobs, and receipts before retiring only the scoped requests. Do not patch a failed approval to Active or restart its Job.

The platform ConfigMap is immutable. Reusing its name after deletion can leave old mounts on existing consumers. Stop the facade and retire the exact completed verifier Pods after preserving their audit records. Verify that every consumer of that ConfigMap has gone before starting the facade with the replacement. Use the authorized platform-maintenance identity; configured revokers cannot create or update non-approval ConfigMaps.

Before creating another request, require all of these:

- The new model bridge is ready and its bounded model smoke check passes.
- The RGD's Ready condition observes its current generation.
- The restarted facade's mounted platform JSON hash equals the current API ConfigMap's JSON hash and names the intended model.
- Actual facade egress selects the intended model bridge, while runtime egress remains limited to the central Gateway and DNS.

Then submit a new owner name and wait for its independent Golden result. A successful Golden must still prove the model, both skills, required knowledge files, typed synthetic MCP operation, and backend witnesses. Require a separate approved-caller answer before claiming the full demonstration works.

The stale-mount check is based on the actual lab failure and Kubernetes' [immutable ConfigMap behavior](https://kubernetes.io/docs/concepts/configuration/configmap/#immutable-configmaps). A fresh install does not need to replay the lab's migration or delete unrelated workplace objects.
