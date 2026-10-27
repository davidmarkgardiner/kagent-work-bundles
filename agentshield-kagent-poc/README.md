# AgentShield with kagent: architecture and PoC plan

This planning bundle explains where AgentShield fits our kagent, agentgateway, Argo, and Flux platform. It contains a source-backed assessment, an offline HTML presentation, and a lab-proven native configuration-drift PoC. The handoff is operator-triggered. An automatic MCP adapter and workplace deployment remain unproven.

## Start here

- [Open the recorded live demonstration](live-demo.html), [read its results](LIVE-DEMO.md), or [run the bounded native PoC](runtime/README.md).

- [Read the one-page benefits and security posture summary](ONE-PAGE-SUMMARY.md), or [open the printable HTML version](one-page-summary.html).

- [Open the HTML presentation](presentation.html) for a 13-slide explanation with diagrams, a concrete investigation example, installation footprint, tests, and workplace transfer.
- [Read the detailed assessment](assessment.html) for the proposed installation recipe, current limitations, and proof gates.
- [Read the validation record](validation.json) for checks performed and unproven runtime behavior.

GitHub displays HTML source. Download the repository ZIP, extract this folder, and open `presentation.html` in Chrome. Keep the folder together so the relative links to the assessment and README work. The presentation needs no server, package installation, internet connection, or JavaScript. Its external source links need internet access. Scroll or use the Previous and Next links. Browser printing produces one slide per page where page size permits.

## Recommendation

Start with the upstream disposable detector-only eval stack on a capacity-checked Proxmox executor. Keep its CNI and mesh changes separate from the existing native kagent cluster. Then install a read-only observer beside native kagent and prove one bounded findings handoff.

The proposed integration is infrastructure observations, AgentShield findings, an authenticated read-only adapter, a kagent security specialist, external human review, and scoped Argo/Flux delivery. The adapter is proposed work. The current reasoning MCP binary serves a saved packet, rather than a continuously refreshed graph.

## Verified source limitations

The research snapshot is 27 October 2026 at upstream commit `b179824e455401783f031a370b8794358a10dd8c`.

- Kubernetes inventory and policy relationships are implemented.
- Agentgateway Gateway API topology is implemented. Access-log ingestion has no live transport. Cross-namespace backends are omitted because ReferenceGrant coverage is unavailable.
- Cilium CNI policy and endpoint state are implemented. Hubble transport is unwired, and L7 policy semantics are omitted.
- Istio and Falco have registered telemetry paths to test with actual events.
- The default Helm install builds inventory. Detection runs only when investigation or Deployment rule authoring is enabled. Setting a model endpoint alone enables neither.
- Investigation requires an OpenAI Responses-compatible endpoint. Test tool use and structured output through the installed gateway.
- The current cloud provider plugin is AWS. Kubernetes discovery on AKS does not prove Azure identity or network-path coverage.

## Installation boundaries

Build the image from pinned source and use a dedicated PostgreSQL 16 database. Keep one process per database. The chart grants read-only Kubernetes access, including access to all Secrets. Secret values are discarded before persistence but enter process memory. ConfigMap data and literal Pod environment data can persist.

The API has no built-in authentication. Restrict API and collector access with verified enforcement and approved authenticating infrastructure. The stock in-cluster listener disables live remediation. Preserve external review and scoped execution identities for the proposed Argo/Flux path.

## Workplace transfer

Carry the reviewed source/image pin, chart adaptation, evidence contract, dummy fixtures, and test receipts. Configure the internal registry, database, TLS, cluster/source IDs, telemetry, enterprise model endpoint, permissions, and existing kagent registration locally. Preserve deployed object names, authentication, and delivery flow. Do not copy lab credentials, kubeconfig, or database state.

The assessment includes proposed success criteria for attack and benign controls, source evidence, duplicate/stale findings, policy enforcement, and rollback. No live workplace or homelab integration is claimed.

## Primary sources

- https://www.solo.io/press-releases/introducing-agentshield
- https://github.com/agentshield-dev/agentshield/tree/b179824e455401783f031a370b8794358a10dd8c
- https://agent-shield.dev/docs/operations/helm/
- https://agent-shield.dev/docs/operations/security/
- https://agent-shield.dev/docs/operations/evals/
- https://agent-shield.dev/docs/concepts/security-semantics/
