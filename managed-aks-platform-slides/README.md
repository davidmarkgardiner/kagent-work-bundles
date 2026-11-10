# Managed AKS platform delivery slides

Open [index.html](index.html) in Chrome. The seven-slide deck is a self-contained HTML file with no build, install, external fonts, or network dependency. Download the raw HTML from GitHub, then open the downloaded file locally.

The deck follows the white-and-red DICE / UK8S secure-agent presentation format. It reuses the published `secure-kro-classic-kagent/journey.html` presentation engine and its keyboard navigation, animation, component details, notes, responsive layout, and print support. The source was read from `kagent-work-bundles` main at `b8a4be748f19c916ebd601bd9045371a40e72e50`.

## Presenter path

1. The delivered platform. The managed foundations and the application-team value.
2. Ongoing platform work. Application and AKS upgrade operations, patching, node recycling, NAP capacity management, policies, encryption, and service-mesh lifecycle.
3. ARM automation. AKS, Azure CNI Overlay, managed Istio, encryption settings, and GitOps bootstrap.
4. GitOps services. cert-manager, ExternalDNS, External Secrets, LGTM observability, Kyverno, and the security baseline. Teams connect an approved secret store and add the documented observability annotation for the standard metrics and alerting integration.
5. RBAC onboarding. Controllers bind the namespace to its approved group or access bucket and establish observability-only or namespace-admin access.
6. Application deployment. Apply the application YAML and use the managed HTTPS path for an API or UI. RBAC, certificates, DNS, and mesh traffic have distinct controllers.
7. Existing resources. PVCs, storage, Key Vault through UAMI, databases, and other services use connection templates, guides, and owner-approved permissions.

## Controls

Use Left and Right, Page Up and Page Down, Home and End, or the Previous and Next buttons. Press R to replay an illustrated flow. The repeat control offers Off, 3, 5, or 10 seconds. Press N for presenter notes. Click a component for its explanation, prerequisites, and source qualification. Print all slides produces seven landscape pages. Reduced motion skips travelling markers.

## Content and evidence

The delivery description comes from the project owner's account on 10 November 2026. It includes application upgrade operations, node lifecycle, Azure Policy, Kyverno and Istio policy, encryption defaults, and mesh onboarding. Application teams retain ownership of their code and release requirements. External service integrations are template-assisted and guided, rather than universally provisioned or managed automatically. The estimated one to two weeks needed to establish equivalent foundations independently is the project owner's estimate. It is not a measured productivity comparison or a service-level commitment.

The deck describes a ready deployment target, not an application installed automatically by namespace creation. The application team supplies a working image, application manifests, routing and certificate requirements, and any application-specific dependencies. External Secrets and LGTM are provided by the platform. Teams use the supported secret-store connection and observability annotation, with application-specific permissions and telemetry configuration following the platform guides. The exact annotation key is not included because it was not supplied. HTTPS follows workload readiness, DNS availability, and certificate issuance through the supported platform conventions.

PVC references remain namespace-scoped. Storage and Key Vault resources still require the appropriate network access and owner-granted permissions. UAMI access uses the matching ServiceAccount federation and least-privilege vault access. Current internal guide URLs and environment-specific values are intentionally absent from this public copy.

The animations make no Azure, Kubernetes, identity, certificate, or storage calls. This deck does not establish current runtime health or prove policy enforcement. All examples are sanitized. It describes the current ARM delivery path without presenting KRO or ASO exploration as the deployed cluster lifecycle.

## Files

`index.html` contains the complete deck. To change the narrative, edit the seven-entry JSON registry in `<script id="deckData">`. `evidence/browser-review.json` records the checks performed on this edition, with their scope.

Node auto-provisioning behaviour is supported by the official [NAP overview](https://learn.microsoft.com/en-us/azure/aks/node-auto-provisioning) and [disruption guide](https://learn.microsoft.com/en-us/azure/aks/node-auto-provisioning-disruption), checked on 10 November 2026. The deployed use is the project owner account. The separate public KRO example has NAP disabled and is not deployment evidence for this ARM environment.
