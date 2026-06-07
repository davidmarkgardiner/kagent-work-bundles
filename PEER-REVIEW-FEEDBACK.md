# Peer Review Feedback — Work-Agent Bundles

Current status: actioned in the follow-up remediation pass. The original review
findings are retained below as an audit trail.

Applied fixes:

- Follow-up live audit added `runtime-model-gateway-readiness/` and promoted it
  from a missing P0 concept to the required preflight before downstream demos.
- Follow-up live audit tightened GitLab official-vs-lite MCP wording, A2A/chaos
  runtime dependencies, lifecycle historical-failure review, and governance
  audits of actual agent tool lists.
- Converted the copied cert-manager diagnostic agent payload to read-only
  posture by removing Kubernetes mutation tools and removing "act if safe"
  wording.
- Added "Start Here" reading order and static-only disclaimers to terse bundles.
- Normalized shared variable names to canonical `{{CHAT_MODEL_CONFIG}}`,
  `{{CLUSTER_NAME}}`, and `{{KAGENT_NAMESPACE}}`.
- Bound `{{APPROVAL_CHANNEL}}` into chaos and HITL prompts/requests.
- Extended the governance bundle to audit read-only triage agents for
  delete/exec/apply/patch/create/label/annotation tools.

Reviewer pass against `PEER-REVIEW-PROMPT.md`. Scope: `work-agent-bundles/` only.
Original static verifier run: `WORK_AGENT_BUNDLES_VERIFY: passed` (all 12 bundles green).
Follow-up static verifier after the runtime-readiness bundle was added:
`WORK_AGENT_BUNDLES_VERIFY: passed` across 15 bundles.
Static pass proves internal consistency only — not live GitLab/Grafana/kagent/Argo/chaos behavior.

---

OVERALL_STATUS: NEEDS_SMALL_EDIT

The set is well structured, public-safe (secret scan clean), and the placeholder
vocabulary is closed (every bundle placeholder used by a bundle is defined in
`SHARED-VARIABLES.md` — zero orphans). One real safety contradiction must be
fixed before handover; the rest are consistency and token trims.

---

TOP_5_FIXES:
1. **Safety contradiction (must-fix).** `sre-grafana-mcp-observability/payload/agents/kagent-triage/cert-manager-agent.yaml:77-100` grants a *diagnostic/triage* agent `k8s_delete_resource`, `k8s_execute_command`, `k8s_apply_manifest`, `k8s_create_resource`, `k8s_patch_resource`, and its `systemMessage:54` says "**Act** if safe to do so". This directly violates the same bundle's `FRONT-SHEET.md` Safety Rules ("Start read-only", "Do not use write-capable tools from the default triage agent") and the `policy-governance-safety` DoD ("General triage/front-door agents do not have delete, exec, broad apply"). Either strip the write/delete/exec tools from this triage agent, or relabel it a bounded remediation specialist with an explicit HITL gate and namespace bound in the manifest.
2. **Terse-bundle reading order.** 6 bundles (`a2a-smart-triage-workflows`, `memory-mcp-shared-context`, `lifecycle-evaluation-review-manager`, `byo-kagent-onboarding`, `hitl-remediation-approval`, `aks-fleet-reporting-day2`) have FRONT-SHEETs with no "Start Here" reading order and 17-line START-PROMPTs that skip `CHECKLIST.md` / `payload/REFERENCE.md`. Add a 4-7 line "Start Here" list to each so a low-token agent knows the file order without guessing.
3. **`SHARED-VARIABLES.md` synonym debt.** It carried duplicate names a work agent had to reconcile: retired `KAGENT_MODEL_CONFIG` vs canonical `{{CHAT_MODEL_CONFIG}}`, retired `CLUSTER` vs canonical `{{CLUSTER_NAME}}`, and retired `KAGENT_NAMESPACE_OR_PLATFORM_SCOPE` vs canonical `{{KAGENT_NAMESPACE}}`. Pick one canonical name per concept, delete the synonym rows, and keep a single 1-line "synonyms" note. Cuts the sheet and removes ambiguity.
4. **Static-vs-live separation is strong but uneven.** The richer bundles state "static check only … does not prove live X" explicitly; the 6 terse bundles do not. Add the same one-line static-only disclaimer to the terse FRONT-SHEETs so no work agent infers live readiness from a green verifier.
5. **`{{APPROVAL_CHANNEL}}` underused.** It is defined and listed as minimum-required, but `hitl-remediation-approval` and `chaos-reliability-remediation` reference approval in prose without binding the placeholder. Wire `{{APPROVAL_CHANNEL}}` into those two requests/prompts so the approval route is a filled variable, not free text.

