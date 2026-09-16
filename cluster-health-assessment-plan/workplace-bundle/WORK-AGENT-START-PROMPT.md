# Work-agent start prompt

Copy the prompt below into the approved work agent. Replace only the explicit
placeholders; do not paste credentials or private endpoint values into chat.

```text
You are implementing the cluster-health assessment bundle in the workplace
platform repository. Work locally and through the existing GitOps workflow.
Do not modify, push to, open issues on, or submit pull requests to
https://github.com/foxj77/autonomous-monitor or any colleague-owned repository.
If source changes are required, create/use an approved internal fork or mirror.

Start from:
  work-agent-bundles/cluster-health-assessment-plan/workplace-bundle/

Outcome:
  Run one state-only Fox Go collector for every namespace selected by the
  existing Alloy Kubernetes-event and pod-log configuration. B1 calculates the
  deterministic cluster health gate. Only the alert bridge's Vector sidecar
  may connect to the normal Kafka service. After the configured UTC time it
  emits one bounded cluster-health.alert.v1 record per date. Argo invokes one
  read-only worker-targeted cluster-health-investigator agent only when the
  deterministic gate is active. A separate fixed adapter may create/update one
  labelled GitLab SRE summary after its explicit gate is enabled. Do not create
  individual tickets or feed raw Fox findings to an existing incident Sensor.

Mandatory sequence:

1. Read the bundle README, TEST-PLAN, FOX-STATE-ONLY-ADAPTATION and repository
   instructions. Record the current branch/dirty state and preserve unrelated
   changes. Record installed Argo Events, Argo Workflows, kagent and AKS-MCP
   versions plus the effective controller/runtime image IDs; those
   platform-managed images are outside this bundle but still need policy proof.
2. Inspect the live/owned Alloy configuration. Extract the exact ordered
   namespace lists for Kubernetes events and pod logs. Stop if they differ.
   Replace fox-mesh/namespaces.json with that reviewed list, regenerate
   fox-mesh/rendered.yaml and b1/k8s/watched-namespaces.yaml using the supplied
   renderers, and run fox-mesh/verify.py --alloy-config against the owned live
   Alloy source. The bundled Alloy file is only a sanitized parser fixture.
3. Clone the pinned Fox commit
   7c785b574c36f7100ae321ec0f880782dfead311 into an approved internal fork or
   source mirror. Implement the strict PUBLISH_FINDINGS_ENABLED switch exactly
   as specified. Add the five required Go tests. Do not contact or push to the
   upstream/colleague repository.
4. Build and test the Fox state-only image and the local assessor image using
   the supplied Dockerfiles/scripts. Use approved digest-pinned builder/runtime
   bases. Run unit tests, vulnerability scans, licence checks and SBOM
   generation. Push only to {{WORK_REGISTRY}} after the normal internal
   approval. Capture immutable registry digests.
5. Mirror/pin the approved Vector 0.45-compatible image and curl/jq toolbox.
   Do not enable Vector's Kafka disk buffer; this repository has evidence that
   it accepted writes without draining on Vector 0.45.0. Use the supplied
   bounded memory buffer and prove actual production/consumption.
6. Create a private values JSON from values.example.json. Never commit
   credentials, private endpoints, subscription IDs or kubeconfigs. Use the
   existing Kafka Secret shape (bootstrap/key/secret), a new cluster-health
   topic, and a unique consumer group. Configure verified CIDRs for the worker
   API, manager API and Kafka egress; do not use 0.0.0.0/0. Set EXPECTED_NAMESPACE_COUNT
   to the reviewed namespace-list length and KAFKA_PORT to the approved TLS
   listener port. Align KAGENT_NAMESPACE and KAGENT_A2A_PORT with the internal
   A2A service URL. Configure the GitLab HTTPS origin, project and exact egress
   CIDR, but keep GITLAB_WRITE_ENABLED=false.
7. Verify the AKS-MCP RemoteMCPServer is the approved worker reach-back path.
   Confirm live discovery exposes only the needed call_az/call_kubectl tools to
   this agent, the target identity has least-privilege read-only Kubernetes
   authorization, Secret reads and mutating verbs are denied, and every call
   requires an explicit approved worker target. A prompt is not an RBAC
   boundary.
8. Render placeholder-free worker.yaml and manager.yaml. Run scripts/verify.py,
   server-side dry-runs, admission policy checks and scripts/verify-live.sh.
   Do not apply until those are green and the change window is approved.
9. Follow TEST-PLAN gates in order: report-only canary, Kafka produced/consumed
   and one-record-per-date proof, controlled smoke fault, one agent Workflow,
   recovery, then a disposable GitLab project proof. Pre-create the exact
   health-summary, managed-by-cluster-health and cluster-health::<cluster-id>
   labels. Deliver a project-scoped issue token only to the writer step. Enable
   GITLAB_WRITE_ENABLED only after the no-write agent proof passes. Then run the
   full-scope weekday-plus-weekend soak. Record commands, exact image digests, object
   generations, Kafka offsets, workflow names, tool audit and sanitized agent
   output in an evidence document. Run scripts/verify-running.sh after apply;
   inspect the controller-generated EventSource/Sensor/Workflow/Agent pods for
   effective security contexts and image IDs, and do not substitute readiness
   for the separate Kafka delivery proof.
10. Prove first unhealthy day creates exactly one SRE issue and the next
    unhealthy day updates it. Replays, multiple matching issues, pagination,
    missing labels, token denial and ambiguous API responses must fail closed.
    The Agent never receives the GitLab token. Do not auto-close the issue or
    perform Kubernetes remediation.

Fail closed if:
  - Alloy event/log namespace scopes differ;
  - the Fox image does not prove state-only mode;
  - an image is floating or not digest-pinned;
  - any placeholder remains;
  - Kafka TLS verification is disabled;
  - NetworkPolicy needs a broad CIDR;
  - AKS-MCP can mutate or read Secrets;
  - the alert contains raw logs/events or exceeds 64 KiB;
  - one date produces more than one investigation Workflow or SRE issue;
  - the GitLab identity search is ambiguous or paginated;
  - the agent investigates the management cluster instead of the named worker.

Return a delivery receipt containing: changed files, internal commits/PRs only,
image digests and scans, render/dry-run results, RBAC denials, namespace parity,
Kafka produced+consumed evidence, one-record-per-date proof, alert payload
validation, Argo workflow and agent target proof, GitLab create/update/replay
evidence, recovery/rollback proof, soak status, and every remaining blocker.
Do not describe a build, push, deployment or live test as complete without its
real receipt.
```
