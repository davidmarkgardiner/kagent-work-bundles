# Manifest index

Implementation lives at `agents/cluster-health-sentinel/`. Not duplicated here —
one source of truth.

| File | Phase | Kinds | What it is |
|---|---|---|---|
| `01-rbac.yaml` | 1 | ServiceAccount, ClusterRole, ClusterRoleBinding, Role, RoleBinding | Read-only cluster access. No secrets, no `pods/log`, verbs limited to get/list/watch. ConfigMap writes namespaced to `kagent` only. |
| `02-collector-configmap.yaml` | 1+2 | ConfigMap | `collect.py` — the collector and baseline detector. ~850 lines, stdlib only. |
| `03-cronjob.yaml` | 1 | CronJob | `*/10 * * * *`, `concurrencyPolicy: Forbid`, `CLUSTER_NAME` env. |
| `04-eventsource-webhook.yaml` | 2 | ConfigMap, EventSource | The sentinel's event ingress. **No Service declared** — Argo Events creates it. |
| `05-sensor-cluster-health.yaml` | 2+4 | Sensor | Baseline transitions + allowlisted cluster-scope alerts. **No raw-event dependency.** |
| `06-workflow-cluster-health-triage.yaml` | 2+3 | ConfigMap, WorkflowTemplate | Triage workflow + `REPORT_MODE` switch. Mutex, incident_key, A2A call. |
| `07-orchestrator-agent.yaml` | 3 | Agent (`kagent.dev/v1alpha2`) | The read-only orchestrator. |
| `08-alertmanager-route.yaml` | 4 | ConfigMap, AlertmanagerConfig | Baseline thresholds + cluster-scope alert allowlist. **Route untested.** |
| `09-fault-injection.yaml` | test | Namespace, Deployment ×2, PVC, ConfigMap | Injection cases with acceptance criteria. **Never run.** |

## Key snippets

### Agent-type tool ref — verified syntax

Confirmed against the vendored CRD (`kagent/go/api/v1alpha2/agent_types.go`:
`Agent *TypedReference`, CEL rule *"type.agent must be specified for Agent
filter.type"*) and the working `agents/kagent-triage/a2a-hello-poc/`. Reached
`Accepted=True` / `Ready=True` on RED via server dry-run.

```yaml
tools:
  - type: McpServer
    mcpServer:
      apiGroup: kagent.dev
      kind: RemoteMCPServer
      name: kagent-tool-server
      toolNames:
        - k8s_get_resources        # read-only set only —
        - k8s_describe_resource    # every mutating tool deliberately absent
        - k8s_get_events
        - k8s_get_resource_yaml
        - k8s_get_cluster_configuration
        - k8s_get_available_api_resources
        - k8s_check_service_connectivity
  - type: Agent
    agent:
      apiGroup: kagent.dev
      kind: Agent
      name: k8s-readonly-agent
      namespace: kagent
```

### Right-sizing an agent (the 100m default tax)

kagent agents inherit `requests.cpu: 100m, memory: 384Mi` unless set. RED runs 31
agents = 3830m = 51% of the cluster. Supported one-line fix:

```yaml
spec:
  declarative:
    deployment:
      resources:
        requests:
          cpu: 10m
          memory: 256Mi
```

### Untrusted payload — do NOT interpolate into a script body

```yaml
# WRONG — Argo does literal text substitution; a payload containing """ escapes
# and executes as Python with the workflow SA's credentials.
source: |
  payload_raw = r"""{{inputs.parameters.trigger-payload}}"""

# RIGHT — the payload stays data.
env:
  - name: TRIGGER_PAYLOAD
    value: "{{inputs.parameters.trigger-payload}}"
source: |
  payload_raw = os.environ.get("TRIGGER_PAYLOAD", "{}")
```

This pattern appears elsewhere in the repo. Worth auditing.

### Event timestamps — assume MicroTime

```python
# WRONG — returns None for every modern event, and callers guarding with
# `if ts and ts < cutoff` then count it regardless of age.
datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")

# RIGHT — lastTimestamp is often null; eventTime is a MicroTime with fractional
# seconds ("2026-07-15T10:27:13.173860Z").
datetime.fromisoformat(value.replace("Z", "+00:00"))
```