---

SHARED_VARIABLES_REQUIRED:

(All already present in `SHARED-VARIABLES.md`. Listed here are the ones a work
agent MUST supply before any live run, plus the synonym collapses recommended.)

- variable: {{KUBE_CONTEXT}}
  used_by: all live bundles
  purpose: approved non-prod Kubernetes context for proof commands
  example_placeholder: {{WORK_NONPROD_KUBE_CONTEXT}}
- variable: {{KAGENT_NAMESPACE}}
  used_by: all
  purpose: kagent runtime namespace
  example_placeholder: {{WORK_KAGENT_NAMESPACE}}
- variable: {{CHAT_MODEL_CONFIG}}   (canonical; retire KAGENT_MODEL_CONFIG)
  used_by: every agent-creating bundle
  purpose: approved kagent ModelConfig
  example_placeholder: {{WORK_CHAT_MODEL_CONFIG}}
- variable: {{GITLAB_PROJECT}} / {{TARGET_BRANCH}} / {{GITLAB_MCP_REMOTE_SERVER_NAME}}
  used_by: kagent-triage-v2-kb-gitlab-mcp, gitlab-mcp-gitops-pr
  purpose: scoped GitLab MCP write target behind review
  example_placeholder: {{GROUP/PROJECT}}, {{MAIN_OR_INTEGRATION_BRANCH}}, {{WORK_GITLAB_MCP_SERVER}}
- variable: {{GRAFANA_MCP_REMOTE_SERVER_NAME}} + {{MIMIR_OR_PROMETHEUS_DATASOURCE_UID}} + {{LOKI_DATASOURCE_UID}} + {{TEMPO_OR_TRACE_DATASOURCE_UID_OR_NONE}}
  used_by: sre-grafana-mcp-observability, incident-evidence-trace-log-metrics
  purpose: Grafana MCP read evidence; trace UID must allow explicit `none`
  example_placeholder: {{WORK_GRAFANA_MCP_SERVER}}, {{WORK_METRICS_DATASOURCE_UID}}, {{WORK_LOKI_DATASOURCE_UID}}, {{WORK_TRACE_DATASOURCE_UID_OR_NONE}}
- variable: {{MEMORY_MCP_REMOTE_SERVER_NAME}}
  used_by: memory-mcp-shared-context
  purpose: memory MCP server behind a curator path
  example_placeholder: {{WORK_MEMORY_MCP_SERVER}}
- variable: {{APPROVAL_CHANNEL}}
  used_by: hitl-remediation-approval, chaos-reliability-remediation (bind it, currently prose-only)
  purpose: human approval route for risky actions
  example_placeholder: {{TEAMS_OR_GITLAB_APPROVAL_ROUTE}}
- variable: {{DEMO_TARGET_NAMESPACE}} / {{DEMO_TARGET_WORKLOAD}}
  used_by: chaos-reliability-remediation
  purpose: bound chaos to one approved non-prod target
  example_placeholder: lower-env namespace + workload

---

BUNDLE_REVIEW:

- bundle: sre-grafana-mcp-observability
  status: NEEDS_SMALL_EDIT
  strongest_part: richest payload, clear front-door (UI/A2A) contract, read-first posture stated, 14 evidence markers.
  missing_or_unclear: triage agent ships with write/delete/exec tools, contradicting its own Safety Rules.
  variable_gaps: none (59 placeholders, all defined).
  token_reduction_suggestion: FRONT-SHEET "Start Here" lists 15 files; trim to the 6 a work agent must read first, mark the rest "reference".
  safety_concerns: cert-manager-agent.yaml grants k8s_delete_resource / k8s_execute_command / k8s_apply_manifest to a diagnostic agent with an "Act if safe" instruction.
  smallest_fix: remove the 5 mutating tools from cert-manager-agent.yaml, or relabel as HITL-gated remediation specialist.

