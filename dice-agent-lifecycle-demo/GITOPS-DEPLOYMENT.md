# Rehearse the GitOps deployment

Use the existing Flux and KRO platform. This folder does not contain an invented universal owner schema. The workplace agent copies a valid owner from the target repository and validates it against the installed CRD and reviewed platform profile.

## Prepare the request before recording

Put the agent owner in the approved path selected by the existing Flux Kustomization. Keep the agent, route and security policies in their established ownership paths. Pin the approved skill revision/release and MCP catalog entry through fields the installed schema accepts. Credentials remain in the approved secret mechanism.

Build the actual Kustomize path with the existing pipeline flags. If the path uses Helm or remote dependencies, use its established renderer. Store the rendered output privately and review it before a read-only server validation.

```sh
git -C "$DEMO_GIT_REPO" diff -- "$DEMO_GITOPS_PATH"
kubectl kustomize "$DEMO_GIT_REPO/$DEMO_GITOPS_PATH" > "$DEMO_EVIDENCE_DIR/rendered.yaml"
kubectl --context "$DEMO_CONTEXT" apply --dry-run=server \
  -f "$DEMO_EVIDENCE_DIR/rendered.yaml"
```

Server dry-run does not deploy the owner or prove controller reconciliation. The renderer must not include Secrets or unrelated changes for the on-screen review. Use the normal private review/merge/promotion flow. The presenter does not push or merge an unreviewed change during the meeting.

The classic model-only example and its skills-enabled variants are different contracts. An example with `maxItems=0` for skill/tool lists cannot accept catalog selections. The native-owner form also constrains its profile and instructions. Do not transplant a YAML excerpt between them.

Flux documents the applied revision, readiness and reconciliation behavior in [the Kustomization reference](https://fluxcd.io/flux/components/kustomize/kustomizations/).

## Show Flux receiving the approved revision

These commands inspect the configured Git source and Kustomization. They support a normal GitRepository-based Flux path. If the target uses OCIRepository, HelmRelease or a promotion controller, the workplace agent substitutes that actual source and records it in the private sheet.

```sh
git -C "$DEMO_GIT_REPO" show "$DEMO_COMMIT:$DEMO_GITOPS_PATH/$DEMO_OWNER_FILE"
flux --context "$DEMO_CONTEXT" get source git "$DEMO_FLUX_SOURCE" -n "$DEMO_FLUX_NAMESPACE"
flux --context "$DEMO_CONTEXT" get kustomization "$DEMO_FLUX_KUSTOMIZATION" -n "$DEMO_FLUX_NAMESPACE"
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_FLUX_NAMESPACE" \
  get kustomization.kustomize.toolkit.fluxcd.io "$DEMO_FLUX_KUSTOMIZATION" -o json \
  | jq '{generation:.metadata.generation, source:.spec.sourceRef, path:.spec.path,
      lastAppliedRevision:.status.lastAppliedRevision,
      lastAttemptedRevision:.status.lastAttemptedRevision, conditions:.status.conditions}'
```

Compare the delivered revision with the approved commit. A source fetch alone is not a successful Kustomization application. A `Ready=True` observation from an older generation is not current convergence. The workplace agent checks the exact revision format used by the installed Flux version.

Optional reconciliation is an explicit action through the existing delivery plane. Use it only when a manual reconcile is permitted for the selected demo Kustomization. Otherwise wait for its configured interval.

```sh
flux --context "$DEMO_CONTEXT" reconcile kustomization "$DEMO_FLUX_KUSTOMIZATION" \
  -n "$DEMO_FLUX_NAMESPACE" --with-source
```

Do not substitute `kubectl apply` of the owner for this opening scene. If the request was already deployed, say it is an existing deployment and show its delivered revision. Do not present an old Ready object as a new rollout.

## Capture owner-to-runtime evidence

```sh
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_NAMESPACE" \
  get "$DEMO_OWNER_RESOURCE" "$DEMO_OWNER_NAME" -o json \
  | jq '{kind, name:.metadata.name, uid:.metadata.uid, generation:.metadata.generation, status}'
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_NAMESPACE" \
  get agent "$DEMO_AGENT_NAME" -o json \
  | jq '{name:.metadata.name, owners:.metadata.ownerReferences,
      generation:.metadata.generation, observedGeneration:.status.observedGeneration,
      conditions:.status.conditions}'
```

Follow the actual ownership chain through any intermediate objects. Labels and matching names alone do not prove KRO created a workload. Show the graph's expected generated objects and the exact route-policy attachment/status. Do not print entire Secret-bearing manifests or raw pod environments.

## Roll back through GitOps

Use the target repository's normal revert/promotion process for the recorded commit and wait for the exact Flux revision and resource state. Check whether pruning is enabled before claiming removal. Removing the owner file without pruning may leave it live. Do not delete the namespace, shared RGD, Gateway, ModelConfig, collector, identity or MCP service. Keep UID-bound cleanup and finalizer behavior with the platform's existing runbook.
