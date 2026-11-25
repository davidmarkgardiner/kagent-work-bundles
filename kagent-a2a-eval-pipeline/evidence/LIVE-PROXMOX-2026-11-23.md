# Proxmox live evaluation — 23 November 2026

Initial status before the later continuation: **blocked before live evaluation**. The Proxmox host is reachable, but the Kubernetes control-plane and both worker VMs were stopped. No live smoke or full evaluation was run; no live verdict, latency, trajectory, model, agent, Gateway name or kagent version was observed. No Kubernetes resources were created or changed.

## Checks

- `kubectl --context proxmox-k8s --request-timeout=8s get --raw=/readyz`: timed out awaiting headers.
- TCP to the configured Kubernetes API on port 6443: timed out; TCP to that address on 8006 returned host down. TCP to the previously noted Geekom address on 8006 timed out.
- The Mac's Ethernet and Wi-Fi interfaces were active on the same /22 network. Pings to the configured control-plane address from each interface failed; Ethernet reported host down. The router responded to ping.
- Tailscale was connected; its Kubernetes-labelled peer was offline, last seen 61 days earlier. This does not prove it is the target cluster.
- The configured Proxmox SSH alias pointed to a different host from the previously checked Geekom address. That Proxmox host responded to ping, TCP ports 22 and 8006, and authenticated read-only SSH.
- `qm list` on that host showed VM 200 (`k8s-cp1`), VM 101 (`k8s-worker1`) and VM 102 (`k8s-worker2`) **stopped**. No VM power state was changed.
- The main kubeconfig contained the requested context; three local backup kubeconfigs did not contain that context. No other context was contacted.
- The handover is ignored by Git. Bundle offline unit tests: **16 passed**; these are not live proof.

## Initial gate (resolved)

At that point, authorization to power on VMs 200, 101 and 102 was needed before attempting the requested live test. After startup, verify API and workload readiness, then follow the handover's read-only inventory, server-side dry-run, gateway smoke and full pass^3 procedure. A failed live case must be reported as failed, and raw receipts must remain ignored.

## Continuation after VM startup

David authorized startup. VMs 200, 101 and 102 were started and reported running; the Kubernetes API `/readyz` returned `ok`, and all three nodes reported Ready. On initial startup the controller and gateway pods were unavailable while pod networking recovered. A direct A2A attempt failed because the controller pod was unavailable; another, after the controller started but before the agent was ready, returned HTTP 500 and connection refused to the agent. These are startup failures, not evaluation verdicts. The gateway, controller, tool server and agent subsequently became ready.

- kagent controller and agent images: `0.7.13`. Gateway: `agent-gw` (data plane image `0.11.1`).
- Agent: `sre-triage-agent`; its declared Kubernetes tools include get resources and pod logs, with no declared apply, create, delete, patch or execute tools. ModelConfig: `litellm-qwen-14b`, model `qwen3-14b`.
- Existing cross-namespace ReferenceGrant was present. The `a2a-eval-route` and `a2a-eval-policy` passed server-side dry-run, were created, and reported accepted and resolved/attached. A request through the real gateway node port returned a JSON-RPC invalid-request response, demonstrating the route reached the controller. This is not authentication proof; the supplied policy contains rate limiting and timeout, not caller authentication.
- Namespace and both fixtures passed server-side dry-run before creation. Healthy distractor became available; the fault pod reached CrashLoopBackOff and its logs reported `REQUIRED_SETTING` missing.
- Direct A2A after startup reached the agent but returned text reporting HTTP 502, Ollama upstream connection refused. The helper printed `ok: true` because it found error text; this was **not** a successful agent answer.
- The gateway smoke case `smoke-list-fixture-pods`: **error**, no score, 1,706 ms, `API_ERROR`.
- The gateway full case `triage-crashloop-bad-env`, pass^3: **error**, no scores; repeats 1–3 took 1,529 ms, 1,598 ms and 1,327 ms, each `API_ERROR`. Gate exit code 3. No quality pass or failure can be inferred from these infrastructure/model errors.
- All four raw responses reported failed task status and `kagent_error_code: API_ERROR`; they contained no function-call parts. Trajectory completeness cannot be verified without a successful run with tool calls.
- The configured model route targets the Qwen clean proxy; the proxy was running, but the Ollama service had no endpoints. A previous Qwen model pod was Failed/Unknown; the KubeAI Model reported one replica and zero ready, with an RTX 3060 resource profile. No model, workload, or configuration repair was attempted.
- Smoke and full `summary.md` and `junit.xml` were produced locally under ignored `out/`; raw receipts are ignored. Offline tests passed 16/16 before the live run; no code was changed.
- The eval namespace was deleted after the test and its absence was verified. The route and policy are intentionally retained in `agentgateway-system` for David to decide whether to keep.

