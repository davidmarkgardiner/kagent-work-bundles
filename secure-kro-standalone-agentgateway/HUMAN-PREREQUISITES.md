# Human prerequisite sheet

Fill this privately. Unchecked means unverified. The work agent discovers facts it can read; platform owners supply access and decisions that it cannot infer.

| Done | Required input or proof | Owner |
| --- | --- | --- |
| [ ] | Approved target/context, fixed namespaces, platform submission identity and bounded demo/drill scope | Platform owner |
| [ ] | Compatible installed KRO and cluster-scoped instance support; protected RGD authoring | KRO owner |
| [ ] | KRO controller privileges and platform/admission trust reviewed; no uncontrolled tenant request/RGD writes | Platform/security owners |
| [ ] | Agent Gateway 1.7/controller, Gateway API, listener/Service and route/policy schema verified | Gateway owner |
| [ ] | Compatible validating admission policy and Kyverno schemas, protected verifier identity and restricted namespace baseline | Security owner |
| [ ] | CNI actually enforces the proposed NetworkPolicies, including Service translation and API paths | Network owner |
| [ ] | Existing approved Python 3.12 helper image/internal digest, target architecture, `/usr/local/bin/python3`, standard library and CA trust verified; no new build if compatible | Runtime/registry owners |
| [ ] | Immutable approved code/content payload, exact projection/entrypoint and actual code-tamper/command/mount/hook/env admission tests verified | Platform/security owners |
| [ ] | Fixed model destination/identifier works and permits one bounded real scenario | Model owner |
| [ ] | Approved pinned skill/knowledge source and typed MCP capability mapped to existing work contracts | Content/tool owners |
| [ ] | JWT issuer/JWKS/audience, caller/worker/verifier subjects, token delivery and clock synchronization agreed | Identity owner |
| [ ] | Dedicated revoker identities/groups are separate from platform ConfigMap-maintenance identities; admission restricts configured revokers even if additional RBAC roles grant wider writes | Identity/platform owners |
| [ ] | Independent approval publication, expiry/revocation and manual renewal limitations understood | Platform owner |
| [ ] | Exact final owner YAML, variable fields, apply/watch/invoke/reset commands and second request name prepared | Work agent |
| [ ] | Actual model/tool/content, auth, grant, network, data-ownership and recreation receipts pass | Work agent |
| [ ] | Existing OTel/LGTM collection/query/view access and final showcase rehearsal verified | Observability owner/presenter |

David supplies target access, existing contract/owner locations, approved model/content references and registry/identity/observability contacts. Keep keys and private endpoints out of this sheet. The agent prepares the missing-import list and reviews the implementation delta.

Substrate, native worker pools and the native CLI do not belong on this path's prerequisite list. Shared platform installation and artifact import precede the one-file per-agent onboarding.
