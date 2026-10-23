# Set up the cluster security review Agent

Hand [WORK-AGENT-START-PROMPT.md](WORK-AGENT-START-PROMPT.md) to the work agent.
Copy this entire directory into the approved work environment. All runtime
manifests, scan instructions and operator helpers are included; the parent
repository and sibling upstream checkouts are not needed to set it up.

Run `bash scripts/verify-bundle.sh` before adapting the files. It performs offline
checks only. Requirements are Bash, Python 3 with PyYAML, kubectl with Kustomize,
and `sha256sum` or `shasum`. Live verification also needs curl and jq. Use the
work environment's approved tooling; do not install packages into the cluster.
Checksums describe the shipped baseline. After changing environment-specific
manifest names, run `bash scripts/validate-manifests.sh`. That command enforces
the exact three-tool boundary without requiring the baseline hashes to match.

The source snapshot is `agents/cluster-security-review/` in `kagent-public`, with
bundle-local adaptations of the shared invocation, readiness and Agent lint
helpers plus their tool catalog. These copies enforce completed A2A tasks,
generation-aware readiness and standalone catalog validation. Parent-repository
helpers are unchanged. Update the source Agent and bundled manifest together;
retain the bundle-specific helper safeguards when refreshing snapshots.

Deploys one `kagent.dev/v1alpha2` Agent using the existing local `kagent-tool-server`.
It reviews cluster configuration and **all namespaces except names beginning with
`at`, case-insensitively**, including system namespaces. Its first call inventories
namespaces. Findings cite actual tool arguments, resource fields and sanitised
output; every included namespace has a coverage ledger, including unexamined scope.

**Security boundary:** the system prompt and three-tool allowlist are behavioural
constraints, not hard namespace or read-permission enforcement on a shared MCP
server. They do not change the server's Kubernetes identity or permissions. The
get/YAML tools can return entire objects, including embedded workload env values,
before the Agent redacts its response. Do not treat this manifest as a guarantee
that excluded namespaces or sensitive content cannot enter model context. For a
hard boundary, use a separately authorised, read-only MCP identity with scoped
RBAC plus server-side kind/namespace filtering and field redaction; that server is
not provisioned by this bundle. Use an approved model/provider for cluster data.

This is a quick, best-effort configuration review, with a planning budget of about
ten minutes/120 tool calls. It cannot run scanners, prove Internet reachability,
inspect the cloud control plane, certify compliance, or scan the Flux repository.
Existing scoped scanner reports are historical evidence and carry freshness
limitations. The Agent is instructed not to read Secrets or ConfigMaps. Its tool
list contains no logs, exec, probes, remote-cluster switching, arbitrary command,
installation or remediation tools; the shared read tools retain their backend
RBAC permissions as described above.

## Files and configuration

| File | Purpose |
|---|---|
| `WORK-AGENT-START-PROMPT.md` | Implementation instructions and target-side stop gates |
| `GITLAB-TICKET.md` | Copyable implementation ticket and acceptance checklist |
| `manifests/agent.yaml` | Single declarative Agent, system/evidence/coverage contract, three local tools |
| `manifests/kustomization.yaml` | Renders only that Agent; no Namespace, RBAC or scanner workload |
| `scan-prompt.txt` | Ready-to-use first request, also suitable for the kagent UI |
| `scripts/` and `references/` | Offline verifier, shared operator helpers and tool catalog |
| `CHECKSUMS.sha256` | Integrity manifest for the shipped baseline |
| `TOOL-TRACE-VERIFICATION.md` | Source, correlation and completeness gates for actual tool-call evidence |
| `REVIEW-RESOLUTION.md` | Claude/Kimi review issues and final verification status |
| `tests/` | Offline regression fixtures for validation and operator helpers |

The shipped defaults are Agent `cluster-security-review`, namespace `kagent`,
ModelConfig `default-model-config`, RemoteMCPServer `kagent-tool-server`. Before
deploying, edit `metadata.namespace`, `spec.declarative.modelConfig`, and
`spec.declarative.tools[0].mcpServer.name` to match the selected installation. Model
and MCP defaults are names, not evidence that those objects exist or are ready.
Keep both dependencies in the Agent namespace; configure the existing ModelConfig
through your approved environment configuration rather than adding credentials.
No new namespace, model, MCP service, permissions or provider subscription is created.

