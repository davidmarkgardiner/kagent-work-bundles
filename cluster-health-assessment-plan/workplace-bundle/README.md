# Workplace cluster-health deployment bundle

Status: implementation-complete and verified offline; not built, pushed or
deployed. This directory is the lift-and-shift entry point.

For the three-step workplace handoff, start with
[WORKPLACE-QUICKSTART.md](WORKPLACE-QUICKSTART.md). The detailed product
contract is [PRD.md](PRD.md). For a visual explanation of the complete flow,
open [CLUSTER-HEALTH-VISUAL.html](CLUSTER-HEALTH-VISUAL.html).

Upstream collector reference: https://github.com/foxj77/autonomous-monitor

## What deploys

Worker cluster:

1. one locally adapted Fox Go collector per namespace in the shared
   Alloy/Vector namespace inventory;
2. the deterministic B1 assessment every five minutes;
3. one alert controller that reads the latest immutable snapshot; and
4. one Vector sidecar that publishes the bounded daily health record to the
   normal SASL/TLS Kafka service.

Manager/agentic cluster:

1. one Kafka EventSource and one rate-limited Sensor;
2. one bounded WorkflowTemplate with a separately gated GitLab summary writer; and
3. one read-only `cluster-health-investigator` kagent Agent using the approved
   worker-targeted AKS-MCP server.

The Agent has no GitLab credential or write tool. A fixed-purpose adapter in a
separate Workflow step can create or update one labelled SRE summary issue when
`GITLAB_WRITE_ENABLED=true`. There is no Secret manifest, generic GitLab tool,
remediation tool or per-finding ticket path in this bundle.

## Alert policy

The numeric 0–100 score is explanatory, not the admission threshold. The
deterministic gate is the threshold:

- any critical required domain breaches immediately;
- a degraded required domain breaches after two complete five-minute
  assessments;
- recovery requires two complete healthy/watch assessments;
- after the configured UTC time, the controller emits exactly one record for
  that UTC date using the freshest complete snapshot;
- an active gate produces `investigate`; a clear gate produces `healthy`;
- only `investigate` reaches the Agent and optional GitLab writer.

Each alert contains the cluster/MCP target, score, domain states, coverage,
stable top problem groups, implicated namespaces, snapshot identity and the
read-only investigation request. It deliberately excludes raw event messages,
raw log lines, Secrets and credentials.

Every emitted record also carries a deterministic Kubernetes Workflow name
derived from its event identity. A replay of the same daily Kafka event cannot
create a second Workflow. Five-minute collection therefore improves evidence
freshness without increasing agent or ticket frequency.

The controller may update only the named pre-created dispatch-state ConfigMap
and cannot create arbitrary ConfigMaps. Its Flux `IfNotPresent` annotation is
intentional: GitOps creates missing state but does not reset live dedupe state
to `{}` on every reconciliation.

## Fox boundary

The work image is built from the pinned Fox commit plus the small internal
[`state-only adaptation`](FOX-STATE-ONLY-ADAPTATION.md). Fox writes its
namespace state ConfigMap but never creates a Kafka publisher. The manifests
also point its legacy broker fields at `127.0.0.1:1`; an accidental unadapted
image therefore fails safe instead of reaching workplace Kafka.

Only the Vector sidecar receives Kafka credentials. It uses the same
`bootstrap`/`key`/`secret` Secret shape as the existing Vector lane,
`sasl_ssl`, TLS verification, idempotent production, acknowledgements and a
bounded memory buffer. A Vector disk buffer is deliberately absent because the
known 0.45.0 Kafka disk-buffer path must not be trusted without produced and
consumed message proof.

## Configure and render

1. Copy `values.example.json` outside the public checkout and replace every
   placeholder. Use immutable registry digests. Set `KAFKA_PORT` to the broker
   listener port and set `EXPECTED_NAMESPACE_COUNT` to the exact number of
   namespaces in `fox-mesh/namespaces.json`. Supply separate worker and manager
   Kubernetes API CIDRs and keep the kagent namespace/A2A port aligned with the
   A2A service URL so the rendered NetworkPolicies are exact. Supply the GitLab
   HTTPS origin/project/egress values, but leave `GITLAB_WRITE_ENABLED=false`
   until the Kafka and agent-only gates pass.
