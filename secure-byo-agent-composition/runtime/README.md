# Common authorization front door

This standard-library Python service implements the shared local rehearsal boundary. It does not claim Entra authentication. Kubernetes TokenReview verifies a bearer token with audience `secure-byo` on every request. The protected approval record separately permits an exact ServiceAccount username and UID for invocation or MCP.

Run with `python3 server.py --config /config/runtime.json --port 8080`. In-cluster configuration uses the projected service-account token and CA. Rotate the mounted API token normally; the service rereads it for every authority request. Build from an approved Python base using `docker build --build-arg PYTHON_BASE='{{INTERNAL_PYTHON_IMAGE_DIGEST}}' -t '{{INTERNAL_RUNTIME_IMAGE}}' runtime/`. No pip or public network download occurs in the Dockerfile.

Configuration:

```json
{
  "namespace": "secure-byo-hosted",
  "agentName": "demo",
  "approvalName": "demo-approval",
  "request": {
    "apiVersion": "{{REQUEST_API_GROUP}}/v1alpha1",
    "plural": "{{REQUEST_PLURAL}}",
    "name": "demo"
  },
  "upstreamURL": "http://{{EXACT_NATIVE_SERVICE}}/{{EXACT_INVOCATION_PATH}}"
}
```

The platform alone writes the ConfigMap named by `approvalName`. Its `data["approval.json"]` contains:

```json
{
  "state": "Active",
  "expiresAt": "{{RFC3339_EXPIRY}}",
  "requestUID": "{{OBSERVED_REQUEST_UID}}",
  "agentUID": "{{OBSERVED_AGENT_UID}}",
  "agentSpecSha256": "{{CANONICAL_AGENT_SPEC_SHA256}}",
  "callers": {
    "invoke": ["system:serviceaccount:{{CALLER_NAMESPACE}}:{{CALLER_ACCOUNT}}"],
    "mcp": ["system:serviceaccount:{{RUNTIME_NAMESPACE}}:{{RUNTIME_ACCOUNT}}"]
  },
  "callerUIDs": {
    "system:serviceaccount:{{CALLER_NAMESPACE}}:{{CALLER_ACCOUNT}}": "{{OBSERVED_CALLER_ACCOUNT_UID}}",
    "system:serviceaccount:{{RUNTIME_NAMESPACE}}:{{RUNTIME_ACCOUNT}}": "{{OBSERVED_RUNTIME_ACCOUNT_UID}}"
  }
}
```

`agentSpecSha256` is SHA-256 of UTF-8 JSON with sorted keys and separators `,` and `:`. The request and Agent must still exist at the approved UIDs and have no deletion timestamp. The Agent spec must match its approved hash. No positive authorization cache exists. Missing/malformed/unavailable authority returns 503. Inactive, expired, deleting or mismatched bindings return 403. Token rejection returns 401.

The runtime service account needs create TokenReview and namespaced GET of only the named approval ConfigMap, request and Agent. It does not create approvals, identities, tasks in Kubernetes or operational resources. Its namespace, account, configuration and RBAC remain platform controlled. A namespace administrator capable of assuming the approved runtime account remains inside that account's trust domain.

For the native alpha CLI transport, supply these protected fields instead of `upstreamURL`:

```json
{
  "kagentBinary": "/usr/local/bin/kagent",
  "apiURL": "http://{{NATIVE_CONTROLLER}}:8083",
  "gatewayURL": "http://{{NATIVE_GATEWAY}}:8083",
  "nativeUserID": "{{FIXED_AGENT_SPECIFIC_USER_ID}}"
}
```

The CLI transport uses fixed argv flags for API URL, gateway URL, namespace and user ID. It creates one fresh session for the configured Agent, verifies the returned Agent binding, writes the caller's prompt to a private temporary file, invokes that session once, verifies the returned task context, then removes the temporary file. Prompt text never becomes argv or shell code. There is no shell invocation. The native CLI binary and its dependencies must already be provided through the approved image/build process. Authentication/TLS configuration and actual CLI/runtime compatibility remain target prerequisites; no credential is accepted from the caller. The CLI transcript may contain full tool results, bounded by the receiver limit.

Supported HTTP paths:

