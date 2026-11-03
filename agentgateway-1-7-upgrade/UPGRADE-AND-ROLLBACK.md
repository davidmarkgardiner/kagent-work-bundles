# Upgrade through the existing owner

Use the target's approved GitOps/Helm pipeline. The commands below illustrate the lab's separate release ordering using local archives. Fill placeholders privately and review the rendered delta before mutation. Do not adopt unrelated objects or create competing writers.

## Snapshot and preflight

Save current user-supplied and effective values, rendered manifests, Helm revisions, GatewayClass/Gateway/route/policy/backend/parameter resources, destination grants, network rules, session-key references and original workload specifications. Record any existing per-Gateway proxy overrides. Save rollback artifacts and private credentials separately with restrictive permissions.

Compare actual Kubernetes/Gateway API versions with [official support](https://agentgateway.dev/docs/kubernetes/latest/release-notes/versions/). The lab's Kubernetes 1.35 and Gateway API 1.6.2 needed no upgrade. That does not approve a different office version.

Render the new CRDs and controller using local approved archives and a reviewed values file. Preserve effective security, ownership, watch scope, proxy defaults and model-feature settings. Explicitly review the separate `controller.image` and `proxy.image` fields. Supply actual internal destination digests and pull Secrets. Do not copy lab names or public registry defaults into work.

The [controller values example](controller-values.example.json) is a partial merge input, not a replacement for the existing values. Its model-feature setting preserves the lab's disabled baseline; retain the office's actual approved setting instead. Verify pull-secret configuration for generated proxies separately from the controller. The [standalone patch example](standalone-deployment-patch.example.json) is a strategic-merge fragment, not an apply-ready Deployment. Fill its existing container name and private references, then merge it through the actual workload owner. Preserve all other containers, environment variables and configuration.

Use server-side dry-run to validate large CRDs without the client-side last-applied annotation. The lab used `kubectl apply --server-side --dry-run=server --force-conflicts --field-manager=upgrade-validation-only -f {{RENDERED_CRDS}}`. Here `--force-conflicts` is for a **non-persisting validation only**. It does not authorize a real forced server-side apply or change Helm ownership. Plain client-side apply failed because the generated CRD annotation exceeded Kubernetes' size limit.

Inspect stored/served versions and conversion requirements before changing CRDs. Use the existing CRD owner to update them in place. Never delete CRDs or remove a stored version to get validation green.

## Reconcile CRDs, controller, then proxies

Use explicit context and target namespace for every command:

```sh
helm --kube-context '{{CONTEXT}}' upgrade '{{CRD_RELEASE}}' \
  '{{LOCAL_APPROVED_CRD_CHART}}' --namespace '{{GATEWAY_NAMESPACE}}' \
  --values '{{REVIEWED_CRD_VALUES}}' --wait --timeout 10m
```

The 1.7 CRD archive must now be installed before validating existing custom resources against its schema. Run server dry-run on reviewed current objects. Require established CRDs, retained stored versions and applicable defaults/validation compatibility. Do not use `--install` as an ownership-repair shortcut.

```sh
helm --kube-context '{{CONTEXT}}' upgrade '{{CONTROLLER_RELEASE}}' \
  '{{LOCAL_APPROVED_CONTROLLER_CHART}}' --namespace '{{GATEWAY_NAMESPACE}}' \
  --values '{{REVIEWED_MERGED_VALUES}}' --atomic --wait --timeout 10m
kubectl --context '{{CONTEXT}}' -n '{{GATEWAY_NAMESPACE}}' \
  rollout status deployment/'{{CONTROLLER_DEPLOYMENT}}' --timeout=300s
kubectl --context '{{CONTEXT}}' -n '{{PROXY_NAMESPACE}}' \
  rollout status deployment/'{{GENERATED_PROXY_DEPLOYMENT}}' --timeout=300s
```

Helm's wait on the controller does not prove that its separately generated proxies rolled out. Inspect each in-scope proxy's actual image ID/digest, configuration rejection telemetry, current-generation route/policy conditions and listener status. Retain JWT policies and destination ReferenceGrants unchanged unless a separately reviewed compatibility delta is necessary.

For an existing standalone Gateway Deployment, change its image through its actual maintained owner and verify its rollout separately. The lab used a bounded image update because that workload was not Helm-managed. Its immutable config exposed a session-key persistence warning. A newly generated 32-byte hexadecimal key stored in a Kubernetes Secret, referenced through `SESSION_KEY`, resolved the warning without writing the key into config or disabling encryption. Reuse a valid existing key and preserve it across replicas/restarts. Controller-managed Gateways already receive a controller-owned session Secret; do not replace it.

## Verify the outcome

Require allowed JWT invocation, negative JWT cases, caller/runtime separation, forbidden model/tool rejection, handler counters and revocation. Validate repeated-header CEL behavior where applicable. A denial body changing from detailed to generic is expected; a denial becoming an allowed backend dispatch is a regression.

Run one real approved model request and MCP operation. Verify actual returned evidence and Gateway spans/access logs through the existing collector. Query Tempo and log/metrics stores independently for the office demonstration. Preserve privacy before fan-out. A viewer trace is not Tempo proof, and a proxy request is not a full standalone agent workflow.

Re-render the previous telemetry amendment from the actual installed 1.7 policy CRD and full policy snapshot. Keep its exact grants and network fragments under owner review. The upgrade does not itself apply that amendment or finish automated operator onboarding.

Then rehearse a newly named one-file agent request through the existing operator, Gateway, model/MCP bindings and independent activation, using the actual no-Substrate runtime. Do not invoke the native lab helper's `--invoke` path or install Substrate to substitute for missing standalone execution.

## Recover without deleting resources

On a failed upgrade, preserve logs and stop promotion. Helm `--atomic` can revert its controller release, but does not roll back the separate CRD release, generated proxy state, standalone workload, session Secrets or databases as one transaction.

Use the saved previous chart/values and maintained source to restore controller/proxy images and standalone workload configuration. Confirm CRD compatibility before running an older controller. Downgrade CRDs only after checking every current custom resource, stored/served version and conversion requirement against the saved schema. Never delete/recreate CRDs as rollback. Restore a database only with its supported procedure and consistent backup. Preserve session keys and expect reconnects where session encoding changed.

Re-run the same JWT, backend and telemetry canaries after recovery. The lab prepared rollback inputs but did not execute a full downgrade or failure-injection rehearsal. Office rollback remains a target gate, not a proved lab result.
