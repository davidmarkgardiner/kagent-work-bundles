# Replicate the onboarding flow without Substrate

Read this entire package's README.md, DESIGN.md, and WORK-AGENT-PROMPT.md. This prompt adds the workplace runtime requirement. It does not authorize deployment, publication, upgrades, Azure Policy changes, or credential changes. Use the target environment's existing authorization and delivery process.

## Establish the supported runtime first

The workplace has basic kagent. Substrate is unavailable while the security team considers an Azure Policy blocker. Do not depend on that review completing. Do not remove the policy or install a substitute sandbox.

The phrase "kagent 10" is not an exact version. Record the controller image, Helm release version, served Agent CRD group/version, and a representative existing Agent's structure. Inspect these through approved read-only access. Do not collect Secret values. Keep target details outside this public repository.

This package generates `kagent.dev/v1alpha2` declarative Agents with ordinary Deployments. It was tested with kagent 0.7.13. It preserves ownership by the existing kagent controller. It does not install, upgrade, or replace that controller.

For example, these read-only commands reveal the API groups and served versions without reading credentials. Set `TARGET_CONTEXT` explicitly through the workplace's approved access process.

```sh
kubectl --context "$TARGET_CONTEXT" get crd agents.kagent.dev \
  -o jsonpath='{.spec.group}{" "}{.spec.versions[*].name}{"\n"}'
kubectl --context "$TARGET_CONTEXT" get crd agents.api.kagent.dev \
  -o jsonpath='{.spec.group}{" "}{.spec.versions[*].name}{"\n"}'
```

One group may be absent. Record an actual NotFound separately from an authorization or connectivity error. If only the v1alpha3 API is available, stop the installation path and report the incompatibility. Upstream v1.0.0-alpha10 requires a Harness whose `substrate` field is required. Renaming the API version or dropping that field does not produce a supported Substrate-free Agent.

Pinned upstream source and release information are available at:

- https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha10/go/api/v1alpha3/harness_types.go
- https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha10/go/api/v1alpha3/agent_types.go
- https://github.com/kagent-dev/kagent/releases/tag/v1.0.0-alpha10

A standalone ADK container can run without Substrate. The separate OTel bundle contains such a demo. That demo does not establish that the workplace kagent controller can reconcile this package's declarative Agent. Do not present the two paths as interchangeable.

## Preserve the owner contract

The platform installs the four CRDs once. A human or agent submits custom resource instances through review and GitOps. They do not create a new CRD for every skill or agent.

Owners choose reviewed immutable Skill and KnowledgeBase releases, describe the agent's purpose and instructions, and select the approved runtime and model profile. Platform configuration supplies controller images, deployment settings, namespace, ModelConfig, hashes, and source-controller origin. The current implementation permits one skill, one knowledge article, one model profile, and no general MCP grants. The optional ordinary profile adds one pinned `get_demo_status` capability while retaining empty ToolGrant references. It is a fixed onboarding proof, not a general catalog.

Use `package.py content`, `render`, and `bootstrap` as documented. Owners publish skill and knowledge files to a reviewed content repository. They obtain the reviewed full content commit before rendering declarations. They import and review the generated GitOps repository separately. Use existing Flux and approved secret management. Do not publish credentials or target endpoints with the content.

## Deliver in independently proved stages

1. Extract a ZIP with a tool that preserves Unix executable modes, such as `unzip`. Run `python3 -B verify.py` before editing or rendering. Check the immutable source snapshot and the package's public-safety scan. Record local results as offline checks. The 22 October review records an intermittent macOS timeout-cleanup test failure; preserve any new failure evidence instead of weakening that test.
2. Verify the target API, mounted-content support, account ownership, image, ModelConfig, Flux source origin, namespace, and network permissions. Render outside this public package. Review manifests and use server dry-run against the explicit approved target before rollout.
3. After separately authorized GitOps delivery, prove that Skill and KnowledgeBase reconcile and that HostedAgent generates the expected native Agent. Prove native readiness, mounted file hashes, a fresh skill invocation, a knowledge-document read, and citations using the bundled acceptance runners. Keep the original acceptance strict.
4. Follow `ORDINARY-MCP-DEMO.md` and the bundled `ordinary_demo.py mcp`, `bind`, and `observe` stages for the fixed read-only MCP demonstration. They render reviewable files; bind/observe perform named read-only GETs. Review downstream authority and run actual permission negatives before delivery. The original profile and acceptance remain usable. A general ToolGrant engine is still design-only.
5. Verify the ordinary runtime's interpreter, absence of an existing startup hook, supported tracing flags and exact SDK resource identity. Deploy only the isolated ordinary viewer/collector profile. Do not use the separate v1alpha3/Substrate observer values. The viewer is read-only; its named-GET sidecar alone receives Kubernetes credentials.
6. Run one fresh request that demonstrably reads the skill, reads the knowledge article, calls an approved MCP operation, and uses the approved model route. Correlate the same task/session with received spans and backend-observed MCP evidence. Keep fixture workflows visibly separate. Missing telemetry stays unknown. Native skill read spans currently omit package arguments, so do not invent per-package attribution.

A dropdown, typeahead search, conversational creator, arbitrary runtime image, additional model choices, and automatic promotion are later work. Document the reviewed Git contribution path now. Do not widen this first workplace deployment to implement the catalog.

## Keep Substrate as a later profile

Retain the same logical Skill, KnowledgeBase, purpose, and approved model/tool choices where their contracts remain valid. When the security team clears the policy blocker, discover and pin the actual approved kagent and Substrate versions. Review a separate runtime adapter/profile and its deployment delta. The historical newer lab used alpha17 and Substrate 0.6.0-alpha3; those pins are not a workplace upgrade instruction.

The later profile must prove content delivery, identity, tool restrictions, normal request execution, actor restore/checkpoint/suspend telemetry, and rollback to the ordinary Deployment profile. A profile switch is a planned migration with new acceptance, not an already implemented toggle. Keep the no-Substrate path usable until that acceptance passes.

## Return a bounded report

List the selected API/runtime and evidence, generated files, review decisions, authorization used for any target action, and the exact current gate. Distinguish offline checks, GitLab publication, Flux reconciliation, native execution, and received telemetry. A documentation-only run or standalone fixture is not the requested combined onboarding proof. Do not report the complete work demo ready until that combined proof passes.
