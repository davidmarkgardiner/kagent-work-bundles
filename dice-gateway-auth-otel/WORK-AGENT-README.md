# Complete the main-agent demo and registration proposal

Show the full journey of the main workplace Go Agent, from reviewed intent to an authenticated, observable service that another team can consume. Close the evidence gaps in the current walkthrough. Prepare a registration model that supports adaptive agents within approved permissions.

Use this as the work-agent handoff. The registration model is a proposal for discussion with the platform, identity, data, security, and risk owners. It does not establish a new bank policy or authorise broader access.

## Read the supplied material

1. Read [the registration discussion](AGENT-REGISTRATION-DISCUSSION.md) for the proposed distinction between service registration, approved capabilities, and individual runs.
2. Read [the existing one-sheet](ONE-SHEET.md) and [dated home-lab validation](VALIDATION.md) for the controls and evidence already exercised.
3. Use [the dashboard guide](README.md#provision-the-grafana-view) and [plain Grafana JSON](grafana-dashboard.json) with the actual workplace datasource names, namespace, metric families, and log labels.
4. Keep [the Teams message](TEAMS-MESSAGE.md) as a discussion draft. Do not send it automatically.
5. Implement and rehearse [the confidential-data denial scene](CONFIDENTIAL-DATA-DEMO.md) with synthetic fixtures. This is an additional, untested capability, not part of the existing JWT proof.

The 12 November lab proved two authenticated Gateway hops and correlated tool execution for the Python compatibility profile with synthetic data. It did not prove the workplace Go runtime, workplace Entra configuration, KRO/Flux delivery, or production readiness. A separate Python canary remains useful for isolating faults, but its receipt cannot establish those properties for the Go Agent.

## Establish the current workplace baseline

Inspect the existing deployment and source before proposing changes. Record the exact Agent runtime image, controller and Gateway versions, served CRDs, resource ownership, model route, approved skills, MCP bindings, identity flow, and LGTM destinations privately.

Resolve which identity calls the Agent, which identity the Agent presents to the MCP Gateway, and which identity accesses the backend resource. Distinguish application permissions from delegated user permissions. Inspect the effective policy and resolved runtime endpoint, not only the intended YAML.

Preserve the existing object names, approved grants, authentication, model configuration, delivery process, and telemetry exports. Make the smallest reviewed delta. Do not install the Python lab profile, replace the existing collector, or upgrade the shared platform to make the demonstration fit. Apply changes only within the authority already granted for the receiving environment. This README does not authorise production changes, identity consent, new grants, or publishing information from private evidence.

If the Go instrumentation needs a code or image change, identify that scoped change and its build/provenance requirements explicitly. The Python lab's ConfigMap-based instrumentation does not establish that the Go runtime needs no build. Use an isolated demo identity and route for deny/restore tests. Do not disable a shared identity as a rehearsal shortcut.

## Rework the walkthrough around the same main Agent

Retain the useful security scenes, but make the main Go Agent the subject of the evidence throughout.

| Scene | Action | Required evidence |
| --- | --- | --- |
| 1. Declare and deliver | Show the reviewed owner YAML, selected capabilities, delivery revision, KRO graph, and generated resources. | Source revision and delivered revision match. Current owner and Agent generations reconcile. A fresh Golden result identifies the deployed versions and scenarios it checked. |
| 2. Consume the service | A named approved caller invokes the protected Agent API. Show the semantic PONG and then a real permitted tool request. | Caller endpoint, authenticated principal reference, completed native task, and returned result. PONG alone proves no MCP execution. |
| 3. Follow the actual request | Find the same main-Agent request in the viewer and Grafana. | Native task/context ID, caller Gateway activity, runtime/model/tool activity, MCP Gateway activity, and backend completion. Resolve the exact trace or explicit links between traces. |
| 4. Reject caller credentials | Exercise missing, invalid, expired, wrong-audience, wrong-principal, and swapped-hop credentials. Include relevant missing-role or scope cases. | Expected 401 or 403 decisions, the enforcing component, and no upstream Agent execution for the rejected caller request. Never display tokens. |
| 5. Change caller policy | Deny the valid demo caller through the approved scoped change process, verify the denial, then restore. | Effective policy revision, Gateway 403, and a fresh protected request after restoration. Keep the restore action scoped and prepared before the test. |
| 6. Prove the runtime MCP identity | Keep the direct credential probes, then make the actual Go Agent execute its tool. | Resolved Gateway URL, expected runtime principal, native tool call/result IDs, Gateway decision, and matching backend execution. A test token returning 200 is insufficient. |
| 7. Block bypass and excess capability | Probe direct Agent and MCP Service/Pod-IP access from appropriate test locations. Test Agent-to-MCP direct access from the actual runtime network context. Attempt a safe unapproved operation. | Gateway path works as a positive control. Direct paths are blocked. Server-side policy or backend permissions reject the unapproved operation before any resource-changing action. A model refusal is not the permission check. |
| 8. Deny the runtime, then restore | Deny the runtime identity at the MCP Gateway. While denied, submit a new main-Agent task that requires that tool. Restore access and submit another fresh task. | Actual runtime tool attempt reaches the Gateway and is denied. Backend execution does not occur. The Agent accurately reports unavailable evidence. The restored request has a new successful backend completion. |
| 9. Block a confidential-data request | With the same valid identities, allow a public fixture read and reject a restricted fixture request from the actual Agent. Follow [the detailed scene](CONFIDENTIAL-DATA-DEMO.md). | Gateway data-access policy decision linked to the native tool attempt and received trace, independent audit showing no MCP handler/backend read, and an honest Agent denial. No confidential content in telemetry. |
| 10. Show bounded adaptation | Present two different safe problems to the same approved service/profile, using existing approved capabilities. Request a capability outside that scope as a negative case. | Different plans and run IDs, the same applicable permission boundary, recorded resolved capability versions, and a denied scope expansion. Label any unimplemented registration automation as proposed. |
| 11. Hand over operation | Explain onboarding, supported API/error behaviour, support ownership, evaluation, limits, and rollback. | A readiness card names the evidence, outstanding gates, owners, and limits of the production claim. |

The Agent's outer A2A request can return a completed task that honestly reports a tool failure. Do not require an outer HTTP 403 when the rejected request was the internal MCP call. Verify the actual internal decision and absence of backend execution. Do not accept a cached answer, fixture fallback, or model statement as fresh tool evidence.

## Capture the request evidence

Run two consecutive permitted main-Agent requests in separate task contexts. Record these fields privately for each request:

- Agent/owner identifiers and current generations, source and deployed revisions, and applicable Golden/evaluation reference.
- Runtime image, model route/version where reported, skill and knowledge revisions, MCP connection version, and policy version.
- Caller and runtime identity references, target audiences, and application or delegated access mode. Exclude credentials.
- Native task/context IDs and matched tool call/result IDs with the expected operation and bounded arguments.
- Gateway decision records, received trace IDs, parent/span links, and the backend execution ID.
- Backend completion/result digest and an independent permitted resource read-back where available.
- Grafana datasource/query/time-range references, annotation IDs, privacy checks, and unavailable fields.

Use a bounded live read against an approved target when available. Identify synthetic fixtures, cached results, and live backend reads separately in the walkthrough and receipts.

Prefer propagated context through both Gateway hops. If the main runtime emits separate traces, prove their relationship using explicit span links or an exact execution identifier shared by the native tool response and backend record. A matching Agent name, approximate timestamp, or requested `traceparent` is insufficient. The second request must not be associated with the first request's retained context.

Compare the backend audit before and after denied requests while the demo is idle. Confirm that denied caller traces contain no Agent execution, and denied MCP calls contain no backend execution. Distinguish Gateway admission, MCP method authorisation, and backend resource permissions.

## Make the registration proposal concrete

Use [AGENT-REGISTRATION-DISCUSSION.md](AGENT-REGISTRATION-DISCUSSION.md) as the starting position. Return a proposed record for a stable service/profile, its deployed identity bindings, and a task execution. Map each field to the bank's existing registries and approval processes.

Define the changes eligible for automated processing within an approved profile and the changes requiring additional review. Include behaviour and business-impact changes even when tool permissions stay the same. Confirm how the organisation treats ephemeral workers, separate identities, delegated access, executable skills, memory, and retirement.

Do not implement a parallel registry, create identities, or widen permissions merely to demonstrate the proposal. Use the current authorised sources of record. If automation is absent, return a proposed delta and label that scene as design evidence.

## Return a reviewable result

Return the revised walkthrough and a private resolved command sheet. Include the scoped source/configuration diff, evidence for each scene, any restore actions, and a readiness table using **PROVEN**, **CONFIGURED BUT UNTESTED**, **PROPOSED**, or **BLOCKED**. Name the evidence and owner for each gap.

Cover consumer onboarding and HTTPS/CA trust, identity renewal and revocation, least-privilege data access, runtime containment, approved model routing, content/image provenance, behaviour and security evaluations, telemetry redaction/retention, timeout and concurrency/cost limits, dependency failure, availability/recovery, rollback, and support ownership. These can be reviewed records rather than live demonstrations, but their status must remain explicit.

The minimum main-Agent demonstration passes only when the same Go Agent has a verified delivery/verification record, a permitted tool request through both authenticated Gateway hops, correlated backend evidence, the runtime deny/restore test, and the synthetic confidential-data denial scene. Mark the new scene unproven until its request policy, received telemetry, and independent no-read evidence pass. Production acceptance also requires the receiving platform's applicable operational, security, data, and risk gates.
