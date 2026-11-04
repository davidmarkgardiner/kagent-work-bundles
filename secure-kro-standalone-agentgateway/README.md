# Secure KRO agent and Agent Gateway without Substrate

**4 November DeepSeek run: Golden and the authenticated caller scenario passed live. Claude Sonnet and Opus each repeated a successful caller invocation. Read [the successful run and its lease expiry](DEEPSEEK-RESULTS-2026-11-04.md). The earlier [Kimi HTTP 429 failure](RECHECK-2026-11-04.md) remains preserved.**

This is a separate standalone reference implementation. It replaces the native/Substrate execution dependency for this KRO demonstration with a normal long-running Deployment. Keep the earlier native composition and HostedAgent operator bundles unchanged.

The owner submits one immutable request selecting an approved profile and instructions. KRO creates the runtime/configuration, central HTTPRoute and JWT policy, destination ReferenceGrant and automatic verification Job. Shared platform services supply trusted authentication/authorization and independent verification. No per-agent manual Gateway repair is part of successful onboarding.

Read [the owner field guide](docs/OWNER-CONTRACT.md) for the exact YAML and model/skill/knowledge/tool mapping. Individual dependency choices are currently fixed by one approved profile. The [builder handoff](docs/BUILDER-HANDOFF.md) defines how a future UI or agent can produce this request through the protected pipeline.

The optional [DeepSeek model bridge](docs/DEEPSEEK-MODEL.md) reuses Agent Gateway 1.7 and a platform-owned Secret. Its manifest and immutable-profile maintenance checks are included.

The main office path is **RGD and resource YAML using an existing approved Python helper image**. Reviewed application code and content are supplied through immutable, pinned ConfigMaps. It does not require building or importing a new custom image when that compatible helper image is already available. The existing KRO, Gateway and policy-controller images remain platform prerequisites. See [code delivery](docs/CODE-DELIVERY.md).

Use [the deployment runbook](RUNBOOK.md) for commands. Start with [the work-agent prompt](WORK-AGENT-PROMPT.md), [human prerequisites](HUMAN-PREREQUISITES.md), [design and security boundaries](docs/DESIGN.md), [HostedAgent/KRO comparison](docs/COMPARISON.md), [air-gap preparation](AIRGAP-PREREQUISITES.md) and [the demo walkthrough](DEMO-WALKTHROUGH.md). Read the recorded lab evidence before making a verified-deployment claim.

The reference uses standalone model configuration and pinned data-only skill/knowledge packages. It does not fabricate native kagent Agent/Harness readiness or the workplace's existing four-CRD integration. Its GoldenScenario runs as a separate platform verification Job and produces a receipt. Preserve the workplace's existing ModelConfig, Skill, KnowledgeBase, HostedAgent and GoldenScenario contracts when adapting this reference.

Source, manifests/renderer, tests and content are supplied. Images, charts, Python binaries, credentials and private settings are not included. Reuse the existing approved images and verify compatibility before applying. Missing platform artifacts go through the approved import process. No public image/package/chart pull or package installation is required by the office execution procedure. `build/` is an optional custom-image reference, not the main path's prerequisite.

[The offline showcase](SHOWCASE.html) explains the demonstration; it is not a live dashboard. Use [the observability guide](docs/OBSERVABILITY.md) with the existing amendment/showcase folders from the full repository ZIP. Fill [the delivery report](DELIVERY-REPORT-TEMPLATE.json) from final target evidence; its checks start unverified.

The supported local reference matrix is KRO 0.9.4 and Agent Gateway 1.7.0 on the existing Kubernetes/Gateway API installation. Substrate, actor workers and the native CLI are not runtime prerequisites. Entra, production isolation and automatic lease renewal are separate work.
