# ServiceNow integration

## Existing delivery and next evolution

The pod lead confirms the ServiceNow instance and integrations are already built. This guide describes the next reviewed integration contract and version-specific acceptance; it is not a claim that the existing service has yet to be created. The [historical record](historical-achievements.md) preserves completion separately from exact dates, go-live evidence and further scope.

ServiceNow incident intake and agent execution are separate responsibilities. The gateway can route or transform a body; durable processing owns acknowledgement, idempotency, retries, timeouts, task tracking and controlled ticket updates.

```text
ServiceNow event -> authenticated Istio entry -> eligible payload
    -> durable incident state / trusted target mapping
    -> agentgateway -> kagent Agent -> approved specialist/tool reads
    -> reviewed result -> controlled ServiceNow update -> read-back
```

A direct outbound REST call can be a small PoC if it supplies the correct A2A contract. Raw incident JSON needs a version-tested transformation or adapter. Argo Events/Workflows remain appropriate when durable handling or fixed execution gates are needed; a routing rule alone does not provide them.

## Version-aware continuation of yesterday's work

The 17 November incident-ingress bundle remains the canonical source for its existing PoC, values discovery and auth-denial requirements. It used an older A2A route/envelope. For kagent 1.0.1, use the new `/agents/{namespace}/{name}` contract and current card, update the body transform and caller, and retest response/task parsing. Do not copy `/api/a2a/...` or `/api/a2a-sandboxes/...` rewrites into the new deployment.

The downloadable [1.0 HTTPRoute example](downloads/servicenow-a2a-route.yaml) fixes the target to the canary Agent. It is only a route: it generates no Istio JWT authentication, gateway authorisation or incident transformation. Its Gateway parent is a placeholder, so validate ownership/status and attach the reviewed policies before exposing it.

## Pilot contract

Use one queue and 2–3 supported incident patterns. Resolve cluster/service/namespace through trusted inventory. Treat incident descriptions and retrieved content as untrusted. Record incident/event correlation, payload version, ownership, eligibility, timestamps, task/context IDs and final outcome.

Deduplicate on stable incident/event identity and a trusted workload identity. Literal generated Pod names churn; logs and Kubernetes Events need a common derivable key rather than an assumed application label. Bound retries and concurrency, avoid loops from our own ticket updates, and treat an ambiguous write response as a read-back/reconciliation case before retrying.

The first result contains facts with evidence, uncertainty, missing information, recommended checks and an explicit handoff. Internal work notes and customer-visible comments have different publication rules. Begin with SRE review. Ticket writing has a separate narrowly scoped identity and allowed fields; investigation tools stay read-only.

## Acceptance

Prove one allowed end-to-end investigation and, separately, an authorised ticket write with read-back. Deny missing/invalid/wrong-audience/no-role/wrong-subject requests before execution. Exercise duplicates, malformed payload, arbitrary target injection, prompt injection, unavailable tools, timeout and ambiguous update outcome. Verify both gateway and receiving/backend evidence. Earlier transformation checks retain their original version and scenario scope. Obtain receiving-environment evidence for the new runtime and ServiceNow path.

Original bundle: [ServiceNow incident ingress](https://github.com/davidmarkgardiner/kagent-public/tree/main/platform/agentgateway/servicenow-incident-ingress). Its portable MkDocs project can remain a focused sub-guide; this handbook owns the current platform-level contract.
