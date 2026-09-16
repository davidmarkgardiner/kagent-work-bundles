# AKS-MCP tool catalog for this bundle

This catalog is only for mechanical Agent-CR validation. Runtime discovery of
the selected `RemoteMCPServer` remains mandatory.

## Read-Only Tools (safe for triage agents)

| Tool Name | Description |
|-----------|-------------|
| `call_az` | Bounded Azure CLI reads and approved cluster-user credential acquisition against the explicit target |
| `call_kubectl` | Kubectl diagnostic operations constrained by target Kubernetes read-only authorization |

## Write Tools (remediation agents only)

| Tool Name | Description | Risk |
|-----------|-------------|------|
| `none` | This bundle exposes no write tool | High |
