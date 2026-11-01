# Start the workplace Audit pilot

Use this checklist before deploying this bundle at work. The initial milestone is an Audit policy and a visible report. Keep the existing Azure controls in place during this milestone. The home-lab result is recorded in [LAB-RESULTS.md](LAB-RESULTS.md).

## Confirm the components

| Component | Required preparation |
| --- | --- |
| Existing Kyverno | Record its chart, application version, namespace, release name, controller names and CRD schemas. Confirm background reports are enabled. Reuse the installation when compatible; preserve its existing values and owner. |
| Kyverno, if absent | Have the platform owner install a compatible approved chart through the existing delivery process. The lab tested chart **3.7.1**, application **1.17.1**, on Kubernetes **1.35.0**. Other combinations need target validation. |
| Policy Reporter | Install the separate official **policy-reporter** chart. The lab tested **3.11.2**, with its UI **2.9.1** and Kyverno plugin enabled in the same release. No additional UI or plugin Helm chart is required. |
| Policy and fixtures | Use the supplied JSON manifests. No custom Helm chart is required. Deliver permanent changes through the approved Flux/GitOps path. |
| Operator tools | Provide `kubectl`, Helm for chart inspection or direct installation where approved, and Python 3 for `lab.py`. The lab used Python 3.12. The helper needs no pip packages. Run its offline tests with the workplace Python version. |
| Reporting backend | Policy Reporter uses its default SQLite storage in this configuration. An external database and LGTM are optional. The exported namespace matrix is a Python-generated snapshot; it is separate from the live Reporter UI. |

The exact lab pins and checksums are in [versions.lock.json](versions.lock.json). The [Kyverno values](values/kyverno.yaml) use single replicas and one-minute scans. Do not apply those values over an existing workplace release or replace workplace availability settings with them.

## Prepare approved charts and images

- [ ] Make the required charts available from the approved Helm or OCI repository. The portable bundle contains version locks and values, **not chart archives or container images**.
- [ ] Mirror the selected images into the internal registry when public pulls are unavailable. Record the internal references and manifest digests.
- [ ] Adapt image overrides in a workplace values overlay, including chart jobs and hooks. Render the selected charts and check every container and init-container image before import.
- [ ] Use an approved fixture image if the controlled admission demonstration is in scope. The lab used `busybox:1.37.0`; replacing it requires checking its commands and non-root behavior.

For the pinned Reporter chart and supplied values, the rendered images are:

```text
ghcr.io/kyverno/policy-reporter:3.11.2
ghcr.io/kyverno/policy-reporter-ui:2.9.1
ghcr.io/kyverno/policy-reporter/kyverno-plugin:0.7.3
```

If Kyverno is already installed, use its approved image inventory. For a new installation of the pinned chart with the supplied lab values, the rendered inventory also includes the following images. Re-render after changing values because hooks and optional components can change the list.

```text
reg.kyverno.io/kyverno/kyverno:v1.17.1
reg.kyverno.io/kyverno/kyvernopre:v1.17.1
reg.kyverno.io/kyverno/background-controller:v1.17.1
reg.kyverno.io/kyverno/cleanup-controller:v1.17.1
reg.kyverno.io/kyverno/reports-controller:v1.17.1
reg.kyverno.io/kyverno/kyverno-cli:v1.17.1
ghcr.io/kyverno/readiness-checker:v0.1.0
registry.k8s.io/kubectl:v1.34.3
```

## Check access and connectivity

- [ ] Select the approved cluster with an explicit kube context. Keep credentials and captured cluster metadata outside the portable bundle.
- [ ] Confirm the deployment owner can manage the required Helm releases, namespaces, CRDs, webhooks, cluster-scoped RBAC and ClusterPolicy objects. Use the existing approved executor and delivery process.
- [ ] Confirm the report operator can read namespaces, Pods, Deployments, this ClusterPolicy, PolicyReports, the Kyverno ConfigMap, validating webhook configurations and PolicyExceptions where that API exists. The seed helper also reads Nodes. Treat denied reads as evidence gaps.
- [ ] Allow the API server to reach Kyverno's admission webhook. Allow Kyverno and Reporter to reach the Kubernetes API. Allow DNS and the UI/plugin/backend service connections through applicable NetworkPolicies and service-mesh controls.
- [ ] Start with localhost port-forwarding for the UI. If shared access is required, configure the approved internal route and authentication before exposing cluster findings.
- [ ] Check existing Azure Policy, PSA and other admission controls before introducing the demo namespaces or fixtures. They may reject the deliberately violating specimen, its PSA labels, or the dry-run cases.

