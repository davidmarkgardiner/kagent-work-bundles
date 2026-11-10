# Managed AKS platform delivery slides

Open [index.html](index.html) in Chrome. The six-slide deck is a self-contained HTML file with no build, install, external fonts, or network dependency. Download the raw HTML from GitHub, then open the downloaded file locally.

The deck follows the white-and-red DICE / UK8S secure-agent presentation format. It reuses the published `secure-kro-classic-kagent/journey.html` presentation engine and its keyboard navigation, animation, component details, notes, responsive layout, and print support. The source was read from `kagent-work-bundles` main at `b8a4be748f19c916ebd601bd9045371a40e72e50`.

## Presenter path

1. The delivered platform. Cluster foundation, shared services, and Namespace as a Service.
2. ARM automation. AKS, Azure CNI Overlay, managed Istio, encryption settings, GitOps bootstrap, and platform maintenance.
3. GitOps services. cert-manager, ExternalDNS, KAITO, security policies, and operational configuration.
4. Namespace onboarding. The platform establishes the RBAC role binding as a prerequisite, then applies the security baseline.
5. Application deployment. After onboarding, teams can deploy immediately using the platform manifests and receive the supported HTTPS delivery path.
6. Existing resources. Same-namespace PVCs, supported storage integration, and Key Vault access through Workload Identity and UAMI, with platform guides.

## Controls

Use Left and Right, Page Up and Page Down, Home and End, or the Previous and Next buttons. Press R to replay an illustrated flow. The repeat control offers Off, 3, 5, or 10 seconds. Press N for presenter notes. Click a component for its explanation, prerequisites, and source qualification. Print all slides produces six landscape pages. Reduced motion skips travelling markers.

## Content and evidence

The delivery description comes from the project owner's account on 10 November 2026. The estimated one to two weeks needed to establish equivalent foundations independently is the project owner's estimate. It is not a measured productivity comparison or a service-level commitment.

The deck describes a ready deployment target, not an application installed automatically by namespace creation. The application team supplies a working image, application manifests, routing and certificate requirements, and any application-specific dependencies. HTTPS follows workload readiness, DNS availability, and certificate issuance through the supported platform conventions.

PVC references remain namespace-scoped. Storage and Key Vault resources still require the appropriate network access and owner-granted permissions. UAMI access uses the matching ServiceAccount federation and least-privilege vault access. Current internal guide URLs and environment-specific values are intentionally absent from this public copy.

The animations make no Azure, Kubernetes, identity, certificate, or storage calls. This deck does not establish current runtime health or prove policy enforcement. All examples are sanitized. It describes the current ARM delivery path without presenting KRO or ASO exploration as the deployed cluster lifecycle.

## Files

`index.html` contains the complete deck. To change the narrative, edit the six-entry JSON registry in `<script id="deckData">`. `evidence/browser-review.json` records the checks performed on this edition, with their scope.
