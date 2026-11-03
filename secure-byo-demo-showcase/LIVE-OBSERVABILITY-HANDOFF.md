# Connect the existing evidence view to the onboarding

This is a required office integration task. The static HTML/PDF briefing is not this live view. Reuse the installed `otel-agent-flow` viewer and OTel/LGTM services where compatible. Extend only the small read-only onboarding, execution and verification panels needed for the demonstration.

## Use two real sources

| Panel | Authoritative input | What it may show |
| --- | --- | --- |
| Onboarding and connectivity | Named Kubernetes objects and protected operator inventory for the current request | Runtime/content/model/MCP bindings, route/grant/policy conditions, generation/UID/spec pins and last refresh |
| Live execution | Actual accepted OTLP spans and access logs plus approved handler witnesses | Model and MCP calls, tool names, status, duration, actual task/session/trace IDs and content-use metadata |
| Security and GoldenScenario | Trusted bounded probe/scenario receipts matched to the current request and deployed revision | JWT allow/deny results, forbidden-dispatch counters, automatic scenario verdict and evidence links |

OTel alone cannot prove Kubernetes readiness or destination consent. A Kubernetes Ready condition cannot prove a real model/tool call. Configured skills/knowledge are distinct from observed loading/retrieval. A requested trace ID is distinct from a received span.

## Extend the actual installed profile

The existing `otel-agent-flow/onboarding_ordinary.py` is a useful reference for named GETs, UID/spec pins, torn samples, short TTLs and GoldenScenario applicability. It binds `kagent.dev/v1alpha2` Agent/ModelConfig resources and fixed ordinary-runtime assumptions. Do not deploy it unchanged against an alpha17 or custom standalone runtime. Match actual served APIs and existing status/inventory seams; do not install old APIs as a fallback.

Reuse the existing viewer snapshot and OTLP projection mechanisms where compatible. Add an explicit owner-UID/current-revision binding for the new onboarding. Obtain resource references from protected platform inventory, not arbitrary browser-supplied Kubernetes paths. Keep the browser away from cluster credentials and raw collector endpoints.

## Required behaviour

- Before application, show no current request. After application, show the newly observed owner UID and each actual stage. Do not prepopulate green components.
- Distinguish pending, ready, blocked, unknown and stale with text as well as colour. Show observation time and expiry. Lost observation or an expired snapshot becomes unknown/stale within its declared TTL.
- Require current generations, exact resource identities and valid references before a stage becomes ready. Recreated same-name objects invalidate old pins and scenario results.
- Keep historical calls separate from the selected current run. Tool/model edges require actual parent IDs, explicit span links or real task/session identity. Timestamps and equal token counts are not proof of a relationship.
- Show content release/hash references and real read/load operation metadata without exposing document bodies. Show the actual runtime kind and no Substrate activity for the demonstrated request.
- Retain only metadata allowlists before collector fan-out. Exclude prompts, tool arguments/results, headers, tokens, JWT claims and raw error bodies. Keep high-cardinality trace/task/run IDs out of Prometheus labels.
- Protect the view with the existing approved access mechanism. Use namespace/name-bounded read-only observer permissions. Do not expose the Kubernetes API, collector ingest/admin ports, arbitrary log proxy or unrestricted cluster list/watch to the browser.
- Display GoldenScenario pending/failed/passed only from the trusted current receipt. The viewer must not approve access, submit arbitrary workloads or let the audience edit a pass flag.

## Target proof before handover

Show a fresh owner YAML causing actual stage transitions and a real request generating received model/Gateway/MCP telemetry. Show skill/knowledge-use evidence and a fresh automatic scenario result. Then prove an unauthorized call is denied without forbidden dispatch, a deliberately invalid binding remains blocked and stale observation does not remain green. Retain private redacted screenshots and timestamps from the final revision.

Validate Tempo retrieval, log delivery and metrics ingestion independently through the existing approved endpoints. A viewer trace proves reception by that viewer, not LGTM ingestion. No full caller-to-agent-to-model/MCP ancestry claim is permitted until actual propagation or explicit link evidence supports it.

Return the maintained source delta, exact read-only view URL privately, observer/profile settings, privacy changes, original collector fan-out preservation, server admission/attachment results, test receipts and rollback. Use actual internal artifact references. Missing prerequisites remain explicit blockers; do not pull packages/images from the Internet in work.
