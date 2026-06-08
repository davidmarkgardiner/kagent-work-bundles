# Chaos Examples

These examples are sanitized and intended for work-side adaptation. They are
not production-ready defaults.

## Important: No New ChaosTest CRD

`ChaosTest` is a request/config contract in this bundle. It is not a Kubernetes
CRD to install for phase 1.

Do not create a `reliability.platform.example` CRD just because
`chaos-test-pod-delete.yaml` has `apiVersion` and `kind` fields. Use that file
as structured input to the Argo workflow, GitLab evidence, or the chaos agent.

Only apply Kubernetes resources that already have controllers installed in the
work environment:

- `Workflow` requires Argo Workflows CRDs.
- `EventSource` and `Sensor` require Argo Events CRDs.
- `ChaosEngine` and `ChaosResult` require Litmus CRDs.

If those controllers are missing, report the missing controller as a blocker.
Do not invent or install a new `ChaosTest` CRD during this proof.

## Files

- `chaos-test-pod-delete.yaml` - platform `ChaosTest` request contract.
- `litmus-chaosengine-pod-delete.yaml` - reviewed Litmus `ChaosEngine` shape
  that GitOps can sync after approval.
- `argo-workflow-dry-run.yaml` - Argo Workflow submission that starts in
  `dry_run: "true"`.
- `a2a-chaos-request-payload.json` - example payload for a kagent A2A/manual
  test.

## Recommended Work-Side Order

1. Replace placeholders in private work context only.
2. Run static validation against `chaos-test-pod-delete.yaml` and
   `litmus-chaosengine-pod-delete.yaml`. Static validation means YAML/schema
   validation, not `kubectl apply` for `ChaosTest`.
3. Dry-run the Argo Workflow server-side if Argo Workflows is installed.
4. Send the A2A payload to the selected kagent front door.
5. Keep `dry_run: "true"` until runtime readiness, target opt-in, and HITL are
   proven.
6. Only then run the approved lower-environment chaos path.

## Required Safety Properties

- Target environment is `dev`, `test`, or `staging`.
- Target selector includes `reliability.platform/chaos-optin: "true"`.
- `safety.requiresHITL` is `true`.
- Rollback and abort conditions are present.
- Recovery and lifecycle evaluation are recorded before the run is complete.
