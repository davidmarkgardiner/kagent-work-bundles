# Human prerequisites

Phase 1 (Warden) needs rows 1 to 4 and 8; Phase 2 (Assay) adds rows 5 to 7 and 12. Grafana, telemetry and alert rows (8 and later) are Phase 0 checks and gate Phases 2 and 3; see `docs/rollout.md`.

The work agent cannot create these. Complete the sheet before handing over
[WORK-AGENT-PROMPT.md](WORK-AGENT-PROMPT.md). Use placeholders in anything you commit.

| # | Item | Why | Owner |
|---|---|---|---|
| 1 | Target agent(s) to evaluate and the kagent version in use (0.7.x or 1.x) | The URL and request shape depend on it | Platform |
| 2 | Agentgateway route to the A2A endpoint with **caller authentication**, plus a test token scoped to the eval agents | Assay and Warden call agents only through the gateway | Platform / Security |
| 3 | Read-only Kubernetes tool server and its exact tool names (for example the `aks-mcp` read tools) | They go in the contract's `allowedTools`; anything else a worker calls fails the gate | Platform |
| 4 | An approved model route for the agents and the evaluator | The evaluator needs a model too | Platform |
| 5 | GitLab project, a **protected runner tagged `kagent-eval`**, and these protected, masked CI variables: `AGW_BASE_URL`, `AGW_TOKEN`, `EVAL_KUBECONFIG`, `EVAL_IMAGE` | `.gitlab-ci.yml` fails closed without them | Platform / DevEx |
| 6 | A service account for `EVAL_KUBECONFIG` that can only create and delete `eval-*` namespaces and apply the fixtures into them | Assay seeds a fault in a throwaway namespace | Platform / Security |
| 7 | Runner image built from `Dockerfile`, mirrored internally and pinned by digest; the `busybox` fixture image mirrored too | Air-gap: nothing is pulled from the public internet | Supply chain |
| 8 | For Warden: the receiver that writes the GitLab issue after a PASS, and read access to read the issue back | Warden's ticket check reads the issue the receiver wrote | Receiver owner |
| 9 | Decision: where a worker's **first-try evaluator FAIL** routes on 1.x (a handoff cannot retry). Options: labelled `evaluation-failed` ticket, or reject and alert | The code currently rejects | Product owner |
| 10 | Decision: who owns an agent that fails Assay or Warden, and the escalation route | A gate that nobody reads is not a gate | Product owner |
| 11 | **A separate model route and credential for the overseer and the Guard**, not the one the watched agents use | A quota or outage on the shared route would take down the watcher together with the watched (a lesson from our software factory) | Platform |
| 12 | A human to review the first full run of each case against the real agent's answer | Scoring is key-term based; a person calibrates it | Agent owner |
| 13 | RBAC (`get`, `list` and `create` on `agentgatewaypolicies` in the policy namespace; server dry-run needs `create`, which can also create for real, so use a dedicated identity, never `enforce.py`'s, and always pass the dry-run flag) for the identity that runs `propose.py --dry-run-server` | Phase 3 proves the policy is accepted without applying it | Platform / Security |
| 14 | A **start inventory** source for agent runs (gateway or controller list of started tasks: id, agent, started, caller) | Without it the detector cannot see a run that never finishes and reports `degraded`, never `clean` | Platform |
| 15 | Grafana: data source UIDs, a place to run `guard/alert_receiver.py` (Service reachable only from Grafana), a Secret for `ALERT_RECEIVER_TOKEN`, a human paging contact point that does not use the agent system | Phase 4 alert path; see `docs/grafana-alerting.md` | Platform / Observability |
| 16 | Written owner approval of which signals may auto-block (default: only `forbidden_tool` from a receipt or run) and the never-block list | Phase 5 enforcement | Product owner |
| 17 | A narrow identity for `enforce.py` (create, get, list, delete `agentgatewaypolicies` with the guard label, in one namespace) and findings, identity map and rules files writable only by that identity | The trust anchor for what it applies is operational | Platform / Security |
| 18 | A JWT-authenticated test caller and a throwaway route | Phase 5 must prove a Deny really blocks traffic at work (proven in the lab on 25 Nov 2026: 200 → 403 → 200) | Platform |
| 19 | The approved fallback ModelConfig per agent (`guard/fallbacks.yaml`) and who may run `remediate.py` (patch on the listed Agents only) | The overseer's fix-it step switches only between ModelConfigs a person approved | Agent owner / Platform |

## Do not do

- Do not point the evaluation at an agent with write tools (`k8s_apply_manifest`, delete, patch, exec).
- Do not store receipts in git or keep CI artifacts beyond the retention in `.gitlab-ci.yml`.
- Do not widen `allowedTools` to make a run pass. Fix the agent or the case.
