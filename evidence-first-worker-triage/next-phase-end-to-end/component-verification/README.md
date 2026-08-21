# Component and End-to-End Verification Pack

Use this pack before expanding evidence triage beyond one approved
non-production namespace. It proves one boundary at a time, then proves the
complete path with controlled signals:

```text
Alloy -> Vector -> Confluent Kafka -> Argo EventSource -> Sensor/Workflow
      -> read-only kagent (including AKS MCP) -> GitLab work item
```

This is a verification runbook, not another deployment mechanism. Deploy from
the parameterised [pilot overlay](../../kustomize/overlays/pilot/) and use the
proven [reference-config](../reference-config/) and [applied-config](../applied-config/)
only to understand and carry forward behaviour. Do not apply either proof
folder verbatim to a work cluster.

## Mandatory live-discovery gate — never copy proof YAML verbatim

The local proof YAML is evidence, not a work-cluster install. Before rendering
or applying anything, the implementation agent must inspect the live target and
write down the discovered values/references in a private file outside Git:

- Correct worker and management cluster contexts, and the namespaces that
  already own Alloy, Vector, Argo Events, kagent, AKS MCP and GitLab access.
- Existing image names/tags, CRD/API versions, service accounts, labels and
  selectors. Do not assume the proof-cluster image, CR kind or label exists at
  work.
- Existing EventSource/Sensor/WorkflowTemplate names, Kafka topic and consumer
  group, and Confluent/CA Secret *references*. Reuse a working integration; do
  not replace it or create duplicate active consumers.
- Existing workload identity, NetworkPolicy, Pod Security and GitOps/Flux
  ownership. Render an additive change through the established reconciliation
  path rather than applying an unowned duplicate.
- Approved worker namespace, data classification, AKS MCP target cluster and
  read-only tool scope.

The agent must compare those discoveries with the rendered overlay before a
server-side dry run. It must stop and report a mismatch (for example a missing
CRD, different image policy, unavailable Secret reference, group ACL error or
namespace ownership conflict) rather than guessing or substituting a local
proof value.

## Run order

1. Complete every independent check in
   [COMPONENT-VERIFICATION.md](COMPONENT-VERIFICATION.md). Stop at the failed
   boundary; do not use a later success to guess that an earlier component is
   healthy.
2. Run the controlled log and Kubernetes-event cases in
   [SMOKE-TESTS-AND-DEDUPLICATION.md](SMOKE-TESTS-AND-DEDUPLICATION.md).
3. Capture the required evidence, including redacted payloads and GitLab work
   item URLs/IDs, in `../evidence/`. Never capture tokens, Kafka credentials,
   private endpoints, or raw unrestricted logs.
4. Use [ROLLOUT-PLAN.md](ROLLOUT-PLAN.md) to onboard one application namespace
   at a time. Do not widen collection while any gate is amber or red.

## Prerequisites gate

Before starting, record the following in a private values/context file outside
Git. Reuse `kustomize/overlays/pilot/values.env`; add the context names and
kagent namespace locally if they are not already present.

- Worker and management `kubectl` context names.
- One approved worker namespace and its cluster identity.
- Existing Confluent topic, producer identity, EventSource consumer identity,
  and consumer-group ID. The consumer identity needs `READ` on both the topic
  and the group.
- Existing Secret and CA *names* only, never values.
- The read-only kagent A2A endpoint, agent name, and kagent namespace.
- The approved AKS MCP deployment/service identity and the worker cluster(s)
  it may query.
- GitLab project/API configuration and the workflow's approved write identity.

The agent must remain read-only. AKS MCP is used to inspect the target cluster
and its own runtime; it must not apply, delete, patch, exec, or otherwise make
cluster changes.

## Verdict

The pilot is ready to onboard the next namespace only when all component gates,
both end-to-end smoke cases, the duplicate/retry cases, the read-only AKS MCP
tool proof, and the GitLab payload inspection are green. A ready pod, rendered
YAML, or a manually submitted Workflow is not an end-to-end proof.
