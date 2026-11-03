# Make a new agent request configure Agent Gateway

The existing lab proves security behavior for two fixed POC names and prestaged central routes. This amendment requires the office agent to extend the **existing HostedAgent operator and trusted routing owner** so a newly named request automatically receives the reviewed Gateway wiring. The amendment is source and instructions for that delta, not a claim that this operator integration is already complete.

## Resource ownership and activation

| Platform prerequisite | Per-agent generated closure |
| --- | --- |
| Installed compatible Gateway/controller and served CRDs | Runtime/front door and actual model/MCP bindings for the approved profile |
| Protected profiles, issuer/JWKS, allowed subjects and capabilities | HTTPRoute and route-targeted strict JWT/authorization policy for the new agent |
| Existing collector/LGTM, privacy policy and network baseline | Exact destination consent and any approved namespace-local network closure |
| Trusted publisher, routing writer and existing operator authority | UID-pinned request/child/route/policy inventory, current conditions and retirement records |

Keep the shared Gateway and collector platform-owned. The tenant owner writes only the small approved request. A central Gateway namespace needs its trusted routing writer; do not give the tenant arbitrary Gateway or policy writes. Do not create cross-namespace ownerReferences. Use the actual request UID in protected routing inventory and exact UID preconditions during retirement, preserving foreign resources and shared objects.

Preserve independent approval as inactive while desired resources converge. Policy and route application is not a transaction. Activate only after actual route resolution, JWT attachment, consent, effective network control, capability bindings, and selected-runtime readiness pass. The existing call-time front door remains an independent check. The composer cannot grant itself access.

## Minimal implementation sequence

1. Inspect the current office changes before editing. Identify which existing HostedAgent profile creates the runtime and which trusted owner can manage central HTTPRoutes and policies. Preserve the four CRDs, current working profiles, existing content, compatible images and delivery process.
2. Add one reviewed secure profile and one derived routing inventory to those existing seams. Derive safe names and exact destinations from the request and protected profile. Owner instructions confer no permissions. Do not accept arbitrary owner-supplied policies, URLs, images, Secret references or allowed identities.
3. Render a complete reviewed resource delta for a **newly named** request. Include actual model/MCP facade configuration and its route-targeted policy. Have the appropriate destination owner supply exact grants; ReferenceGrant is destination consent, not caller authentication.
4. Reconcile preparation, route/policy attachment and independent activation. Test incomplete creation and a failed attachment while approval stays inactive. Preserve native current-generation/revision checks or the corresponding actual standalone contract.
5. Run the JWT, functional, Kyverno, network, revocation and telemetry gates. Demonstrate new onboarding with no per-agent hand-applied Gateway repair. A manually prestaged new route does not pass this automation gate.
6. Retire the request normally. Revoke fresh authority first, remove owned exposure and dedicated objects, keep shared services, and reject the old approval after same-name recreation. Reapprove and retest current identities before leaving the demo stable.

## JWT scope for this iteration

Use the approved Kubernetes TokenRequest issuer/JWKS and audience accepted by the base TokenReview path, with exact caller and runtime subjects. The base lab uses audience `secure-byo`. Discovery and profile adaptation must preserve the target's approved values. An arbitrary locally signed JWT may validate under a separately configured Gateway but still fails the backend's Kubernetes TokenReview; do not silently mix those identity contracts.

Prepare separate missing-token, wrong-audience, wrong-subject and expired signed-token cases. Mint test tokens only through the already authorized issuer/account scope. Keep them in private files and record their declared expiry privately. Prepare the expired case before the rehearsal rather than exposing signing keys or forging a token. Do not print tokens or authorization headers on screen.

Distinguish Gateway JWT authentication/subject authorization from backend lane, UID/spec, expiry and capability checks. Revoking backend approval does not invalidate a still-valid signed JWT at the Gateway; the backend must still deny fresh authority. Pair denials with backend witnesses.

Entra application registration, UAMI/blueprint federation and Entra-specific acquisition are **deferred**. Record that explicit JWT-only scope against older Entra prerequisite rows. It does not waive audience, authorization, revocation or other security controls, and it does not establish automatic renewal.

## Deployment and upgrade talking point

Describe the existing approved Helm/GitOps installation and pinned CRD/controller/data-plane matrix briefly. For upgrades, explain schema review, canary, JWT/route/telemetry regression and rollback. No upgrade, new dashboard, or replacement observability stack is needed for this onboarding demonstration. Import missing approved artifacts through the existing air-gap process.
