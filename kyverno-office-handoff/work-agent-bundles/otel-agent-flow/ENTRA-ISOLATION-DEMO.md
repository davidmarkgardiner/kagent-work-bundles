# Demonstrate per-agent Entra access isolation

Use two existing approved agent identities with distinct resource permissions. An allowed own-resource call must succeed. A cross-resource call, missing token, and wrong audience must be rejected before reaching the MCP backend. Keep agent identity, gateway authorization, network denial, and sandbox lifecycle evidence separate.

## Existing evidence boundary

The earlier tenant-isolation bundle records a disposable JWT issuer rehearsal on 2026-09-16. It checked allowed A2A/MCP paths and denied cross-tenant, JWT, tool, network, RBAC, and admission attempts. Its Entra overlay passed schema validation. That receipt explicitly does not prove a live Entra tenant, work-token broker, or AKS identity flow. The workflow demo's labelled fixture repeats the allow/deny story using one fixture agent and fixed aliases. It does not create two Entra identities or two tenant-isolated agents.

Do not copy that older bundle's kagent/Substrate manifests into the alpha runtime used by this demo. Port only the reviewed identity and policy contract against the installed CRDs. Preserve existing work deployments.

## Establish the actual identity path

1. Identify which existing mechanism is deployed. A caller UAMI authenticating to A2A is distinct from an agent identity authenticating to MCP. An Entra Agent ID blueprint and child identity is also distinct from ordinary workload identity federation.
2. Verify the selected agent-to-gateway tokens use the actual Entra issuer, MCP audience, and approved application role or subject policy. Keep caller A2A and MCP permissions separate. Check effective child-identity grants and inherited permissions when using Agent ID.
3. Confirm agentgateway validates signature, issuer, audience, expiry, and the intended subject/resource authorization. Keep upstream provider credentials separate from agent authentication. Do not treat a decoded but unvalidated JWT as an authenticated identity.
4. Verify the existing workload broker refreshes short-lived tokens. Do not create or expand Entra identities or grants merely to populate the demo. Have the existing identity owner supply the approved test credentials through the normal secret/broker mechanism.
5. Restrict direct backend/controller access with the existing network, RBAC, and reference policies. A JWT-protected gateway does not by itself block a direct Service bypass.

Microsoft's identity and claim contracts are documented at:

- https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation
- https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-blueprint
- https://learn.microsoft.com/en-us/entra/agent-id/autonomous-agent-authentication-authorization-flow

## Run bounded live probes

The dashboard's normal prompt path calls the internal kagent gRPC API. It is not an Entra-protected front-door test, and its fixed user partition is not an identity credential. Use `isolation_demo.py` for this separate security demo. It calls the approved protected MCP URLs directly and emits client spans with trace context. It does not invoke an agent or execute a tool.

1. Copy `deploy/isolation-plan.json.example` outside the repository. Fill approved HTTPS gateway and private metrics URLs. Select the real backend's unlabelled total-request counter. Keep the counter path restricted to the operator and separate from the audience-facing UI.
2. Use an isolated rehearsal backend or a quiet window with no other request source. Counter resets or unrelated traffic invalidate the comparison. Ensure the counter measures requests at the protected backend, not gateway attempts. Counter collection itself must not increment it.
3. Configure the exact expected denial code. A correct-audience token lacking the required role normally exercises authorization denial. A cross-resource token for a different audience can instead exercise authentication rejection. Record which boundary each test covers rather than changing expectations after a failed run.
4. Populate the plan's named credential environment variables from the approved broker. Do not put bearer values in the plan, command line, UI, OTel, or repository. HTTPS certificate validation is mandatory. Add `--ca` only for the approved private CA.
5. Run from an approved in-cluster utility workload with collector access, or an approved operator connection. The application image contains the probe module. Allow the utility namespace in `collector.sourceNamespaces` when required. Configure `OTEL_HTTP_ENDPOINT` to the existing collector receiver, for example `http://flow-collector.agent-flow-demo.svc.cluster.local:4318` inside the cluster.

```bash
python3 isolation_demo.py \
  --plan '{{PRIVATE_ISOLATION_PLAN}}' \
  --output '{{PRIVATE_EVIDENCE_DIRECTORY}}/isolation-probes.json'
```

The probe performs MCP initialize requests with JSON or completed SSE responses. It follows no redirects. A positive test requires a valid initialize response and a rising backend request counter. A negative test requires the expected 401 or 403 and zero backend delta. It never retries denied requests. The receipt contains aliases, trace IDs, HTTP status, and counter deltas. It contains no tokens or target URLs. Check `otelExported` for each case, then confirm actual delivery in the UI and native gateway records.

## Show and assess the result

Open the UI in Visual flow or Logs. Select the received probe trace in Recent traces. The observed-operation card shows identity/resource aliases, expected and observed HTTP status, backend delta, and the client-probe evidence source. Join its W3C trace to native gateway auth events. Client-probe metadata is not a validated Entra claim and cannot independently establish the issuer or policy configuration.

Run and retain this matrix:

| Test | Required observation |
| --- | --- |
| Agent A to resource A | Valid MCP initialize response and backend counter increase |
| Agent B to resource B | Valid MCP initialize response and backend counter increase |
| A to B and B to A | Exact configured rejection, native gateway denial, zero backend delta |
| No token and wrong audience | Exact configured rejection, native gateway denial, zero backend delta |
| Expired token | Rejection and zero backend delta using an owner-provided expired test token |
| Refresh | An authorized agent still succeeds after the previous token expires, using refreshed credentials |
| Direct backend/controller attempt | Real network or authorization denial from the untrusted namespace |
| Actual agents with bound identities | Each real agent calls the protected MCP route with its own broker-supplied identity. Join native actor identity to gateway principal aliases and reproduce allow/deny outcomes. Operator token probes alone do not prove this binding. |
| Native sandbox execution | Independent restore, checkpoint, actor identity, and final suspend evidence |

The probe intentionally leaves `entraIssuerAndPolicyVerified`, `directBackendBypassTested`, and `tokenRefreshTested` false. Attach the native gateway policy/decision receipts, effective identity authorization review, direct-path tests, and refresh proof before asserting those results in workplace acceptance. A 403 can also come from a proxy or WAF, so status alone does not identify the enforcing boundary.