The successful live quality and trajectory test remains blocked until the configured model backend is available and the evaluation is repeated. Route admission and JSON-RPC reachability alone do not establish agent or model health.

## Kimi model-route check

A subsequent standalone request to the existing `kimi-for-coding` model route through agentgateway returned HTTP 200 with the requested `OK` response. This is model-route proof only; no Kimi-backed agent evaluation or tool trajectory was tested. The read-only agent used for the reported evaluations still had the Qwen ModelConfig; no Agent or ModelConfig was changed.

## Scored run on a Kimi-backed eval agent

David authorised creating a new, separate read-only agent rather than changing `sre-triage-agent` or repairing Qwen.

- **Agent created:** `kagent/eval-sre-triage-kimi`. It is a copy of `sre-triage-agent`'s spec (same system message, same 10 read-only tools: get resources, describe, events, pod logs, resource YAML, API resources, cluster config, service connectivity, helm list, helm get) with only `modelConfig` changed to the existing `agentgateway-kimi` (`kimi-for-coding`). It is labelled `eval.kagent.dev/temporary=true`. It was server-dry-run before creation. No existing Agent or ModelConfig was changed.
- **Capacity:** both workers were full on requests (one at 100% CPU, the other at 99% memory). The agent's requests were lowered to `cpu: 1m, memory: 256Mi`, with limits unchanged. In the eval namespace only, the two fixture Deployments' CPU requests were patched to `0` (limits unchanged) so they could schedule. Repo fixture files are unchanged.
- **Control plane:** `kube-controller-manager` and `kube-scheduler` were in CrashLoopBackOff (170+ restarts) because they lost leader-election lease renewals to a slow API server. The control-plane VM was using about 7.3 of its 8 GiB. Rollouts progressed only in the short windows when they were up. This was observed only; nothing was repaired.
- **Route:** a rule for `eval-sre-triage-kimi` was added to `a2a-eval-route` after a server dry-run. A `{}` POST through the gateway node port returned a JSON-RPC invalid-request error from the controller. A no-tool probe completed in about 2.9 s with the answer `OK`.

### Code fix found live

The first smoke attempt failed in 419 ms with task state `failed`. The agent log showed `403 Forbidden` on `POST /api/sessions/ctx-local-smoke-list-fixture-pods-r1/events`. The capture used a deterministic `contextId`. The earlier Qwen run had already created that session for `sre-triage-agent`, and kagent rejects a second agent writing to it. A CI job retry would hit the same problem, or inherit earlier history. Fix: `run_id` (and so `contextId`) now includes the agent and a random suffix. A regression test was added; the offline suite is 17/17.

The second smoke attempt timed out at 240 s and was recorded as `infra_error`, not retried. The agent log showed the runner closing about 50 ms after the session was created, with no MCP connection or model call, and no reply sent. A retry a few minutes later succeeded. This looks transient and was not reproduced.

### Results, through the gateway

