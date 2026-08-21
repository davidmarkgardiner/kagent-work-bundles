# Kubernetes Delivery Harness

This is a reusable, **read-only-by-default** delivery loop for Kubernetes work
that touches kagent, agentgateway, Argo Workflows, and Argo Events. It turns a
well-scoped issue into a reviewed manifest and a reproducible evidence bundle;
it never gives a language-model agent direct `apply`, `patch`, `delete`, or
`exec` capability.

It is deliberately a delivery aid, not a second deployment platform. GitOps
and the existing approved Argo workflows remain the only paths that change a
cluster.

## What it gives an engineer

```text
Issue / desired outcome
        |
        v
1. intake agent --------> Definition of done, scope, risks, test matrix
        |
        v
2. manifest author -----> Proposed YAML/Kustomize patch (not applied)
        |
        +----------------------------+
        v                            v
3. specialist review          4. deterministic validation
   kagent / agentgateway /        render -> client dry-run -> policy checks
   Argo / Events                  -> optional server dry-run
        |                            |
        +-------------+--------------+
                      v
5. evidence reviewer -> PR-ready report: pass, fail, or bounded blocker
```

The loop is bounded: a failing gate returns a concrete failure report to the
author, who may revise it **twice**. A third failure is a `BLOCKED` result with
the command output and the named owner; it does not spend tokens retrying the
same thing indefinitely.

## Contents

| Path | Purpose |
|---|---|
| `agents.yaml` | Five deployable `kind: Agent` specialists, all read-only. |
| `workflows/manifest-validation-workflowtemplate.yaml` | Optional Argo validation workflow. Server validation is off by default. |
| `scripts/validate-manifests.sh` | Local render, YAML, policy and optional API dry-run gate. |
| `scripts/check_manifest_policy.py` | Portable policy checks with no cluster access. |
| `kustomization.yaml` | Renderable index for the agents and workflow. |

## Run the local gate first

The script accepts a single Kubernetes YAML file or a Kustomize directory. It
does not mutate the cluster. A server-side dry-run is opt-in because Kubernetes
authorisation for it commonly includes create/patch verbs.

```bash
cd work-agent-bundles/kubernetes-delivery-harness

# A plain manifest file
scripts/validate-manifests.sh --path ../my-change.yaml

# A Kustomize root
scripts/validate-manifests.sh --path ../my-overlay

# Only against an explicitly selected, pre-approved context
scripts/validate-manifests.sh --path ../my-overlay \
  --server-dry-run --context {{APPROVED_CONTEXT}}
```

The report states `PASS`, `FAIL`, or `BLOCKED`. `BLOCKED` means a required
local binary or an explicit approval is missing; it is not silently treated as
a successful test.

## Optional in-cluster gate

The WorkflowTemplate is safe to install as a template, but it intentionally
ships with **no ServiceAccount or RoleBinding**. Platform owners must create
the referenced `k8s-delivery-validator` ServiceAccount and bind it to the
smallest approved set of resource types and namespaces before submitting the
template. Keep `server_validation=false` until its dry-run permissions are
approved. The template always runs a client-side parse first, has a 10-minute
outer deadline, and never runs `kubectl apply` without a dry-run flag.

```bash
kubectl kustomize . | kubectl apply --dry-run=client -f -
kubectl apply -f workflows/manifest-validation-workflowtemplate.yaml

argo submit --from workflowtemplate/kubernetes-manifest-validation \
  -n argo \
  -p manifest="$(cat rendered.yaml)" \
  -p source_ref="repo@commit-or-pr" \
  -p server_validation=false \
  --watch
```

Do not add a broad ClusterRole merely to make server dry-run pass. If the
target manifest needs permissions outside the approved validation scope, the
right outcome is `BLOCKED: validation RBAC review required`.

## Specialist contract

Each Agent in `agents.yaml` has an A2A skill and the kagent tool-server's
read-only tool set. Deploy only after replacing `{{MODEL_CONFIG}}` with a
ModelConfig that exists in the target `kagent` namespace:

```bash
sed 's/{{MODEL_CONFIG}}/default-model-config/g' agents.yaml \
  | kubectl apply --dry-run=server -f -

scripts/kagent-verify-agent.sh \
  --agent k8s-delivery-intake --ns kagent \
  --smoke 'Create a definition of done for an Argo WorkflowTemplate change.'
```

The gate above only proves that the Agent is accepted, ready, controller-listed,
and returns a reply. It does **not** prove the proposed YAML is correct; run the
manifest gate on every proposal.

## Prove a model route before assigning it specialist work

`ModelConfig Accepted=True` and a resolved agentgateway route are configuration
signals, not a model proof. Run the disposable A2A smoke for every model you
intend to route to an agent. It creates a tool-less Agent with explicit
resources and A2A skill tags, verifies an exact reply, then deletes it even on
failure.

```bash
# Current RED examples. Substitute the ModelConfig names in another cluster.
scripts/kagent-model-route-smoke.sh --context red \
  --provider kimi --model-config buzz-sdlc-kimi-k2-7-code \
  --expected KIMI_KAGENT_OK

scripts/kagent-model-route-smoke.sh --context red \
  --provider minimax --model-config minimax-model-config \
  --expected MINIMAX_KAGENT_OK

scripts/kagent-model-route-smoke.sh --context red \
  --provider glm --model-config zai-model-config \
  --expected GLM_KAGENT_OK
```

The test checks the **installed** ModelConfig. On RED, MiniMax and GLM are
currently routed via the Hermes compatibility endpoints, while Kimi uses the
dedicated K2.7 agentgateway route. Keep that distinction explicit in evidence;
an accepted public `HTTPRoute` alone does not prove kagent uses it.

| Agent | Job | Required hand-off |
|---|---|---|
| `k8s-delivery-intake` | Turn the issue into DoD, scope, risks and a test matrix. | `DELIVERY_BRIEF` |
| `k8s-manifest-author` | Propose a minimal YAML/Kustomize diff. | `MANIFEST_PROPOSAL` |
| `k8s-platform-reviewer` | Review kagent, agentgateway and workload safety. | `PLATFORM_REVIEW` |
| `argo-integration-reviewer` | Review Argo DAG, Events and bounded execution semantics. | `ARGO_REVIEW` |
| `k8s-evidence-reviewer` | Reconcile gates and give the PR-ready verdict. | `DELIVERY_EVIDENCE` |

## Definition of done for every issue

1. The desired cluster effect and exact namespaces are explicit.
2. The manifest renders and passes client-side dry-run.
3. The policy check has no errors; warnings are either resolved or recorded.
4. Any server dry-run includes the exact approved context and result.
5. kagent changes prove Agent `Accepted`, `Ready`, controller discovery and an
   A2A smoke reply using `scripts/kagent-verify-agent.sh`.
6. Argo changes prove the template can be submitted in a non-production
   environment and has an outer deadline, service account and bounded retries.
7. The evidence reviewer returns one of `READY_FOR_PR`, `NEEDS_REVISION`, or
   `BLOCKED` with evidence rather than a status-column guess.

## Lifting this into another Kubernetes repo

Copy this folder, then change only:

1. the namespace/model configuration and deployment method;
2. the local `check_manifest_policy.py` rules for that repo's policies;
3. the specialist prompts and allowed read-only MCP tools;
4. the `Definition of done` section to reflect its release process.

Keep the invariants: agents draft and inspect, deterministic tools validate,
and a narrowly authorised workflow performs any approved cluster operation.
