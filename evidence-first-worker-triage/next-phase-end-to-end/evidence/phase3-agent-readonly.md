# Phase 3 — Agent read-only proof (tool inventory)

`kubectl get agent k8s-readonly-agent -n kagent -o yaml`, `red`, 2026-07-20.

## Full tool inventory (verbatim from the live Agent CRD)

```text
k8s_check_service_connectivity
k8s_get_events
k8s_get_available_api_resources
k8s_get_cluster_configuration
k8s_describe_resource
k8s_get_resource_yaml
k8s_get_resources
k8s_get_pod_logs
```

Eight tools total, all read-only (`Get*`, `Describe*`, `Check*`). No
`create`/`apply`/`patch`/`delete`/`label`/`annotate`/`exec` tool is bound to
this agent — this is the complete `spec.declarative.tools[].mcpServer.toolNames`
list, not a filtered subset.

## Defense in depth (prompt-level, in addition to tool-level)

The agent's `systemMessage` independently enforces the same boundary:

> You only have read-only tools. Do not ask for or imply use of mutation
> tools. Do not create, apply, patch, delete, label, annotate, or execute
> commands in pods. If a user asks for a change, refuse the change and
> provide a safe diagnostic summary plus a recommended manual approval path.

## Behavioural confirmation (from real ticket bodies, gate 0 / phase 1)

Every agent diagnosis captured in this pass (tickets #448, #450-452, #453,
#456-459, #467-468, #474, #478-479) ends with a "Recommended Human-Approved
Next Steps" section explicitly marking any change as requiring human
approval, e.g. (#450): *"If unintended: Remove the pod or update its
container command... **(Requires human approval — do not auto-remediate.)**"*
— the agent never executed or proposed direct action, only advice routed
through the ticket.

```text
ARGO_AGENT_READ_ONLY: yes
```
