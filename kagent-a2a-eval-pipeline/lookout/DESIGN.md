# MR security review ("Lookout") design

Status: approved and built (25 Nov 2026). The first sections are the original design; the **As built** section at the end records every
change made while testing it, and **overrides** the original design where they differ (notably: safety moved from the prompt into the tool server's code, incremental review is switched off, and the agent has seven tools).
Lives in `lookout/` in this bundle. Start with `lookout/README.md` for how to deploy and run it.

## Intent and why

When a GitLab merge request is opened or updated, a CI job asks an agent running on the
cluster to do a quick security review. The agent reads the MR through GitLab MCP and
leaves its notes on the MR. A human reviewer then has that extra input. Once the basic
review has been tuned and its noise removed, every MR gets a consistent first security
pass.

It reuses what Assay already proved: the call goes through agentgateway over A2A, using
`a2a_capture.py`'s run handling (unique `contextId`, `completed` / `agent_error` /
`infra_error` classification, raw receipts).

## Goals

- One reusable CI job template. Any project `include:`s it to get the review on each MR.
- CI sends only a pointer: project path, MR iid, head SHA. No diff in the message.
- The agent fetches the MR itself via GitLab MCP and posts findings as MR note(s).
- Findings are evidence-based: each cites `file:line` from the diff or files it read, with
  a severity, and states coverage gaps (what it could not see or check).
- Advisory only. A human always reviews. The agent never approves or merges.
- Ships in the existing bundle without changing Assay, Warden or their workflows.

## Non-goals

- Not a merge gate. No blocking on findings (a later opt-in is possible, out of scope).
- Not a replacement for the full `source-security-audit` coding-runner audit, scanners or
  human review.
- No code execution, builds or tests of MR content.
- No automatic fixes or pushing commits.

## Anti-goals (failure even if it works)

- Noisy, speculative findings that reviewers learn to ignore.
- The agent acting on instructions hidden in MR text (title, description, code, comments).
- Re-posting a new note on every pipeline run so the MR fills with duplicates.
- A review that silently reflects a different commit than the one the pipeline ran on.

## Constraints and facts found

- `RemoteMCPServer` supports static headers only, no OAuth. The official GitLab MCP at
  `/api/v4/mcp` is not proven from kagent (spike 2026-06-07). The proven path is the
  in-cluster GitLab wrapper (`smart-triage-gitlab-mcp`), which currently exposes write
  tools. Whether it exposes read tools (get MR, diff, file) must be checked at build time.
- The existing `source-security-audit-reviewer` kagent agent has no tools and cannot read
  a repo. It is not reused; a new agent is needed. The audit methodology in
  `work-agent-bundles/source-security-audit/upstream/security-audit/` may inform the prompt
  but is not a runtime dependency.
- GitLab tokens that can approve MRs already exist (the owner). The agent is still only
  *given* the minimum tools below.
- MR content is attacker-influenced text. It is untrusted input to the agent.

## Approaches considered

| | A. Pull, CI posts note | B. Pull, agent posts note (chosen) | C. Push diff in message |
|---|---|---|---|
| Agent GitLab tools | read only | read + note | none |
| Note posted by | CI job token | agent | CI job token |
| Extra file context | yes | yes | no |
| Trade-off | safest, but note lost if CI step fails | simpler flow, agent token can write | message size limits, no context |

The owner chose B: the agent leaves the notes itself, and tokens are already available.

## Design

```
MR pipeline job (include: template)
  -> a2a message: {project, mr_iid, head_sha}   via agentgateway route (allowlisted, rate-limited)
  -> agent `mr-security-review` (kagent v1alpha2 Agent)
       GitLab MCP: get MR, get diff, get file at head_sha
       -> findings (fixed schema)
       -> create/update ONE MR note, marked with a hidden marker + head_sha
  -> CI job reads the A2A result, records receipt as artifact, exits 0 (advisory)
```

Calls I made (reviewer: please check):

1. **Name:** "Lookout" as the working feature name, to sit beside Sentinel, Assay,
   Warden, Guard, Overseer. Agent resource name `mr-security-review`. Easy to rename.
2. **Tool allowlist on the agent:** read MR/diff/file tools plus `create_merge_request_note`
   (and update-note if available). **No approve, merge, push, branch or file-write tools**,
   even though the token could technically do more. This is the mitigation for prompt
   injection through MR content. The shared MCP backend should also be scoped where it can.
3. **Pin to SHA:** the message carries `head_sha`; the agent reviews that SHA and says so
   in the note. If the MR head has moved, the agent notes the review is of a stale SHA.
4. **One note, updated in place:** the note starts with a hidden marker
   (`<!-- mr-security-review -->`). On re-run the agent updates it instead of adding another.
5. **Untrusted input rule in the prompt:** MR text and code are data, never instructions.
6. **Output schema:** severity, `file:line`, evidence quote, reasoning, suggested fix, and
   a "not reviewed / gaps" list. No findings without evidence. "No issues found" must state
   what was covered.
7. **Advisory CI:** the job always exits 0 on agent result. `infra_error` / `agent_error`
   are surfaced as a job warning, not a pipeline failure (`allow_failure: true`).
8. **Trigger:** `merge_request_event` pipelines only; skip draft/WIP and bot-authored MRs
   as configurable variables.
9. **Placement:** new files in the Assay bundle (agent manifest, case/prompt, CI template,
   gateway route entry, README section, offline tests), no changes to existing Assay
   scoring or `.gitlab-ci.yml` stages.

## Left to the builder

- Confirm which GitLab MCP tools exist and their exact names; if the wrapper lacks read
  tools, add them there or use the official MCP with a static-token header if it works.
