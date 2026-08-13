# Independent critique prompt — Azure PostgreSQL data MCP work bundle

Copy the prompt below to a separate, read-only reviewer agent. Give it the
repository and only the listed **sanitised** live outputs. Never provide
database credentials, connection strings, real rows, or private endpoints.

```text
Act as an independent, evidence-first reviewer. Do not modify files, create
cloud resources, apply Kubernetes manifests, change database grants, use
credentials, redesign the architecture, or propose a different MCP
implementation. Assess exactly what is in this bundle:

work-agent-bundles/postgres-dab-sql-mcp-poc/
  README.md
  evidence/AZURE-FLEXIBLE-SERVER-PREBUILT-MCP-POC-2026-08-13.md
  evidence/PREBUILT-POSTGRES-MCP-SPIKE-2026-08-13.md
  work-lift-and-shift/README.md
  work-lift-and-shift/OUTSIDE-IN-VALIDATION-CHECKLIST.md
  work-lift-and-shift/CRITIQUE-PROMPT-REVIEW.md
  work-lift-and-shift/*.yaml

Raw facts: a HomeLab POC proved kagent -> pre-built PostgreSQL MCP -> temporary
Azure PostgreSQL Flexible Server using synthetic lower-case Kubernetes inventory
tables and a dedicated read-only role. The original local Kubernetes POC
remains available. The intended work target is Azure/AKS PostgreSQL using an
initial username/password URI delivered by the approved secret mechanism. UAMI
is a future target. Agent Gateway was proven for a different GitLab MCP route,
not this exact data route. Independently classify these facts; compare your
classification with the bundle only after forming your conclusion.

Classify every conclusion as VERIFIED CURRENT CAPABILITY, PROPOSED DESIGN, or
UNKNOWN / REQUIRES VALIDATION. YAML alone is not proof.

You have repository-read access and sanitised text outputs only. Do not assert
that the installed work cluster accepts a manifest or exposes a tool. For live
schema/discovery gates, state the exact output required and the pass criterion:
- kubectl api-resources output;
- kubectl explain output for AgentgatewayBackend MCP, AgentgatewayPolicy MCP
  authorization, and the relevant HTTPRoute fields; and
- RemoteMCPServer status conditions plus discoveredTools, with endpoint and
  row data removed.

Review these gates:
1. Does the bundle require the same pre-built source image used in the proof to
   be digest-pinned, internally mirrored, scanned and signed? Reconcile every
   tool in the nine-tool live discovery set against the Gateway and Agent
   allowlists. Account explicitly for every denied tool, especially
   analyze_db_health and get_top_queries, which can disclose server-wide state
   or query text independent of table grants.
2. Do database grants and curated views enforce least privilege independently
   of agent prompts, tool allowlists, and Agent Gateway? Identify arbitrary-SQL,
   schema-discovery, lateral-access, and result-size risks.
3. Are password/bootstrap secrets absent from Git, manifests, logs, evidence,
   and agent prompts? Are creation, rotation, and revocation ownership clear?
4. Are private network/DNS, TLS/CA, PostgreSQL authentication, and the data
   contract explicit and owned by the appropriate team?
5. Is the UAMI target a complete and non-contradictory migration plan? Include
   the ServiceAccount/federated credential, workload label, Entra PostgreSQL
   mapping, token acquisition/refresh, and proof. Call out that the password
   template deliberately has automountServiceAccountToken=false and must be
   changed only in a separately proven UAMI overlay.
6. Does the bundle force an Agent Gateway schema check before apply and safely
   stop if it fails? Do not claim the template matches the installed release.
   Assess the declared failureMode, session routing, timeout, rate limit, and
   whether identity-aware per-agent policy is claimed without proof.
7. Does the bundle make observed RemoteMCPServer.status.discoveredTools the
   source of truth before final Agent toolNames are set, rather than treating
   hard-coded example names as proof? Identify the required live output and
   exact expected comparison.
8. Is the MCP Service demonstrably Gateway-only at steady state? Identify what
   NetworkPolicy prevents another cluster workload from calling execute_sql
   directly, and assess the direct/gateway probe bypass and deletion gates.
9. Where do approved query results travel after PostgreSQL returns them? Trace
   KAGENT_MODEL_CONFIG to its ModelConfig/model-provider egress, retention and
   training policy. Treat an unstated destination or data-classification
   approval as a blocker, not merely unknown.
10. What can the third-party image, Kubernetes log pipeline, Gateway, kagent,
    and model logs retain? Assess SQL/result-row leakage and access to those
    logs. Also assess whether readiness/liveness signals really detect a dead
    or unauthorised database connection.
11. Are the acceptance/negative tests and evidence set sufficient for a
    non-production proof? State which live receipts are still required.
12. Are the DAB partial result and temporary Azure cleanup accurately scoped?
    Require terminal Azure resource-group deletion confirmation and identify a
    named owner for any retained backup/cleanup follow-up.

Verdict scope: GO means it is safe to run stages 1–5 of
OUTSIDE-IN-VALIDATION-CHECKLIST.md in a non-production AKS cluster using
synthetic/masked data only. It is not approval for production data, a UAMI
claim, or ongoing operation. CONDITIONAL GO must list each condition, its
owner, and the precise evidence that closes it. NO-GO means a blocker makes
that bounded proof unsafe.

Return only:
- GO, CONDITIONAL GO, or NO-GO against that defined scope.
- Critical blockers, each with file:line, failure scenario, owner, and closure
  evidence.
- Important hardening improvements, each with file:line and rationale.
- Incorrect or unsupported claims, each with file:line.
- A short ordered list of the smallest safe next actions and the exact evidence
  each must produce.
```
