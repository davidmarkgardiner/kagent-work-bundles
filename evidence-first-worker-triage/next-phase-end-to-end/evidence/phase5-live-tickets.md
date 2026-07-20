# Phase 5 — Live ticket URLs/IDs created this session

All real GitLab work items in `davidmarkgardiner/mcp-test-repo`, created by
the live Alloy → Vector → Confluent → Argo → kagent → GitLab path running on
`red`. Every one carries the rendered incident contract (fingerprint,
cluster, workload/pod/container, reason+severity, first/last seen, redacted
evidence, agent diagnosis with confidence, ticket state) — not a raw payload
— per the Gate-0 fix. All test signals are synthetic; no real credential or
production incident was involved.

| Ticket | Context |
|---|---|
| [#446](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/446), [#447](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/447) | The claim-race defect being re-proven, caught live (see `phase0`) — kept as evidence of the defect this gate exists to catch |
| [#448](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/448), [#451](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/451) | Redaction re-proof (P0-1) |
| [#449](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/449) | Correlation single-ticket proof (repeated BackOff, ~28 workflow runs, 1 ticket) |
| [#450](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/450) | Correlation re-proof (P0-2), post-CAS-fix: log + event race → exactly one ticket |
| [#452](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/452) | Post-claim-failure retry drill — no duplicate, no evidence loss |
| [#453](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/453) | `FailedScheduling` event class + explicit in-window replay proof |
| [#456](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/456), [#457](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/457), [#459](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/459), [#468](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/468) | Log-path fixtures (payments timeout, OOM pre-kill log ×2, missing-ConfigMap) |
| [#467](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/467) | `BackOff` (image pull) event class |
| [#474](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/474), [#478](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/478) | `Unhealthy` event class (readiness/liveness probe failure) |
| [#479](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/479) | Post-disk-buffer-revert sanity check (confirms Kafka delivery healthy again) |
| [#480](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/480), [#481](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/481) | Fingerprint pod-churn test — the real DS-04 gap (two tickets where one was expected) |
| [#484](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/484) | Valid record through the new DLQ/validate gate |
| [#485](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/485) | DLQ replay proof — a quarantined record, fixed and resubmitted |
| [#486](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/486) | Real Sensor-triggered (not `argo submit`) fixture through the new DLQ gate — confirms the gate is safe for live traffic |
| [#487](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/487)–[#494](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/494) | Bounded-concurrency burst drill: 8 concurrent incidents, capped at 5 running, all 8 eventually ticketed, none lost/duplicated |

```text
LIVE_TICKET_VALUE_SHOWN: yes
```