| Case | Tier | Verdict | Scores | Latency | Tools called (captured / raw) | Tokens in/out |
|---|---|---|---|---|---|---|
| smoke-list-fixture-pods | smoke, pass^1 | **pass** | 1.0 | 6.2 s | `k8s_get_resources` | n/a |
| triage-crashloop-bad-env | full, pass^3 | **pass** | 1.0, 1.0, 1.0 | 14.2 s / 95.0 s / 51.4 s | get_resources, get_events, get_pod_logs, describe_resource — 4/4 each repeat | 13249/449, 13267/393, 13679/347 |

- Gate exit codes: smoke 0, full 0. `summary.md` and `junit.xml` were produced under ignored `out/live-kimi-smoke3/` and `out/live-kimi-full/`.
- **Trajectory claim verified:** on kagent 0.7.13, every `function_call` data part in the raw A2A history (4 per repeat, each with a matching `function_response`) was captured by `normalize()`. No tool errors.
- **Answer quality (repeat 1, read manually):** it named the missing `REQUIRED_SETTING` as the confirmed root cause, cited exit code 1, the FATAL log line and `Environment: <none>`, ruled out image pull, OOM and node pressure, and did not blame the healthy decoy.
- All 7 scorer dimensions were scored at 1.0. The forbidden-tool check relies on A2A history only (warning recorded).
- The model label recorded as a placeholder because `EVAL_MODEL_LABEL` was unset. The model was `kimi-for-coding`, taken from the ModelConfig.
- The advisory judge was not run (no judge endpoint configured).

### Left in place, for David to decide

- `kagent/eval-sre-triage-kimi` (temporary eval agent).
- `agentgateway-system/a2a-eval-route` (rules for `sre-triage-agent` and `eval-sre-triage-kimi`) and `a2a-eval-policy`. **There is no caller authentication.** It is reachable on the gateway node port from the LAN.
- The eval namespace was deleted and its absence verified.

## Stage 2: live A2A completion gate (Sentinel)

The user authorised two temporary, read-only agents on the Kimi ModelConfig. `completion-evaluator-agent` was rendered from the contracts and has no tools. `sentinel-investigator-agent` has the six read-only Kubernetes tools, plus the evaluator as a native `type: Agent` tool. Both passed server dry-run. Their CPU requests were set to `0` (memory 256Mi, limits unchanged) because worker CPU requests were exactly full. A route rule for the investigator was added to `a2a-eval-route`. The fault namespace was seeded as in stage 1.

- **Attempt 1:** gateway `504` at the 300 s policy timeout. The worker log showed `Failed to resolve AgentCard from URL http://completion-evaluator-agent.kagent:8080/.well-known/agent-card.json: ... All connection attempts failed`, twice. The evaluator's Service endpoint was flapping while kube-controller-manager crash-looped. The same URL returned `200` from inside the worker pod a few minutes later.
- **Attempt 2: completed through the gateway in 155 s.** The worker made 5 successful read-only calls (`k8s_get_resources` ×2, `k8s_describe_resource`, `k8s_get_pod_logs`, `k8s_get_events`), then one `kagent__NS__completion_evaluator_agent` call. The report identified the missing `REQUIRED_SETTING` and the incident key `gitlab-whisky/proxmox-lab/<ns>/Deployment/eval-crashloop/rollout_unavailable`. The evaluator returned PASS for `sentinel-investigation@1`, with all four checks true.
- **Agent-tool response shape, now observed:** the call's `args` is `{"request": "<text>"}`. The response is `{"result": "<verdict JSON as a string>"}`. The verifier parsed it unchanged.
- **Finding:** after the PASS, the worker reworded one sentence of `Owner and next steps` in its final answer, dropping an optional suggestion, despite being told to return the block unchanged. The first verifier version correctly returned FAIL / `reject` ("final output was not the text sent to the evaluator"). That would have dropped a valid investigation.
  - **Fix:** contracts now default to `output.deliver: approved`. The verifier returns `approved_output`, the exact envelope the evaluator judged, taken from controller history. The receiver delivers that, and the contract is checked against it. A reworded final copy is a warning. `deliver: final` keeps the strict behaviour.
  - Re-verified: **PASS, route `ticket`**, 1 evaluator attempt, 1 warning, with the Agent CRD check passing. The sanitized receipt is now a regression fixture (`tests/fixtures/a2a-live-agent-tool-completed.json`). Offline suite: 57/57.
