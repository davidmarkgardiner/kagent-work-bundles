# Adopt the office workflow

Copy this folder into the office repository or retain the existing directory
layout in your handoff. Use `scheduled/` as the implementation overlay.
The sibling root lab manifests reproduce the earlier single-fault demo.

## Map the receiving environment

| Bundle area | Bind to the office target |
| --- | --- |
| `scheduled/policy.json` | Logical cluster, application, Deployment, controller container, selector and application-specific signal policy. [Download the example](assets/policy.json){: download="policy.json" }. |
| `scheduled/scanner.yaml` | Application namespace, unique CronJob and ServiceAccount, two named runtime ConfigMaps and the private ingress URL and Host header. |
| `scheduled/gateway.yaml` | The approved Istio ingress and Agent Gateway listener, hostname, exact POST path, kagent route and A2A transform. Preserve existing caller authentication and network controls. |
| `scheduled/agent.yaml` | Installed kagent APIs, selected model and Substrate harness, approved MCP service and authentication binding. |
| `scheduled/mcp.yaml` | Scoped identity for source reads and named outcome writes, plus the approved GitLab destination, scoped credential and numeric assignee. |

The example lab uses kagent 1.0.1 on Substrate 1.0.0, Agent Gateway 1.7.0,
Gateway API 1.4.1, Istio 1.30.8 and cert-manager 1.21.3. Verify office
versions, API shape, model/harness readiness, connectivity to the source
cluster, and the receiving GitLab contract before adapting the bindings.

A fresh application profile should have unique state names, caller, route
and agent identities. Keep its runtime ConfigMaps outside declarative code
and policy reconciliation. Create the state once with `state.json` set
to `{"version":1}`, and the outcomes once with `outcomes.json` set to
`{}`. Confirm the scanner can update only its state and read its outcomes.
Confirm the MCP identity can read the named application data and update its
outcome store. Kubernetes allows pod log access at namespace scope in this
example. The scanner filters to containers owned by the selected workload.

## Review an application policy

- Use `extra_event_reasons` to include selected Normal events.
- Use `related_event_objects` to associate additional named objects.
- Use `log_rules` for identifiable application log messages without standard severity.
- Use `ignore_log_patterns` to drop known noise before classification and
  `ignore_signals` to drop a reviewed exact log or event signature.
- Read `pending-review` suggestions in the outcome store. Compare the
  suggested signature with source evidence before editing policy.

A single profile covers one Deployment and one configured controller
container, including existing previous logs. The bundled poller limits
collection to eight pods, 400 lines per log stream, four API pages per list,
and 128 active signatures. Use the approved log/event backend when the
application needs broader or longer-lived telemetry.

## Start in preview and keep rollback available

Render the private overlay against the intended target schema and use
the local tests before canary execution. The committed CronJob starts
suspended and the ticket tool starts in preview. Follow
[the receiving canary](validation.md#receiving-canary) before enabling
the schedule and private GitLab creation.

To stop dispatch, suspend the CronJob in the owning overlay and reconcile it.
Inspect any in-flight Job and reconcile its exact incident receipt before
an operator replay. Preserve the durable state and outcomes across rollback.
Restore the previous reviewed policy, route or agent configuration through
the owning GitOps path if a change needs to be reverted.
