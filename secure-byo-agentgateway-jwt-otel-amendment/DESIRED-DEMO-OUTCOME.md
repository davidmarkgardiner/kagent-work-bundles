# Onboard one complete agent without Substrate

The delivered demonstration starts with a newly named, schema-valid owner YAML. The user selects approved variable fields, applies that file, and receives a working, secured agent plus a fresh passing GoldenScenario result. The existing HostedAgent operator and its trusted platform integrations configure the per-agent resources. No per-agent manual route, grant, policy, content-binding or test-job repair may be required.

This is the office implementation's acceptance contract. It is not evidence that the current office operator already implements it. The existing four-CRD standalone reference uses a separately prepared Job and GoldenScenario. Extend its real operator/profile integration to automate those steps. Preserve the existing `skills.platform.kagent.dev/v1alpha1` APIs and make only reviewed compatible schema changes.

## What the user selects

| User-facing choice | Platform responsibility |
| --- | --- |
| Agent name, authorized namespace/team and purpose/instructions | Validate identity, ownership, naming and instructions against the approved profile |
| Approved no-Substrate runtime profile | Assemble/deploy the approved image with its service account, configuration and runtime controls |
| Approved model profile | Create or bind the actual ModelConfig and Gateway model path, keeping credentials private |
| Approved MCP capabilities or ToolGrant references | Bind only permitted tools and destinations with exact grants and runtime permissions |
| Approved skills and knowledge releases | Resolve and pin Ready immutable content, validate ownership and hashes, and make it usable by the running agent |
| Approved scenario/profile selection or platform default | Derive the GoldenScenario, its agent/spec/content pins and platform-owned pass criteria |

These are logical inputs, not a proposed Kubernetes schema. Map them to the actual installed HostedAgent fields and approved profiles. Return the final apply-ready YAML and a short field guide after implementation. Do not invent fields in a sample and claim the installed API accepts them.

The user does not write raw security policies, grants, service accounts, image credentials or arbitrary backend URLs. Protected profiles determine the Gateway, JWT issuer/audience, authorized subjects, exposure rules, telemetry privacy and network baseline. The owner cannot weaken the GoldenScenario or grant itself new capabilities by editing its request.

"Build the agent" means assemble and deploy it from approved components. Container builds, registry imports, shared CRDs/controllers, approved content releases, credentials, Gateway and observability services are platform prerequisites. The onboarding operator must not pull public artifacts or perform an implicit container build in the air-gapped office.

## What the operator process must produce

1. A real no-Substrate runtime with the selected model, MCP tools, skills and knowledge available to its actual execution path. Record whether the profile deploys a long-running Deployment or a Job. A completed Job does not prove a long-running agent service.
2. A usable authenticated agent endpoint through the existing Agent Gateway, with its HTTPRoute, exact destination ReferenceGrants and attached JWT/authorization policies. Shared Gateway resources stay platform-owned; a trusted routing/grant owner performs privileged operations.
3. The necessary per-agent RBAC, Kyverno-compatible workload controls, effective network restrictions, configuration/Secret references and UID-pinned ownership inventory. Preserve independent backend authorization, capability checks, expiry and revocation.
4. Automatic authentication and authorization checks through the real endpoint. Prove authorized access, required JWT denials, caller/runtime separation and forbidden-operation rejection without backend dispatch.
5. Automatic creation/submission and verification of the approved GoldenScenario against the newly generated runtime and endpoint. Pin its result to the actual owner UID, relevant generation/spec digest, deployed image, selected content and capability versions. A prior same-name result cannot pass a new request.
6. A user-visible outcome with the endpoint, deployed bindings/resource inventory, security-test summary, GoldenScenario verdict and evidence references. Report missing dependencies or failed checks with a specific reason. Do not report the onboarding complete from resource existence or a Ready Pod alone.

The existing GoldenScenario contract contains `hostedAgentRef` and `hostedAgentSpecSha256`. The platform process computes those from the actual finalized HostedAgent. The user must not manually calculate hashes or submit a separate test Job after applying the owner YAML. Use the approved GoldenScenario defaults/profile or a reviewed compatible extension of the current API. Do not require a fifth replacement CRD just to obtain a single-file experience.

## Activation and the GoldenScenario

Resource reconciliation is not atomic. Keep the front door fail-closed and owner access inactive while resources converge. Once configuration, route/policy attachment and network/readiness checks pass, an independent trusted authority may permit the bounded verification identity to run the scenario through the secured endpoint. The composer must not publish its own unrestricted approval.

The platform-owned GoldenScenario must prove actual model execution, approved MCP handler execution, skill loading and knowledge retrieval from the selected pinned content. Its result must include the expected response/citations or other scenario-specific evidence. A matching answer string, a synthetic marker, a configured reference or a requested trace ID alone cannot prove all those bindings worked. Keep content and provider evidence labels accurate.

After the scenario and security checks pass, publish the completed outcome and enable the approved user access according to the independent platform authority. Revocation, stale pins, dependency loss or a superseded request must invalidate the old pass/access state. Preserve bounded verifier authority separately from normal user access so tests do not depend on disabling security.

Condition names are implementation-specific. Use the actual served status contract or a reviewed extension. Any claimed final Ready/complete state must mean that the current request's resource, security and GoldenScenario gates passed.

## What David should be able to watch

1. Select the approved variable fields in one file and apply a new agent name.
2. Watch the operator create/bind the runtime, model, MCP, skills, knowledge and Gateway/security resources without hand-applied per-agent fixups.
3. Watch the automatic JWT/security checks and GoldenScenario execute against that new endpoint.
4. Inspect a passing result tied to that exact request and see the real model/tool/content evidence, Gateway spans and access logs. Verify Tempo, log-store and metrics-store delivery separately using the existing observability handoff.
5. Invoke the agent as an approved caller, then show an unauthorized caller denied. Demonstrate a deliberately invalid profile/binding failing closed in the approved drill scope.

Deliver the final owner YAML, field guide, generated inventory, outcome/status output, GoldenScenario receipt and repeatable demo/reset commands. Continue implementation until this final-revision rehearsal passes, or record the exact unresolved gate and continue independent work. Substrate, Entra integration and new dashboards remain outside this iteration.