The target placeholders below are `{{KUBE_CONTEXT}}` (explicit selected deployment
context), `{{KAGENT_NAMESPACE}}`, `{{MODEL_CONFIG}}`, `{{MCP_SERVER}}` and
`{{CONTROLLER_NAMESPACE}}`. Use an additional approved absolute
`{{PRIVATE_OUTPUT_DIRECTORY}}` for evidence, outside this public checkout.
Replace them with approved local values. Do not commit
private cluster details, endpoints, IDs, scan output or credentials to this public
repository. A private review report should be saved only in an approved location.

## Preflight on the chosen cluster

Run from this bundle root, after selecting the correct cluster explicitly.
These checks read configuration; they do not deploy the Agent.
Inspect any existing Agent named `cluster-security-review` before applying this
manifest. Review its diff and preserve existing configuration; do not overwrite
someone else's Agent without target-side authority.

```bash
set -euo pipefail
SCAN_CONTEXT='{{KUBE_CONTEXT}}'
KAGENT_NAMESPACE='{{KAGENT_NAMESPACE}}'
MODEL_CONFIG='{{MODEL_CONFIG}}'
MCP_SERVER='{{MCP_SERVER}}'
CONTROLLER_NAMESPACE='{{CONTROLLER_NAMESPACE}}'

kubectl --context "$SCAN_CONTEXT" get crd agents.kagent.dev -o json |
  jq -e 'any(.spec.versions[]; .name == "v1alpha2" and .served == true)'
kubectl --context "$SCAN_CONTEXT" get namespace "$KAGENT_NAMESPACE"
kubectl --context "$SCAN_CONTEXT" -n "$KAGENT_NAMESPACE" get modelconfig "$MODEL_CONFIG" -o json |
  jq '{name:.metadata.name, conditions:.status.conditions}'
kubectl --context "$SCAN_CONTEXT" -n "$KAGENT_NAMESPACE" get remotemcpserver "$MCP_SERVER" -o json |
  jq '{name:.metadata.name, generation:.metadata.generation, observedGeneration:.status.observedGeneration, conditions:.status.conditions, tools:[.status.discoveredTools[]?.name]}'
kubectl --context "$SCAN_CONTEXT" -n "$KAGENT_NAMESPACE" get remotemcpserver "$MCP_SERVER" -o json |
  jq -e '[.status.discoveredTools[]?.name] | contains(["k8s_get_resources","k8s_describe_resource","k8s_get_resource_yaml"])'
```

Confirm current conditions indicate accepted/ready dependencies, with observed
generation matching the configuration where reported. Tool discovery must contain
all three exact names; then inspect the installed tool input schemas. The upstream
get tool accepts `resource_type`, optional `resource_name`/`namespace`,
`all_namespaces`, and `output`; do not assume your installed version matches it.
The prompt uses structured output because default wide tables omit security fields.
The MCP backend must already target the same local cluster and have sufficient
authorised read access; deployment kubectl context does not retarget an MCP backend.
If prerequisites fail, resolve the specific dependency before deploying. Never
substitute a shell or arbitrary-command tool to make this Agent work.

## Render, dry-run, deploy and invoke

Edit the three manifest fields described above, then render and run server schema
and admission validation against the **explicit selected context**:

```bash
bash scripts/validate-manifests.sh
kubectl --context "$SCAN_CONTEXT" apply --dry-run=server -k manifests
```

When deploying to that selected cluster is authorised, apply this Agent and gate
on Accepted, Ready and presence in the controller API. These deployment/helper
commands are operator actions; the Agent itself has no apply or port-forward tool.
The readiness helper requires current generation evidence. If the installed
controller does not expose it, report that missing gate and use a reviewed
version-specific receipt; do not treat an old Ready=True as acceptance.

