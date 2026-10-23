# Verify what the Agent actually called

Use this procedure after the first review. A model's evidence appendix and a
successful A2A response do not prove which tools ran. Record the actual trace
source, its installed version, run correlation and completeness in the private
evidence directory. Never publish raw traces or access credentials in this repo.

## Identify the run before dispatch

Follow the README invocation recipe. It creates a private directory for this run,
saves the explicit context ID before the HTTP request and retains invocation
diagnostics. After a response, record the returned task ID and context ID from the
raw receipt when present. A supplied context ID is a correlation key; do not assume
it is identical to a database session ID or telemetry trace ID.

On timeout, use the saved context ID and invocation time to inspect the existing
run through the approved runtime UI or telemetry source. Do not invoke another
scan to manufacture missing evidence. The client timeout does not cancel work.

## Select an existing source for this installed version

Prefer the runtime's existing session/tool-call view or its approved export if it
contains the complete ordered calls, input arguments and results for this run.
Record how that view maps the returned task/context ID to the displayed session.
A terminal receipt's `result.history` is usable only when it actually contains
those tool records; a history containing only final text is insufficient.

For installations exposing the controller database API, the inspected upstream
source at `9fd3c84d` implements these read-only routes:

```text
GET /api/tasks/{task_id}
GET /api/sessions/agent/{namespace}/{name}
GET /api/sessions/{session_id}?order=asc&limit=500
```

The session response in that source contains `data.session` and `data.events`.
Each event's `data` is a serialized JSON message. Use the installed runtime's
schema to inspect its data parts; do not assume every message records a tool call.
The task read can supply additional correlation when available. A list of sessions
or matching timestamps alone does not prove the selected session belongs to this
invocation. Require the explicit task/context mapping from the runtime.

These are source-backed candidate routes, not a claim that this API works on the
work cluster. Verify the installed version and use the approved controller client
or an operator-owned local port-forward, with existing authentication. Read only
the named Agent and exact correlated session. Do not enumerate other tenants or
use a database shell, broad account, alternate endpoint or new permissions after
an access denial. An unavailable session API is a proof gap, not a reason to fall
back to the broken session/chat invocation path on older versions.

If the session route truncates at the requested event limit, obtain an existing
complete approved export or mark the trace incomplete. Do not treat a first page
as absence of later excluded calls. Do not auto-page raw cluster evidence back
into chat. Keep the raw export private and inspect it locally with approved tools.

An existing OTel/MCP observability source is another option if it records tool
name, arguments, result/error and run correlation. A span that records only a tool
name cannot prove the namespace or resource scope. Do not enable logging, change
sampling or install instrumentation as part of this handoff without separate scope.

## Check the actual records

For each call, retain the sequence/time, tool name, submitted arguments, result or
error, and task/context/trace correlation when supplied. Verify that:

- The first Kubernetes tool call inventories namespaces.
- Every later namespaced resource read specifies an included namespace explicitly.
- No direct read/list/describe targets a namespace beginning with `at`, Secret or
  ConfigMap resources, including aliases and combined resource types.
- The complete tool set contains only the three allowed inspection tools. No
  write, exec, shell, connectivity probe, delegation or cluster switch occurs.
- Cluster-scoped reads are justified and excluded-namespace references are not
  followed. Namespace metadata inventory itself is the permitted scope discovery.
- Findings' evidence IDs match actual arguments, resource fields and sanitized
  result excerpts. Errors, truncated results and missing checks remain gaps.
- The report's namespace inventory and coverage ledger agree with the actual
  inventory. An unexamined namespace is never described as clean.

Record `VERIFIED`, `VIOLATION`, or `UNVERIFIED` for each criterion, with the trace
location and reason. Missing correlation, omitted arguments, missing results,
partial retention or unavailable traces requires `UNVERIFIED`, never a pass.
Any violation stops acceptance of the review as meeting evidence. A complete
trace of compliant calls proves observed behavior for this run; it does not create
a hard backend authorization boundary or prove future invocations are safe.

## Private handoff receipt

```text
Agent and deployed generation:
Installed controller/runtime version:
Invocation context ID and returned task ID:
Trace source and correlated session/trace ID:
Full-run coverage or missing/truncated ranges:
Observed tool names and call count:
Namespace inventory and at-prefix exclusions:
Criteria results, VERIFIED / VIOLATION / UNVERIFIED:
Private report, response, log and trace locations:
Unresolved gates and smallest next action:
```

Upstream source references for the candidate routes and event envelope:

- https://github.com/kagent-dev/kagent/blob/9fd3c84d/go/core/internal/httpserver/server.go
- https://github.com/kagent-dev/kagent/blob/9fd3c84d/go/core/internal/httpserver/handlers/sessions.go
- https://github.com/kagent-dev/kagent/blob/9fd3c84d/go/api/database/models.go
