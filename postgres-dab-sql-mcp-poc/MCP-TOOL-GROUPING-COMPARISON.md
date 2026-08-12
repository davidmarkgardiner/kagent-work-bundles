# MCP tool grouping and variable-passing comparison

This note explains the common MCP pattern using three examples:

1. AKS-MCP — a broad infrastructure tool server;
2. GitHub MCP — a broad product API grouped into toolsets; and
3. the PostgreSQL data MCP HomeLab POC — a deliberately narrow data-product
   adapter.

It is a design comparison, not a claim that the target data platform already
has these functions or that the HomeLab POC connects to Azure PostgreSQL.

## The common model

```text
MCP server
  groups related functions (tools)
    each function declares a name + input schema + result schema
      agent chooses an allowed function and supplies typed variables
        server authenticates and executes within its own permissions
          server returns structured data; agent explains it
```

The agent does not obtain the database, GitHub, or Azure permissions simply by
seeing a tool name. The MCP server is the execution boundary. In kagent there
is an additional binding boundary: the Agent's `toolNames` list selects which
of the server's discovered functions it may call.

## Side-by-side comparison

| Concern | AKS-MCP | GitHub MCP | Bounded PostgreSQL data MCP POC |
|---|---|---|---|
| Primary purpose | Kubernetes/AKS diagnostics and operations | Repository, issue, pull-request and CI/API work | Answer defined questions over one governed data product |
| How functions are grouped | Components such as `kubectl`, `helm`, `cilium`, `hubble`, `az_cli` | Toolsets such as `repos`, `issues`, `pull_requests`, `actions` | One small domain group: data-product metadata and approved data queries |
| Typical function shape | `call_kubectl(args)` or component-specific operation plus resource variables | `issue_read(owner, repo, issue_number)` or `get_file_contents(owner, repo, path, ref)` | `get_open_exceptions_summary(severity_min, from_date, to_date, limit)` |
| Variable style | Often command/operation arguments; powerful and potentially broad | Typed GitHub identifiers and request fields | Typed business filters with tightly constrained enums/ranges |
| Server-side authority | Azure identity + Kubernetes RBAC + configured access level/namespaces | OAuth/PAT/App identity and GitHub repository permissions | Microsoft Entra-backed read-only PostgreSQL role, restricted to curated views/procedures |
| kagent control | Bind only discovered tool names required by the Agent | Bind only the few GitHub tools needed by the role | Bind only the four-to-five data functions required by the POC |
| Ideal use | Platform investigation/operations | Software-delivery automation | Governed retrieval of business/operational facts |
| Main risk if over-broad | A general command interface can perform too much | A broad token/toolset can read or change too many repos | Arbitrary SQL could expose fields, bypass semantic rules, or create costly queries |

## How each server groups functions

### 1. AKS-MCP: components expose platform operations

AKS-MCP enables components at server startup, for example `kubectl`, `helm`,
`cilium`, and `hubble`. Its unified `call_kubectl` function accepts an `args`
input, so a representative call is:

```json
{
  "tool": "call_kubectl",
  "arguments": {
    "args": "get pods -n payments -o wide"
  }
}
```

That is useful for an operations assistant, but it illustrates why server-side
restrictions matter: the same general interface could represent many commands.
AKS-MCP's configured access level and allowed namespaces, plus the identity's
Azure/Kubernetes RBAC, remain the enforcement point. The local AKS-MCP guidance
also treats `RemoteMCPServer.status.discoveredTools` as the source of truth;
never rely on a tool list copied from an older example.

### 2. GitHub MCP: product API functions are grouped by toolset

GitHub's official MCP server groups related API functions into toolsets such as
`repos`, `issues`, and `pull_requests`. A delivery/review agent could be given
only individual read functions, for example:

```json
{
  "tool": "issue_read",
  "arguments": {
    "owner": "{{GITHUB_OWNER}}",
    "repo": "{{REPOSITORY}}",
    "issue_number": 123
  }
}
```

