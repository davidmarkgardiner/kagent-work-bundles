# KRO scanner pilot evidence

**20 November 2026 · isolated Kind fixture run**

The shared home-lab Kubernetes context was unreachable and its control plane and workers were stopped. An isolated Kind cluster ran Kubernetes v1.34.0 and KRO v0.7.1. The test used the ExternalSecret CRD from External Secrets Operator chart 0.20.4 and a local non-root scanner image with kubectl v1.34.0.

Both RGDs passed API server dry-run, reached KRO `Active` and generated their custom APIs, ServiceAccounts, Roles, RoleBindings and suspended CronJobs. One-shot Jobs were created from the generated CronJobs.

| Profile | Live Kubernetes fixture | Job result |
| --- | --- | --- |
| ExternalDNS | Deployment reconciled with one available replica | `healthy` |
| ExternalDNS | Deployment scaled to zero | `unhealthy` |
| External Secrets | ExternalSecret with `Ready=True` | `healthy` |
| External Secrets | ExternalSecret with `Ready=False` | `unhealthy` |
| External Secrets | ExternalSecret with no Ready condition | `unknown` |

Effective RBAC allowed each ServiceAccount to read its named target and denied a different target. The External Secrets scanner also received a denial for Kubernetes Secret access.

The initial Job connected to localhost and returned `unknown`. Both profiles now pass an explicit kubeconfig to kubectl using the projected token file and CA. The five successful result checks above were run after the fix. Both schedules stayed suspended.

The fixtures exercise real Kubernetes APIs and generated Jobs. They use a synthetic Deployment and an ExternalSecret status set by the test. ExternalDNS provider delivery, External Secrets provider sync, generic baseline pairing, central receipt, missing-report alerting and GitLab were outside this run. Use the [implementation handoff](implementation-handoff.md) for the remaining acceptance checks.

## Actual controller follow-up

Both upstream controllers were installed in the same isolated Kind cluster. ExternalDNS ran v0.20.0 from chart 1.20.0 and used the in-memory provider with the reserved `sentinel.test` zone. External Secrets Operator ran v0.20.4 and used its built-in fake SecretStore provider.

ExternalDNS read a namespaced Whisky Service and logged creation of its A record and TXT ownership record. The next reconciliation logged that the records were already up to date. The scanner checks the live controller Deployment. Provider reconciliation was verified separately from the scanner output. Scaling the actual controller to zero changed the scanner result from `healthy` to `unhealthy`. Restoring one replica recreated the records and returned the scanner to `healthy`. Both controllers finished Ready and the Sentinel schedules remained suspended.

External Secrets Operator reconciled two actual ExternalSecrets. A valid key produced `SecretSynced` and the expected dummy value in its target Secret. An absent key produced `SecretSyncedError`. KRO-generated Jobs returned `healthy` and `unhealthy` respectively. Fixing the reference produced a Secret, then the next one-shot Job returned `healthy` for the recovered resource. No ExternalSecret status was manually set in this follow-up.

The local provider setup uses [ExternalDNS in-memory reconciliation](https://kubernetes-sigs.github.io/external-dns/latest/docs/contributing/sources-and-providers/) and the [External Secrets fake provider](https://external-secrets.io/latest/provider/fake/). Cloud provider credentials, authoritative DNS, central agent reporting and GitLab were outside the run.

## Review fixes verified in Kind

The updated definitions moved the scanner image and five-minute UTC schedule to the platform-owned RGD. After rendering the lab image, both revised CronJobs stayed suspended and one-shot Jobs against the installed controllers returned `rollout_available` and `secret_ready`. The generated instance CRDs had no image or schedule input.

In a dedicated labelled namespace, two test service accounts had identical RBAC for creating ExternalDNS Sentinel instances. Server dry-run allowed the approved GitOps identity and denied the ordinary caller through the admission policy. This verifies the example policy in the lab. Workplace bindings and effective controller permissions still require review.
