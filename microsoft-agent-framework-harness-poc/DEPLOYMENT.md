# Python Harness POC deployment and evidence runbook

Status: **deployable template; exact image, model secret, endpoint, and OTLP
collector are environment inputs.** No live run is claimed by this document.

## Build once, then pin the image

Build from this directory in the approved registry pipeline. Do not install
packages at Job start in an air-gapped cluster.

```bash
docker build -t {{REGISTRY}}/maf-python-harness:{{VERSION}} .
docker push {{REGISTRY}}/maf-python-harness:{{VERSION}}
docker inspect --format='{{index .RepoDigests 0}}' {{REGISTRY}}/maf-python-harness:{{VERSION}}
```

Use the returned immutable `repo@sha256:...` as `HARNESS_IMAGE_DIGEST`; never
use `latest` in `argo-stage-workflow.yaml`.

## Environment inputs

| Input | Owner | Required | Notes |
| --- | --- | --- | --- |
| `HARNESS_IMAGE_DIGEST` | Platform | Yes | Approved image digest built from this bundle. |
| `MODEL_SECRET_NAME` | Platform | Yes for `approve` | Secret keys: `model`, `base-url`, `api-key`; never commit it. |
| `KAGENT_A2A_URL` | Platform | Yes for `approve` | Fixed known A2A specialist endpoint only. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Observability | No | Leave empty until a collector, retention, and redaction policy are approved. |
| Stateful PVC | Platform | Yes | One access-controlled state volume per execution or serialized Workflow. |

## Ordered execution

1. Apply the base, then inspect the rendered service account and PVC:

   ```bash
   kubectl apply -k .
   kubectl get sa,pvc -n kagent
   ```

2. Substitute the four placeholders in `argo-stage-workflow.yaml` from an
   environment-specific overlay. Apply it and the reviewed
   `network-policy.yaml`:

   ```bash
   kubectl apply -f rendered/argo-stage-workflow.yaml --dry-run=server
   kubectl apply -f rendered/network-policy.yaml --dry-run=server
   kubectl apply -f rendered/argo-stage-workflow.yaml
   ```

3. Submit `request` as a short Workflow; record the emitted `run_id`. It must
   show `awaiting-approval` and produce no model or A2A call.

4. Either submit `deny` with the same `run_id` and request (expected terminal
   `DENIED`, no A2A receipt), or obtain explicit operator approval and submit
   `approve` with the same `run_id` and exact request. The function itself
   rejects a changed request digest and duplicate A2A send.

5. Submit `evaluate` with the same `run_id`. It requires a matching request,
   approval, and exactly one successful terminal A2A receipt. Both the
   deterministic gate and Agent Framework `LocalEvaluator` must return PASS.

## Evidence and stop conditions

Keep only these redacted receipts: `request.json`, `approval.json`,
`a2a-prd-attempt-1.json`, `terminal.json`, `evaluation.json`, and
`framework-evaluation.json`. They include IDs/digests/status/latency but not
prompts, model output, endpoint URLs, tokens, or secret values.

Stop and investigate rather than retry when the A2A receipt is `BLOCKED`, a
receipt is stale or has a different digest, the evaluator fails, the Workflow
does not reach a terminal state, or the image digest/NetworkPolicy cannot be
verified. Do not retry a timed-out A2A `message/send`: submission may have
reached kagent even when the response was lost.

The former five-hop `factory-job.yaml` is retired as an execution pattern. Add
future plan/build/test/docs stages only as separate short Argo Workflow stages,
each with its own receipt and deterministic gate.
