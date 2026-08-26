# Platform MCP catalogue for application onboarding

This is an onboarding catalogue, not a declaration that every entry is
deployed. A tool is offered to a customer only after its target-environment
status and evidence are recorded.

## Catalogue states

| State | Customer meaning |
|---|---|
| POC candidate | May be selected for a bounded proof after named owners approve it |
| Available | Target environment has current deployment, identity, tool and denial evidence |
| Proposed | Design exists but is not selectable |
| Blocked | Known condition prevents selection |

## Current catalogue

| MCP capability | State | Candidate tools | Resource boundary | Notes |
|---|---|---|---|---|
| PostgreSQL schema discovery | POC candidate | `list_schemas`, `list_tables`, `describe_table` | Dedicated MCP identity plus database grants; metadata only | Best first proof. HomeLab verified with MCPg v0.7.1; work overlay still requires validation |
| PostgreSQL approved-view query | Proposed extension | `run_select` | SELECT-only role and owner-approved views | Requires data owner, model-egress and result-redaction approval |
| GitLab review workflow | Proposed | Exact branch/file/MR/note tools discovered from approved server | Approved project/group and non-production branch | Existing bundle still has TODO evidence; do not advertise as available |
| Kubernetes namespace diagnostics | Proposed | Read-only list/get/log/event tools only | Dedicated namespace/cluster identity and RBAC | No shared fleet reader for tenant use; cluster/context crossover must fail |
| Argo OpenAPI tools | Blocked | None | N/A | Inspected agentgateway CRD lacks the OpenAPI target shape |
| Bring-your-own MCP | Separate workflow | Determined after inventory | Server-specific | Not part of the first application onboarding POC |

## Attaching a platform MCP

The application team requests:

1. one catalogue entry/version;
2. exact tool names;
3. exact target resource/data scope;
4. read/write classification and business reason;
5. expected rate and timeout; and
6. data/logging restrictions.

The platform and MCP owner then provide:

- a private MCP backend and identity;
- a gateway route and fail-closed backend;
- a gateway tool-name allowlist;
- direct-backend network denial;
- resource-level authorization in the MCP/backend; and
- positive and negative evidence.

The application receives the gateway MCP URL. It does not receive the MCP
credential.

## Bring-your-own MCP promotion gate

Keep this separate from normal application onboarding. Require at least:

- named owner, source repository, version and immutable image provenance;
- complete discovered tool inventory and read/write/destructive classification;
- credential source and rotation ownership;
- inbound authentication and outbound egress destinations;
- resource/tenant isolation independent of tool-name filtering;
- prompt-injection and untrusted-output handling;
- direct-access denial and audit/redaction evidence; and
- rollback, expiry, offboarding and incident-response procedures.
