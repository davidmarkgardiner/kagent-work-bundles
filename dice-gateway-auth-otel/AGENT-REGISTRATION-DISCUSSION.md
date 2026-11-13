# Register adaptive agents without fixing every future task

Our proposal is to register the accountable service, approved operating scope, and capability versions, then record each execution automatically. An agent can adapt its plan to a new problem within those limits. A change in permitted access or material business risk takes the appropriate review path.

This is a discussion proposal. It does not establish an exemption from the bank's registration, identity, change, data, or model-risk processes. Whether registration currently takes weeks, and which part causes that delay, needs evidence from the process owners.

## The concern we want to address

Some agents deliver a stable, specific function. Others investigate a changing problem, select relevant guidance, and compose an approach at runtime. We should support both patterns.

If approval requires an exact future task description for every new composition, it could make an adaptive service impractical to use. The team would need to predict each incident or question before it arrives. The useful approval question is which problems the service is authorised to address, with which data, capabilities, constraints, and accountable owner.

Non-deterministic behaviour makes runtime enforcement and evaluation more important. It does not require us to pre-approve every possible sequence of reasoning or tool calls. It also does not remove the need for identity, ownership, or limits on intended use.

## Tools are central, but the complete execution boundary matters

The model can propose an action. Independently enforced authorisation determines whether an execution channel can perform it. A description such as "read-only agent" is not an access control.

Gateway policy, MCP method checks, typed argument/result limits, backend grants, and network controls can bound tool execution. The effective boundary must also cover direct APIs, SDK calls, shell/code execution, files, memory, credentials, outbound destinations, and delegated agents. If one of those paths bypasses the tool Gateway, registering the MCP catalogue alone leaves an ungoverned capability.

A skill is usually guidance, but its package can also contain scripts, dependencies, or instructions that influence data handling. Its version and provenance matter. Executable content needs the relevant software and execution controls. Retrieved documents and tool responses remain untrusted data, even when the retrieval service is approved.

Agent definitions still influence behaviour, disclosure, quality, escalation, and business decisions. An agent with unchanged read permissions can produce a harmful recommendation or expose permitted information to the wrong recipient. Intended use, model/content changes, evaluations, and output/data controls therefore remain part of governance.

## Separate the records by what they govern

The following is a proposed logical model. Map these records to existing systems of record rather than assuming one new registry must own everything.

| Record | What it records | When it changes |
| --- | --- | --- |
| Stable agent service or approved profile | Owner/sponsor, supported problem domain, consumers, environment, risk/data classification, approved runtime/model options, capability bindings, evaluation requirements, limits, support and retirement policy. | When the service's approved scope or operating contract changes. |
| Identity and deployed instance | Principal and deployment identity, approved profile/release, environment, effective grants, credential lifecycle, deployment provenance, and disable/revoke controls. | At deployment or an approved identity/access change. Ephemeral instances also remain accountable. |
| MCP service and exposed operations | Server owner, connection and identity contract, method/schema/version, backend/data scope, enforced bounds, audit, availability, and permitted consumers. | When a service, operation, backend contract, or approved binding changes. Registering a server must not approve every future tool it exposes. |
| Skill/content release | Owner, source, immutable release/digest, review and evaluation evidence, declared dependencies, and whether it contains executable code. | For a new reviewed release. Referencing a skill does not grant its requested permissions. |
| Task execution | Requester, service/profile and resolved release, runtime/delegation identities, selected skill/model/tool versions, data scope, approvals, policy decisions, outcomes, and trace/execution links. | Automatically for each run, including ephemeral workers and their cleanup. |

Distinguish catalogue registration for discovery, directory identity for authentication, connection grants for authorisation, release/change records, and the execution audit. One status called "registered" should not silently mean all five have passed.

A new prompt or plan does not automatically require a new directory identity. It does require attribution to an approved service and an execution record. Use separate principals where the environment, tenant, data boundary, permissions, or required accountability demands them. An ephemeral worker that has its own principal must still satisfy the applicable identity lifecycle policy.

## Approve reusable profiles and record their use

As an example, a proposed "namespace investigation, read-only" profile could permit bounded workload and event reads in named namespaces, reviewed runbooks, and an approved model route. It could exclude Secrets, resource mutation, arbitrary shell, unapproved egress, and cross-tenant access.

Within that approved scope, one request could concern a failed rollout and another a DNS symptom. The agent can select different approved guidance and read operations. The problems differ, while the applicable access and business-purpose boundaries remain controlled. The execution record identifies the resolved content and capabilities used on each occasion.

