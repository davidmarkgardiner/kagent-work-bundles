# Review the repository remediation handoff

Use these checks on the actual workplace run. Bundle preparation does not satisfy
the target checks.

- The report hash, repository identity and exact source commit are recorded.
  Report/source mismatches remain explicit.
- The original checkout and existing user work remain unchanged. Work is in a
  new isolated branch/worktree or separate editable copy. Its location is recorded.
- Every in-scope report item has a disposition with file/symbol evidence or a
  concrete blocker. The report's severity is attributed to the report.
- Repairs touch only approved finding IDs and paths. Findings outside the repair
  budget remain open. The patch includes new files and no raw credentials.
- Target code ran only under the explicit private execution grant in the named
  verified sandbox. Missing tooling or isolation remains a blocker.
- Applicable regressions and required project checks have actual recorded
  results. Checks not run remain unverified. No suppression or weakened security
  gate substitutes for a fix.
- `changes.patch` applies to the exact clean base in a trusted copy, or that gate
  is explicitly unverified. The handoff describes the impact and reversal.
- `fixed_locally` means the repair passed required checks. Untested changes remain
  `proposed_local_change`. No local result is described as a deployed fix.
- No push, remote branch, pull request, merge, deployment, cluster mutation,
  credential rotation or external communication occurred.

Retain private `request.json`, `repository-map.md`, `findings.json`,
`changes.patch`, `validation.md` and `HANDOFF.md`. Keep the report and workplace
source outside the public bundle.
