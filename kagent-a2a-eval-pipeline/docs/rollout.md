# Rollout order

The work agent adds this bundle **one phase at a time**, easiest first, and stops at each gate until a human says go. Warden (the in-place A2A eval) and Assay (the pipeline eval) are separate tasks. The table is the same one that opens `WORK-AGENT-PROMPT.md`.

| Phase | Scope | Needs | Gate: stop and report |
|---|---|---|---|
| **0. Readiness (no changes)** | Confirm the pinned versions; that **Grafana is reachable and its Loki, Tempo and Mimir/Prometheus datasources are healthy**; that **the applications are configured to send traces, logs and events** (find a recent trace and log for each); that Alertmanager exists and can call a webhook; that the model routes answer | Read access only | A readiness table. Anything red is reported, **not built**. Do not install or repair Grafana |
| **1. Warden: the in-place A2A eval** | Steps 1 to 3 (common), then 4, 5, 6, 10, 11 and 12 | Rows 1 to 4 and 8 of `HUMAN-PREREQUISITES.md` (gateway auth, tools, model routes, the receiver). **No CI, no monitoring** | The worker sends its payload to the evaluator and is corrected; the ticket step only after PASS; the negative tests pass, with receipts |
| **2. Assay: the pipeline eval** | Steps 7, 8 and 9 | Phase 1 done; rows 5 to 7 and 12 of `HUMAN-PREREQUISITES.md` (GitLab project, runner, variables, mirrored images, human review) | Smoke, then pass^3 per case through the gateway, with the CI runs; an unprotected-branch MR fails closed |
| **3. Guard: detection and proposals only** | Step 13, **detector and proposals, no enforcement** | Phase 0 green for telemetry; Phases 1 and 2 done | `detect.py` clean on good runs, `forbidden_tool` on a bad one, `degraded` on a gap; a proposal accepted by server dry-run, nothing applied |
| **4. LGTM integration** | Steps 14 and 15: spend guards, model probe, alert intake, the agent-health agent | Phase 0 fully green; Phase 3 done; a separate model route for the overseer | One bounded overseer run (tool budget on, stop at the first failure), then one real alert end to end |
| **5. Direct blocking** | The `enforce.py` part of step 13 (it needs `--findings`, `--identity-map` and `--ledger`) | Written owner approval of which signals may auto-block; a narrow identity for `enforce.py` | Applied, read back and released on a **throwaway route**, with a real request proving the Deny blocks |


Why this order: Warden needs no CI or monitoring, so it can be proven alone; Assay adds the pipeline; the Guard and the alert loop need Grafana and telemetry confirmed healthy first; direct blocking is a real power over the cluster, so it comes last and needs written owner approval.
