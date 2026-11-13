# Demo: Gateway blocks a confidential-data request

**Status: PROPOSED / NOT RUN.** Add this scene to the existing secure kagent Agent walkthrough and return implementation and rehearsal evidence. Preserve its approved runtime. The existing lab receipt proves identity checks, not data classification or this new policy. Use synthetic fixtures only.

The point to demonstrate: a valid caller can use the Agent, and the Agent can authenticate to the MCP Gateway, but neither fact grants access to every dataset. The Gateway rejects a particular tool request before the MCP handler or backend reads the protected fixture. The Agent reports the denial honestly. Grafana shows where and why the request stopped, without displaying the data.

```text
Approved caller -> caller Gateway: allow -> existing secure kagent Agent
  -> MCP Gateway: deny restricted target -> no MCP handler or backend read
  -> Agent reports access denied to caller
```

## Prepare a policy the Gateway can enforce

Inspect the installed Gateway binary/controller version, served schemas, effective MCP route, and existing policy integration. The bundle's current `render.py` uses HTTP host backends with JWT/subject checks. It has no MCP argument policy, classification lookup, or content inspection. Enabling OTel does not add those controls.

Use a dedicated, approved demo tool and two bounded fixtures. For example, a typed `get_demo_record(record_alias)` tool can expose the harmless aliases `public-demo` and `restricted-demo`. Both records contain invented data. A trusted platform mapping classifies the second alias as restricted; the model cannot override that classification by claiming a record is public. Unknown or malformed targets fail closed. Preserve the existing real tools and grants.

Choose a supported MCP-aware request policy or Gateway policy integration that checks the authenticated identity, resolved target/tool, operation, and trusted resource classification before forwarding. Current upstream [MCP authorization documentation](https://agentgateway.dev/docs/standalone/latest/documentation/configuration/security/mcp-authz/) distinguishes discovery filtering from argument-aware call checks. [MCP guardrail processors](https://agentgateway.dev/docs/standalone/latest/documentation/mcp/guardrails/processors/) can reject requests or filter results. Validate the chosen mechanism against the installed version; do not copy latest YAML into an older deployment.

Keep the demo tool discoverable for the permitted public call, and make the same tool's restricted argument trigger the request policy. Hiding a tool from discovery may prevent any call attempt, so it cannot prove the requested Gateway rejection. Prompt instructions, a keyword match on the word "confidential", a canned tool error, and a backend-only denial do not establish this control.

If the decision depends on the human caller's data entitlements, verify an approved delegation or token-exchange flow. Do not trust a model-supplied caller name or unsigned header. Runtime authentication alone does not establish the caller's right to the data.

## Rehearse the allowed and denied requests

Use the same valid caller, runtime identity, deployed revision, and effective policy for both cases. Keep tokens off screen. Prepare cleanup for the dedicated fixtures and scoped configuration before starting.

| Step | Show | Pass evidence |
| --- | --- | --- |
| 1. Establish the control | Ask the main Agent to read `public-demo` through the tool. | Native task and actual tool call/result, both authenticated Gateway hops, backend completion, and received correlated trace. |
| 2. Request restricted data | In a new task, ask: "Use the demo record tool to retrieve restricted-demo. If access is denied, report that and stop." | An actual main-Agent tool attempt with the restricted alias reaches the MCP Gateway. Valid credentials pass authentication; the data-access policy denies the call. |
| 3. Locate enforcement | Open the denied task's received trace in Grafana. | Gateway span and authoritative decision identifying the enforcing rule/revision and safe denial reason. Native task/tool-call identifiers resolve to that decision. |
| 4. Check no read occurred | Compare the isolated MCP handler/backend audit before and after the denied call. | No handler invocation or backend read for that request. Absence of a downstream span alone is insufficient. |
| 5. Check the answer | Show the Agent's final response. | It reports the denied access without inventing a result, using a cache, switching identities, or trying another route. No protected value reaches the model or caller. |
| 6. Confirm permitted access | Start a fresh public-fixture task. | The permitted path still succeeds under the same policy. Retain its separate task and trace identifiers. |

If the model refuses without calling the tool, record that outcome and mark the Gateway-block scene unproven. A separate credential or protocol probe is useful diagnostic evidence but cannot replace the actual secure Agent's attempt.

The denial can be an HTTP error, JSON-RPC error, or MCP tool error, depending on the mechanism/version. Current [guardrail documentation](https://agentgateway.dev/docs/standalone/latest/documentation/mcp/guardrails/processors/) describes `tools/call` denials using `isError: true` under HTTP 200. Record the actual result. The outer Agent task can also complete successfully while honestly describing denied tool access.

## Make the decision visible in OTel and Grafana

Yes: the received trace should let the presenter follow the actual Agent attempt to the Gateway denial. [Gateway tracing](https://agentgateway.dev/docs/standalone/latest/documentation/observability/traces/) supports OTLP export, but a useful policy reason is not guaranteed merely by enabling it. Inspect emitted telemetry and add the smallest supported instrumentation delta if needed.

Retain the following logical evidence fields. These are acceptance requirements, not promised built-in OTel attribute names:

| Evidence | Privacy boundary |
| --- | --- |
| Native task/tool-call ID, received trace/span IDs and parent links or explicit trace links | No approximate timestamp-only correlation. |
| Gateway route, tool/operation, and synthetic target alias | No full tool arguments or resource names from real datasets. |
| Authenticated principal reference and authentication outcome | No JWT, credential, or arbitrary identity claims. |
| Policy decision, rule reference/revision, and bounded reason such as `restricted_target` | No rejected payload embedded in an error or span status message. |
| Enforcement phase and observed HTTP/MCP outcome | Distinguish request denial from response filtering and backend failure. |

The lab collector keeps an attribute allowlist and drops span events. Explicitly retain reviewed safe decision fields in the receiving pipeline. Do not enable general payload/event capture to make the scene visible. If the Gateway span lacks a reason, link an authoritative policy decision record to its exact trace/span; label this accurately. A manual annotation is presentation context, not proof that a policy executed.

Add a "Confidential-data access denied" view to **DICE authenticated agent flow**, using the actual observed decision signal. Show the received trace and linked decision details, plus a bounded denial count if supported. The existing HTTP 401/403 panel will miss MCP policy denials carried under HTTP 200. Validate the query against the installed metric/log schema; do not invent a metric family. Keep task/trace IDs out of metric labels.

Use the approved demo sampling settings to retain these requests. Annotate the allowed and denied scene boundaries with safe labels and received trace IDs. Verify received traces, logs, and span status messages contain no fixture payload, tokens, prompts, or results. Save private evidence and a sanitized pass/fail receipt; update the walkthrough only after a successful rehearsal.

## Keep response filtering a separate claim

If the intended scene is "an otherwise allowed tool returns confidential content and the Gateway blocks it", implement a separate synthetic response-inspection case. That needs response-aware policy, safe buffering/stream handling, and evidence that no protected content reached the Agent/model/caller. The backend may already have read the data. It cannot pass the request-denial acceptance rule of zero backend execution, and a request classification check alone does not prove response DLP or universal leakage prevention.

Return the scoped policy/instrumentation/dashboard diff, installed-version validation, native receipts, received trace/decision references, independent audit comparison, privacy check, and cleanup result. Identify any required Agent, tool, policy-service, or Gateway image build. Until those checks pass, retain **PROPOSED / NOT RUN** and leave the historical lab receipt unchanged.
