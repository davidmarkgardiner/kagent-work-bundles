# Agent platform naming: work-agent review and adoption plan

**Status: draft for workplace discovery and owner review.** The examples below are proposals, not a claim about current workplace names or an instruction to rename anything.

## Outcome

Make agent platform resources easy to find, understand and refer to consistently across GitOps, kagent, Agent Gateway, MCP and documentation. Give engineers and agents one approved, versioned naming reference and a small repeatable check. Existing integrations continue to work while the owners decide what to adopt.

## Work-agent request

Review our existing workplace naming standards and the deployed platform before recommending a convention. Deliver an inventory, a gap analysis, an agreed proposal, and a staged adoption plan. The included [draft naming skill](agent-platform-naming/SKILL.md) is a starting point to review against the receiving platform and its agent skill format; it is not installed or approved.

### Scope and operating boundaries

- Cover kagent Agents, A2A agent-card skills, reusable instruction skills, MCP servers and individual tools, ModelConfigs, Agent Gateway Gateways/listeners/routes/policies, Istio Gateways/VirtualServices/DestinationRules/PeerAuthentication, KRO definitions and generated resources, service accounts and identities, and relevant telemetry attributes and catalog entries.
- First discover the exact deployed versions, API kinds, current workspace conventions and current owners. Inspect the existing GitOps repositories, registries/catalogues and read-only deployed object metadata. Use the workplace-approved context and permissions. Record namespace, type and source, not secrets or private values in a public report.
- Do not rename, delete, deploy, change policies, identities, tools or traffic, register resources or create a new registry as part of the review. Treat later implementation and migration as separately scoped work through normal approval and GitOps processes.
- Organisation-wide and service-owned naming rules take precedence. If they differ from this proposal, report the conflict and recommend the smallest coherent alignment. Do not infer that names grant access or imply that an existing resource is unsafe merely because of its name.

## What we already see in the public reference

These examples are a guide to discovery, not workplace evidence:

- `agents/skills/byoa-agent-builder/SKILL.md` uses `{team}-{type}-agent` and a namespace discovery convention. Existing discovery rules may depend on names or labels.
- `agents/grafana-evidence-agent/agent.yaml` uses `grafana-evidence-agent`, A2A skill ID `grafana-incident-evidence-pack`, a separate display name and upstream MCP tool names such as `list_datasources` and `query_loki_logs`.
- `work-agent-bundles/secure-kro-classic-kagent/demo/yaml/` has example `ModelConfig` and `RemoteMCPServer` references; actual destination names and endpoint contracts are environment-specific.
- `agents/skills/yaml-to-kro.md` documents repository-specific RGD name and resource-ID conventions, including KRO reserved identifiers. Verify the installed KRO version before applying these rules to work.

These patterns are not yet a single approved standard. Inventory actual usage before selecting a final convention.

## Proposed starting convention

Use meaningful, stable lowercase identifiers with hyphens for new Kubernetes resources where the target kind permits them. Follow the receiving API's exact validation rules; a conservative target of at most 63 characters is a planning budget, not a claim that every Kubernetes name has the same limit. Account for generated suffixes, Helm/KRO transformations and collision risk before deciding the final length. Use labels/catalog metadata for ownership, environment, capability and lifecycle rather than stuffing all attributes into every name. Avoid internal hostnames, secrets, personal names, temporary version numbers and vague values such as `test` or `new` in durable names.

| Surface | Proposed shape for new work | Example | Boundary |
| --- | --- | --- | --- |
| Agent object | `{domain}-{purpose}-agent` | `grafana-evidence-agent` | Namespaced Kubernetes identity; retain existing discovery labels and IDs. |
| Reusable instruction skill | `{domain}-{purpose}` | `grafana-incident-evidence-pack` | Follow actual skill loader folder/frontmatter rules. Skills are instructions, not necessarily an A2A capability. |
| A2A agent-card skill ID | `{domain}-{capability}` | `grafana-incident-evidence` | Stable external capability ID; human-readable `name` is a separate field. Check client contracts. |
| MCP server / RemoteMCPServer | `{domain}-{purpose}-mcp` | `grafana-observability-mcp` | Distinguish the deployed server/service from a kagent reference; one may be shared. |
| MCP tool | `{verb}_{resource}` for new first-party tools when compatible | `get_workload_health` | Preserve exact upstream/server-exposed names; inspect protocol, SDK, provider restrictions and collisions before choosing. Never silently rename or wrap an existing tool. |
| ModelConfig | `{provider-or-gateway}-{model-or-profile}` | `model-gateway-general` | A configuration reference, not a network endpoint. Avoid embedding credentials or claiming the provider where an abstract profile is intended. |
| Agent Gateway Gateway/listener | `{scope}-agent-gateway`; listener `{purpose}` | `platform-agent-gateway`, `agent-api` | Listener names have their own API constraints and are scoped to a Gateway. Reuse installed conventions. |
| Agent Gateway HTTPRoute | `{subject}-{purpose}-route` | `grafana-evidence-agent-route` | Establish whether subject means caller, agent, MCP or model; route names are namespaced and may be externally referenced. |
| Agent Gateway policy | `{target}-{control}-policy` | `grafana-evidence-agent-caller-auth-policy` | Choose a control-specific name; inspect actual `targetRefs` and supported policy merge/conflict rules. The name does not enforce policy. |
| Istio resources | `{target}-{purpose}-{kind}` where appropriate | `grafana-evidence-agent-ingress-vs` | Kind, namespace, host and selectors define meaning. Do not confuse an Istio Gateway with an Agent Gateway. Follow existing abbreviations if already mandated. |
| KRO RGD / generated resources | Follow existing approved KRO and kind-specific conventions | `agentNamespace` resource ID | RGD name, schema kind, resource ID and generated `metadata.name` are different namespaces and formats. Preserve IDs referenced by CEL. |
| Service account / identity | `{workload}-{role}`; identity format per identity owner | `grafana-evidence-agent-runtime` | Kubernetes identity, UAMI, Entra app, API audience and display name are separate contracts; never rename or rotate them as a naming exercise. |
| Operational labels / catalog | Stable, approved label keys and structured fields | `app.kubernetes.io/name: grafana-evidence-agent` | Respect ownership and label/domain rules. Keep run IDs, secrets and high-cardinality data out of metric labels. |

