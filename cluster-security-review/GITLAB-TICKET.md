# Set up an evidence-backed local cluster security review Agent

## Outcome

Deploy the bundled `cluster-security-review` Agent through the approved delivery
path and run one read-only configuration review of its own cluster. Exclude all
namespaces whose names begin with `at`, case-insensitively. Include system
namespaces and report coverage for every included namespace.

Start with [WORK-AGENT-START-PROMPT.md](WORK-AGENT-START-PROMPT.md) and follow
[README.md](README.md). This is a target-cluster implementation ticket template,
not evidence that the setup has run or deployment approval has been granted.

## Inputs

- Target context and Agent/controller namespaces.
- Existing approved model and local MCP server.
- Deployment and invocation authority through the established work process.
- Private evidence destination and approved data/model-provider boundary.
- Decision on whether namespace/secret filtering requires a dedicated backend.

Keep actual work values and scan results in approved private work systems.

## Acceptance criteria

- [ ] Shipped bundle checksum, render and offline triage lint pass.
- [ ] Installed Agent API, model and exact tool schemas are verified.
- [ ] MCP backend target and permission/filtering limits are recorded.
- [ ] Adapted manifest passes the checksum-independent exact-tool validator.
- [ ] Server-side dry-run passes on the named target.
- [ ] Authorised delivery produces current-generation Accepted/Ready and controller API evidence.
- [ ] Context ID is saved before dispatch; a completed A2A review produces the private report.
- [ ] Failed/nonterminal/timeout output stays incomplete and is not retried automatically.
- [ ] Trace source and run correlation are recorded using TOOL-TRACE-VERIFICATION.md.
- [ ] Complete tool trace shows namespace inventory first and no excluded namespace reads.
- [ ] No write, exec, Secret/ConfigMap or remote-cluster operations occur.
- [ ] All findings cite source evidence; every included namespace has a coverage ledger.
- [ ] Scanner, cloud, runtime and incomplete checks appear as assessment gaps.
- [ ] No unsupported CVE, control ID, compliance pass or reachability claim appears.

## Scope boundary

One Agent using existing infrastructure and three local read tools. New MCP
servers, new RBAC grants, scanner Jobs, infrastructure upgrades, remediation and
other-cluster access require separate scoped work. Prompt exclusion is not an
RBAC or data-redaction boundary on the shared MCP server.
