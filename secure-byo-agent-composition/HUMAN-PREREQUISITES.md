# Human prerequisite sheet

Use this sheet in the private work context. Leave boxes unchecked until the named owner supplies current target evidence. Record references and checksums, never passwords or token values. A lab pass is not a work prerequisite pass.

| Handoff field | Record privately |
| --- | --- |
| Target environment and approved scope | `{{TARGET_AND_SCOPE}}` |
| Source repository revision or transferred ZIP checksum | `{{REVIEWED_REVISION_OR_CHECKSUM}}` |
| Runtime path | `{{EXISTING_NO_SUBSTRATE_OR_APPROVED_NATIVE}}` |
| Existing HostedAgent operator owner and revision | `{{OWNER_AND_REVISION}}` |
| Platform owner and execution authorization | `{{OWNER_AND_AUTHORIZATION_REFERENCE}}` |
| Evidence directory and reviewer | `{{PRIVATE_EVIDENCE_DIRECTORY_AND_REVIEWER}}` |

Native-only rows may be marked not applicable with a reason for the existing standalone path. That does not satisfy native KRO/Hosted comparison or actor-isolation gates. No required row may be skipped without a recorded scope decision.

## 1. Confirm the starting point

| Done | ID | Required evidence | Owner |
| --- | --- | --- | --- |
| [ ] | P01 | Both repository folders copied, source revision/checksum recorded, extracted source verifier passed | Human transferring source |
| [ ] | P02 | Existing Skill, KnowledgeBase, HostedAgent, and GoldenScenario schemas, operator source/image, profiles, and ownership inventoried | Existing operator owner |
| [ ] | P03 | Runtime path selected from actual APIs and the authorized no-Substrate/native requirement; no silent install or upgrade | Platform owner |
| [ ] | P04 | Allowed namespace, kubeconfig/context, identities, delivery method, and change scope recorded privately | Platform owner |
| [ ] | P05 | Existing working content, images, model route, MCP wiring, credentials, and receipts recorded for reuse and regression | Work agent and operator owner |
| [ ] | P06 | Safe recovery inputs and original controller/CRD/profile configuration captured before changes | Operator owner |

## 2. Supply imports and build inputs

| Done | ID | Required evidence | Owner |
| --- | --- | --- | --- |
| [ ] | P07 | Every required chart, CRD, image, binary, sandbox asset, wheel, and Go dependency is preapproved and available internally; missing imports named explicitly | Artifact or registry owner |
| [ ] | P08 | Artifact ledger records source checksum, approved transfer, internal destination digest, architecture, and actual executor/node access | Registry and build owners |
| [ ] | P09 | Compatible existing helper/content/operator images identified and reused; new front-door build has its approved base and exact CLI when native is selected | Build owner |
| [ ] | P10 | Missing image builds can run with network disabled and local staged inputs; deployed references use approved internal locations | Build and platform owners |
| [ ] | P11 | Reviewed skill and knowledge source files, license/provenance, full content revision, and exact hashes are available | Content owner |
| [ ] | P12 | Standalone uses verified immutable owned ConfigMaps, or native OCI packages have been rebuilt/imported and retrieved by a cold worker without public access | Content and registry owners |
| [ ] | P13 | Required Python tooling and approved wheelhouse are available; diagnostic compiler/module cache is present if those probes are to run | Executor owner |

## 3. Establish the protected platform baseline

| Done | ID | Required evidence | Owner |
| --- | --- | --- | --- |
| [ ] | P14 | Approved model endpoint, model ID, tool-calling support, TLS/CA, private credential references, and consumer connectivity verified | Model owner |
| [ ] | P15 | Caller and runtime identities, exact audiences/subjects or roles, expiry/revocation source, and separate approval publisher agreed | Identity and platform owners |
| [ ] | P16 | If Entra is required, the actual adapter, role/federation bindings, token acquisition, renewal, and client reload are implemented and proved; Kubernetes JWTs are not substituted | Entra owner |
| [ ] | P17 | NetworkPolicy provider enforces traffic; effective additive policies and approved runtime egress inspected | Network owner |
| [ ] | P18 | Shared Gateway, HTTPRoutes, exact destination-owned ReferenceGrants, backend protocol, listener authentication, and policy attachment validated against installed schemas | Gateway owner |
| [ ] | P19 | Kyverno is enforcing in the approved scope, fail-closed admission is healthy, protected writers are restricted, and any privileged worker exception has an owner and removal plan | Security owner |
| [ ] | P20 | Existing operator extension and its new protected profile are reviewed; old CRDs/profiles remain compatible; only one composer owns each child | HostedAgent owner |
| [ ] | P21 | KRO controller, CRDs, RGD/CEL compatibility, and approved RBAC are available if the KRO path is selected | KRO owner |
| [ ] | P22 | Native-only: compatible kagent/Substrate, matching CLI, Harness/WorkerPool, sandbox assets, snapshot storage, DNS, and certificate projection work | Native runtime owner |
| [ ] | P23 | Native-only: non-overlapping controller watch scopes, database schema/grants, lease ownership, and exact same-namespace credential-provider mappings approved | Native platform and database owners |
| [ ] | P24 | Resource limits, quotas, invocation budgets, credential renewal, and operational ownership meet the intended exposure; singleton lab defaults are not treated as HA | Service owner |

## 4. Gate target activation on receipts

| Done | ID | Required evidence | Owner |
| --- | --- | --- | --- |
| [ ] | P25 | Existing operator integration is implemented in the existing source, reviewed, regression-tested, and has one-file owner YAML; the separate lab adapter is not presented as that upgrade | HostedAgent owner |
| [ ] | P26 | Real admission allows approved controls and denies unsafe privileges, wrong bindings, copied worker identity/image/lineage, and live ephemeral-container injection | Security owner |
| [ ] | P27 | Fresh execution uses the selected skills, knowledge, approved model and MCP capability; wrong caller/tool/target and direct bypass fail with backend witnesses | Work agent |
| [ ] | P28 | Expiry, authority loss, revocation during an unfinished call, dependency/grant loss, composer restart, retirement, and stale same-name approval are proved in the target | Work agent |
| [ ] | P29 | Shared resources remain owned by the platform; private receipts, current limitations, cleanup, and rollback are reviewed | Platform owner |

## Record the decision

| Decision | Evidence |
| --- | --- |
| Prerequisites ready for scoped implementation | `{{YES_OR_NO_AND_OUTSTANDING_IDS}}` |
| Target activation gates passed | `{{YES_OR_NO_AND_RECEIPT_REFERENCES}}` |
| Reviewer and date | `{{REVIEWER_AND_DATE}}` |
| Outstanding owner, input, and next action | `{{BLOCKER_OWNER_INPUT_ACTION}}` |

Unchecked required prerequisites block their dependent changes. Unchecked target acceptance gates block the corresponding exposure or success claim. The agent can continue independent source review, offline tests, and rendering. Preserve existing working resources and builds while a prerequisite is supplied.
