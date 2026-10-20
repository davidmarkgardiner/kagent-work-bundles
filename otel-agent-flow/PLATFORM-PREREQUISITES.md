# Platform prerequisites

The `both` and `substrate` execution modes add the demo to an existing, approved kagent/Substrate installation on the same cluster. `execution.mode: standalone` runs the native ADK in an ordinary Deployment and requires neither platform installation. Its preflight and installer skip their CRDs, WorkerPools, chart-version checks, and telemetry configuration. See RUNTIME-COMPARISON.md. It does not bootstrap a cloud cluster, identity authorities, PostgreSQL, object storage, or a gVisor worker runtime.

The verified compatibility line is:

| Component | Pinned version or contract |
| --- | --- |
| Linux rehearsal Kubernetes | 1.37.0 |
| kagent chart and CRDs | 1.0.0-alpha8, `api.kagent.dev/v1alpha3` |
| Substrate chart | 0.4.0-alpha1 |
| Worker backend | Healthy approved gVisor WorkerPool |
| Declarative runtime | Digest-pinned Go ADK image in `image-lock.json` |
| Model gateway | agentgateway 1.5.0 |
| OTel collector | 0.146.0 |

The cluster must serve the certificate APIs and support the trust-bundle and pod-certificate projections required by this Substrate release. Require healthy API/controller/router/egress/atelet components, the Substrate credential provider, its private CA/identity pools, the platform databases, approved snapshot/object storage, and ready worker capacity before installing the demo. Verify the matching runtime archive and digest on the actual worker architecture. A container image alone does not supply the gVisor runtime assets.

For a fresh workplace platform, use the approved pinned Substrate bootstrap procedure first. That procedure owns CA material, actor identities, storage, runsc/runtime assets, node requirements, and platform credentials. In this repository the related handoff is `work-agent-bundles/agent-substrate/AKS-EVAL-WORK-AGENT-HANDOFF.md`. The earlier AKS evaluation does not replace fresh target checks and did not prove this HTTPS/model/MCP demo on AKS.

AKS regional availability, support status, add-on compatibility, node OS/architecture, admission policy, runtime permissions, storage authentication, and registry access must be verified on the target. Do not assume Kubernetes 1.37 or these alpha releases are approved or available merely because the Linux lab ran them. A version mismatch is an explicit port/review task, not a reason to upgrade the work cluster automatically.

For Substrate execution, the installer expects Helm releases named `kagent` and `substrate`, with the default platform namespaces. The demo chart supports an agent namespace/WorkerPool/snapshot location override. Review the installer if the approved deployment uses different release names or Substrate namespace conventions.