- bundle: kagent-triage-v2-kb-gitlab-mcp
  status: READY
  strongest_part: GitLab-write-is-specialist rule explicit; expected/ contracts + NO_RELEVANT_DOCS fallback marker; "local copy is not proof" warning.
  missing_or_unclear: none material.
  variable_gaps: none (8 placeholders, all defined).
  token_reduction_suggestion: minor — fold the 12-file "Start Here" into the 5 must-reads.
  safety_concerns: none — write scoped to KB author behind MR + HITL.
  smallest_fix: none required.

- bundle: gitlab-mcp-gitops-pr
  status: READY
  strongest_part: tight scope, human-review boundary marker (HUMAN_REVIEW_REQUIRED), no cluster-mutation claim from git write.
  missing_or_unclear: none.
  variable_gaps: none.
  token_reduction_suggestion: already lean.
  safety_concerns: none.
  smallest_fix: none.

- bundle: chaos-reliability-remediation
  status: NEEDS_SMALL_EDIT
  strongest_part: TARGET_NON_PROD + HITL_REQUIRED_FOR_REMEDIATION + RECOVERY_VERIFIED markers; prod-chaos-blocked posture.
  missing_or_unclear: no "Definition Of Done" section; {{APPROVAL_CHANNEL}} referenced in prose, not bound as a variable.
  variable_gaps: bind {{APPROVAL_CHANNEL}}, {{DEMO_TARGET_*}}.
  token_reduction_suggestion: keep markers, add 3-line DoD.
  safety_concerns: none in manifest; ensure prod-block is schema/runtime, not just prose.
  smallest_fix: add DoD + wire approval/target placeholders.

- bundle: a2a-smart-triage-workflows
  status: NEEDS_SMALL_EDIT
  strongest_part: clear fan-out marker set, context-preservation + synthesis proof.
  missing_or_unclear: FRONT-SHEET has no "Start Here"; START-PROMPT (17 lines) skips CHECKLIST/payload reading order.
  variable_gaps: none (2 placeholders).
  token_reduction_suggestion: already terse — add reading order, do not expand prose.
  safety_concerns: none.
  smallest_fix: add a 5-line "Start Here" list.

- bundle: memory-mcp-shared-context
  status: NEEDS_SMALL_EDIT
  strongest_part: CURATOR_PATH_DEFINED + DANGEROUS_MEMORY_WRITE_BLOCKED markers enforce the write-boundary requirement.
  missing_or_unclear: no "Start Here" / DoD.
  variable_gaps: none.
  token_reduction_suggestion: add reading order only.
  safety_concerns: none — curator path required.
  smallest_fix: add "Start Here".

- bundle: lifecycle-evaluation-review-manager
  status: NEEDS_SMALL_EDIT
  strongest_part: pass + below-threshold dual case, HARD_FAILURES_ENFORCED, review routing.
  missing_or_unclear: no "Start Here" / DoD.
  variable_gaps: uses {{PASSING_LIFECYCLE_CASE}} / {{FAILING_LIFECYCLE_CASE}} — both defined.
  token_reduction_suggestion: add reading order only.
  safety_concerns: none.
  smallest_fix: add "Start Here".

- bundle: byo-kagent-onboarding
  status: NEEDS_SMALL_EDIT
  strongest_part: DANGEROUS_TOOLS_ABSENT + POLICY_DENIAL_TESTED prove the onboarding boundary.
  missing_or_unclear: no "Start Here" / DoD.
  variable_gaps: none.
  token_reduction_suggestion: add reading order only.
  safety_concerns: none — read-only default, bounded remediation optional.
  smallest_fix: add "Start Here".

- bundle: hitl-remediation-approval
  status: NEEDS_SMALL_EDIT
  strongest_part: suspend-before-action + approver identity capture + after-approval-only markers — the strongest governance proof in the set.
  missing_or_unclear: no "Start Here"; {{APPROVAL_CHANNEL}} not bound as a variable.
  variable_gaps: bind {{APPROVAL_CHANNEL}}.
  token_reduction_suggestion: add reading order only.
  safety_concerns: none — this bundle is the control.
  smallest_fix: add "Start Here" + wire approval placeholder.

