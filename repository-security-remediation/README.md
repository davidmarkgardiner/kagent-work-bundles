# Prepare repository fixes from a security report

Give a coding agent this bundle, the approved private repository checkout and a
redacted copy of the Mythos report. The role maps each finding to current code,
records its disposition, and prepares bounded fixes in a local branch or patch.
It does not assume that the report's claims or suggested patches are correct.

This is a portable coding-agent role. It requires an existing trusted coding
runner with local source access, editing and Git support. It is not a deployable
kagent Agent and does not provide an in-cluster Git worker, execution sandbox,
GitLab credentials or a native tool service. The existing source-security-audit
bundle remains the discovery/audit role. This role consumes reports and owns the
reviewable repair work.

## Start the work agent

1. Transfer this complete directory. Run `shasum -a 256 -c CHECKSUMS.sha256`
   from its root before adapting files. Linux can use `sha256sum -c`.
2. Read `ACCEPTANCE.md`. Use the office's trusted local tools and approved
   internal model route. Do not download dependencies or use a public model
   endpoint as a fallback.
3. Copy `remediation-request.example.json` outside the public bundle. Supply the
   exact local repository, base commit, redacted report, scope and a new private
   output path. Use one request per repository. Document any report-to-repository
   or report-to-commit mismatch before editing.
4. Give the runner `WORK-AGENT-START-PROMPT.md`, this bundle's absolute path and
   the populated request. The runner reads `prompts/repository-remediator.md`.
5. Review the resulting disposition ledger, diff and validation evidence. A
   local fix is not a deployed fix. Pushes, remote branches, pull requests,
   merges and releases are outside the default request.

## Configuration

`{{ABSOLUTE_TRUSTED_REPOSITORY}}` identifies an operator-provisioned stable Git
checkout. `{{FULL_REVIEWED_BASE_COMMIT}}` is its full commit ID.
`{{ABSOLUTE_PRIVATE_REDACTED_REPORT}}` points to the supplied report.
`{{REPORTED_SOURCE_COMMIT_OR_UNKNOWN}}` records the report's stated revision.
`{{ABSOLUTE_NEW_PRIVATE_OUTPUT_DIRECTORY}}` is a new directory outside both the
repository and this bundle. `{{APPROVED_SCOPE_PATH}}` limits edits and reads.
`{{UNIQUE_RUN_ID}}` names the new local branch and run. Replace all placeholders.

`delivery` is `local-branch` or `patch-only`. `local-branch` uses a new isolated
worktree and branch, leaves changes uncommitted, and records a patch in the output.
`patch-only` produces a patch from a separate editable copy without modifying the
source checkout or creating a branch. The operator must supply a trusted isolated
copy if the runner cannot safely provision one. Neither mode pushes or commits.

`approved_finding_ids` is a nonempty explicit list of report finding IDs allowed
for repair. Other findings are triaged and recorded. If IDs are absent, assign
stable local IDs and produce a triage-only result until the repair scope is set.
This is a scope boundary for the workplace run, not approval to alter every repo
mentioned in a report. `max_findings_to_fix` bounds one review unit.

`execution.authorized` defaults to false. In that mode, read and edit source
without running target tests, builds, scripts, package managers or config loaders.
Set it to true only when the private request identifies an approved sandbox and
an explicit list of allowed commands. The bundle does not create that sandbox.
An empty command list still authorizes no execution. Static review alone must
remain labelled as such.

## Outputs and proof limits

Keep `request.json`, `repository-map.md`, `findings.json`, `changes.patch`,
`validation.md` and `HANDOFF.md` in the private output directory. Hash the supplied
report locally and retain that hash with the source commit. The example
`finding-record.example.json` defines the ledger fields. Emit one record for
every in-scope report item, including items that cannot be repaired.

Do not include raw credentials, private report content or workplace source in the
public bundle. Use bounded sanitized excerpts with exact file and symbol
locations. Inspect Git binary patches for sensitive content before retaining them.

Preparation checks cover this bundle's links, example JSON, checksums and
placeholder safety. No Mythos report or target repository was supplied during
preparation. No vulnerability was reproduced, fixed or independently verified by
creating this bundle. The workplace agent must produce that evidence.
