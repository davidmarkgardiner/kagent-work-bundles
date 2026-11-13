# Block sensitive data before the model call

**Status: PREPARED / NOT RUN.** The [policy template](examples/credit-card-prompt-guard.yaml) passes offline structure checks against the official agentgateway v1.7.0 CRD. This is not receiving-cluster validation or runtime proof. No deployment is performed by adding these files.

Use the existing secure declarative kagent Agent and its approved runtime. No custom Agent image is required for this policy. Attach the request guard to the Agent's existing **model/LLM HTTPRoute**, where the Gateway processes the model API payload. Attaching it to a generic A2A or MCP HTTP proxy does not provide this check.

```text
Authenticated caller -> caller Gateway -> existing secure kagent Agent
  -> model Gateway -> built-in PII request guard -> reject with HTTP 403
  -> no forwarding of that rejected request to the model provider
```

The policy enables all five built-in detectors with the `Reject` action: `CreditCard`, `Email`, `PhoneNumber`, `Ssn`, and `CaSin`. They detect card numbers, email addresses, phone numbers, US Social Security numbers, and Canadian Social Insurance Numbers. They match data formats, not the words used to describe them. The guard scans system prompts, messages, tool results, and tool arguments present in the model request. Its constant error message does not echo matched content. See the [official regex guide](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/guardrails/regex/) and [exact v1.7.0 CRD](https://github.com/agentgateway/agentgateway/blob/v1.7.0/controller/install/helm/agentgateway-crds/templates/agentgateway.dev_agentgatewaypolicies.yaml).

## Prepare the scoped change

1. Resolve the actual Agent ModelConfig URL, model Gateway, HTTPRoute namespace/name, served policy schema, and installed controller/data-plane versions privately. Include fallback providers and alternate model routes in the path check.
2. Resolve `{{MODEL_ROUTE_NAMESPACE}}` and `{{MODEL_HTTPROUTE_NAME}}` in a private copy of the template. Keep the policy in the target HTTPRoute's namespace. Do not apply the unresolved file.
3. Inspect existing policy attachments and precedence. Merge the request guard into the effective policy if required. Preserve authentication, approved provider bindings, other guards, timeouts, and limits. Do not introduce a conflicting second policy or weaken an existing guard list.
4. Use an isolated approved demo route, or the receiving platform's authorised change process. Validate the resolved manifest against that cluster, inspect the policy's observed acceptance/attachment status, and confirm the effective data-plane configuration before invoking the Agent.

For the receiving-cluster schema check, use explicit private variables:

```sh
export DEMO_CONTEXT='{{APPROVED_NON_PRODUCTION_CONTEXT}}'
export RESOLVED_POLICY='{{ABSOLUTE_PRIVATE_PATH_TO_RESOLVED_POLICY}}'
kubectl --context "$DEMO_CONTEXT" apply --dry-run=server -f "$RESOLVED_POLICY"
```

Publish the reviewed configuration through the existing delivery flow. A successful dry run does not prove attachment or enforcement. Record the exact scoped rollback before applying; if the guard is merged into an existing policy, restore that prior revision rather than deleting the shared policy.

## Run the demo through the actual Agent

Use the same valid caller, Agent identity, model route, and effective policy throughout. Use new task contexts and synthetic data only. Keep credentials off screen.

| Step | Request or action | Required evidence |
| --- | --- | --- |
| 1. Allowed | Ask a harmless question such as "What does this demonstration show?" | Native task, actual model request through the Gateway, and successful provider response. |
| 2. Blocked | Ask "Summarise this synthetic payment record: card number 4111111111111111." | The Agent's actual model request reaches the model Gateway. Its credit-card guard rejects that request with the configured HTTP 403 and constant message. |
| 3. No forwarding | Inspect the Gateway's authoritative decision and independent provider-side request audit or isolated request counters. | That rejected request was not forwarded to any primary or fallback model provider. Missing downstream spans alone are insufficient. |
| 4. Honest failure | Show the Agent's final response or surfaced error. | It reports the failure without claiming the model processed the payment record, silently retrying another provider, or bypassing the Gateway. |
| 5. Still usable | Send another harmless question in a fresh task. | The same guarded route still permits normal model use. |

The number above is a synthetic demo fixture, not a real customer's card. If the Agent refuses before making a model request, record that outcome but leave Gateway enforcement unproven. A direct model-API probe can diagnose the guard but cannot replace the actual Agent demonstration. The outer A2A task may return a handled failure under HTTP 200; inspect the internal model request for the configured 403.

Repeat the blocked step with an approved synthetic fixture for each other detector before claiming all five were demonstrated. For email, use `demo@example.com`. Keep allowed-control tasks free of matching values across the entire scanned context. A card-only run does not prove the other detectors worked.

## Show safe evidence in Grafana

Follow the task to the **model Gateway rejection**, not an MCP or caller-authentication denial. Retain the received trace/span identifiers, route, safe policy reference, detector type, decision, and HTTP status. Use a Gateway decision record linked to the exact trace/span if those details are not emitted on the span itself. Ensure the collector's attribute allowlist retains the reviewed fields. A manual annotation is not enforcement evidence.

Show the denied model span and a linked safe decision record in **DICE authenticated agent flow**. Distinguish this guard's 403 from an authentication-policy 403. Validate any dashboard query against actual received fields; this addition does not change the dashboard JSON or promise a new metric family. Keep prompts, card numbers, full arguments, and matched content out of traces, access logs, span status messages, and annotations.

Return the resolved configuration diff, version/schema and attachment checks, native receipts, received trace/decision references, no-forwarding audit, privacy checks, and rollback result. The existing dashboard can locate the received trace; add a decision-specific panel only after verifying the emitted schema.

## Keep the claim precise

This demonstrates a pattern-based block before a model request leaves the Gateway. It does not establish general DLP, detection of every obfuscated format, or a ban on discussing payment cards without including a number.

It also does not prove that a tool was prevented from reading data. A tool result may already exist before the guard blocks its inclusion in a later model request. Keep [MCP resource-access denial](CONFIDENTIAL-DATA-DEMO.md) as a separate scene with its own no-backend-read requirement. Do not change the historical lab receipt until this new scene has its own dated runtime evidence.