- bundle: policy-governance-safety
  status: READY
  strongest_part: the audit charter for the whole set — FORBIDDEN_TOOLS_BLOCKED, PROD_CHAOS_BLOCKED, GITLAB/MEMORY write boundaries, secret-leak scan.
  missing_or_unclear: none — but note it should *catch* the cert-manager-agent finding above; confirm its audit actually flags triage agents holding delete/exec/apply.
  variable_gaps: none.
  token_reduction_suggestion: already structured as checklist.
  safety_concerns: none.
  smallest_fix: add cert-manager-agent.yaml as a known positive test case for the ToolGrant audit.

- bundle: incident-evidence-trace-log-metrics
  status: READY
  strongest_part: NO_MUTATION_TOOLS_GRANTED marker + explicit trace-fallback ("does not invent trace evidence") — exemplary read-only evidence design.
  missing_or_unclear: none.
  variable_gaps: none (7 placeholders, all defined).
  token_reduction_suggestion: lean already.
  safety_concerns: none.
  smallest_fix: none.

- bundle: aks-fleet-reporting-day2
  status: NEEDS_SMALL_EDIT
  strongest_part: repeatable report contract; CHAOS_RUNS_REPORTED allows yes_or_not_available (honest about gaps).
  missing_or_unclear: no "Start Here" / DoD; thinnest bundle.
  variable_gaps: uses {{FLEET_SCOPE}} — defined.
  token_reduction_suggestion: add reading order only.
  safety_concerns: none — read/report only.
  smallest_fix: add "Start Here".

---

MISSING_CONCEPTS:

(All seven are already captured in README "Future Bundle Ideas" as backlog, not
built. Priorities below mark which should precede broad live use.)

- concept: Runtime / model / agentgateway readiness
  priority: DONE
  why_it_matters: every other bundle assumes kagent + a working ModelConfig + gateway routing. Without a readiness proof, a failed model/route looks like a bundle failure.
  suggested_bundle_name: runtime-model-gateway-readiness
  status: implemented as a dedicated bundle and placed second in the recommended work order.

- concept: Alert ingestion and dedup
  priority: P1
  why_it_matters: triage bundles start *after* an alert exists. The ingestion/dedup/replay-safety front-end is unproven, so the platform's entry path is a gap.
  suggested_bundle_name: alert-ingestion-dedup

- concept: SRE first-contact app onboarding
  priority: P1
  why_it_matters: cold-start path (bring an app → generate agents/failure-modes/eval/report) is the demo narrative; currently only source material exists.
  suggested_bundle_name: sre-first-contact-onboarding

- concept: Deployment-state / GitOps context
  priority: P2
  why_it_matters: maps workload to Helm/Flux/MR/rollout history for safer rollback proposals; enriches triage but not blocking.
  suggested_bundle_name: deployment-state-gitops-context

- concept: AKS-MCP day-to-day Kubernetes ops
  priority: P2
  why_it_matters: separates normal cluster debugging from fleet/chaos; nice-to-have alongside aks-fleet-reporting.
  suggested_bundle_name: aks-mcp-day2-ops

- concept: Ticket / report closure workflow
  priority: P2
  why_it_matters: closes the loop into GitLab/Jira with eval gating; backlog.
  suggested_bundle_name: ticket-closure-eval-gated

- concept: Fleet scheduling / randomized game-day selection
  priority: P2
  why_it_matters: auditable bounded selection for reliability runs; backlog.
  suggested_bundle_name: fleet-gameday-selector

---

HANDOVER_READINESS_SUMMARY:
- can_work_agent_use_with_limited_tokens: yes
- can_work_agent_identify_required_variables: yes
- can_work_agent_separate_static_vs_live_proof: yes (strong in 6 bundles; add the static-only disclaimer to the 6 terse FRONT-SHEETs)
- safe_to_hand_to_work_agent: yes, after Fix #1 (cert-manager-agent.yaml write/delete/exec tools). Every other item is a small consistency/token edit, not a blocker.

---

## Reviewer Notes

- Did not implement any bundle or claim live proof.
- Did not add private environment values.
- Static verifier passed for all 12; treated as internal-consistency evidence only.
- Single must-fix before handover: `sre-grafana-mcp-observability/payload/agents/kagent-triage/cert-manager-agent.yaml` (lines 77-100 tool list + line 54 "Act if safe"). Everything else is NEEDS_SMALL_EDIT polish.
