# Deploy an agent

## 1. Submit a reviewed onboarding contract

Record owner/support contact, consumer identity, supported runtime profile and version, purpose, permitted model, tools and resource scope, knowledge release, retention, cost/concurrency limits and disable/revoke procedure. Platform approval resolves each requested grant to a catalog entry. The contract drives the reviewed KRO/GitOps path.

## 2. Discover the receiving platform

Use an explicit context and keep output private. Record Kubernetes APIs, installed Helm versions and image digests, served kagent/Gateway API/policy CRDs, CNI enforcement, namespace/RBAC ownership, approved identity route and the current policy rejection. The [preflight script](downloads/preflight.py) collects selected non-secret discovery; it never applies resources.

```bash
python3 labs/kagent-1.0.1/preflight.py   --context '{{LAB_CONTEXT}}' --output '{{PRIVATE_EVIDENCE_DIRECTORY}}'
```

A second 1.0 cluster needs the required certificate APIs, trusted CA/JWT material, database access, snapshot storage, workers, DNS/egress and approved model/tool backends. Do not replay an old 0.0.9 install script. Follow the exact pinned upstream installation and convert the approved values into the organisation's GitOps releases.

## 3. Separate runtime and behaviour

A platform Harness selects the runtime and WorkerPool. An AgentTemplate supplies behaviour, model and approved bindings. An Agent pairs them. The [downloadable canary](downloads/agent-canary.yaml) is a schema-validated, tool-free example referencing the platform's `kagent-default` Harness and `default-model-config`. These dependencies must exist and be approved before use.

The [lab values](downloads/kagent-values.yaml) render only the native Harness and one gVisor worker; the private database and identity prerequisites still need provisioning. These are **render-test values**, not a complete production install. Replace the model with the approved gateway route and pin/mirror images by digest in the private overlay.

## 4. Review and reconcile

Validate the new resources against the tagged CRDs offline and against the receiving API with server dry-run. Review policy denials before reconciliation. Permanent state goes through Flux; approved workflows own resource-changing permissions. The ordinary agent profile has no generic apply/delete tools.

## 5. Accept before widening access

Require Agent readiness, a successful model turn, a real approved tool read, the expected identity at the backend, denied out-of-scope access, token rotation/expiry, Actor suspend/resume, session isolation and correlated evidence. A Ready condition or successful Helm release is insufficient. Start with one pod-owned agent before a second team.

## Rollback and retirement

Retain the previous approved endpoint/configuration until cutover is accepted. Disable the new caller route if needed, cancel/hand over active work, revoke new grants and restore the previous GitOps revision through its owner. Record database/snapshot compatibility separately. Decommissioning includes session records, snapshots and tags, credentials, grants, artifacts, logs and external retention; object deletion alone does not prove erasure.
