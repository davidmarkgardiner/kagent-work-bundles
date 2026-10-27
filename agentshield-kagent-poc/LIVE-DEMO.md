# Native Proxmox AgentShield demonstration

Verified on 27 October 2026 using kagent `1.0.0-alpha17`, Kubernetes `v1.35.0`, Substrate `0.6.0-alpha3`, and existing Agent Gateway `v1.5.0`.

[Open the recorded HTML demonstration](live-demo.html). [Read the sanitized receipt](runtime/evidence/proxmox-native-2026-10-27.json). [Read the redacted native reply](runtime/evidence/native-assistant-redacted.txt).

## What actually passed

| Phase | Actual dummy HTTP result | Sensitive selector edge | Finding records |
|---|---|---|---|
| Baseline | Reporting marker | Absent | 0 |
| Metadata-only benign control | Reporting marker | Absent | 0 |
| Service selector drift | Dummy-sensitive marker | Present | 1 |
| Rollback | Reporting marker restored | Absent | Same 1 retained match |

The observer used real Kubernetes watch observations. An activated, fixed-sensitive-Pod CEL rule produced a persisted `origin=detection_rule` finding through the normal engine and FindingSink. The fixture curl calls separately proved where the Service routed requests. AgentShield did not ingest those HTTP calls as traffic telemetry.

A 2,560-byte bounded packet was passed through an operator-triggered native session. The task completed, cited the exact finding/rule/current graph, and made zero observed tool calls. Existing Agent Gateway recorded one Kimi chat-completions request with 2,216 input tokens and 463 output tokens. This is observed usage for this demonstration, not a general cost or performance claim.

## Configuration and safety evidence

The AgentShield API and dedicated PostgreSQL database listen only on executor loopback. The observer uses its own read-only service-account kubeconfig, kept on the executor. Authorization checks denied Pod patches and NetworkPolicy creation. The default inventory still requires Secret reads; values enter its process memory before the upstream provider discards them from publication.

The existing CNI daemonset spec, Agent Gateway deployment spec, and gateway ConfigMap data matched their before-run values after the test. No shared worker restart was performed. The Service was restored to its reporting backend. The observer, dummy fixture, dedicated database, native Agent, and dedicated worker remain available for review. The observer token was issued for 12 hours; refresh it through the approved executor workflow before a later replay. Existing VM power schedules were not changed.

## Why this uses a local source patch

The reviewed upstream daemon starts detection only with a model-calling feature. Our existing gateway uses chat completions, while AgentShield investigation expects Responses. A narrow `--detector-only` patch enables the existing deterministic engine and finding sink without either model worker, and rejects combinations with model features. It is an explicitly modified build, not an upstream installation feature.

The patch applies to upstream commit `b179824e455401783f031a370b8794358a10dd8c`. The receipt records patch and binary SHA256 values. The full command package tests passed locally. A separate executor database test proved deterministic startup with no model workers. All 10 evidence-packer boundary tests passed.

## Runtime recovery that mattered

The existing default worker retained a pre-reboot pod address. Two initial CLI calls were explicitly unaccepted; the affected native session had zero persisted tasks and no model request reached the gateway. We preserved those receipts and created an owned dedicated worker pool. Required native worker selector labels were added before snapshot preparation could complete. A new session on that prepared revision then completed one accepted task.

The shared default pool's stale registration is a separate remaining lab issue. The dedicated PoC worker avoids it for this demonstration. Do not interpret an Agent Ready condition as proof of a working conversation.

## Limits the demonstration preserves

- This proves Service selector configuration drift and a native operator-triggered handoff. It does not prove detected exfiltration, blocked lateral movement, or NetworkPolicy enforcement. The native cluster uses kindnet.
- Upstream detection-rule findings retain `active` status after rollback. The packet separately reports the current target edge absent and labels the record historical. The product UI's active count is not proof that the risky path still exists.
- No external MCP tools, skills, or plugins were bound. The runtime supplied six built-in ADK tools, and none were observed being called. Built-in tool isolation was not established.
- No automatic MCP handoff, autonomous remediation, or workplace deployment was performed. The rule targets one fixed dummy Pod identity; it is a demonstration policy, not a general application-intent model.

## Run it or transfer it

Follow [the runtime guide](runtime/README.md). Use only the owned fixture and a dedicated database. Keep raw packets and native logs on the executor. The public receipt omits internal addresses, native session/task IDs, kubeconfig, credentials, and the full graph.

For workplace adaptation, preserve installed names, authentication, model routing, and delivery flow. Review the patch, CRDs, collector permissions, and evidence contract in a dedicated lower environment before installation. Native API and worker behavior must be re-proven there.
