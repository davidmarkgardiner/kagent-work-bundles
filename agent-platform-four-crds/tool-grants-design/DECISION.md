# Design decision

The selected base is a fixed MCP adapter with a fresh protected approval check for each invocation. It adds no capability-token broker. This is a design choice, not deployed enforcement.

Two independent sketches were compared before synthesis. Candidate A compiles policy and issues 30-second capability JWTs from a new protected broker. Candidate B keeps authorization in the necessary adapter and reads current protected records per call. Both use fixed typed operations, independently verified caller identity and narrow downstream RBAC.

The independent native judge scored both 23/30. A scored higher for identity/revocation detail and failure tests. B scored higher for its smaller implementation, avoiding a signing broker, token issuance fence and additional refresh protocol. The parent's criterion scores also favoured B for this first small capability.

The synthesis adopts B and these corrections from review:

1. Separate the namespace-admin trust domain from individual-Agent isolation. Protected runtime ownership would be needed for the latter.
2. Prepare a tool-less child, approve observed identities and expected final spec, then stage wiring and activate. Approval does not wait for prior tool readiness.
3. Define the protected-store revoke commit and the earlier-read dispatch race. Each decision belongs to one call with a whole-call deadline. No claim of zero post-commit dispatch is made.
4. Pin typed request/subject/capability/backend contracts and use all-replica, backend-observed negative tests, including live-session expiry and credential copying.

A's protected activation receipts, typed approval pins and adversarial test matrix were retained. Its broker, signing-key lifecycle, capability leases and proposed 32-second residual-access window were rejected for this first implementation. A lease optimization remains a separate future decision if source availability or latency makes per-call checks unsuitable.

Admission-only ToolGrant existence and KAgent toolNames were rejected as runtime authority. Generic kubectl/SQL/HTTP wrappers were rejected because a tool name cannot bound their targets, arguments or outputs. Tool annotations are advisory; they do not establish backend permissions.

Review provenance. A fresh native Codex architect produced candidate A. The parent authored the structurally distinct B. A fresh native Codex judge compared both. Claude remained usage-limited and Grok CLI was absent. This was not a multi-provider review.

The scope of this task ends at the reviewable contract, fixtures and acceptance plan. The current CRDs, no-tools runtime, source snapshot, GitLab repositories and clusters were not changed.