Or a narrowly authorised build agent may need a write operation such as a
pull-request creation function, whose variables identify repository, source
branch, target branch, title, and body. That is a different risk class and
should use a separately scoped identity and allowlist.

The official server supports enabling whole toolsets or individual tools, and
supports read-only mode. GitHub permissions still determine whether a selected
function can succeed.

### 3. Our data MCP: functions should represent approved questions, not SQL

The live HomeLab POC intentionally started with two parameterless functions:

```json
{
  "tool": "get_compliance_data_product_details",
  "arguments": {}
}
```

```json
{
  "tool": "get_open_high_severity_compliance_findings",
  "arguments": {}
}
```

That proved the kagent -> RemoteMCPServer -> MCP service -> PostgreSQL path.
The production-shaped next step is not an `execute_sql(sql)` tool. It is to
turn agreed business questions into typed functions, for example:

```json
{
  "tool": "get_open_exceptions_summary",
  "arguments": {
    "severity_min": "high",
    "from_date": "2026-08-01",
    "to_date": "2026-08-31",
    "limit": 50
  }
}
```

The MCP service validates the enum, date range, limit, caller identity, and
authorised product before using parameter binding to execute a data-owner
approved view, stored procedure, or query template. It returns only the result
schema agreed in the data contract.

## Same kagent binding pattern in all three cases

The kagent portion is structurally the same. The server can expose many tools;
the Agent receives a deliberate subset.

```yaml
tools:
  - type: McpServer
    mcpServer:
      apiGroup: kagent.dev
      kind: RemoteMCPServer
      name: {{MCP_SERVER_NAME}}
      namespace: kagent
      toolNames:
        - {{TOOL_1}}
        - {{TOOL_2}}
```

Examples of sensible subsets:

| Agent role | Tools it should receive |
|---|---|
| AKS read-only investigator | `call_kubectl` only, with AKS-MCP configured read-only and namespace-limited; or dedicated read tools if available |
| GitHub issue reviewer | `issue_read`, `get_file_contents`, `pull_request_read` |
| GitHub PR publisher | only the necessary branch/file/PR write tools, under a separate write identity |
| Data compliance analyst | `get_data_product_details`, `get_open_exceptions_summary`, and other approved read functions |

## Recommended Azure data-MCP function contract

Define each tool like an API endpoint. The data team owns its meaning; Platform
owns deployment, binding, identity plumbing, and evidence.

| Contract element | Example for `get_open_exceptions_summary` |
|---|---|
| Purpose | Answer “how many qualifying exceptions are open?” |
| Inputs | `severity_min` enum, bounded `from_date`/`to_date`, `limit` integer |
| Validation | Allowlisted severities; maximum 31-day range; `1 <= limit <= 100` |
| Data boundary | One curated Azure PostgreSQL view or approved semantic/data-mesh query |
| Output | Count, masked summary rows, freshness timestamp, correlation/query ID |
| Identity | AKS Workload Identity -> Microsoft Entra -> dedicated read-only PostgreSQL role |
| Deny cases | Unauthorised product, unsupported field, invalid range, excessive limit, any write request |
| Evidence | Tool name, redacted inputs, identity/audit correlation, result hash/count, policy decision |

## The key conclusion for the data team

The team does not need to design a generic “AI database.” It needs to choose a
small data product and express four or five useful, governed questions as
functions. We then decide whether an existing MCP/API already exposes those
functions; if not, the thin MCP adapter simply turns those validated functions
into parameterised calls to Azure PostgreSQL or the approved data-mesh layer.

## References

- [AKS-MCP upstream](https://github.com/Azure/aks-mcp) — components, access
  levels, namespaces, and `call_kubectl` behaviour.
- [GitHub MCP server](https://github.com/github/github-mcp-server) — toolsets,
  individual tools, and read-only configuration.
- [Repo-local AKS-MCP binding guidance](../../../platform/aks-mcp/README.md)
- [Repo-local PostgreSQL POC evidence](README.md)
- [GitLab data-contract discovery issue](GITLAB-ISSUE-DATA-CONTRACT-AUTH-DISCOVERY.md)
