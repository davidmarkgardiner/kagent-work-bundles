# Work-agent task: adopt the agent platform handbook

Use this complete folder as a standalone MkDocs source project. Read `docs/index.md`, `docs/versions.md`, `docs/isolation.md`, `docs/labs.md` and `docs/handoff.md` first.

1. Build with the pinned requirements, run the download freshness check and strict MkDocs build. Adapt source pages to our internal approved documentation repository and hosting conventions. Keep owners, evidence dates and unresolved gates visible.
2. Discover installed versions/APIs with an explicit approved context; keep output private. Preserve existing object names, authentication, views/grants, gateway ownership and GitOps delivery. Do not convert legacy manifests by tag substitution.
3. Plan a separate-cluster 0.x -> 1.0 migration with a fresh database. kagent 1.0.1 pins Substrate 1.0.0. Treat Substrate 1.0.1 as a separate candidate until lifecycle/security testing closes the gap. Use the bundled offline verifier and collect its digest receipt.
4. Port KRO composition outputs to api.kagent.dev/v1alpha3 Harness/AgentTemplate/Agent, current model/tool bindings and A2A routes. Preserve the supported read-only contract and protected identity/network controls. Custom Skills/KnowledgeBase APIs are not native kagent resources.
5. Keep the capabilities/root-filesystem policy blocker open until the security owner approves a bounded exception and verifies replacement enforcement across every affected cluster. Do not self-grant identity/Graph permissions or broaden namespace exceptions.
6. After the existing deployment gates are met, execute L01–L12 on the selected lab and then the receiving environment. Require model/tool read receipts, independent-session isolation, actual checkpoint/restore, denials without backend activity, credential refresh/expiry and disable/revoke. Candidate chart rendering alone is insufficient.
7. For ServiceNow, update the legacy A2A route and envelope for 1.0, preserve durable dedupe/retry/target mapping, and keep ticket writes independently scoped and reviewed. No production remediation or ticket writes are authorised by this documentation handoff.
8. Prepare an internal static-site artifact and reviewed hosting change through the existing approved pipeline. Return build/link/download and hosted-URL proof separately. Do not publish externally or change policy/identity/production infrastructure without its existing authority.

Private placeholders: {{LAB_CONTEXT}}, {{PRIVATE_EVIDENCE_DIRECTORY}}, {{APPROVED_MODEL_ROUTE}}, {{APPROVED_MCP_ROUTE}}, {{INGRESS_DOMAIN}}, {{GATEWAY_NAME}}, {{OWNER}}, {{RUNTIME_IMAGE_DIGEST}}, {{SNAPSHOT_LOCATION}}. Resolve these from owned target inventory, never from guessed values.

Return: source commit, actual version/digest matrix, changed paths, offline checks, lab/receiving receipts with date and scenario, remaining blocker/owner/next action and rollback. Never report old lab evidence as fresh workplace proof.

## Stakeholder delivery reference

Maintain `delivery/roadmap.yml` and append a reviewed snapshot to `delivery/updates.yml` every two weeks. Follow `docs/fortnightly-updates.md`. Report achieved outcomes, state changes, unchanged items, next outcomes and decisions with owners and evidence. Q4/Q1 are delivery horizons, not committed dates. Preserve the published history. Keep all work-facing wording generic: no external environment names, hosts, VM/context labels or environment-specific anecdotes. A Kubernetes agent is a proposed/read-only capability until receiving runtime and tool evidence proves its acceptance. Generate the pages, sync downloads and run `scripts/build_docs.py`.


## Calendar and commit contract

Follow `AGENTS.md`. Maintain named Agents, MCP/Skills Tools and Governance (policy/evaluation/observability/SDLC) lanes with month buckets. Record built and live separately with accepted dated proof. Before an authorised commit, update the roadmap and achievement log together for a delivery event, or include an explicit no-impact note for editorial work. Regenerate and run the build and staged impact check. The CI template checks committed content; source configuration alone does not prove remote enforcement. Do not install hooks, publish or change repository protection as a side effect.


### Historical owner-confirmed achievements

Keep already delivered capabilities distinct from their next-stage hardening or expansion. Q2/Q3 entries may use `historical` metadata with `precision: approximate-quarter`, a confirmation date and an `owner-confirmation` evidence link when the pod lead confirms completion but exact delivery dates are unavailable. Leave `built_on` unset in that case; never substitute the confirmation date for a build date. These entries are built, with the evidence basis visible. Live status still requires a precise date and receiving-service acceptance. Append a dated historical-backfill update; do not rewrite older reporting snapshots. Evaluation and central agent/tool/skill registration are owner-confirmed active work.
