# Office handoff for the work agent

Adopt the scheduled application incident scanner for one opted-in application
using the office's existing Kubernetes, Agent Gateway, kagent and GitLab
service ownership. Use the direct CronJob to gateway to agent to MCP path.
The home-lab example uses cert-manager. Preserve the receiving environment's
names, approved identity, request authentication, service boundaries and
GitOps ownership wherever the mapping allows it.

1. Read [START-HERE.md](START-HERE.md), [the office adoption guide](docs/office-adoption.md),
   [validation and evidence](docs/validation.md) and
   [documentation maintenance](docs/maintain.md).
2. Inventory the installed APIs and runtime versions, source application and
   scoped Kubernetes access, gateway and A2A transform, model/harness, MCP
   authentication, and approved private GitLab project and numeric assignee.
   Resolve the target bindings in a private overlay. Keep secrets in the
   receiving environment's secret-management path.
3. Run the included tests and render the overlay. Compare the actual bound
   routes, RBAC, per-application state objects and preview mode against the
   target. Carry operational state outside the declarative reconciliation
   that installs code and policy.
4. Verify the approved canary in the receiving environment. Collect the
   original observation, admitted incident ID, kagent task or transport
   outcome, matching durable MCP receipt, and duplicate/limit results.
   Use the office test project and scoped credentials when verifying actual
   issue creation and assignment.
5. Make the corresponding change to the office MkDocs sources. Keep a link
   to the interactive HTML presentation and cite receiving-side evidence in
   the internal documentation. Preserve previously recorded evidence and
   record any newly approved milestone in the office delivery calendar.
6. Report the scoped diff, actual versions and target receipts, the Markdown
   and HTML paths that changed, validation output, rollback path and any
   unresolved acceptance items.

Home-lab defaults are examples. Workplace execution and publishing follow
the receiving team's existing authority and change process.
