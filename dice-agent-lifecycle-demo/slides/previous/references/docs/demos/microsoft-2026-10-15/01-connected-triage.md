# Demo 1: connected triage, agents and tools

Time: about three minutes. Lead with: “The aim is an investigation that arrives with evidence and a clear human handoff.”

## Recorded incident path, ready without a cluster

```sh
sed -n '1,100p' work-agent-bundles/evidence-first-worker-triage/next-phase-end-to-end/evidence/phase5-value.md
sed -n '1,80p' work-agent-bundles/evidence-first-worker-triage/next-phase-end-to-end/evidence/phase3-agent-readonly.md
```

Explain the recorded path: Alloy collects logs / events, Vector redacts and normalizes, Kafka delivers, Argo coordinates, a read-only kagent agent investigates, and the workflow creates or updates a sandbox GitLab ticket. The scheduling-failure example includes the scheduler's reason and agent diagnosis. The second file records eight read-only tools for the tested triage agent.

These commands display retained proof. They do not trigger a fresh incident, prove current connectivity, or create a ServiceNow incident. ServiceNow remains the formal escalation design in this pack.

## Optional live discovery, only after rehearsal

Fill these values privately. Do not run the block with unresolved placeholders.

```sh
export DEMO_CONTEXT='{{APPROVED_LAB_CONTEXT}}'
export DEMO_AGENT_NS='{{AGENT_NAMESPACE}}'
export DEMO_AGENT='{{READ_ONLY_AGENT_NAME}}'
export DEMO_CONTROLLER_NS='{{CONTROLLER_NAMESPACE}}'
export DEMO_TARGET_NS='{{SYNTHETIC_WORKLOAD_NAMESPACE}}'

kubectl --context "$DEMO_CONTEXT" --request-timeout=10s -n "$DEMO_AGENT_NS" get agents \
  -o 'custom-columns=NAME:.metadata.name,TYPE:.spec.type,CONDITIONS:.status.conditions[*].type,STATUS:.status.conditions[*].status'
kubectl --context "$DEMO_CONTEXT" --request-timeout=10s -n "$DEMO_AGENT_NS" get remotemcpservers \
  -o 'custom-columns=NAME:.metadata.name,TOOLS:.status.discoveredTools[*].name'
kubectl --context "$DEMO_CONTEXT" --request-timeout=10s -n "$DEMO_AGENT_NS" get agent "$DEMO_AGENT" -o json \
  | jq '{name:.metadata.name,tools:.spec.declarative.tools}'
```

Expected: the chosen agent is ready, the intended MCPs advertise the expected tool names, and the agent selects only approved read operations. The field projection is intended for the declarative 0.x contract. Discover the installed CRD before rehearsal if using a different version. Missing fields are a schema mismatch to investigate, not a successful gate.

For a prepared Grafana service, run the existing helper with its actual namespace, Service and datasource UID:

```sh
scripts/observability/smoke-grafana-mcp.sh \
  --context "$DEMO_CONTEXT" \
  --namespace '{{GRAFANA_MCP_NAMESPACE}}' \
  --service '{{GRAFANA_MCP_SERVICE}}' \
  --prom-datasource-uid '{{PROMETHEUS_DATASOURCE_UID}}' \
  --prom-query 'count(up)'
```

Expected: MCP initialization and tool discovery, datasource listing and a non-empty Prometheus response. This calls the MCP Service directly through a temporary port-forward. It demonstrates the tool/data path, not gateway policy or model-mediated investigation. Use only the approved synthetic lab datasource. The helper owns cleanup.

## Optional live agent question

Only run after checking the actual tool inventory and downstream RBAC. This consumes a small model call and can persist an agent task. The helper invokes the controller directly via its managed temporary port-forward. It does not demonstrate gateway authentication.

```sh
scripts/kagent-a2a-invoke.sh \
  --context "$DEMO_CONTEXT" \
  --controller-ns "$DEMO_CONTROLLER_NS" \
  --ns "$DEMO_AGENT_NS" \
  --agent "$DEMO_AGENT" \
  --timeout 45 \
  --text "Investigate namespace ${DEMO_TARGET_NS} using only the approved read-only tools. Report observed health, evidence, uncertainty and the next operator action. Do not change resources, create tickets or submit workflows."
```

Success requires an answer grounded in a real tool result and a matching runtime/tool trace available privately. A plausible answer alone is insufficient. If it times out, return to the retained incident evidence. Do not repair the provider route while screen sharing.

Close with: “The investigation can be automated while remediation authority stays in a separate approved workflow.”