The platform should reject a request for a new namespace, unapproved tool, external destination, or write action until the relevant access/change review permits it. A model cannot modify its own approval, create a privileged child identity, or expand its rights by editing a definition or loading a skill.

For delegated operations, retain the user's identity and enforce the applicable user permission boundary. For autonomous operations, use explicitly approved application permissions and purpose. Do not silently convert one mode into the other or pass the caller's bearer token to a different protected resource. The platform and data owners must define the actual policy for each binding.

In a multi-agent workflow, delegation must preserve the caller's authorised scope, task constraints, and traceable parent/child relationship. Do not give a child the combined privileges of every available worker. Deleting a worker must not delete its required audit record, and its temporary access must expire or be revoked through the approved mechanism.

## Use a change path proportional to the actual change

These are proposed categories for agreement with the process owners, not existing approvals.

| Change | Proposed treatment |
| --- | --- |
| New task, plan, or selection among already approved releases, within the same intended use and access scope | Automated admission and execution recording under the approved profile. No fresh manual registration solely because the question differs. |
| New worker instance within an approved deployment pattern | Policy-checked provisioning, accountable identity/instance record, bounded access and lifetime, and automated retirement. Follow any required directory registration. |
| Prompt, skill, model, memory, or code revision within the same permission scope | Versioned engineering change with applicable behavioural, data/security and regression evaluation. Escalate if behaviour, exposure, or business risk changes materially. |
| New tool/operation, backend, data class, consumer group, write permission, runtime execution channel, or outbound destination | Review the changed access, containment, data, and consumer boundaries before activation. |
| New business purpose or materially higher-impact decision, even using the same tools | Obtain the applicable business, risk and data review. Unchanged permissions do not establish unchanged risk. |

An automated path should check the recorded approval, current identity, resolved artefacts, permitted bindings, and current policy before execution. It should fail closed when those records are absent, expired, revoked, or inconsistent. An auditable exception has an owner, scope, reason, and expiry.

Per-run recording should identify the deployment and policy state, resolved model/content/tool releases, authorisation decisions, approved data scope, and task/trace/backend execution IDs. Retain only the information permitted by the data and audit policies. Full prompts, results, credentials, and internal reasoning are not a prerequisite for a useful registry record.

## Keep the adaptive path testable

The demonstration should show two different problems handled by the same existing secure kagent service within its approved profile. Show the separate run records and actual tool execution. Then show an out-of-scope capability denied, and the runtime deny/restore test from [the work-agent README](WORK-AGENT-README.md).

This is a useful test of the proposed operating model. It does not prove that a new registration workflow or a policy engine exists. Where those integrations are absent, show the design and the missing implementation explicitly.

## Questions to resolve with the process owners

- Does "agent registration" mean a business service, a deployment release, an identity, a runtime worker, or every task? Which record is authoritative for each?
- Can an approved profile support automated tasks and ephemeral instances? What evidence permits that path, and who owns exceptions?
- Which changes trigger renewed security, data, architecture, business or model-risk review, even without broader tool permissions?
- How are application and delegated access distinguished, and how are child agents prevented from increasing authority?
- Which registry links skills, MCP methods, identities, connection grants, releases and execution evidence? How do revocation and retirement propagate?
- What is the observed lead time at each current gate? Set separate measures for initial profile approval, in-scope provisioning, and scope expansion. Agree targets after measuring the baseline.

The decision we are seeking is an agreed registration unit and change policy. This would preserve accountability and control while allowing an approved service to address problems that were not individually specified at registration time.

## Sources and interpretation

These references support the distinctions above. The proposed profile and approval process are our design recommendation, not a feature or compliance verdict supplied by these documents.

- Microsoft documents agent identities, human sponsorship and lifecycle/access governance. [Governing agent identities](https://learn.microsoft.com/en-us/entra/id-governance/agent-id-governance-overview).
- Entra blueprints support programmatic identity provisioning and an ownership structure. This does not replace organisational approval or grant every child identical access. Verify current tenant permissions and supported APIs before implementation. [Create an agent identity blueprint](https://learn.microsoft.com/en-us/entra/agent-id/create-blueprint).
- MCP guidance requires appropriate token audiences and addresses token passthrough and other bypass risks. [MCP security best practices](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices).
- Microsoft distinguishes required agent behaviour from its changing implementation and recommends scenario-based verification. [Agentic behaviour engineering](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/agentic-behavior-engineering).
- NIST provides a voluntary risk-management framework across AI design, development, use and evaluation. It does not determine the bank's specific registration obligations. [AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework).
