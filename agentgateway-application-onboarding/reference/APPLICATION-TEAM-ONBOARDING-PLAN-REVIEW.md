# Review: Application-team onboarding to agentgateway

Bundle location: `work-agent-bundles/agentgateway-application-onboarding/reference/`.

Reviewer: independent architecture review
Date: 2026-08-25
Reviewed revision: 543-line uncommitted draft of
[`APPLICATION-TEAM-ONBOARDING-PLAN.md`](APPLICATION-TEAM-ONBOARDING-PLAN.md);
no commit identifier existed for that draft.
Resolution baseline: commit `57f92720691e2f34eb315dcfa2054992877c9769`
(638-line plan), plus the proposal-artifact inventory correction recorded below.
Method: full read of the plan, cross-checked against the repository files it
cites. No cluster was contacted; no Entra or Azure state was inspected.

Resolution note: the current plan incorporates B2-B4, G1-G4, the App Team front
sheet, and the ownership/date additions. B1 is corrected in the current plan
and in this historical finding: `ToolCatalogEntry` and `ToolGrant` have
checked-in proposal artifacts, but they are not deployed or runtime-proven
controls. The findings below describe the reviewed draft, not outstanding
documentation blockers. The live meeting/showcase remains design-review-only
until the plan's Phase 1 and Phase 2 evidence passes. Live use of kagent Pattern
C additionally requires the Phase 3 authenticated A2A evidence. This review
authorises no deployment or live access.

## Verdict

Approve the security model. Do not present the reviewed draft to the App Team
without the additions in the historical blocking findings below.

The central architectural call — the team UAMI is authorised to call
agentgateway, not the model — is correct and is the single most valuable thing
in the document. The four-identity table, the separation of federation from
authorization, and the refusal to treat `toolNames` or `x-kagent-*` headers as a
security boundary are all right, and they are the conclusions most teams get
wrong. The evidence table is genuinely good: it tests denials, not just
successes.

The weaknesses are not in the reasoning. They are: three claims that the
repository does not actually support, four operational gaps that will surface
in Phase 0 and cost time, and a document shape that does not fit the audience
it was written for.

## Verified against the repository

These plan claims were checked and hold:

| Claim | Evidence |
|---|---|
| Repository baseline is agentgateway v1.3.1 | `DEPLOY.md:28-29,38-39,53`, `AUTHENTICATION.md:163` — consistent |
| Existing `ModelConfig` examples use a dummy API-key Secret | Confirmed across `modelconfig-*.yaml` |
| The multi-namespace guide grants tenants more than this design allows | `docs/architecture/MULTI-NAMESPACE-AGENT-AS-A-SERVICE.md:89-92,169-172` grants tenants `create/update/patch/delete` on `modelconfigs` **and** `agentgateways`. The plan's warning is accurate and understated |
| Strict JWT authentication shape exists in-repo | `authentication-policy.yaml` — issuer, audiences, JWKS, `mode: Strict` |
| All six internal document links resolve | Checked individually |

## Historical blocking findings from the reviewed draft

### B1. `ToolCatalogEntry` / `ToolGrant` were presented as proven controls

The reviewed draft listed them under *"Verified repository pattern, but
requiring target-version revalidation"*. The repository does contain proposal
CRDs in `infra/byo-kagent/crds/`, bootstrap `ToolCatalogEntry` manifests in
`infra/byo-kagent/bootstrap-catalog/`, and a Kyverno admission-policy example in
`infra/byo-kagent/kyverno-policies/validate-agent-tool-grants.yaml`. This review
did not establish that those artifacts are deployed, compatible with the target
cluster, runtime-enforced, or backed by a working controller or renderer.

The reviewed draft then leaned on `ToolGrant` as a load-bearing control in three
separate places (the tool-parity triple at lines ~180-190, the tenancy RBAC
deny-list, and the Phase 4 exit criterion). Presenting proposal artifacts as an
existing, proven platform primitive is exactly the kind of claim an App Team
will repeat back as a commitment. Classify both as *"Proposed and not yet proven
at work"* and keep the parity mechanism as Phase 4 design work.

### B2. The JWKS path has an undocumented hard dependency

`authentication-policy.yaml:20-30` and `AUTHENTICATION.md:62` both resolve JWKS
through a `Service` named `oidc-proxy` in `agentgateway-system`. That service is
not defined anywhere in this repository, and the plan never mentions it.

For a private AKS cluster this is the most likely Phase 1 failure and it is
invisible in the current text. Strict JWT validation is a hard dependency on the
gateway reaching Entra's signing keys, and every request fails closed until it
does. Add to Phase 0:

- who owns `oidc-proxy`, or what replaces it (egress allow-list to
  `login.microsoftonline.com`, corporate forward proxy, or pinned static JWKS);
- the corporate CA path for that TLS connection;
- JWKS cache duration and behaviour during a key-rollover window; and
- the observable symptom when it breaks, so it is not misdiagnosed as a bad
  token.

### B3. App-role assignment to a managed identity cannot be done in the portal

The plan's Entra setup (steps 1-6) reads as a portal-clickable sequence. Step 3,
*"Assign only the required agentgateway application roles to that UAMI"*, is not
available in the Entra portal UI for a managed identity service principal. It
requires a Microsoft Graph `appRoleAssignments` call, and the operator needs
`AppRoleAssignment.ReadWrite.All` plus `Application.Read.All`.

This is a real Phase 1 blocker with a named permission owner. Say so explicitly,
and name who in the platform team holds those Graph permissions — otherwise the
first onboarding stalls at a step the plan implies takes thirty seconds.

### B4. The 40-minute showcase has no stated prerequisite

