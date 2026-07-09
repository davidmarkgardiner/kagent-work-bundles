# Critique Review: Agentic Triage Smoke Tests — 2026-07-09

Independent read-only review produced against `prompts/CRITIQUE-PROMPT.md`.
No files were edited during the review. No live validation was assumed. Absent
evidence is treated as not proven. Private hostnames, node names, internal
service URLs, and secrets are kept out of this output; where they appear in
committed evidence they are cited by `path:line` only.

## Reviewer summary

The bundle is disciplined about **source-type** honesty — it clearly separates
the metrics path from the still-unproven logs, events, and traces paths. The
core weakness is the **end-to-end chain claim**: no single run with one
`run_id` proves `crashloop metric alert -> Kimi route -> eval pass`. The claim
is stitched from two runs — an alert-intake run that failed at the agent, and a
manual fan-out run whose evidence source is synthetic. Committed evidence also
embeds internal cluster/node identifiers inside a bundle that declares itself
public.

Verdict: **revise**.

```text
VERDICT: revise

CLAIMS_AUDIT:
- claim: Full chain pod failure -> Grafana metric alert -> webhook/EventSource -> Argo Workflow -> smart-triage fan-out -> agentgateway Kimi route -> HITL/eval success is proven end to end
  status: partially_proven
  evidence:
    - evidence/PROXMOX-E2E-SMOKE-2026-07-09.md:69   # alert Alerting
    - evidence/PROXMOX-E2E-SMOKE-2026-07-09.md:101  # workflow created
    - evidence/PROXMOX-E2E-SMOKE-2026-07-09.md:128  # agent fan-out FAILED (502)
    - evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md:168  # fan-out Succeeded 14/14
    - evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md:196  # eval score=1.0
  gap: No single run proves the whole chain. Run 1 (run_id triage-smoke-...083506) proves alert->webhook->Argo->normalize but the agent half FAILED at 502. Run 2 proves fan-out->Kimi->HITL->eval but was NOT triggered by a Grafana crashloop metric alert; its trigger is a manual fan-out (fingerprint kimi-full-fanout-..., no run_id) and its evidence source is synthetic. The two halves do not share a run_id, so "end to end" is stitched, not demonstrated.

- claim: The Proxmox evidence proves agent correctness with SOURCE-BACKED output and eval scoring (not just alert delivery)
  status: partially_proven
  evidence:
    - evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md:46   # EVIDENCE_SOURCE: synthetic-flux
    - evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md:196  # score=1.0 passed=true
  gap: The only eval-scored (1.0) run used a synthetic evidence source and a bad_deploy/deployment scenario, not the real Grafana crashloop metric evidence from run 1. "Real Grafana source evidence -> agent output -> eval pass" is not proven together in one run. Eval currently proves the scoring mechanism works on a synthetic case.

- claim: README/FRONT-SHEET statement "proves the metrics crashloop path end to end, including Kimi routing and lifecycle eval success"
  status: not_proven
  evidence:
    - README.md:29
    - FRONT-SHEET.md:23
    - evidence/PROXMOX-E2E-SMOKE-2026-07-09.md:4   # verdict red, agent failed
  gap: The crashloop run's verdict is red and it never reached Kimi or eval. No crashloop-origin run reaches Kimi+eval. The statement conflates two runs. Reword to "metric alert intake proven in one run; model/fan-out/eval proven in a separate manual run."

- claim: Bundle distinguishes live-proven source types from planned source types
  status: proven
  evidence:
    - README.md:36
    - FRONT-SHEET.md:27
    - SCORECARD.md:177
  gap: none — this separation is the bundle's strongest quality.

- claim: Worker-capacity fix prevents reintroducing control-plane pressure during periodic runs
  status: partially_proven
  evidence:
    - evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md:124  # fix applied
    - evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md:200  # "keep watching worker1 capacity"
  gap: All 14 specialists pinned to one node via nodeSelector (single point of failure), requests=16Mi but limits=256Mi (14 pods -> up to ~3.5Gi burst against ~2.7Gi node headroom -> OOM/eviction risk), and --max-pods=180 is a manual kubelet arg not GitOps-managed (lost on node rebuild). The doc itself flags residual risk. Not durable for unattended periodic runs.

- claim: agentgateway provider manifests and ModelConfigs are plausible for OpenAI-compatible Kimi/GLM/MiniMax without leaking secrets
  status: partially_proven
  evidence:
    - platform/agentgateway/backend-openai-compatible-external-models.yaml:48   # secretRef, no inline key
    - platform/agentgateway/modelconfig-openai-compatible-external-models.yaml:28 # placeholder client key
  gap: Secret hygiene is clean (secretRef + not-required placeholder). But host api.kimi.com and model MiniMax-M2.7 look like placeholders, not verified real endpoints; temperature is a quoted string "0.2" while maxTokens is an int — confirm kagent v1alpha2 schema accepts a string temperature.

CONTRADICTIONS:
- README.md:29-34 and FRONT-SHEET.md:23-25 assert a single end-to-end crashloop path through Kimi and eval, but evidence/PROXMOX-E2E-SMOKE-2026-07-09.md:4 records that same crashloop run as verdict red / agent failed. The proving run for Kimi+eval is a different, manually triggered run with a synthetic source.
- SCORECARD.md:177-181 is more accurate than README/FRONT-SHEET: it states the follow-up run proves the model/backend path "after the worker-capacity fix" and does not replace the logs/events/traces need. Align README and FRONT-SHEET to SCORECARD's wording.

MISSING_LIVE_SMOKES:
- source: metrics
  required_evidence: A single continuous run_id from crashloop alert through Kimi fan-out and eval pass
  current_status: partially_proven
- source: logs
  required_evidence: Real Grafana-origin Loki alert with LogQL evidence cited in agent output
  current_status: not_proven
- source: events
  required_evidence: Real Grafana-origin Kubernetes warning-event alert; run 1's BackOff surfaced via a Prometheus metric, not an event alert
  current_status: not_proven
- source: traces
  required_evidence: Real Tempo alert with trace_id/deeplink, OR an explicit captured TRACE_FALLBACK: NO_TRACE marker
  current_status: not_proven
- source: negative-health
  required_evidence: A scored failing run whose published metric drives an observed alert firing
  current_status: not_proven
- source: periodic
  required_evidence: One scheduled run emitting agentic_triage_smoke_* metrics with an observed self-alert
  current_status: not_proven

SAFETY_CONCERNS:
- score-smoke-run.py (README.md:104, SMOKE-RUNBOOK.md:174) is cited as the metric emitter but is not present in the reviewed set; cannot confirm it publishes agentic_triage_smoke_score/passed/hard_failures. All periodic alerting depends on it.
- A total smoke-runner crash emits NO metrics, so only absent/stale rules fire (severity warning); AgenticTriageSmokeHardFailure needs the metric present with value>0 (examples/monitoring/agentic-triage-smoke-rules.yaml:54). A fully dead smoke system never pages critical.

OPERABILITY_GAPS:
- Single-node pin of all specialists removes fault tolerance; a worker1 outage takes out the entire fan-out (evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md:136-145).
- requests/limits ratio 16Mi/256Mi overcommits the node on repeated runs; scheduler packs on requests, pods then burst past node memory.
- --max-pods=180 kubelet arg is imperative, not in GitOps; drift on node rebuild silently re-breaks capacity.
- No run_id on the Kimi/agentgateway usage evidence or the full-fanout workflow; model-call cost/latency cannot be joined to a specific smoke.

DASHBOARD_OR_ALERT_GAPS:
- No "smoke runner heartbeat/critical-dead" rule. Add a critical alert on absence of any agentic_triage_smoke_* series, separate from the warning-level stale/missing rules.
- AgenticTriageSmokeScoreLow, DailyProfileStale, and QuickProfileMissing are all severity warning (examples/monitoring/agentic-triage-smoke-rules.yaml:19,29,39,48); a persistently degraded score never escalates to critical.
- agentic_triage_smoke_source_coverage is defined (SCORECARD.md:107) but no rule consumes it; a source-coverage regression is silent.

PUBLIC_SAFETY_ISSUES:
- Committed evidence files in this stated-public bundle (README.md:11) embed internal cluster name, internal node names, and an internal service DNS URL (evidence/PROXMOX-E2E-SMOKE-2026-07-09.md:16-20, :55-56, :72-79; evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md:63-70, :92-103, :134-145). No API keys/tokens/public IPs are leaked, so severity is low, but this contradicts the bundle's own placeholder-safe rule. Sanitize node/cluster/service identifiers before publishing.
- Provider host api.kimi.com and model id MiniMax-M2.7 (platform/agentgateway/backend-openai-compatible-external-models.yaml:47,149; platform/agentgateway/OPENAI-COMPATIBLE-PROVIDERS.md:38) read as placeholders — confirm they are intentional, not real-but-wrong endpoints, before anyone applies the manifest.

JOIN_KEYS_STATUS:
- run_id convention is defined (SMOKE-RUNBOOK.md:16-18) but not applied consistently. The Kimi/eval run uses fingerprint kimi-full-fanout-... with no run_id and off-format naming (evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md:163), so Grafana alert, Argo workflow, kagent output, and eval for the passing run cannot be joined by run_id.
- Ticket join fields exist in the lifecycle collector (SCORECARD.md:67-69) but no ticket evidence appears in either run.
- agentgateway usage tokens are captured without a run_id label; cost/latency cannot be tied to a smoke.

RECOMMENDED_PATCHES:
- path: README.md:29-34
  change: Split the Current Evidence Boundary claim into two proven sub-paths with their real run_ids (alert-intake run vs manual Kimi/eval run) and state explicitly that no single continuous run_id yet spans alert->Kimi->eval.
- path: FRONT-SHEET.md:23-25
  change: Remove "end to end ... including Kimi ... eval success" for the crashloop path; the crashloop run is verdict red. Describe the two halves separately, matching SCORECARD.md:177-181.
- path: prompts/CRITIQUE-PROMPT.md
  change: Add required output sections CONTRADICTIONS and JOIN_KEYS_STATUS; require per-hop status for Q1's seven hops; relax "line" to "path or path:line" for screenshot/YAML/log evidence; add an explicit VERDICT gate (block if the core chain is not_proven, revise if any of Q4-Q6 sources are not_proven, else pass); cap evidence to <=3 lines per claim and require a quoted snippet, not just a path.
- path: examples/monitoring/agentic-triage-smoke-rules.yaml
  change: Add a critical rule for total-runner-dead (absent all agentic_triage_smoke_* series over the max expected window) and a source-coverage-regression rule; raise persistent ScoreLow to critical.
- path: evidence/PROXMOX-E2E-SMOKE-2026-07-09.md and evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md
  change: Sanitize internal cluster/node names and internal service DNS to placeholders; add run_id to the Kimi/agentgateway usage block and rename the full-fanout fingerprint to the runbook run_id format so evidence joins.
- path: platform/agentgateway/modelconfig-openai-compatible-external-models.yaml:48,64
  change: Verify openAI.temperature type — quoted "0.2" (string) vs maxTokens int; confirm kagent v1alpha2 accepts a string temperature or change to numeric.

REVIEWER_NOTES:
- Prefer not_proven over inference was applied: SPECIALIST_TRACE: completed (evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md:184) is NOT credited as trace coverage because no trace_id/deeplink and no explicit NO_TRACE marker are present.
- No credit was given for planned periodic/negative alerting; rules exist as static files but no firing evidence was shown.
```
