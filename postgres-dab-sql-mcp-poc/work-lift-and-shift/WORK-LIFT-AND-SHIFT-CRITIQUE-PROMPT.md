# Independent critique prompt — Azure PostgreSQL data MCP work bundle

Copy the prompt below to a separate, read-only reviewer agent. Give it this
repository and the intended work cluster's **sanitised** API/schema outputs;
do not provide database credentials, connection strings, real records, or
private endpoints.

```text
Act as an independent, evidence-first reviewer. Do not modify files, create
cloud resources, apply Kubernetes manifests, change database grants, or use
credentials. Review this exact bundle:

work-agent-bundles/postgres-dab-sql-mcp-poc/
  README.md
  evidence/AZURE-FLEXIBLE-SERVER-PREBUILT-MCP-POC-2026-08-13.md
  work-lift-and-shift/

Context: a HomeLab POC live-proved kagent -> pre-built PostgreSQL MCP ->
temporary Azure PostgreSQL Flexible Server using synthetic lower-case
Kubernetes inventory tables and a dedicated read-only role. The temporary
Azure resource group was deleted after the proof. The original local Kubernetes
POC remains available. The intended work target is Azure/AKS PostgreSQL using
an initially supplied username/password connection URI delivered through the
approved secret mechanism. UAMI/AKS Workload Identity is a future target, not
yet proof. Agent Gateway is desired as the MCP traffic policy/telemetry route;
the same repository has proven it for a GitLab MCP route, not for this exact
data path.

Classify every conclusion as VERIFIED CURRENT CAPABILITY, PROPOSED DESIGN, or
UNKNOWN / REQUIRES VALIDATION. Do not promote a design claim to a proof merely
because YAML exists.

Review these gates:
1. Is the pre-built MCP image digest-pinned, internally mirrored, scanned and
   signed? Is its restricted mode accurately described, given execute_sql?
2. Do database grants/views enforce least privilege independently of agent
   prompts, tool allowlists and Agent Gateway? Identify any arbitrary SQL,
   schema-discovery or lateral-access risks.
3. Are password/bootstrap secrets absent from Git, manifests, logs, evidence,
   and agent prompts? Is rotation/revocation clear?
4. Are the network/TLS/Private Endpoint/private DNS and PostgreSQL authentication
   assumptions explicit and owned by the appropriate team?
5. Is the claimed UAMI path complete? Call out every missing dependency:
   federated identity, ServiceAccount/workload label, Entra PostgreSQL mapping,
   token acquisition/refresh by the selected image or approved adapter, and
   independent evidence.
6. Verify the actual installed Agent Gateway CRD schema rather than assuming the
   template applies. Assess the route, timeouts, fail-closed behavior, and
   whether identity-aware per-agent policy is really available.
7. Confirm `RemoteMCPServer.status.discoveredTools` is the source of truth and
   each Agent mounts only the exact minimum discovered tools.
8. Assess the acceptance/negative tests and evidence set. State what needs a
   live receipt before any production-like use.
9. Check that the DAB partial result and the temporary-Azure cleanup are neither
   hidden nor overstated.

Return only:
- GO, CONDITIONAL GO, or NO-GO.
- Critical blockers (must fix before a work proof).
- Important hardening improvements (not blockers).
- Any incorrect or unsupported claims, with file/section references.
- A short ordered list of the smallest safe next actions and the exact evidence
  each must produce.
```