**Important:** examples are deliberately illustrative. Set the actual vocabulary, abbreviations, owner/team and environment strategy from existing organisational standards. Names may be unique only within a namespace, kind, server, gateway, catalogue, tenant or other actual scope; document the applicable scope rather than assuming global uniqueness. Keep DNS hostnames, URL paths, identity audiences, route object names and display names as separate contracts.

## Plan and deliverables

### 1. Discover and inventory

1. Find existing organisation naming standards, platform catalogues, ownership records, skill loader rules, API/CRD schemas, admission policies and CI checks. Record conflicts and their owners.
2. Build a private inventory for each object: type, namespace/scope, exact current name/ID, human display name, owner, lifecycle, authoritative source, actual references/consumers, version and evidence. Include tool names exposed by each MCP server and how agents refer to them. Avoid secrets.
3. Identify collisions in the correct scope, inconsistent synonyms, ambiguous policies and hidden dependencies. Distinguish generated names from owner-defined names and record their generator. Do not use naming alone as a security verdict.

**Deliverable:** inventory, coverage and access gaps. No changes to live resources.

### 2. Agree the design

1. Propose a short vocabulary and per-kind patterns based on the inventory. Explicitly cover singular/plural forms, abbreviation dictionary, scope, display names, case, separators, allowed character sets, practical length budgets, stable IDs, generated suffixes and collision handling. Avoid automatic truncation without a deterministic collision-safe design.
2. Specify required metadata separately from names: owner, capability, environment, lifecycle, source and support contact as appropriate. Decide whether existing catalogue fields already provide this.
3. Define who owns standards, exceptions and conflict resolution; include rationale, expiry/review date, approving owner and an auditable exception record. Treat approval as a separate decision.
4. Check resource-specific naming constraints against the **installed** CRDs, Kubernetes/Gateway/Istio APIs, skill runtime and MCP clients. Separate protocol constraints from local style choices and upstream server-owned names.

**Deliverable:** proposed naming standard, examples and non-examples, the decision owners, compatibility assessment and unresolved decisions.

### 3. Reference and verify

1. Review the included draft skill against the accepted standard and the actual agent runtime's skill-discovery format. Place a single authoritative reference in the existing approved documentation/skills location; link it from existing onboarding and builder workflows. Decide whether a skill, a shared document or both are supported; avoid conflicting copies.
2. Reuse an existing registry and CI checks where possible. Add a small offline validator only after the standard is accepted: validate kind-specific syntax, scope, collisions within available inventory and explicit exceptions. Check generated names with the real renderer. A local linter cannot prove live uniqueness, permissions or security.
3. Run checks in **report-only** mode against representative existing and proposed manifests. Include positive, invalid, collision, generated-name length and approved-exception examples, plus checks that untouched legacy names are not silently rewritten. Confirm there is a supported owner and a clear path to fix false positives before enforcement.

**Deliverable:** reviewed reference and skill draft, report-only check proposal, test results and remaining ownership decisions. Installation and enforcement require the applicable delivery authority.

### 4. Adopt without breaking consumers

- Apply the approved convention to new resources first. Preserve current object names and IDs unless a separately reviewed migration has an explicit owner and reason.
- For any proposed rename, enumerate inbound references and outbound clients: GitOps, KRO CEL/generated names, services and DNS, agent tool lists, MCP clients, HTTP paths, Gateway targets, VirtualServices, identity audiences, RBAC, dashboards, traces, alert rules, documentation, external consumers and rollback.
- Plan compatibility/aliases only where the actual component supports them; verify route and identity semantics. Define coordinated rollout, owner approval, acceptance tests, monitoring, rollback and deprecation dates. Avoid changing a shared MCP tool contract as a cosmetic cleanup.
- Update the existing platform roadmap and dated evidence through its documented process if the owners accept a milestone. Until then, this is a draft plan: no built/live milestone or workplace compliance claim.

## Return to David

1. Current state and coverage: what was inspected, access gaps, existing owners and authoritative standards.
2. Naming inventory and conflicts, grouped by component and actual uniqueness scope.
3. Recommended convention table with concrete examples and constraints, showing where it differs from existing standards.
4. Proposed skill/document location and owners, plus the draft skill changes needed for the receiving runtime.
5. Prioritised report-only checks and adoption phases, including compatibility risks, exceptions and approval gates.
6. Decisions needed, owners, evidence and the smallest next actions. Clearly distinguish an accepted convention from a proposal and deployed enforcement from offline checks.
