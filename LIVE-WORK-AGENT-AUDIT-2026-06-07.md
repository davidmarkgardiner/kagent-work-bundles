# Live Work-Agent Audit - 2026-06-07

Scope: `work-agent-bundles/` plus live read-only checks against the current home
lab cluster context. This audit simulates the work-agent handover path and
records what is genuinely live versus what remains blocked or needs governance
tightening.

No destructive chaos, remediation, write-capable GitLab action, dashboard write,
or memory mutation was run during this pass.

## Summary

```text
HANDOVER_PACK_REVIEWED: yes
STATIC_BUNDLE_VERIFY: passed
KAGENT_AGENTS_READY: yes_or_blocked
GRAFANA_QUERY_PATH_READY: yes
LOKI_QUERY_PATH_READY: yes
A2A_DIRECT_SMOKE_COMPLETED: yes
MODEL_BACKEND_READY: yes
AGENTGATEWAY_QWEN_ROUTE_READY: yes
GITLAB_OFFICIAL_MCP_ACCEPTED: no
GITLAB_LITE_MCP_ACCEPTED: yes
MEMORY_MCP_ACCEPTED: yes
CHAOS_SAFE_TARGET_PRESENT: yes
POLICY_GAPS_FOUND: fixed_for_front_door_triage
OUTPUT_SANITIZED: yes
```

## Follow-Up Fix Pass

After this audit, the runtime blockers were rechecked and fixed where the
cluster state allowed it:

- Deleted stale failed KubeAI model pod `model-qwen3-14b-*` after a node/GPU
  disruption. KubeAI recreated the pod, allocated the GPU, pulled/warmed
  `qwen3:14b-q4_K_M`, and reported `ready:1`.
- Proved Agent Gateway route `agent-gw:8081/qwen/v1/chat/completions` returned
  HTTP 200 with the expected marker.
- Proved direct A2A `message/send` against `smart-triage-incident-commander`
  returned HTTP 200 and completed a task.
- Removed `k8s_execute_command` from live `sre-triage-agent`, keeping it
  read-only as documented.
- Re-ran the front-door/specialist governance audit and found no dangerous
  tools on the checked triage agents.
- Checked the approved secret manager and found a valid GitLab API token at
  `{{SECRET_MANAGER_PROJECT}}/{{GITLAB_TOKEN_SECRET_NAME}}`. Refreshed the
  home-lab Kubernetes GitLab secrets from that value without printing it.
- Proved the GitLab-lite MCP pod can call GitLab `/api/v4/user` with HTTP 200,
  and its MCP `tools/list` exposes `gitlab_create_mr_demo`.
- Confirmed the official hosted GitLab MCP remains blocked after token refresh:
  `smart-triage-gitlab-mcp` is still `Accepted=False`. The error moved away
  from invalid local token material and now points at the hosted MCP
  endpoint/session/auth model. Treat the lite/API wrapper as the proven demo
  path unless the work environment has an approved GitLab MCP OAuth path.
- Fixed the Qwen3 stakeholder-output issue by adding an OpenAI-compatible
  no-think proxy in front of the native KubeAI/Ollama API. Agent Gateway and A2A
  smoke tests now return the expected markers with no `<think>` wrapper.

## Live Evidence Collected

| Area | Result | Notes |
|---|---|---|
| Kubernetes context | available | Current context was reachable and listed kagent, Argo, Litmus, Agent Gateway, monitoring, AKS-MCP, and chaos-demo namespaces. |
| kagent agents | mostly ready | 32 kagent agent info series and 31 ready series were visible in Prometheus. One team demo agent was not accepted. |
| Grafana MCP | accepted | RemoteMCPServer was accepted and exposed required read tools including `list_datasources`, `query_prometheus`, and `query_loki_logs`. |
| Prometheus direct query | ready | `count(up)` returned live data; kagent agent/eval metrics were also present. |
| Loki direct query | ready | Recent kagent namespace log series were queryable. |
| Memory MCP | accepted | Memory server exposed read/search tools plus write/delete tools; bundle governance still needs curator-only enforcement. |
| GitLab lite MCP | accepted after token refresh | Demo fallback exposed `gitlab_create_mr_demo`; pod token verified against GitLab API with HTTP 200. |
| Official GitLab MCP | blocked | RemoteMCPServer remained `Accepted=False` after valid API token refresh; use lite/API wrapper unless approved OAuth/hosted MCP path is available. |
| A2A endpoint | ready after fix | Agent-card and health endpoints worked; after model repair, direct `message/send` returned HTTP 200 and completed. |
| Model backend | ready after fix | Stale failed KubeAI model pod was deleted; replacement pod reached `1/1 Running` and KubeAI status reported `ready:1`. |
| Agent Gateway Qwen route | ready after fix | `/qwen/v1/chat/completions` returned HTTP 200 through `agent-gw`; clean proxy suppressed `<think>` wrappers. |
| Chaos target | ready for controlled lower-env use | `chaos-demo/chaos-target` exists, is labelled opt-in, and has two ready replicas. |
| Chaos lifecycle | mixed historical state | Recent lifecycle workflows include successful runs and one earlier failure due to a missing runtime volume. |

## Findings

### P0 - Runtime Preflight Was Missing As A Bundle

The work-agent bundle set previously had runtime/model/Agent Gateway readiness
as a future idea, but live proof showed it is a hard precondition. A2A can time
out even when agents are Ready and ModelConfigs are Accepted.