```bash
kubectl --context "$SCAN_CONTEXT" apply -k manifests
scripts/kagent-verify-agent.sh --agent cluster-security-review \
  --ns "$KAGENT_NAMESPACE" --controller-ns "$CONTROLLER_NAMESPACE" \
  --context "$SCAN_CONTEXT" --timeout 180
SCAN_OUTPUT_ROOT='{{PRIVATE_OUTPUT_DIRECTORY}}'
umask 077
SCAN_CONTEXT_ID="cluster-security-review-$(date -u +%Y%m%dT%H%M%SZ)-$$"
SCAN_OUTPUT_DIR="$SCAN_OUTPUT_ROOT/$SCAN_CONTEXT_ID"
mkdir -p "$SCAN_OUTPUT_ROOT"
mkdir "$SCAN_OUTPUT_DIR"
printf '%s\n' "$SCAN_CONTEXT_ID" > "$SCAN_OUTPUT_DIR/context-id.txt"
if scripts/kagent-a2a-invoke.sh --agent cluster-security-review \
  --ns "$KAGENT_NAMESPACE" --controller-ns "$CONTROLLER_NAMESPACE" \
  --context "$SCAN_CONTEXT" --context-id "$SCAN_CONTEXT_ID" --timeout 720 \
  --receipt-file "$SCAN_OUTPUT_DIR/a2a-response.json" \
  --text "$(cat scan-prompt.txt)" > "$SCAN_OUTPUT_DIR/report.pending.md" \
  2> "$SCAN_OUTPUT_DIR/invocation.log"; then
  mv "$SCAN_OUTPUT_DIR/report.pending.md" "$SCAN_OUTPUT_DIR/report.md"
else
  SCAN_INVOKE_RC=$?
  printf 'Review did not complete; exit code %s. Inspect the private invocation log and session.\n' "$SCAN_INVOKE_RC" >&2
  exit "$SCAN_INVOKE_RC"
fi
```

The helper owns its temporary controller port-forward and sends the correct A2A
envelope. The 720-second client timeout allows a best-effort ten-minute review and
report generation; it does not enforce or cancel the Agent's work. A client timeout
does not prove the review stopped: inspect the existing session before any retry.
Avoid concurrent duplicate scans. Readiness alone does not prove successful tool calls, evidence quality, namespace
exclusion or scan coverage. Inspect the report and follow
[TOOL-TRACE-VERIFICATION.md](TOOL-TRACE-VERIFICATION.md). A missing or incomplete
trace leaves the safety gate unverified. A failed/unavailable check must appear as
a gap. The helper rejects failed/nonterminal tasks even when they contain text;
`report.md` is promoted only after successful invocation. Retain any partial output
as incomplete evidence and do not retry automatically.

## Evidence and review contract

The data shapes are the Agent CR and these report records; no custom runtime is
required:

```text
Evidence: {id, tool, arguments, resource, field, excerpt, timestamp}
Coverage: Namespace | Check family | Complete/Partial/Not assessed |
          Objects reviewed/total if known | Evidence IDs | Reason/gap
```

The report covers exposure/routes/auth, workloads/PSA, RBAC, ingress **and** egress
network selectors, admission/Kyverno and existing reports. Cluster-wide checks
include nodes, ClusterRole bindings and admission policies. Excluded namespace
subjects in global bindings are recorded only as excluded, never followed.
Every finding must reference short sanitised source evidence and distinguish
confirmed configuration from conditional risk. Exact benchmark controls/versions
must be verified; otherwise only the benchmark family is mapped as unverified.
No invented CVEs, scanner execution, compliance scores or clean unexamined scope.

## Other clusters

Not configured here. A separate, explicitly scoped extension would need a named
target cluster, approved read-only Kubernetes MCP endpoint/identity, and its own
Agent/system scope. Keep the local Agent unchanged until that extension is
reviewed. Never auto-switch contexts, reuse an arbitrary remote endpoint, or add
cluster-switch/exec tools to the local Agent.

## Validation status and references

This bundle is an offline handoff. No workplace deployment, server dry-run,
scanner execution or review report has been produced. All target runtime gates
remain pending. Final offline checks and resolution of the Claude/Kimi review
are recorded in [REVIEW-RESOLUTION.md](REVIEW-RESOLUTION.md). Run the shipped
checksum verifier before adapting files, then the manifest validator and regression
fixtures. Neither offline fixture results nor a model review proves live cluster
behaviour, namespace isolation or scanner execution.

Official sources used for the resource/tool shape:

- https://github.com/kagent-dev/kagent/blob/main/go/api/config/crd/bases/kagent.dev_agents.yaml
- https://github.com/kagent-dev/kagent/blob/main/go/api/config/crd/bases/kagent.dev_remotemcpservers.yaml
- https://github.com/kagent-dev/tools/blob/main/pkg/k8s/k8s.go

Repository helpers: `scripts/validate-agent-cr.py`,
`scripts/kagent-verify-agent.sh`, `scripts/kagent-a2a-invoke.sh`.
