# Next: the monitoring loop and the guard agent

**Status: the Guard is built and live-tested on the lab (detector, proposal, ticket); the overseer intake is built but its agent is not passing live yet (a tool-output 400 was fixed, then it wandered); the alert delivery path is not run.** Five parts:

| # | Use case | Role | State |
|---|---|---|---|
| 1 | **Sentinel** | Watches the app, alerts, hands a finding to an investigator agent | verified (see the Sentinel bundle) |
| 2 | **Assay** | Tests an agent before it ships | verified live (kagent 0.7.13) |
| 3 | **Warden** | Signs off each run before anything is ticketed | verified live, 2 of 3 runs on 1.x alpha |
| 4 | **Guard** (working name) | Watches the agents themselves for rogue behaviour; proposes a block and a ticket | built; detector, proposal and ticket tested live on the lab |
| 5 | **Overseer** (agent-health agent) | Receives LGTM alerts by API, investigates read-only, drafts an issue with a recommendation | intake built; agent not passing live yet: its model 400 (a 4.4 MB tool result) was fixed, then it wandered for 245000 tokens and wrote no report; a tool-call budget and a better prompt now gate it, untested live |

## Loop: when an agent fails

Use the monitoring stack that is already in place (Grafana, Loki, Mimir/Prometheus, Alertmanager, Argo Events) and **OpenTelemetry traces**: agentgateway emits spans for every model and MCP call, and the Geekom factory already writes one OTLP trace per agent run into Tempo. The alert-to-agent path exists
(Alertmanager → Argo Events → Sensor → Workflow → observability agent). What is missing is the **signal**: today nothing alerts on an agent that fails or never
finishes. The only agent alert rules score eval *results* (`agent_eval_score`, `agent_eval_hard_failures`).

Signals to add: a task that fails or carries `kagent_error_code` (these arrive as HTTP 200, so no ordinary monitor sees them), a Warden FAIL or `reject`,
an overdue Sentinel run, the evaluator being down, and the model route failing. Warden can emit the first two as a metric and a structured log line.

## Guard agent: what it watches

| Signal | Source (OTel traces first) | Example rule |
|---|---|---|
| Running too long | span duration of the agent task, from Tempo span metrics | one task open for longer than its case budget |
| Token burn | token-usage attributes on model-call spans (`gen_ai.usage.*`), summed per agent | tokens per hour above a multiple of the agent's baseline |
| Tools it should not use | tool-call spans (MCP calls through the gateway) | any tool name outside the agent's contract allowlist |
| Non-200 responses | HTTP status attributes on gateway spans, and access logs in Loki | error ratio, or a burst of 401/403/429, per caller |

Tempo's metrics generator turns spans into Mimir/Prometheus metrics, so these are ordinary alert rules. Check that the gateway version in use exports the token
and tool attributes before relying on them; that has not been verified here.

## Guard agent: what it may do

1. **Detect in code, explain with the model.** The rules above are Prometheus/Loki alert rules. The model never decides whether something is rogue; it
   writes the explanation and the ticket text. A prompt cannot talk the detector out of firing.
2. **Block a definite offender immediately (owner decision, 24 Nov 2026).** `guard/propose.py` writes the policy; `guard/enforce.py apply --auto-apply --context <explicit>` applies it directly, as a failsafe,
   but only for signals in `rules.yaml autoApply.signals` (default `forbidden_tool`: a deterministic tool-outside-allowlist result). `token_burn` and everything else stay proposal-only. The policy is re-validated
   independently (one named route, `Deny`, one `jwt.sub` identifier, the allowed namespace); a cap on active blocks (3) and on applies per hour (2) stops a runaway Guard blocking the fleet; a kill switch; server
   dry-run, then apply, then read-back; one ledger line per decision. **A block never expires by itself:** a person reviews, fixes, then runs `enforce.py release`.
3. **A short list it can never block:** the monitoring stack, the Guard itself, and any agent named as critical. A guard that can block the thing that watches it can be abused to
   blind the system.