Fix applied: added `runtime-model-gateway-readiness/` and moved it to second in
the recommended work order, immediately after the human handover pack.

### P0 - ModelConfig Acceptance Is Not Live Model Proof

The selected model configs were accepted by kagent, but the backend model pod
was initially not Ready. Direct A2A smoke reached the agent service and created
kagent session/task records, then timed out without a response.

Fix applied in home lab: deleted the stale failed model pod after the GPU/device
plugin recovered. Replacement pod reached Ready and both Agent Gateway and A2A
smoke tests returned HTTP 200.

Required work-side action: run runtime preflight before every SRE/game-day demo
and block downstream proof if model backend or A2A smoke fails.

### P0 - Official GitLab MCP Auth Is Blocked

The official GitLab RemoteMCPServer exists but is not accepted. Controller logs
show Unauthorized during MCP initialization. The GitLab-lite MCP is accepted,
but it is a sandbox/demo fallback with a narrower tool set.

Validated update: GCloud Secret Manager contains a valid GitLab API token, and
the home-lab Kubernetes GitLab secrets were refreshed from it. The GitLab-lite
MCP/API wrapper can call GitLab successfully and exposes the expected demo tool.

Remaining blocker: the official hosted GitLab MCP remains `Accepted=False` after
valid token refresh. Required work-side action: either use the proven lite/API
wrapper for branch/file/MR demos, or implement the approved GitLab hosted MCP
auth/session flow for the work environment and re-run RemoteMCPServer
acceptance.

### P1 - Read-Only Names Do Not Guarantee Read-Only Tools

Live tool inventory showed that some agents or MCP servers labelled read-only
still expose tools such as exec or broad write/admin commands. The governance
bundle must audit actual discovered tools and agent ToolGrant/tool lists, not
trust resource names or descriptions.

Fix applied in home lab: removed `k8s_execute_command` from live
`sre-triage-agent`. Required work-side action: policy/governance audit should
fail any front-door or general triage agent with delete, exec, apply, patch,
create, label, annotation, or broad GitLab write tools unless explicitly
classed as a HITL-gated remediation specialist.

### P1 - A2A Bundle Needs Runtime Dependency Awareness

The A2A workflow contract is structurally valid, but direct smoke proved it can
be blocked by model/backend readiness. The A2A bundle should direct the work
agent to run runtime preflight first.

### P1 - Chaos/Eval Proof Should Report Historical Failures

The chaos lifecycle had successful runs, but also a previous failed run caused
by a missing runtime volume. The lifecycle/eval evidence should include recent
failed workflows and not only the latest successful run.

## Bundle-By-Bundle Result

| Bundle | Audit result | Action |
|---|---|---|
| `team-handover-pack/` | Ready | Use for tickets, Teams messages, and meeting presentation. |
| `runtime-model-gateway-readiness/` | Added by this audit | Run before all live demos; home-lab model/A2A/Agent Gateway path now passes after fix. |
| `sre-grafana-mcp-observability/` | Mostly ready | Grafana read/query path works; live demo still depends on runtime preflight. |
| `sre-adoption-feedback-loop/` | Ready with dependency | Start once runtime preflight has a go/no-go decision. |
| `kagent-triage-v2-kb-gitlab-mcp/` | Needs live querydoc/GitLab proof | GitLab-lite/API wrapper is proven; official hosted MCP still needs approved auth/session path. |
| `gitlab-mcp-gitops-pr/` | Ready for lite/API proof, blocked for official hosted MCP | Lite demo fallback has a valid API token and exposes `gitlab_create_mr_demo`; official hosted MCP remains `Accepted=False`. |
| `a2a-smart-triage-workflows/` | Runtime smoke fixed | Direct A2A `message/send` returns HTTP 200 after model repair. |
| `chaos-reliability-remediation/` | Safe target exists | Do not run new chaos until runtime preflight and explicit lower-env scenario are agreed. |
| `lifecycle-evaluation-review-manager/` | Metrics exist | Include recent failed workflow cases in evidence. |
| `hitl-remediation-approval/` | Static-ready | Live proof should use existing Argo HITL sensors and avoid direct mutation. |
| `policy-governance-safety/` | Front-door triage fixed | `sre-triage-agent` no longer has exec; continue auditing actual tools, not labels/descriptions. |
| `incident-evidence-trace-log-metrics/` | Metrics/logs ready | Trace path still needs explicit datasource or fallback proof. |
| `memory-mcp-shared-context/` | Accepted | Enforce curator-only writes because server exposes write/delete tools. |
| `byo-kagent-onboarding/` | Static-ready | Live team demo should include denial proof for dangerous tools. |
| `aks-fleet-reporting-day2/` | Metrics present | Good candidate for adoption dashboard once runtime is fixed. |

## Immediate Work-Side Priorities

1. Run `runtime-model-gateway-readiness/` in work.
2. Decide whether work will use the proven GitLab-lite/API wrapper or implement
   the official hosted GitLab MCP OAuth/session path.
3. Deploy the Qwen3 no-think proxy before stakeholder demos and confirm
   `/qwen/v1/chat/completions` responses contain no `<think>` wrappers.
4. Run governance audit against actual agent tool lists.
5. Start SRE adoption/game-day only after the preflight returns go or go-with-known-blockers.
