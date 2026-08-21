# Component Verification Guide

Run the checks in order. Replace placeholders locally; do not put private
contexts, broker addresses, credentials, or GitLab URLs into this repository.

```bash
set -a; source /secure/evidence-first-values.env; set +a
export WORKER_CONTEXT={{WORKER_KUBECTL_CONTEXT}}
export MANAGEMENT_CONTEXT={{MANAGEMENT_KUBECTL_CONTEXT}}
export KAGENT_NAMESPACE={{KAGENT_NAMESPACE}}
export AKS_MCP_NAMESPACE={{AKS_MCP_NAMESPACE}}
export AKS_MCP_LABEL='app.kubernetes.io/name=aks-mcp'
```

## Gate 0 — rendered intent and runtime identities

Confirm the deployed objects use the intended namespace, topic, group and
Secret *references*. Do not print Secret data.

```bash
kubectl --context "$WORKER_CONTEXT" -n "$WORKER_NAMESPACE" get deploy evidence-first-alloy evidence-first-vector
kubectl --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" get eventsource evidence-first-confluent
kubectl --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" get sensor evidence-first-triage workflowtemplate evidence-first-triage
kubectl --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" get eventsource evidence-first-confluent -o yaml
```

Pass only when the EventSource topic and `consumerGroup.groupName` are the
approved work values, and the EventSource points at existing Secret/CA
references. A `GROUP_AUTHORIZATION_FAILED` log is a failed gate: use the
Confluent consumer-group onboarding to grant the EventSource principal `READ`
on the exact topic and consumer group.

## Gate 1 — Alloy collects only the approved namespace and forwards to Vector

Alloy has namespace-scoped read access to `pods`, `pods/log`, and `events` and
forwards OTLP logs to `evidence-first-vector:4318`.

```bash
kubectl --context "$WORKER_CONTEXT" -n "$WORKER_NAMESPACE" rollout status deployment/evidence-first-alloy --timeout=180s
kubectl --context "$WORKER_CONTEXT" -n "$WORKER_NAMESPACE" auth can-i get pods,pods/log,events --as system:serviceaccount:"$WORKER_NAMESPACE":evidence-first-alloy
kubectl --context "$WORKER_CONTEXT" -n "$WORKER_NAMESPACE" logs deploy/evidence-first-alloy --tail=100
kubectl --context "$WORKER_CONTEXT" -n "$WORKER_NAMESPACE" get endpoints evidence-first-vector
```

Create one controlled log fixture only after the deployment and RBAC checks
pass. Capture Alloy logs around the fixture timestamp and Vector input
counter/log evidence. Pass when the marker appears at Vector; an Alloy pod
being Ready by itself is insufficient.

## Gate 2 — Vector normalises, redacts and produces to Kafka

Vector receives Alloy OTLP, applies the allow-list/redaction transform, and
publishes the bounded envelope using the worker producer identity.

```bash
kubectl --context "$WORKER_CONTEXT" -n "$WORKER_NAMESPACE" rollout status deployment/evidence-first-vector --timeout=180s
kubectl --context "$WORKER_CONTEXT" -n "$WORKER_NAMESPACE" get pvc evidence-first-vector-buffer
kubectl --context "$WORKER_CONTEXT" -n "$WORKER_NAMESPACE" logs deploy/evidence-first-vector --tail=150
kubectl --context "$WORKER_CONTEXT" -n "$WORKER_NAMESPACE" port-forward svc/evidence-first-vector 9598:9598
# In another terminal: curl -fsS http://127.0.0.1:9598/metrics | rg 'component_(received|sent|discarded)_events'
```

Pass when the controlled marker is accepted by the allow-list, Vector reports a
successful Kafka sink delivery, and the bounded/redacted envelope is the only
payload leaving the worker. A secret-shaped fixture value must be redacted;
the original value must not appear in Vector output, Kafka, workflow logs, or
GitLab.

## Gate 3 — Kafka accepts the record and Argo consumes it

Verify both sides without creating a second unapproved production consumer
group.

1. In the Confluent portal, inspect the approved topic for the controlled
   record timestamp/key and producer activity.
2. Inspect the approved EventSource group's membership, committed offsets and
   lag. A brief increase followed by an offset advance is expected.
3. Inspect the EventSource pod logs.