- **Attempts 3 and 4 (repeatability):** no response within 290 s, with no model or tool calls logged. A trivial no-tool probe to the previously healthy Kimi agent also hung for 100 s; it had answered in 2.9 s an hour earlier. kagent-controller was logging `failed to fetch tools for toolServer` for every RemoteMCPServer, plus A2A forwarding errors. Proxmox host load was 9.0. This is cluster degradation, not a gate result, so live pass^3 for stage 2 was **not** achieved. Infrastructure was not repaired (out of scope).
- **Not live-tested:** the evaluator FAIL → correct → retry loop (the evaluator passed first time), the GitLab receiver write and `--readback` (no receiver on this cluster), and the `evaluation_failed_ticket` route.
- **Cleanup:** both temporary agents were deleted and the route was restored to its two earlier rules. The eval namespace and the two leftover Deployments were still pending garbage collection while kube-controller-manager was in CrashLoopBackOff. Re-check them.

## Stage 2 on kagent 1.x (alpha17 lab, VM 201): later the same day

The 0.7.13 cluster kept failing, so the gate was re-run on the earlier kagent 1.0.0-alpha17 + Substrate 0.6.0-alpha3 kind lab (inside Proxmox VM 201, Kimi model, A2A 1.0). Recovery took several fixes: a CoreDNS forwarding loop, a stopped local image registry that blocked actor restore, a stale worker registration, and Kyverno needing a restart. Then: kagent-tools 0.3.0 installed read-only (get/list/watch, no Secrets, k8s provider only), a `completion-evaluator` AgentTemplate, and a `sentinel-investigator` Agent with the evaluator as a `subAgent`.

**1.x differences, now handled in `verify_completion.py` and covered by 9 new tests and a sanitized live fixture (`tests/fixtures/a2a-v1x-subagent-completed.json`):**
- Method `SendMessage`, header `A2A-Version: 1.0`, role `ROLE_USER`, parts `{"text": ...}` with no `kind`. A caller-supplied `contextId` is rejected (it maps to a Substrate session), so omit it. The path is `/agents/<ns>/<name>`.
- Tool events are task `artifacts` (tagged `kagent.dev/a2a/part-type`), not `history`.
- The evaluator is a `subAgent` reached by an ADK `transfer_to_agent` handoff. **Control does not return**, so there is no FAIL → fix → retry loop on 1.x; the evaluator's JSON verdict is the final text of the turn.

**Three live runs, each verified by `verify_completion.py` with the deployed Agent checked against the contract:**
| Run | Gate | Detail |
|---|---|---|
| 1 | PASS, route `ticket` | 4 read-only tool kinds succeeded, evaluator PASS for the right contract, all sections present |
| 2 | FAIL, route `reject` | The evaluator returned FAIL: the worker omitted the `contract:` line in its handoff. The gate correctly refused. The tool calls and report were otherwise fine |
| 3 | PASS, route `ticket` | Same as run 1 |

So the gate caught a real defect in 1 of 3 runs, and 2 of 3 pass. **Pass^3 was not achieved.** Because a handoff can't retry, a first-attempt evaluator FAIL is final on 1.x; the route for that case (currently `reject`) still needs a decision. The likely fix for run 2 is a stronger worker prompt, or having the evaluator infer the contract from the worker's name.

Not done: the GitLab receiver write and read-back, and the Agent-tool alias on the 0.7.x gate was not rerun. Raw receipts stay in the gitignored `out/live-stage2-v1x/`.

Left running on VM 201 for the demo: namespace `eval-live-1795470811`, agents `sentinel-investigator` and `sentinel-investigator-v2`, template `completion-evaluator`, kagent-tools, and the three kind clusters I stopped (`incident-substrate`, `flux-d2-fleet`, `codex-harness`) remain stopped.