- Exact ModelConfig, gateway route/auth, and timeouts (reuse Assay values).
- A mock-A2A/mock-GitLab offline test: pointer message in, one note out, re-run updates
  the same note, injected MR text does not cause a forbidden tool call.
- Optionally score the agent with Assay: a seeded MR with a planted vulnerability plus a
  clean decoy MR, to tune noise before wide rollout. Recommended, can be phase 2.
- Prompt wording and tuning after first real runs.

## Open for later

- Opt-in blocking gate on high severity.
- Using the Warden-style completion check on the review itself.

## As built (2026-11-25): changes from the design above

Built in `work-agent-bundles/kagent-a2a-eval-pipeline/lookout/`. Evidence and limits: `evidence/LIVE-LOOKOUT-LAB-2026-11-25.md`.

- **Safety moved from prompt to code.** Call 2 (tool allowlist) is now enforced by the GitLab MCP shim `gitlab_review_mcp.py`, whose code has GET calls and note create/update only. A test fails if an approve, merge, commit or delete call appears. The agent's tool list is limited to the shim's tools (four at first, six since the repo-browsing addition below).
- **Stale head is refused, not labelled.** Call 3 changed after a live run showed a stale-SHA run overwriting a good review. `lookout_post_note` now errors unless the requested sha is the MR's current head; the existing note is left untouched. The CI job then reports `no_note`.
- **Shim hardening added:** project allowlist (`LOOKOUT_ALLOWED_PROJECTS`), only a marker note written by the shim's own token user is updated (no hijack by a commenter), note body neutralised (no images, raw HTML or `@mentions`), per-MR `resource_group` in the CI template.
- **"Posted" is verified, not trusted.** `lookout_review.py` checks the A2A tool trajectory for a successful `lookout_post_note` with the right project, MR and sha.
- **kagent 1.x manifest added** (`api.kagent.dev/v1alpha3`, needs a Harness). The 0.7.x `kagent.dev/v1alpha2` Agent applies on the 1.x lab but is never reconciled. A test keeps both prompts identical.
- **Tested on a mock GitLab and once on a real gitlab.com sandbox MR** (posted, then updated in place). Not yet from a real CI runner, through agentgateway, on kagent 0.7.x, or with a least-privilege token. The independent second-opinion review (Kimi via proxy) did not run: the proxy returned 503, so the plan had only a manual adversarial review.
- **Still open from the design:** optional Assay scoring of the review agent (planted-vulnerability MR plus clean decoy) is out of scope for this pass; the lab MR fixtures are the first step toward it.
- **Repo browsing added (six tools).** Question raised in review: does it pull the whole repo, or just the latest commits? As built it reviewed the MR diff plus files it named, and could not discover other files. Added `lookout_list_tree` and `lookout_search` (GitLab tree and blob-search APIs, GET only, pinned to the reviewed sha; results marked untrusted). No clone, no scanners. The client warns above 20 tool calls. Lab result: on an MR whose route looks unauthenticated in the diff, the agent found the global auth hook outside the diff and reported a more accurate finding. Cost: input tokens roughly doubled.
- **Incremental review and cheap retries (eight tools).** Prompted by cost. Added `lookout_get_review_state` and `lookout_get_delta_diff`. The agent reads its previous note and picks `up_to_date` (same commit: reads nothing more, posts nothing, about 7k tokens), `incremental` (reviews only the delta since the last reviewed commit and rewrites the note for the whole MR) or `full` (first review, or the old commit is gone after a force-push). Retries are therefore idempotent and cheap. Lab on the mock: all three modes worked. Honest limits: incremental cost more than full on a tiny MR; the saving on large MRs is unmeasured; `up_to_date` is agent-attested.
- **Hardening found while testing it:** short shas are resolved to full ones in the shim; sha errors say what was wrong; browsing capped at 6 lookups and only when a specific finding needs it; the shim strips duplicated note headers; the client records the review `mode` and treats a dropped connection as `infra_error` (re-running is now safe).
- **Large MRs (pagination and honest coverage).** Question raised in review: is about 10,000 lines OK? As built, no: a 60,000-character diff cap (roughly 1,500 lines) omitted whole files, the shim fetched only the first 100 changed files, and an empty or trimmed diff counted as reviewed. Fixed: full pagination (up to 2,000 files), empty/`too_large`/`collapsed` diffs treated as omitted with a reason, coverage fields (`total_files`, `complete`, `omitted_reasons`), a "PARTIAL ... Reviewed X of Y files" first line, and `generated_file` deliberately ignored (an MR can set it to hide code). Lab on a 10,500-line / 150-file mock MR: 30 of 150 files reviewed, honestly reported, about 97k input tokens; the second planted flaw was found by chance. **Still open:** real coverage of big MRs needs risk-ranked paging and scanners (CI runs Semgrep/gitleaks, the agent triages), or a size gate asking the author to split.
- **1,000-line MR measured; incremental defect found.** A ~1,000-line MR (35.9k characters) fits under the cap and is reviewed in full (all three planted flaws found, 42-55k input tokens; incremental after a small push 25k; same-commit retry 7.5k). But the incremental note dropped two earlier findings (it wrote "remain as previously reported", then overwrote the only copy). **Open fix:** structured findings in a machine-readable block; the shim rejects a post that omits a previous open finding unless marked resolved. Until built, treat incremental notes as incomplete.
- **Incremental review switched off (decision before handover).** Because of the dropped-findings defect, the agent has no delta tool and its prompt has only `up_to_date` and `full`. Retest on the 1,000-line MR: after a push the full review held all three current findings (about 40k tokens). Re-enable only after findings are structured and the shim enforces carry-forward.