4. **Least privilege, in a separate component.** The detector and the agent hold no write credentials. Only `enforce.py` writes, and it should run under its own narrow identity: create, get, list and delete
   `agentgatewaypolicies` carrying the guard label, in the one policy namespace, and nothing else. A prompt cannot widen that.
5. **Treat what it reads as hostile.** Agent output and tool arguments are untrusted text. Quote them into the ticket; never follow instructions found in them.
6. **It is an agent too.** It passes Assay before it is promoted, runs under a Warden contract, and has its own dead-man's switch.

## Two rules for the whole loop

- **No self-trigger.** An investigation of an agent failure must not be able to trigger itself: dedupe key, rate cap, and an excluded label.
- **If the agent system is what is down, a person is told, not another agent.** Liveness is owned by code, not by a prompt.

## Open decisions

Names; which signals may auto-block (decided: `forbidden_tool` only, through `enforce.py`); which agents are on the never-block list; token baselines per agent; the ticket project and labels.

## What was built (see `guard/` and `evidence/GUARD-AND-LOOP-2026-11-24.md`)

`detect.py` (deterministic detector over A2A receipts, OTLP traces, access logs and `warden.jsonl`; missing data reads as `degraded`, never `clean`; hung runs are found through a
start inventory), `propose.py` (ticket plus a block-policy proposal; it writes files only; identity only from a trusted map; never-block list; hostile text quoted; dedupe; never applies), `alerts/guard-alerts.yaml`,
`enforce.py` (applies a proposal directly for definite offences, with caps, kill switch, ledger and a human `release`), `model_probe.py` (one-token model-route check), `alert_to_a2a.py` (Alertmanager payload to an agent-health request: human-only alerts never reach an agent, no self-trigger, capped, quoted), and the Guard and overseer agents with Warden contracts.

## Spend and retry guards (`guard/circuit.py`, `guard/loop-limits.yaml`)

A failing agent, a 429 storm or a bad alert must never become a loop that burns tokens. This is enforced in code before any agent is called:

| Guard | Behaviour |
|---|---|
| Attempt cap | At most 2 tries per alert per hour: the first, plus one retry |
| Permanent errors | 400, 404, 422: held for 24 hours and **never retried**. 401 and 403: held for 6 hours (a person fixes credentials and permissions within hours). A person is told either way |
| 429 (rate limit or quota) | **Pauses the whole loop** until the backoff (60 s, doubling, capped at 15 min, honouring `Retry-After`) passes, because a quota is shared. It counts as **waiting, never as broken**: it does not count towards the breaker and does not raise a failure |
| 5xx | One bounded retry after the same backoff; counts towards the breaker |
| Circuit breaker | 3 consecutive failures anywhere in the loop stop all calls for 30 minutes |
| Token budget | 150000 tokens per hour for the whole loop, **failed runs included** |
| Kill switch | Create `guard-loop.disabled` next to the state file, or set `GUARD_LOOP_DISABLED=1` |
| Corrupt state | Fails **closed**: no agent is called and the damaged file is left alone. A missing file is a fresh start |

Each withheld alert is reported as `withheld_<reason>_human_notified`, so a person hears about it instead of a retry happening. The overseer's real failed run (a model 400 after about 11,000
tokens) is replayed in the tests: the alert is parked and the retries stop. Wiring: `alert_to_a2a.py --breaker STATE` before a call, `--record RECEIPT --key FP` after it.

## Learnings from our software factory (reference only)

The software factory is a separate system with the same shape: code-owned liveness, an escalation ladder, run traces in Tempo shown in Grafana, and a nightly summary. It is not part of
this bundle. What was taken from its notes, and what was not:

| Factory lesson | Used here |
|---|---|
| **Quota is a wait, not a death.** A shared quota filled on 23 Nov and three sprints were wrongly reported as broken; the watchdog now keeps the run and retries, and quota never counts towards "broken" | Yes, built: a 429 pauses the whole loop and never opens the breaker (`guard/circuit.py`, 6 tests) |
| After 3 failures of the same task, stop that task and tell a human | Same rule: 3 consecutive failures open the breaker and a person is told |
| Liveness is owned by code, never by a prompt | Same: detection, budgets and the breaker are code; the model only explains |
| Silence is a defect: every piece of work ends as done, or as a specific question to a human | Same: a withheld alert is reported as `withheld_<reason>_human_notified`, never dropped quietly |
| Check every model and tool before assigning work; use a model only when healthy and under its quota | **Not built.** A preflight on the model route before the intake dispatches would have avoided the 400 and the 245000-token run. Recommended next step |
| Every autonomous decision is one ledger line: what, why, cost if wrong | Partly: `warden.jsonl` and `proposals.json` record outcomes; a single rulings ledger is not built |
| Reassign the work to another worker, then escalate | Not applicable: the overseer drafts an issue for a person; it does not reassign |

The factory has traces and Grafana but no Loki, Mimir or Alertmanager yet, so its alert path is the watchdog rather than LGTM. The two systems could share the Guard rules and the circuit breaker.

## What the factory's observability handoff adds (ideas only; its code is private)

The factory built this same loop, and its handoff note names three layers: **live alerts** (agent events go to Loki, a Grafana rule fires on any `api_error`, and a plain-code webhook handler
pauses the provider), an **agent pulse** (code-only, every two minutes: stuck, slow, looping or risky), and **token guards** (spent before anything is run). Ideas taken, and ideas not yet built:

| Idea | Status here |
|---|---|
| A plain-code handler, not an agent, reacts to the alert first: 429 pauses the provider for an hour, repeated 5xx for 15 minutes, 401 and 403 for 6 hours and a person is woken | Partly built: `guard/circuit.py` (429 pauses the loop, 401 and 403 held 6 hours, 5xx counts towards the breaker). The factory's 1 hour 429 pause is longer than ours (60 s doubling, capped at 15 minutes); tune ours from real quota behaviour |
| Tell **rate-limited** apart from **refused** at the source: errors that looked like permissions were often quota | Built for status codes; the classifier trusts the HTTP status and falls back to the error text, so a provider that hides a quota error inside a 403 will be mis-held |
| **A per-task token stop-loss**, not just an attempt cap (4M tokens a sprint including fix rounds) | **Not built.** Our budget is per hour for the whole loop. One overseer run used 245000 tokens inside a single call sequence; a per-run cap plus the new `maxToolCalls` gate is the fix. Recommended next |
| **The supervisor must not share a quota with what it supervises** | **A flaw in what we built:** the overseer and the agents it watches use the same model route in the lab. Give the overseer and the Guard their own route and credential, so a quota problem cannot take the watcher down with the watched. Added to the prerequisites |
| A nightly cold review of 24 hours of evidence for problems no alert raised | Not built. A good fit for the Guard: run the detector over a day of receipts and traces |
| A model or agent is "proven" only by a delivered run, not by being up | Matches Warden: a run counts only if the controller history shows it |
| A circuit breaker plus a quota-aware launch gate | Breaker built. The launch gate (do not dispatch if the model route is unhealthy or low on quota) is not |

## Decisions recorded on 24 Nov 2026

- The injectable watcher is a template or skill. It is meant to be re-pointed at another application, so no more is built for it here.
- The Sentinel sends to an HTTPS virtual-service endpoint that is already proven at work; cross-cluster delivery is not re-built here.
- The worker must send its payload to the eval agent and fix what it reports before the ticket. Built as Warden. On 0.7 the evaluator is a tool that returns, so the worker can correct and retry. On the 1.x lab it is a handoff that does
  **not** return, so "evaluator says PASS, then the first agent closes the ticket" needs a returning call (the controller's `invoke_session` tool is the candidate; not verified).
- The agent-health agent should also be able to verify that a downstream model route is down and ticket it: `guard/model_probe.py` does the check in code (one token, classified ok, rate limited, server error, auth, timeout, DNS or connect); its result is evidence for the ticket.
- Direct blocking for definite offences: built (`guard/enforce.py`), live-tested on the lab (apply, read back, release). The Deny blocking live traffic was proven on 25 Nov 2026 (200 → 403 → 200 on a throwaway JWT route; `docs/demo.md`).
- Rough edge: re-applying the same finding applies it again and (fixed after review: a repeat apply is now idempotent and uses no cap slot); it should be idempotent.
