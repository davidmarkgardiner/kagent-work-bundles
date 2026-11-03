# Admission policies

`generate.py` emits three namespaced-scope ClusterPolicies for Kyverno 1.17.1 using `kyverno.io/v1` and CEL validation. The namespace names are exact and must begin `secure-byo-`; wildcard scope and existing shared namespaces are rejected. Policy generation performs no cluster operation.

```sh
python3 policies/generate.py --config reviewed-policy-config.json > policies.json
kubectl --context '{{LAB_CONTEXT}}' apply --dry-run=server -f policies.json
```

Replace the sample config's identities, profile bindings, internal image references and runtime service accounts with observed approved values. `composerUsers` must be exact Kubernetes service-account usernames. `platformUsers` are explicit bootstrap/maintenance users. `nativeControllerUsers` allow the native controller to reconcile Agent/Template status and reserved workload labels. `garbageCollectorUsers` authorize only DELETE, not object creation or updates. Never give owners an identity in these lists.

The model, Harness and content references use the actual native API shapes in `api.kagent.dev/v1alpha3`. `templateTools` must contain the complete reviewed tools array and defaults to no tools. The identity policies do not exempt controllers from model, content or tool validation. `requestKinds` and `requestEquals` constrain both composers' request APIs without creating another request schema.

`workloadImages` optionally constrains every regular/init/ephemeral container to the listed digests; use a nonempty list for the demonstrated environment. `workloadServiceAccounts` constrains selected accounts. `reservedLabelPrefixes` must include every label prefix used to identify trusted workloads in NetworkPolicies. Configure both request and controller-template label protection before relying on those labels for network identity.

`fixtures.py` exposes `cases(config)` for the live acceptance runner. Each specimen identifies the principal, operation, expected decision and expected rule. These fixtures are not a test result. Some route/grant specimens intentionally contain only the admission-relevant fields; enrich them to schema-valid objects before submitting to an API server. Kubernetes schema or RBAC rejections do not prove Kyverno enforcement. Use a bounded test principal that has permission to reach the admission webhook and capture its specific rule denial.

The local CLI versions 1.14.4 and 1.17.1 skipped ClusterPolicy CEL rules during inspection, including an always-false control. Their exit status must not be accepted as behavioral proof. The Python tests validate config safety and policy coverage only. Actual allow/deny behavior requires the installed Kyverno webhook. Require nonzero matched case counts, schema-valid positive controls and the specific policy/rule name on denials.

The policies validate objects already admitted to this exact scope. They do not install namespace baseline NetworkPolicies, approve capability grants, authenticate runtime calls, revoke sessions or control cluster administrators. Protected policy/webhook configuration, restricted RBAC and runtime authorization remain separate controls.

Reference: [Kyverno CEL validation](https://kyverno.io/docs/policy-types/cluster-policy/validate/#common-expression-language-cel).

## Dedicated Substrate worker exception

A namespace-local native Harness requires a namespace-local WorkerPool. Substrate workers need privileges that ordinary application workloads are denied. An optional trusted `workerException` profile admits that specific worker path without adding a namespace or principal exemption to the policy.

```json
{
  "workerException": {
    "serviceAccount": "approved-worker",
    "images": ["registry.example.invalid/reviewed/worker@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"],
    "deploymentName": "approved-worker",
    "controllerUsers": ["system:serviceaccount:ate-system:ate-controller", "system:kube-controller-manager"],
    "namespaces": ["secure-byo-hosted", "secure-byo-kro"]
  }
}
```

Merge this fragment into the trusted config only after observing the actual worker service account, Deployment name, image digests and controller admission identities. All fields are mandatory. The namespace set must be a subset of the exact policy scope. Every regular and init container image must be in the reviewed worker image list. Ephemeral containers disqualify the exception. Deployment names must match exactly. ReplicaSets and Pods must have the expected controlled owner-reference lineage and name prefix. An owner copying the account, image or labels does not qualify because the admission principal must also match.

This is an explicitly privileged worker trust boundary. The named controllers can create the approved worker image with worker-level privileges; the profile does not attest the entire dynamically rendered Pod spec or protect against compromise of those controllers. It affects workload safety checks only. Native content/model/tool binding checks and protected-object ownership are unchanged. Removing the profile disables new exceptional admissions; it does not stop an already running worker. There is no automatic exception expiry. The platform must withdraw the profile and retire worker workloads when the approved use ends.

`fixtures.cases(config)` adds five worker acceptance specimens when this profile is present. Prove the real worker starts and that copied identity, changed image, wrong lineage and ephemeral injection remain denied before claiming the exception works.

The current live receipts prove the real worker starts, approved lineage is admitted, and copied identity, changed image, and wrong lineage are denied. Ephemeral injection has source-policy coverage but no live admission receipt in this POC. Keep that specific subresource admission case as an outstanding target gate.
