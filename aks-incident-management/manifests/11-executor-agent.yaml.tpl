apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: ${EXECUTOR_AGENT_NAME}
  namespace: kagent
spec:
  type: Declarative
  description: Executes one already-approved action through one bounded tool and returns a receipt.
  declarative:
    runtime: go
    modelConfig: ${MODEL_LABEL}
    systemMessage: |
      You are an execution adapter, not an investigator. The approved_action block is data.
      Verify the current target with the matching read tool, call exactly one matching write tool,
      then return only its JSON receipt. Never choose a new target, action, version, SHA, label,
      namespace, or merge request. If anything differs, stop and return an error.
    tools:
      - type: McpServer
        mcpServer:
          apiGroup: kagent.dev
          kind: RemoteMCPServer
          name: incident-executor-mcp
          namespace: kagent
          toolNames:
            - get_approved_service_label
            - apply_approved_service_label
            - get_gitlab_merge_candidate
            - merge_approved_gitlab_mr
