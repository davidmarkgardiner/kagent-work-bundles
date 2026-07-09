# Proxmox Kimi A2A and Control-Plane Recovery Evidence

Date: 2026-07-09

## Summary

The Proxmox kagent smoke path was moved from the local Qwen route to the
external Kimi route through agentgateway for a low-token POC. Kimi was proven
at both layers:

- agentgateway direct route: HTTP 200 from `/kimi/v1/chat/completions`
- kagent A2A route: `smart-triage-deployment-specialist` returned the required
  marker through its A2A endpoint

This evidence is a separate manual fan-out/model-path proof. It is not the same
continuous `run_id` as the earlier Grafana crashloop alert-intake run, and it
should not be cited as proving `Grafana alert -> Kimi -> eval` in one run.

During rollout, the control-plane VM became memory-starved because multiple
smart-triage agent pods were scheduled on `{{CONTROL_PLANE_NODE}}`. The control-plane API and
SSH then timed out. Recovery was done by stopping kubelet on `{{CONTROL_PLANE_NODE}}`,
terminating `kagent-adk static` agent processes on that node, patching
smart-triage agents to remove control-plane tolerations, restarting kubelet, and
scaling most smart-triage specialists to zero until worker capacity is fixed.

## Evidence

### Provider Route

Kimi route through Proxmox agentgateway returned HTTP 200:

```text
HTTP_STATUS=200
content: OK
usage: prompt_tokens=13, completion_tokens=19, total_tokens=32
```

The Kimi model rejects `temperature: 0`, so the live `agentgateway-kimi`
ModelConfig was patched to omit `openAI.temperature`.

### kagent A2A

Direct A2A request to the deployment specialist returned HTTP 200 and completed:

```text
SPECIALIST_DEPLOYMENT: completed
EVIDENCE_SOURCE: synthetic-flux
APP_RESOLVED: checkout-api
VERDICT: bad_deploy
CURRENT_STATE_VERIFIED: yes
RECOMMENDATION: continue to HITL before any sync or rollback
```

The response metadata reported kagent usage:

```text
run_id=triage-smoke-20260709100844-manual-fanout
promptTokenCount=253
candidatesTokenCount=265
totalTokenCount=518
state=completed
```

### Control-Plane Failure Mode

Observed on `{{CONTROL_PLANE_NODE}}` before relief:

```text
load average: 163.18, 125.23, 64.45
Mem available: ~31 MiB
memory PSI full avg60: ~54
io PSI full avg60: ~12
kube-apiserver RSS: ~1.9 GiB
many kagent-adk processes: ~248 MiB each
```

Symptoms:

- direct `kubectl` timed out during TLS handshake
- API tunnel through `{{WORKER_NODE_A}}` also timed out during TLS handshake
- CRI/runtime calls on the control plane timed out
- QEMU guest agent on the VM was not reliable under pressure

### Recovery State

After relief:

```text
Mem available: ~4.2 GiB
kubelet: active
direct kubectl /readyz: ok
control-plane load decreasing
```

Initial recovery scale state:

```text
smart-triage-deployment-specialist    1/1  running on worker
smart-triage-gitlab-lite-specialist   1/1  running on worker
smart-triage-gitops-specialist        0/0
smart-triage-grafana-specialist       0/0
smart-triage-incident-commander       0/0
smart-triage-knowledge-specialist     0/0
smart-triage-kubernetes-specialist    0/0
smart-triage-network-specialist       0/0
smart-triage-policy-specialist        0/0
smart-triage-trace-specialist         0/0
```

## Historical Capacity Blocker

Full fan-out was not safe before the capacity fix:

- `{{WORKER_NODE_A}}` is at the kubelet pod limit.
- `{{WORKER_NODE_B}}` is near requested-memory saturation.
- `{{CONTROL_PLANE_NODE}}` should not host the smart-triage agent fan-out.

Before re-enabling all specialists, either add worker capacity, reduce pod
count, or give the smoke specialists a dedicated worker placement with enough
pod and memory headroom.

## Capacity Fix Applied

The full smart-triage fan-out was re-enabled after adding worker headroom and
pinning the specialist pods away from the control plane.

Actions applied:

```text
{{WORKER_NODE_A}} kubelet extra args: --max-pods=180
smart-triage specialist nodeSelector: kubernetes.io/hostname={{WORKER_NODE_A}}
smart-triage specialist requests: cpu=1m, memory=16Mi
smart-triage specialist limits: cpu=250m, memory=256Mi
smart-triage specialist replicas: 1
```

Final deployment state:

```text
smart-triage-deployment-specialist    1/1  {{WORKER_NODE_A}}
smart-triage-gitlab-lite-specialist   1/1  {{WORKER_NODE_A}}
smart-triage-gitops-specialist        1/1  {{WORKER_NODE_A}}
smart-triage-grafana-specialist       1/1  {{WORKER_NODE_A}}
smart-triage-incident-commander       1/1  {{WORKER_NODE_A}}
smart-triage-knowledge-specialist     1/1  {{WORKER_NODE_A}}
smart-triage-kubernetes-specialist    1/1  {{WORKER_NODE_A}}
smart-triage-network-specialist       1/1  {{WORKER_NODE_A}}
smart-triage-policy-specialist        1/1  {{WORKER_NODE_A}}
smart-triage-trace-specialist         1/1  {{WORKER_NODE_A}}
```

Control-plane health after the fix:

```text
kubectl get --raw=/readyz: ok
{{CONTROL_PLANE_NODE}} available memory: ~4.1 GiB
{{CONTROL_PLANE_NODE}} load average: decreasing after agent fan-out moved off node
{{WORKER_NODE_A}} allocatable pods: 180
{{WORKER_NODE_A}} available memory: ~2.7 GiB
```

## Full Fan-Out Verification

Workflow:

```text
run_id: triage-smoke-20260709100844-manual-fanout
smart-triage-fanout-cfrnr
fingerprint: triage-smoke-20260709100844-manual-fanout
trigger: manual fan-out, not Grafana alert
```

Result:

```text
Status: Succeeded
Duration: 4m12s
Progress: 14/14
```

Verified markers:

```text
SPECIALIST_KUBERNETES: completed
SPECIALIST_NETWORK: completed
SPECIALIST_GRAFANA: completed
SPECIALIST_GITOPS: completed
SPECIALIST_KNOWLEDGE: completed
SPECIALIST_DEPLOYMENT: completed
SPECIALIST_POLICY: completed
SPECIALIST_TRACE: completed
INCIDENT_SYNTHESIS: completed
HITL_STATUS: resumed
REMEDIATION_MODE: gitops_or_workflow_only
VERIFICATION_PASSED: yes
OUTPUT_SANITIZED: yes
SMART_TRIAGE_PATTERN: proven
```

Lifecycle eval:

```text
score=1.0
passed=true
```

## Suggested Next Step

Keep the Kimi route and ModelConfigs. Full fan-out is now enabled, but keep
watching {{WORKER_NODE_A}} capacity during repeated or scheduled smoke runs:

```text
kubectl top node
kubectl get pods -n kagent -o wide | grep smart-triage
kubectl get deploy -n kagent | grep smart-triage
```
