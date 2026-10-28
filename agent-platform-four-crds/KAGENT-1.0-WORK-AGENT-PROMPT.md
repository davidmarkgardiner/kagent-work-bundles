# Work agent: port the four-CRD bundle to kagent 1.0

Target kagent **1.0.0-alpha17**, source commit `8392184232e9c78196433a34b1fd3b33db5fcb97`, with the approved matching Substrate platform. This is the latest published 1.0 release checked on 28 October 2026. Start with [build/README.md](build/README.md) and [build/kagent-1.0-target.json](build/kagent-1.0-target.json). Report an installed-version mismatch instead of upgrading or falling back to 0.7.

## Establish prerequisites

Inspect the target's served CRDs, controller image and Helm version through approved read-only access. Verify `api.kagent.dev/v1alpha3` Agent, AgentTemplate, Harness, ModelConfig and RemoteMCPServer contracts at the pinned source. Alpha17 requires `Harness.spec.substrate`. Its Go module pins Substrate `0.6.0-alpha3`. A Substrate-free deployment is not this target.

Reuse the existing approved platform, internal model route and credentials. Inventory all effective images and sandbox runtime assets. Import the native Go ADK digest from the build lock. Build only missing approved helper or collector images. Keep registry destinations, source credentials, target snapshots and generated configuration private.

## Port the implementation before installation

1. Preserve the custom `Skill`, `KnowledgeBase`, `HostedAgent` and `GoldenScenario` APIs, immutable pins, bounded content checks and owner/platform permission separation. Treat historical 0.7 receipts as historical evidence.
2. Replace the legacy HostedAgent output in `implementation/platform/skills-registry/hosted/contract.py` with native AgentTemplate and Agent references. The native Agent selects `spec.template` and `spec.harnessRef`; the template selects `spec.modelConfig.name`. Select an approved same-namespace Harness. Do not copy ordinary `declarative.deployment`, `imageRegistry`, volume mounts or service-account ownership assumptions into this API.
3. Replace or adapt content delivery for the native compiler. Alpha17 template skills use immutable `source.oci`, full-commit `source.git`, or versioned bucket artifacts. Preserve selected-file hashes, limits and private-source authentication. The current Flux-to-ConfigMap projection is not automatically a native skill source. Choose a bounded supported knowledge mechanism and prove both the document version and actual model use. Do not add a vector database or arbitrary fetch tool for this small corpus.
4. Port reconciliation, finalizer/in-use checks, RBAC, profile hashes, readiness and drift handling to the native resources and runtime ownership model. Inspect default native tools and enforce the allowed capabilities at runtime. Instructions and retrospective trace checks alone do not prevent shell or write tools. A platform-owned Harness and bounded read-only MCP must not widen owner permissions.
5. Port packaging, private configuration, rollout order and acceptance runners together. Replace Python-only tracing hooks and ordinary A2A/Pod assumptions with the alpha17 native invocation and OTel contract. Keep documentation-only and fixed `get_demo_status` profiles distinct. General ToolGrants remain outside scope.
6. Update `snapshot.lock.json` only after reviewing changed copied sources. Update offline behavioral checks for native output, rejected stale APIs, bounded content and permissions. Keep the original failure cases. Regenerate source fingerprints and GoldenScenario pins from the reviewed native implementation.

## Validate and hand over

Render offline first. Check objects against the exact alpha17 schemas, then use server dry-run against the explicit approved target. Preserve existing shared resources. Apply only through the authorized workplace delivery process after the platform gates pass.

Run a fresh native request that loads the pinned skill, uses the cited knowledge document and, for the fixed MCP profile, completes only `get_demo_status`. Inspect actual workload image/digest, selected Harness, model route, effective tool permissions, network behavior and correlated model/tool/server telemetry. Prove the source/backend result independently. Missing observations stay UNKNOWN. A Ready resource or passing 0.7 test suite is not native execution proof.

Return the reviewed port diff, immutable image/artifact inventory, schema checks, native acceptance receipt, remaining gaps and bounded rollback. Keep build/import completion, offline verification, lab proof and workplace proof separate.

## Pinned upstream contracts

- Release: https://github.com/kagent-dev/kagent/releases/tag/v1.0.0-alpha17
- Agent: https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha17/go/api/v1alpha3/agent_types.go
- Template and skill artifacts: https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha17/go/api/v1alpha3/agenttemplate_types.go
- Harness: https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha17/go/api/v1alpha3/harness_types.go
- Source dependencies: https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha17/go/go.mod
- Go runtime build: https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha17/go/Dockerfile
