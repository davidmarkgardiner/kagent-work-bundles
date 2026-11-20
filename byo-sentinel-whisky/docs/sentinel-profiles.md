# KRO Sentinel profiles

The platform design uses Flux or Sync to reconcile Sentinel custom resources. KRO expands each instance into the resources its scanner needs. The two downloadable definitions each manage a ServiceAccount, Role, RoleBinding and suspended CronJob in the instance namespace.

| Profile | Source in this bundle | What it checks |
| --- | --- | --- |
| Generic application, with Whisky as the example | Workplace Sentinel source still needs confirmation. The repository's generic application certification RGD is a separate reference. | The workplace generic scanner contract. |
| cert-manager | Workplace Sentinel source still needs confirmation. | Confirm the intended certificate and issuer checks with the existing owner. |
| ExternalDNS controller rollout | [RGD](profiles/external-dns-rgd.yaml) · [Instance example](profiles/external-dns-instance.yaml) | One existing ExternalDNS Deployment. Compares its observed generation and desired, updated and available replicas. |
| External Secrets Operator | [RGD](profiles/external-secrets-rgd.yaml) · [Instance example](profiles/external-secrets-instance.yaml) | One existing ExternalSecret. Reads its Ready condition using name-scoped get permission. |

ExternalDNS Deployment health covers the controller rollout. DNS record delivery requires separate evidence. External Secrets Operator health follows its Ready condition. Checking refresh freshness against the configured refresh policy remains a separate pilot enhancement. The profile has no permission to read Kubernetes Secrets and emits no provider values or condition messages.

See the [isolated KRO pilot evidence](kro-lab-evidence.md) for live scanner Job results and remaining integration checks.

## Combine the shared baseline with the specialist

Keep the generic scanner enabled for the workload when adding a specialist. For the pilot, pair the existing generic workload registration with each supplemental RGD under the same application or platform-component identity. Let each scanner keep its own expected run and completion receipt. In central triage, correlate findings by cluster, namespace and affected resource. Use the canonical finding type to deduplicate repeated evidence for the same incident while retaining distinct problems.

For example, the generic scanner can report that the External Secrets controller is crash-looping, while the specialist can independently report that a named ExternalSecret has `Ready=False`. These checks can cover different namespaces. Place each scanner beside its approved target and correlate their reports centrally.

The two downloadable RGDs implement the checks listed above. Pairing them with the workplace generic scanner is part of pilot integration. Demonstrate one generic failure and one specialist failure separately, then show that both reach triage when present together. Verify the same ExternalDNS rollout finding from both scanners produces one incident.

## Integrate the profiles

1. Confirm the workplace KRO version, the registered Sentinel APIs, and the existing central report schema. Check that these proposed kinds and names are available. Use an approved digest-pinned image with `/bin/sh` and compatible `kubectl` that runs as UID 65532.
2. Review each RGD through GitOps. Verify KRO accepts it and generates the expected namespaced API. Replace the image placeholder in the platform-owned RGD with an approved digest-pinned image. Use the [GitOps admission policy example](profiles/gitops-admission.yaml) on Kubernetes versions that serve ValidatingAdmissionPolicy v1. Render the controller identity actually seen by admission, including any Flux impersonation, then label the approved namespaces. Restrict instance writes and namespace-label changes through RBAC. Apply these controls before granting team self-service. Test a GitOps write and an ordinary caller denial. Check effective access for ordinary namespace users and review KRO permissions for creating Roles, RoleBindings and CronJobs. The platform-owned schedule is every five minutes in UTC. Replace placeholders in the chosen instance and use a unique instance name of at most 52 characters so the generated CronJob name fits.
3. Wire the runner's bounded JSON result into the existing authenticated report transport. These source candidates emit `healthy`, `unhealthy`, or `unknown` and a bounded reason to stdout. The receiving contract needs the authenticated registration identity, expected run ID and completion, including healthy or unknown scans. The independent missing-report monitor covers runs with no accepted completion.
4. Keep the sample suspended while reviewing generated objects, including effective RBAC. On an approved worker, test one instance against its existing target and capture KRO reconciliation, the scanner output and the receiver read-back before enabling a schedule.

A healthy result is scoped to the individual target and check. An unknown result means the query failed or the ExternalSecret had no known Ready status.

References include the [KRO RGD overview](https://kro.run/next/docs/concepts/rgd/overview/) and [ExternalSecret API](https://external-secrets.io/latest/api/externalsecret/).
