# Live demo: lights, healthy, rogue, broken

One script, `demo/run-demo.sh`, shows every product working on a real cluster in about seven minutes. Each scene uses real agents, real model calls and a real gateway. Nothing is replayed.

| Scene | What you see | Products |
|---|---|---|
| `lights` | Every demo agent, its model route (probed with one token), the gateway route as the caller, and active Guard blocks | Guard probe, gateway |
| `healthy` | A read-only agent does its job; the Guard reads the real run and finds nothing | Guard detector |
| `rogue` | An injected instruction makes an agent call `k8s_delete_resource`; the Guard flags `forbidden_tool` from the real run, proposes a block (server dry-run), applies it, and the gateway goes from **200** to **403** for that caller on that route; a ticket is written | Guard detect, propose, enforce |
| `release` | A person lifts the block; the gateway goes back to **200** | Guard release |
| `broken` | An agent whose model answers 429 fails; both routes are probed; `remediate.py` switches it to an approved fallback and reads it back; the same question now completes; a ticket says what changed | Overseer fix-it step |
| `reset` | Puts the broken agent back on its failing model and clears blocks, so the demo can run again | |

Run all of it with `demo/run-demo.sh all`, or one scene at a time.

## Verified on the home lab (25 November 2026)

A full `all` run passed in 6 min 30 s on kagent 1.0.0-alpha17 with agentgateway:

- lights: three agents Ready; the stub route `rate_limited 429`, the fallback `ok 200`; gateway route 200; no blocks.
- healthy: `TASK_STATE_COMPLETED`, one allowed tool call; detector `clean`.
- rogue: the agent called `k8s_delete_resource` (refused by the read-only RBAC as well); detector `forbidden_tool` (source: receipt); proposal accepted by server dry-run; block applied; gateway **200 → 403**; the same caller on another route stayed 200.
- release: gateway back to 200.
- broken: `TASK_STATE_FAILED` with `429 Too Many Requests`; probes `rate_limited` and `ok`; switched and read back; the same question `TASK_STATE_COMPLETED`; ticket written.

The two live receipts are fixtures: `tests/fixtures/a2a-v1x-demo-healthy-live.json` and `a2a-v1x-demo-rogue-delete-live.json`.

## Set it up

1. Deploy the demo objects (fill the `{{...}}` values first):
   - `demo/lab/broken-agent.yaml`: a 429 stub, its ModelConfig and the `demo-worker` agent. Needs a python image your cluster can pull.
   - `demo/lab/demo-agents.yaml`: `demo-healthy` and `demo-rogue`. Point `{{READONLY_MCP_SERVER}}` at a tool server whose Kubernetes RBAC is get/list/watch only, so the rogue's delete cannot succeed.
   - `demo/lab/guard-demo-route.yaml`: a throwaway gateway route behind JWT authentication. Copy `jwtAuthentication` from a working policy on the same gateway. Policies on a listener and on a route stack: both must allow.
2. Pick an approved fallback ModelConfig that works (the demo agents can use it too). A model with tight rate limits will fail the healthy and rogue scenes; the lab used a local model for that reason.
3. Copy `demo/demo.env.example` to `demo/demo.env` and fill it. Every value is explicit; the script never uses the current kubectl context.
4. `demo/run-demo.sh forward` (lab port-forwards), then `demo/run-demo.sh all`.

## What it does not show

- **Grafana in the loop.** The broken scene starts from the failure itself. The alert path (Grafana's built-in Alertmanager → receiver → request, with spend guards) is proven separately: see the Grafana alerting page.
- **The overseer agent writing its own report.** The fix-it step and its ticket are plain code acting on checked facts. A full overseer agent run, gated by its Warden contract, has not passed live.
- The ticket is a file. Writing it to GitLab and reading it back belongs to the receiver at work.

## Why the fix-it step is code

The overseer agent may recommend a fallback. `guard/remediate.py` decides and applies it, and only when it can check the facts itself: the agent and both ModelConfigs are on an allowlist (`fallbacks.yaml`); a probe of the current route shows a failure that a fallback can fix (429, 5xx, timeout, connection), while 401/403, 400/404 and DNS go to a person; a probe of the fallback shows `ok`, and each probe must test the model its ModelConfig names. It is capped (one switch per agent per hour, two in total per hour, counted from the ledger and from the agents' own annotations), has a kill switch and a never-touch list, runs a server dry-run first, and reverts if the agent is not Ready on the fallback. `revert` puts the primary back once a person has fixed it. 15 offline tests; five safeguards were broken on purpose and each was caught.
