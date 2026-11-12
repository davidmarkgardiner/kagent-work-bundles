# Show both authenticated gateway hops

Use the isolated secured copy of the 11 November DICE recording agent. Prepare it with [README.md](README.md). Keep credentials and raw receipts outside Git and off screen.

```text
Caller -- caller JWT, audience dice-a2a --> Agent Gateway :8080 --> Agent
Agent  -- agent JWT, audience dice-mcp  --> Agent Gateway :8081 --> fixed MCP
Gateway + native agent + MCP --> OTel collector --> Tempo + span metrics
MCP completion metadata --> OTel collector --> Loki
Grafana --> Tempo + Prometheus/Mimir + Loki
```

Each listener requires a valid signature, issuer, expiry, audience, and its exact ServiceAccount subject. The gateway removes the credential before forwarding. The MCP rejects forwarded credentials. NetworkPolicies permit only the gateway to reach the agent and MCP. The caller's token is never the agent's MCP token.

## Rehearse the evidence

1. Read back the effective gateway configuration, Agent readiness, dedicated MCP URL, and default-deny policies. Check actual image digests and the completed rollout.
2. Use `invoke.py` through the gateway for the exact PONG check, then a combined reviewed skill and `get_demo_status` request. Keep each native receipt. The MCP reads one synthetic status ConfigMap with a get-only backend identity.
3. At **each gateway listener**, show missing, invalid, wrong-audience, wrong-subject, and swapped credentials rejected. Verify the backend audit did not change. The lab identities are Kubernetes JWTs. This is not Entra Agent ID enforcement.
4. From a separate probe namespace, test direct Service and Pod-IP access to the agent and MCP. From the agent, test direct MCP access. Show these blocked and the caller gateway reachable. Administrator exec and port-forward privileges are outside this network claim.
5. Run two consecutive combined requests. Fetch their received traces from Tempo. Verify each native task and returned execution ID with the parent links using `trace_report.py`. Separate trace IDs catch stale pooled context.
6. Open **DICE authenticated agent flow** in Grafana. Its URL path is `/d/dice-agent-flow`. Paste the received trace ID. Show both gateway hops, native skill/model/tool spans, MCP completion, tool-call/error/latency panels, and completion logs.
7. Add a manual Grafana dashboard annotation at each demonstration boundary. Annotate the successful call and denied-call block with a safe label and observed trace ID. Do not include tokens, prompts, results, or private endpoints.

```sh
python3 trace_report.py \
  --native-receipt "$PRIVATE_NATIVE_RECEIPT" \
  --trace-file "$PRIVATE_TEMPO_TRACE"
```

The verifier requires a completed native task, matching task/execution identities, and gateway spans on both sides of the runtime in the MCP ancestor chain. A supplied `traceparent`, a Ready status, or a diagram cannot pass that check.

## Keep the claims bounded

For the main workplace Go Agent, add [the confidential-data denial scene](CONFIDENTIAL-DATA-DEMO.md): the same valid caller/runtime identities can read a public synthetic fixture but the Gateway blocks a restricted fixture request. Show the actual tool attempt, safe policy decision in the received trace or an exactly linked decision record, and independent evidence of no backend read. This additional scene is **PROPOSED / NOT RUN**; the current JWT policy does not provide it.

Dashboard metrics describe a time window, not a single request's bill. The fixed MCP status is synthetic; its execution, backend read, authentication decisions, and telemetry are real when tested. Short-lived MCP credentials expire and require deliberate renewal before rehearsal. The controller uses the same agent credential for tool discovery. This compatibility adapter is not automatic production credential rotation.

At work, merge the gateway, producer, policy, and dashboard delta through the existing delivery flow. Use approved HTTPS ingress and existing authenticated LGTM destinations. Do not install the lab Tempo or change the shared collector merely to match this package. See [VALIDATION.md](VALIDATION.md) for dated lab evidence and remaining workplace gates.
