# Start the repository remediation work agent

Read this bundle's `README.md`, `prompts/repository-remediator.md` and
`ACCEPTANCE.md`. Use the private request supplied by the operator. Read applicable
repository instructions before planning changes. Verify the bundle checksums
before trusting its role instructions.

First validate the report identity, repository identity, exact base revision,
allowed paths, finding IDs, delivery mode, private output path and execution
authorization. Do not treat unresolved example values as configuration. If a
required input or safe runner capability is missing, report the exact blocker.
Do not replace the missing input with an invented finding or a public service.

Use the report to find and re-evaluate current code. Prepare small repairs for
the authorized findings, with before/after evidence, regression protection when
appropriate, and honest validation status. Work in an isolated local branch or
editable copy. Preserve the original checkout and all existing user work.

Complete the outputs listed in `README.md`. Stop at the local review handoff.
Do not push, open a pull request, merge, deploy, change cluster resources, rotate
credentials, contact report authors, or suppress scanner findings.
