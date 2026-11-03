# Connect the existing observability path

The full repository ZIP also contains the existing JWT/OTel amendment and demo showcase. Keep those folders beside this one:

- https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/secure-byo-agentgateway-jwt-otel-amendment
- https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/secure-byo-demo-showcase
- https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/agentgateway-1-7-upgrade

Apply their no-Substrate guidance to the **new standalone Gateway and runtime**. Do not run a native alpha/Substrate telemetry installer. Inspect the served Agent Gateway 1.7 policy schema and conflicting telemetry policy ownership first. The amendment's typed telemetry renderer is read-only and produces proposed resources for review; it is not an installer or a verified export claim.

Configure Gateway frontend tracing/access-log export to the approved existing collector. When crossing namespaces, grant the exact collector Service reference from AgentgatewayPolicy and permit the actual Gateway-to-collector network path. Preserve the independent JWT route policies and existing collector receivers, processors, exports and fan-out.

Keep producer content/body capture disabled. Filter metadata before shared fan-out; hiding fields in a viewer does not sanitize Tempo, logs or other exporters. Never put prompts, tool arguments/results, Authorization values or private endpoints into the public report. Keep trace IDs out of metrics labels.

Demonstrate actual route/agent identity, timestamps, operation names, outcome and latency. Observe the standalone invocation and its Gateway model/MCP traffic. If the application does not propagate real W3C context across those boundaries, report separate observed traces; timing alone cannot establish a parent-child relationship. Full agent ancestry is a separate instrumentation gate.

Query the final collector exports and Tempo/log/metrics stores independently, using actual trace IDs and service identity. Report absent/unqueried paths as unknown. The live view must include current request UID, approval expiry/revocation, fresh scenario result and telemetry freshness. A completed historical Job or this folder's static HTML is not a current health signal.

The local recorded evidence determines what was observed here. Office collector connectivity, LGTM storage and final presenter rehearsal need their own receipts. Dashboard creation remains outside this bundle's core composition implementation.
