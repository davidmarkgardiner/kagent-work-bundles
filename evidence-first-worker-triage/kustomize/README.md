# Native Kustomize Pilot

This is the human-operated deployment path. Copy the values example to the
ignored `values.env`, replace only the `{{PLACEHOLDER}}` values, and run from
the overlay directory:

```bash
cp values.env.example values.env
$EDITOR values.env
kubectl kustomize .
kubectl apply --dry-run=server -k .
kubectl apply -k .

# Prove worker/Vector and management Argo health.
./verify-healthy.sh values.env

# Create controlled log, OOM, scheduling and image-pull signals.
./smoke-test.sh values.env

# Remove only the controlled smoke fixtures.
./smoke-test.sh values.env --cleanup
```

For the self-contained demonstration, set
`WORKER_NAMESPACE=evidence-first-demo`. The overlay creates that namespace.

Work through [MANUAL-RUN-CHECKLIST.md](overlays/pilot/MANUAL-RUN-CHECKLIST.md)
with the implementation agent; it is the operator acceptance path.

The overlay produces a scoped demo namespace, a dedicated pilot Alloy
collector with namespace-only read RBAC, worker-local Vector/PVC/PDB, and the
management EventSource/Sensor/WorkflowTemplate. It references existing secrets
by name and key; it does not create credentials.

The dedicated Alloy collector is deliberately limited to the demo namespace.
For a real worker rollout, merge the same collection configuration into the
existing managed Alloy release and remove this pilot-only Deployment.

Use the accompanying commands after apply:

```bash
bash ../../scripts/verify-healthy.sh --values values.env
bash ../../scripts/simulate-failures.sh --values values.env
```

## Signal policy and scale-out

The pilot does **not** forward every log or every Kubernetes event. Vector
forwards application lines matching error/failure/exception/fatal/CrashLoop,
BackOff or OOM signatures, and Kubernetes `Warning` events with the explicit
reason allow-list: `FailedScheduling`, `OOMKilled`, `OOMKilling`, `BackOff`,
`Failed`, and `Unhealthy`. It caps/redacts evidence and suppresses exact local
repeats before Kafka. The management durable TTL claim is the final 24-hour
deduplication boundary.

To scale, create one worker overlay per approved namespace/cluster and deploy
one worker-local Alloy/Vector pair (or merge the Alloy fragment into the
existing worker Alloy release). Do not simply widen the demo collector to all
namespaces without an approved data-classification, capacity and redaction
review.