2. Replace `../../fox-mesh/namespaces.json` with the exact ordered namespace
   scope from the workplace Alloy event and pod-log selectors. Regenerate both
   Fox and B1 manifests and run their drift verifier.
3. Render:

```bash
python3 workplace-bundle/scripts/render.py \
  --values /secure/path/cluster-health-values.json \
  --output-dir /secure/path/cluster-health-rendered
```

The renderer rejects unresolved values, floating images, malformed CIDRs and
images without `@sha256` digests.

## Build

Build the local assessor from this bundle:

```bash
workplace-bundle/scripts/build-assessor-image.sh \
  {{WORK_REGISTRY}}/platform/cluster-health-assessor:{{BUILD_ID}}
```

Create an internal Fox fork/mirror from the pinned upstream commit, implement
and test `PUBLISH_FINDINGS_ENABLED=false`, then build it without modifying or
pushing to Fox's repository:

```bash
workplace-bundle/scripts/build-fox-image.sh \
  /path/to/internal/autonomous-monitor \
  {{WORK_REGISTRY}}/platform/autonomous-monitor-state-only:{{BUILD_ID}} \
  {{WORK_REGISTRY}}/mirror/golang@sha256:{{GO_BUILDER_DIGEST}} \
  {{WORK_REGISTRY}}/mirror/distroless-static@sha256:{{RUNTIME_DIGEST}}
```

Scan both images, generate SBOMs, push to the approved internal registry, and
put the returned registry digests into the private values file. Mirror and pin
the approved Vector and curl/jq toolbox images as well.

The approved secret delivery mechanism must create:

- Kafka `bootstrap`, `key` and `secret` keys in the worker and Argo namespaces;
- a GitLab `token` key in `argo-events`, scoped only to issue read/write in the
  selected SRE project.

Pre-create the three project labels `health-summary`,
`managed-by-cluster-health`, and `cluster-health::<cluster-id>`. The writer
searches all three exactly, creates only when none match, updates when exactly
one matches, and fails closed on ambiguity. It does not automatically close
issues or retry an uncertain create in the same run.

GitLab API references:

- https://docs.gitlab.com/api/issues/
- https://docs.gitlab.com/api/labels/

## Verify

Offline:

```bash
python3 workplace-bundle/scripts/verify.py
```

Against compatible worker and manager clusters, before apply:

```bash
workplace-bundle/scripts/verify-live.sh \
  {{WORKER_CONTEXT}} {{MANAGER_CONTEXT}} \
  /secure/path/cluster-health-rendered aks-mcp-readonly
```

Then follow [TEST-PLAN.md](TEST-PLAN.md). The work-agent execution prompt is
[WORK-AGENT-START-PROMPT.md](WORK-AGENT-START-PROMPT.md).

After deployment, perform the read-only running-state gates:

```bash
workplace-bundle/scripts/verify-running.sh \
  {{WORKER_CONTEXT}} {{MANAGER_CONTEXT}}
```

This proves effective positive/negative RBAC, collector/bridge readiness, fresh
snapshot shape, per-namespace Fox state, manager resources and kagent
Accepted/Ready/controller visibility.
The Kafka produced/consumed and controlled-fault proofs remain separate gates
in the test plan; Kubernetes readiness is not evidence of message delivery.

## Rollback

Set `GITLAB_WRITE_ENABLED=false` first, then stop new investigations by
removing or disabling the dedicated Sensor through GitOps. Scale
`cluster-health-alert-bridge` to zero and revoke its Kafka producer ACL. Fox
and B1 can remain report-only. If collection itself must stop, suspend the B1
CronJobs and scale the Fox Deployments to zero through the owning GitOps
source. Preserve snapshot/report ConfigMaps and GitLab issue identity labels
until the incident review and evidence export are complete.