The collector currently expects namespace `kyverno`, its standard controller names, ConfigMap `kyverno` and the `wgpolicyk8s.io/v1alpha2` PolicyReport API. Inspect these assumptions in `lab.py` against the installed system. Adapt and review the collector when names or report APIs differ. Do not rename or reinstall workplace components to satisfy the lab helper.

The full 34-case demonstration also assumes the named demo namespaces, `default` for its Audit control case and `policy-reporter` for its exclusion case. Existing admission policies can change those outcomes. Record the actual denying control; an Azure, PSA or RBAC denial is not a successful Kyverno denial test. Do not weaken an existing namespace to make the demonstration pass.

## Begin with read-only discovery

Replace the placeholder and record the results privately. These commands inspect the target; they do not change the current context or install components.

```bash
export WORK_CONTEXT='{{WORK_CONTEXT}}'
kubectl --context "$WORK_CONTEXT" version -o json
helm list --all-namespaces --kube-context "$WORK_CONTEXT"
kubectl --context "$WORK_CONTEXT" get crd clusterpolicies.kyverno.io policyreports.wgpolicyk8s.io
kubectl --context "$WORK_CONTEXT" get deployments --all-namespaces
kubectl --context "$WORK_CONTEXT" get validatingwebhookconfigurations
python3 -m unittest discover -s tests -v
```

If a required API is absent or inaccessible, record that result and resolve its owner, compatibility or access dependency before claiming coverage.

## Deploy the first milestone

1. Record the observed versions, existing policy ownership, exclusions, reporting settings and namespace inventory. Resolve the prerequisite gaps above.
2. Prepare a reviewed workplace overlay for Reporter and any required engine changes. Preserve existing Kyverno configuration, replica counts and resource names. Install through the approved delivery process.
3. Review the scope of [policies/audit.json](policies/audit.json), including its five excluded namespaces. Validate it against the target CRD and introduce it in **Audit** through GitOps.
4. Wait for actual background PolicyReports. Generate the inventory snapshot with `lab.py report` using an explicit context and a private output directory. Adjust the report age limit to the approved scan interval; the lab default is 300 seconds.
5. Open Reporter and the exported namespace matrix. Verify that current Pods have the expected rule results and that excluded, empty, missing or inaccessible namespaces remain distinct from a pass.
6. Introduce the controlled fixtures and demo Enforce overrides only after their namespaces and admission-test scope are approved. Follow the [lab procedure](README.md#run-on-an-explicitly-selected-lab-context). Do not run `seed` or `test` automatically as part of the initial workplace Audit deployment.

The first milestone is complete when the target Audit policy is accepted, controllers are healthy, real background results are visible, and the namespace inventory exposes its coverage gaps. Capture target evidence rather than copying the lab verdict.

## Keep the Substrate rollout as a separate acceptance step

The supplied baseline rejects the capabilities and host access used by the lab's Substrate workers under Enforce. A narrowly scoped Substrate exception has **not** been implemented or tested in this bundle. Record the exact workload, namespace, service account, approved image digest, affected rules, owner, justification and expiry before designing that exception.

Cluster-wide enforcement, a tested Substrate exception, actual webhook-outage behavior and equivalence to the workplace Azure control remain separate acceptance gates. This guide authorizes no Azure exemption or workplace enforcement change.

## Installation references

- [Policy Reporter chart, UI and plugin installation](https://kyverno.github.io/policy-reporter-docs/getting-started/installation.html).
- [Policy Reporter chart configuration](https://kyverno.github.io/policy-reporter-docs/getting-started/helm.html).
- [Policy sources and adaptation notes](policies/SOURCES.md).