The agenda allocates fifteen minutes to a live allow-and-deny demonstration, and
the demonstration story assumes a working token, an approved model route, a
scoped MCP endpoint, and a revocable grant. That is the exit state of Phase 1
**and** Phase 2.

Right now the document reads as though the showcase could be booked next week.
State plainly at the top of the showcase section: *this agenda is deliverable
only after Phase 2 exits; before that, the same slot must be a design review
with no live demo.* The plan's own closing advice — "avoid a demo that relies
only on a port-forward, dummy API key, open route" — is precisely what will
happen if the meeting is booked against the current state.

## Significant gaps

### G1. Rate limits do not mean what the cost-control section implies

The plan promises "request, token, and concurrency limits by team/cost centre".
Agentgateway's `rateLimit.local` (as used in `ai-policy.yaml:32,74` and
`policy-a2a-fleet-agent.yaml:38`) is enforced per data-plane instance. With N
gateway replicas the effective tenant limit is N times the configured number,
and it changes silently when the gateway autoscales.

If the limit is a cost-control commitment to a team, it needs either a global
rate-limit backend or an explicit statement that the number is per-replica and
the ceiling is `replicas x limit`. Add the replica count to the Phase 0
discovery record.

### G2. Token expiry during long-lived MCP and streaming sessions

MCP Streamable HTTP sessions and streaming model responses can outlive a token.
The plan sets a maximum request timeout but never addresses what happens when a
bearer token expires mid-stream, whether the gateway re-validates on the
existing connection, or how a client is expected to refresh. For an agent doing
a long tool-calling loop this is a routine occurrence, not an edge case.

Add a Phase 0 probe and one row to the evidence table: *expired token on an
established session → deterministic, documented outcome.*

### G3. A2A ingress to the Agent itself is unauthenticated in this design

Pattern C ends with "invoke the Agent through the normal A2A/client path". The
plan authenticates app → gateway, gateway → model, and gateway → MCP, but never
authenticates caller → kagent Agent. The repository already exposes A2A
(`A2A-FLEET-DEMO.md`, `policy-a2a-fleet-agent.yaml`), so this is a live path,
not a hypothetical.

If any pod that can reach the Agent's A2A endpoint can drive it, the Agent
becomes a confused deputy holding the kagent runtime's gateway grant — which
defeats the per-agent isolation spike the plan correctly flags elsewhere. Either
route A2A ingress through the gateway with the same JWT policy, or state that
Pattern C is not tenant-isolated until that is resolved.

### G4. Evidence table is missing four denials

The table is strong. Add:

| Test | Expected result |
|---|---|
| Expired token | `401`, and the same on an already-established stream |
| Token replay from a different pod/namespace | Denied, or explicitly documented as not detectable and mitigated by short lifetime |
| Gateway restart or policy reload | Denials still hold; no fail-open window during reconciliation |
| Audit record inspection | Caller, route, and decision present; prompts, tokens, and secrets absent |

The last one matters because the plan promises redaction but never tests it.

## Smaller points

- **Line ~180, tool-list parity.** "The same tool list should exist in three
  places and be generated or checked for parity" invites the drift it warns
  about. Rewrite as *one* source of truth generating three artefacts. Three
  hand-maintained copies with a parity checker is a weaker second choice, and it
  should be named as such.
- **Length and audience.** 543 lines is a platform-engineering design record,
  not an App Team onboarding document. The team needs roughly one page: what
  they get, what they must supply, what they cannot do, and what to decide.
  Consider splitting: keep this as the design record, and cut a front sheet from
  "Recommended decisions" + "Self-service onboarding contract" + "Questions for
  the App Team". As it stands, the ten questions the team must actually answer
  sit at line ~430.
- **No owner, no dates, no RACI.** The document requires teams to supply an
  owner, cost centre, and review date, but carries none itself, and the four
  phases have no owners or target dates. For a document that will be presented
  and then referenced for months, add them.
- **Decision 4 wording.** It asserts a position on "Model Garden" access while
  the model-access section still asks what Model Garden is. Keep the decision,
  but mark it conditional on the Phase 0 answer.
- **Overlap with `AUTHENTICATION.md`.** The JWT/OIDC, API-key, and
  authorization-is-separate sections restate that file. Cite rather than
  duplicate, so the two cannot drift.

## What is worth keeping unchanged

- The four-identity table. It is the clearest statement of the boundary in the
  repository and should be lifted directly into the showcase deck.
- "Federation and authorization are separate." This is the single most common
  Workload Identity misconception and the plan kills it in three sentences.
- "Tool access is not resource access", with the three named hard boundaries.
  Correct, and the preference ordering is right.
- The refusal to accept `x-kagent-*` headers as identity, and the explicit
  statement that the shared kagent runtime does not give each Agent CR its own
  identity. This is the finding most likely to change the delivery plan, and it
  is stated without hedging.
- The independent-review question list. Seven falsifiable questions is a better
  review gate than any checklist of controls.
- "Do not call the proof complete from a `Ready` status alone."

## Historical recommended next actions

1. Apply B1-B4. B1 and B3 are text changes; B2 and B4 change scope.
2. Add G1-G4 to Phase 0 discovery and the evidence table.
3. Cut the one-page App Team front sheet from the existing material.
4. Book the showcase slot as a design review, not a demo, until Phase 2 exits.
5. Route the revised plan through independent security and architecture review
   before implementation.

## Review boundary

This review is documentation-only. It does not verify that any described control
works in a live cluster, does not validate `AgentgatewayPolicy` fields against
the installed v1.3.1 CRDs, and does not confirm any Entra, UAMI, or Azure RBAC
state. The plan's own Phase 0 remains the first real evidence gate.