| Path | Contract |
| --- | --- |
| `GET /healthz` | Liveness only. Does not attest authorization or native runtime readiness. |
| `POST /mcp` | Authenticated MCP JSON-RPC initialize, initialized notification, tools/list, and tools/call `get_demo_status` with empty arguments. Returns a bounded synthetic status, no Kubernetes operation. |
| `POST /invoke` | Authenticated JSON containing only `prompt`, at most 8,192 characters. Creates a fresh native session through the configured CLI, or generates a fresh A2A `SendMessage` for the explicitly configured HTTP transport. Native protocol compatibility requires target acceptance. |
| `POST /witness` | Invocation-principal authorization and empty JSON object. Returns counters for authorized tool dispatch, invocation dispatch and rejected HTTP requests. |

History, polling, cancellation, caller-selected session/task IDs, query parameters and streaming APIs are not exposed. The 16 KiB request and 1 MiB upstream response limits bound transport. The HTTP upstream timeout is 45 seconds. The optional native CLI transport has one 100-second deadline shared by session creation and invocation, no retry, bounded stdout and process-group termination on timeout. Authorization is checked again before releasing an invocation result. This withholds a result after revocation but does not cancel a model call already dispatched. A call authorized before revocation may already be in flight; changing the protected record denies subsequent authorization decisions and does not retract work already dispatched. Clock correctness is a deployment prerequisite. Direct access to the native controller must be independently blocked before claiming this is the only access path.

The tests exercise the real local HTTP service with a fake authority and upstream. They establish the adapter contract, not Kubernetes TokenReview issuance, Entra compatibility, network enforcement or a native model invocation. The lab acceptance must prove those applicable components separately.

## Model route

`POST /v1/chat/completions` uses the same fresh TokenReview and protected `callers.mcp`/ServiceAccount UID binding as MCP. Supply `upstreamModelURL` as the exact approved provider chat-completions endpoint, `upstreamModelKeyFile` as an absolute Secret mount path, `modelName` as the fixed accepted model ID, and `modelMaxTokens` as the approved limit, normally 1200 (compiled maximum 4096). An optional `upstreamModelCAFile` selects an internal CA. The runtime holds the upstream key; callers and native ModelConfig use their scoped Kubernetes token instead.

The route accepts at most 256 KiB of JSON and returns at most 1 MiB. It rejects other model names, streaming, multiple completions, unknown endpoint-related fields, ambiguous token-limit fields and limits exceeding the configured ceiling. An omitted limit is replaced with the approved ceiling. Only the fixed provider URL and server-loaded Authorization value are used; client headers, URLs and query parameters are never forwarded. Redirects are rejected to prevent credential forwarding to a second endpoint. Authorization is rechecked before releasing the result. `authorizedModelCalls` counts permitted provider dispatch attempts; provider-observed counters/traces are still required as an independent backend witness.

The first native POC must set model streaming false. Direct provider access from native workers must be blocked independently before claiming exclusive routing through this model boundary. Approval revocation prevents fresh dispatch decisions and withholds responses observed after revocation; an already-dispatched provider request may still finish and incur usage.

## Fresh dispatch and dependency gates

All lab profiles must set `dependencyNames` to an exact mapping for `agenttemplates`, `harnesses`, `modelconfigs` and `remotemcpservers`. When enabled, the protected approval contains exactly four `dependencies` entries with `apiVersion`, `plural`, `name`, `uid` and `specSha256`. Every authorization freshly reads those objects, rejects deletion/UID/spec changes, and checks the Agent→template/Harness and template→model/MCP reference edges. This deployment requirement is checked by the lab profile renderer; profiles omitting the mapping exercise only the smaller adapter contract.

Invocation additionally requires Accepted, ResolvedRefs, Compatible, EgressPoliciesApplied and Ready conditions for the current Agent generation, plus matching nonempty desired/latest-successful revisions. Active MCP/model permission may precede native readiness to allow tool discovery during preparation; invocation remains denied until the native revision is ready. It is therefore incorrect to interpret an Active approval alone as complete readiness.

The body receiver has a five-second absolute deadline. The request budget is 105 seconds, checked before dispatch and result release. Authorization is refreshed after the entire body is received. Native CLI transport refreshes it again between session creation and invocation. Model/HTTP transport refreshes it after connecting and immediately before sending the fixed request. Provider HTTP responses have a 45-second absolute budget, bounded chunk reads and socket cancellation; delayed DNS/connect completion cannot dispatch after that deadline. These controls prevent a slow body or delayed connection from reusing an earlier positive authorization decision.
