# Workplace cluster-health bundle offline receipt

Superseded by
[`2026-09-16-daily-gitlab-bundle-offline.md`](2026-09-16-daily-gitlab-bundle-offline.md).
This file preserves the earlier breach/reminder and no-ticket design receipt.

Date: 2026-09-16

Result: PASS for local source, contract, render and static security gates. NOT
BUILT, NOT PUSHED, NOT DEPLOYED, and NOT LIVE-VERIFIED.

No change, commit, fork, pull request, issue or push was made to
https://github.com/foxj77/autonomous-monitor or to any colleague-owned
repository. All changes are local to this work bundle.

## Delivered boundary

- Fox is a state-only namespace sensor in the workplace design. The required
  internal-fork adaptation makes `PUBLISH_FINDINGS_ENABLED=false` prevent
  publisher construction. The deployment also points legacy broker fields to
  `127.0.0.1:1` and grants Fox no Kafka Secret.
- B1 is the sole deterministic health-score and breach/recovery owner. The
  numeric score is display context; domain status and complete-coverage rules
  own the gate.
- The alert controller emits only a new breach, one active reminder per four
  hours, or recovery. The record is capped at 64 KiB and removes raw event/log
  examples.
- A Vector sidecar is the only worker Kafka client. It uses SASL/TLS,
  certificate verification, idempotent production, all acknowledgements and a
  bounded memory buffer. No Vector Kafka disk buffer is configured.
- Argo accepts only the versioned alert and `investigate` action, rate-limits
  admission, and creates a deterministic Workflow name derived from the event
  identity. Replaying the same event cannot create a second Workflow.
- The Agent has only the named AKS-MCP server/tool pair and instructions for a
  bounded read-only investigation of the supplied worker target. Hard
  read-only enforcement remains an identity/RBAC promotion gate; the prompt is
  not treated as authorization.
- No GitHub/GitLab client, ticket writer, Secret manifest, remediation tool or
  individual-finding Sensor exists in the bundle.

## Offline commands and results

```text
PYTHONDONTWRITEBYTECODE=1 python3 \
  work-agent-bundles/cluster-health-assessment-plan/workplace-bundle/scripts/verify.py
RESULT: PASS — controller tests, alert schema/fixture, Fox scope verifier,
Agent CR validator, placeholder-free fixture render, immutable-image checks,
22-namespace render, pod security/resources, Kafka controls and no-ticket
boundary

PYTHONDONTWRITEBYTECODE=1 bash \
  work-agent-bundles/cluster-health-assessment-plan/verify-all.sh
RESULT: PASS — 28 B1 tests, 5 B3 tests, 1 B4 test, Fox verifier, workplace
verifier, Go intake compile/test, schemas, all Kustomize builds, accelerated
qualification assertions and strict public-safety scan

bash -n workplace-bundle/scripts/*.sh
RESULT: PASS

negative build-script tests with tag-only base images
RESULT: PASS — assessor and Fox build scripts both rejected non-digest bases
before attempting a build

fixture render with Kafka port 9443 and kagent A2A port 8443
RESULT: PASS — both worker/manager Kafka policies and the kagent workflow
egress policy rendered the configured ports rather than retaining defaults
```

The Docker daemon was not available to this execution sandbox:

```text
permission denied while trying to connect to the Docker daemon socket
```

Therefore this receipt does not claim a built image, image scan, SBOM,
registry digest or runtime container proof.

The required independent review lane was attempted with Claude and a Kimi
fallback. Both providers exited unsuccessfully, so no independent approval is
claimed. The failure-only receipt is retained at
`workplace-bundle/evidence/peer-review-receipt.json`; a successful review is a
promotion gate rather than a reason to overstate this offline build.

## Deployment and live proof still required

1. Extract and review the exact workplace Alloy pod-log and Kubernetes-event
   namespace scope; update and regenerate the shared namespace contract.
2. Apply and test the state-only adaptation in an approved internal Fox
   fork/mirror at pinned commit
   `7c785b574c36f7100ae321ec0f880782dfead311`.
3. Build with approved digest-pinned base images; run Go/Python tests, licence
   checks, vulnerability scans and SBOM generation; push only to the approved
   internal registry and capture immutable digests.
4. Supply private placeholder values and existing externally managed Kafka
   Secrets, then run `verify-live.sh` with the same context twice when the
   current single cluster represents both worker and manager.
5. Apply through the owning GitOps flow, then run `verify-running.sh` and the
   separate Kafka produced/consumed proof.
6. Complete the reversible fault, replay-dedupe, recovery, unavailable-MCP and
   weekday-plus-weekend soak gates in `workplace-bundle/TEST-PLAN.md`.

Kubernetes readiness, dry-run success and this offline receipt are not Kafka
delivery or live agent-investigation proof.
