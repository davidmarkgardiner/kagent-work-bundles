# Manual Pilot Checklist

Run this with the implementation agent. Do not proceed past a failed check;
capture the command output and fix the named component first.

## 0. Confirm operator access and context

- [ ] Confirm the exact worker-cluster and management-cluster `kubectl`
  contexts; do not rely on whichever context happens to be active.
- [ ] Confirm the implementation agent is already authenticated to both
  clusters and has the required read/apply scope for this non-production pilot.
- [ ] If using AKS MCP for read-only enrichment, record the approved worker
  target(s), identity and read-only tool scope.
- [ ] Collect the GitLab API/project and read-only kagent A2A endpoint details.
- [ ] Collect existing image names/tags, Secret/CA references, service-account
  names, Kafka topic/consumer group and durable-idempotency endpoint.
- [ ] Keep this context in a private values file outside Git; do not place
  credential values, tokens, CA material or private endpoints in this bundle.

## 1. Prepare values

```bash
cd kustomize/overlays/pilot
cp values.env.example values.env
$EDITOR values.env
```

- [ ] Set `WORKER_NAMESPACE=evidence-first-demo` for the self-contained pilot.
- [ ] Set the management namespace, worker cluster name, Confluent bootstrap,
  topic and consumer group.
- [ ] Set names of existing Confluent, Kafka CA, idempotency and GitLab
  secrets—never their values.
- [ ] Set the approved idempotency claim URL and the read-only kagent A2A URL
  and agent name.
- [ ] Set the existing Argo Events and Workflow service-account names. Verify
  the Events identity can create Workflows and the Workflow identity can call
  the approved idempotency, kagent and GitLab integrations.
- [ ] Confirm the management Kafka identity has consume permission and the
  worker identity has produce permission on the selected topic.

## 2. Render and deploy

```bash
kubectl kustomize . > /tmp/evidence-first-rendered.yaml
kubectl apply --dry-run=server -k .
kubectl apply -k .
```

- [ ] The server dry run succeeds.
- [ ] The apply succeeds without replacing existing Alertmanager/Grafana
  objects.

## 3. Confirm health

```bash
./verify-healthy.sh values.env
```

- [ ] `evidence-first-alloy` and `evidence-first-vector` Deployments roll out.
- [ ] Vector PVC is `Bound`.
- [ ] The EventSource and Sensor exist in management.
- [ ] EventSource pod is `Running`; its recent logs show no Kafka connection
  or authentication error.
- [ ] No existing human paging route was changed.

## 4. Run controlled smoke signals

```bash
./smoke-test.sh values.env
sleep 60
kubectl -n "$MANAGEMENT_NAMESPACE" get workflows --sort-by=.metadata.creationTimestamp
kubectl -n "$MANAGEMENT_NAMESPACE" logs -l eventsource-name=evidence-first-confluent --tail=100
```

- [ ] Application error log creates one evidence-triggered workflow.
- [ ] OOM fixture produces an OOM warning path.
- [ ] Unschedulable fixture produces `FailedScheduling`.
- [ ] Invalid image fixture produces image-pull/`BackOff` or `Failed`.
- [ ] Workflow reaches validation, durable claim and read-only diagnosis.
- [ ] Workflow output/ticket contains bounded, redacted evidence; the fake
  token from the log fixture is absent.
- [ ] The agent tool inventory is read-only—no apply, delete, patch or exec.

## 5. Verify duplicate handling

```bash
./smoke-test.sh values.env --cleanup
./smoke-test.sh values.env
sleep 60
kubectl -n "$MANAGEMENT_NAMESPACE" get workflows --sort-by=.metadata.creationTimestamp
```

- [ ] Exact repeat does not create a second Kafka-triggered triage/ticket for
  the same incident fingerprint inside the 24-hour window.
- [ ] A changed reason/signature is allowed to produce a separate incident.

## 6. Capture outcome and clean up

```bash
./smoke-test.sh values.env --cleanup
```

- [ ] Save redacted workflow names, EventSource evidence and GitLab issue IDs
  in `../../evidence/EVIDENCE-TEMPLATE.md`.
- [ ] Record DS-01 through DS-16 result and the green/amber/red verdict.
- [ ] Keep the pilot deployed only if the owner approves the next namespace;
  otherwise remove it with `kubectl delete -k .`.