```bash
kubectl --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" get pods -l eventsource-name=evidence-first-confluent
kubectl --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" logs -l eventsource-name=evidence-first-confluent --tail=150
```

Pass when the topic receives the record and the approved group advances past
it. Fail and stop for authentication, topic, group-authorisation, schema, or
deserialisation errors. Do not reset offsets or create a new group as a repair.

## Gate 4 — EventSource, Sensor and Workflow preserve the event contract

```bash
kubectl --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" get sensor evidence-first-triage -o yaml
kubectl --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" get workflows --sort-by=.metadata.creationTimestamp
kubectl --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" logs -l sensor-name=evidence-first-triage --tail=150 || true
```

For the new workflow, inspect its rendered `incident` parameter and validation
step. Capture a redacted copy showing `schema_version`, cluster, namespace,
pod/workload, reason or log signature, severity, container, timestamp,
fingerprint, and bounded evidence. Pass only if the workflow was triggered by
the EventSource record—not by a manual Workflow submission.

## Gate 5 — kagent receives the event and returns a diagnosis to the workflow

Inspect the workflow's agent-call step and the kagent controller/agent logs
using its actual labels. The diagnosis must be present in the workflow output
and must reference the controlled evidence without treating it as instructions.

```bash
# Preferred when the Argo CLI is installed:
argo -n "$MANAGEMENT_NAMESPACE" logs "{{WORKFLOW_NAME}}" --all-containers
# Kubernetes-only fallback: list the Workflow's pods, then inspect each one.
kubectl --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" get pods -l workflows.argoproj.io/workflow="{{WORKFLOW_NAME}}"
kubectl --context "$MANAGEMENT_CONTEXT" -n "$KAGENT_NAMESPACE" get pods
kubectl --context "$MANAGEMENT_CONTEXT" -n "$KAGENT_NAMESPACE" logs deploy/kagent-controller --tail=150
```

Pass only if the workflow shows a successful A2A response, extracts non-empty
diagnosis text, and hands that text to the GitLab step. The agent must not make
a remediation call or claim it performed an action.

## Gate 6 — prove the agent can use AKS MCP, read-only

First verify the configured agent has the expected AKS MCP tool binding and no
write-capable Kubernetes/AKS tools. Then use one controlled incident whose
namespace and pod are known, and require the agent to query that target.

```bash
kubectl --context "$MANAGEMENT_CONTEXT" -n "$AKS_MCP_NAMESPACE" get pods -l "$AKS_MCP_LABEL"
kubectl --context "$MANAGEMENT_CONTEXT" -n "$AKS_MCP_NAMESPACE" logs -l "$AKS_MCP_LABEL" --since=15m
kubectl --context "$MANAGEMENT_CONTEXT" -n "$KAGENT_NAMESPACE" get agents "${KAGENT_AGENT_NAME}" -o yaml
```

Use this bounded test instruction in the controlled workflow/agent request:

> Use only the configured read-only AKS MCP tools to inspect pod status,
> relevant events and recent logs for `{{TEST_NAMESPACE}}/{{TEST_POD}}` in
> `{{APPROVED_WORKER_CLUSTER}}`. Return the observations, tool names used and
> confidence. Do not apply, delete, patch, exec, scale, restart or modify
> anything.

Pass only when all three are captured: the agent response names the inspected
object and evidence, the AKS MCP pod logs show the correlated read request, and
the agent/tool configuration contains no mutation capability. If MCP logs show
an auth, target-cluster or tool error, stop here rather than accepting a
diagnosis based only on the Kafka payload.

## Gate 7 — GitLab work item preserves the safe original context

```bash
argo -n "$MANAGEMENT_NAMESPACE" logs "{{WORKFLOW_NAME}}" --all-containers | rg -i 'gitlab|issue|ticket|diagnosis'
```

Open the resulting work item and verify it contains the redacted incident
contract plus the read-only diagnosis: cluster, namespace, workload/pod,
reason/signature, severity, container, observed time, fingerprint, bounded
evidence and agent conclusion. Verify it does **not** contain the secret-shaped
smoke value, a token, raw unbounded log content, or a claim that remediation
was executed.

Record the workflow name, topic partition/offset or portal evidence, GitLab
item ID/URL, and redacted tool proof in `../evidence/`. Then proceed to the
end-to-end and deduplication tests.
