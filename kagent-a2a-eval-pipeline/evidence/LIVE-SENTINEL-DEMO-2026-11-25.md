# Live: the demo's Sentinel scene, 25 Nov 2026

**Where:** the home lab (kind cluster on a Proxmox VM), kagent 1.0.0-alpha17, namespace `kagent`. Not run at work, and not on kagent 0.9.

**What ran:** `demo/run-demo.sh sentinel`, three times in a row, with no changes between runs 2 and 3.

- **Workload:** a small "whisky" app in `guard-demo` that exits at startup because `WHISKY_DB_URL` is not set.
- **Detection:** `demo/sentinel_check.py`, plain code reading the pod list.
- **Investigator:** `demo-sentinel`. This is the bundle's v1alpha3 Sentinel worker (`completion-gate/manifests/sentinel-investigator-agent-v1alpha3.yaml`) renamed, on ModelConfig `glm-coding` (GLM 4.6), with read-only tools from `kagent-tools-readonly`.
- **Evaluator:** an AgentTemplate generated from `completion-gate/contracts/sentinel-investigator.yaml` by `render_evaluator.py`, on the same model. It is reached as a sub-agent by hand-off.
- **Check:** `verify_completion.py` against the same contract, with the deployed Agent object passed as `--agent-crd`.

## Results

| Run | Finding (code) | Agent tool calls | Warden | Report names `WHISKY_DB_URL` | Scene time |
|---|---|---|---|---|---|
| 1 | `demo/<cluster>/guard-demo/Deployment/whisky-app/restarting` | 6 read-only calls, then `transfer_to_agent` | PASS, route `ticket`, 1 evaluator attempt | yes | 87 s |
| 2 | same key | 5 read-only calls, then `transfer_to_agent` | PASS, route `ticket` | yes | 89 s |
| 3 | same key | 9 read-only calls, then `transfer_to_agent` | PASS, route `ticket` | yes | 95 s |

**3 of 3 passed** on 25 Nov.

**Run 4, 26 Nov 2026:** part of a full `demo/run-demo.sh all` rehearsal, after VM 201 was moved to 16 GB and restarted.
- **Detection and investigation:** the code found the app, and the agent made 5 read-only calls, all successful, then handed off. It used about 337,000 tokens.
- **Warden:** FAIL, route `reject`, so no ticket was written. The reason: "worker text before the handoff must contain exactly one <result> envelope, found 0". The agent handed off without first writing its report in its own reply. That is the failure the worker's numbered prompt exists to prevent, and the gate caught it.
- **Running total: 3 of 4.** The rest of that rehearsal passed: 8 of 9 checks.

- Every run used only allowlisted read-only tools (get, describe, events, logs, yaml) and stayed under the 14-call budget. Runs 1 to 3 had their report approved by the evaluator for `sentinel-investigation@1`.
- In runs 1 to 3 the ticket file was written from the exact `approved_output` the evaluator judged.
- After each run the scene deleted the app (`deployment "whisky-app" deleted`). The agent and evaluator stay for the next run.

## Changed during the session
- **Run 1:** the app's error text was part of its startup command, so the agent could read the cause from the Deployment YAML without looking at the logs.
- **Before runs 2 and 3:** the app was changed to read `WHISKY_DB_URL` at startup and exit when it is missing, which is a real configuration fault. Both later runs still found the cause through the logs and events.

## Limits
- **Model sensitivity.** The original lab `sentinel-investigator` agent uses a Kimi route that is out of quota, which is why the demo has its own copy on GLM. In an earlier session (`LIVE-PROXMOX-2026-11-23.md`), the same worker on another model passed 2 of 3 runs, and Warden caught the failure. The demo treats a FAIL as the gate working, never as something to retry in a loop.
- **No retry after FAIL.** On kagent 1.x the evaluator is a hand-off, so a first FAIL is final.
- **Detection and the ticket are simplified.** Detection runs once, whereas the real Sentinel is a scheduled job in its own bundle (`cluster-health-baseline-sentinel`). The ticket is a file in `$RUN`, not a GitLab issue, and no receiver read-back was run.
- **Finding type.** The finding type was `restarting` in all three runs: when the code polled, the pod was between crashes rather than in `CrashLoopBackOff`. Both are crash states; the key is stable across runs.
