# Network showcase — end-to-end (smoke → evaluation → ticket → network A2A)

One self-contained folder with **everything** needed to replicate the full
demo: fire a network-shaped signal, watch the primary triage agent diagnose it,
call the **network-flow (Hubble) agent** for cluster-wide flow evidence, call the
**evaluation agent** to score its own work, and create a GitLab ticket stamped
with that score. Copy this whole folder to work and deploy it there.

```
Alloy event/log
  → primary triage agent (evaluated-k8s-readonly-triage-agent)
       ├─ read-only k8s diagnosis
       ├─ [network-shaped?] ──A2A tool──▶ aks-network-flow-triage   (Hubble/Cilium:
       │                                    cluster-wide flows, DNS, drops, policy)
       └─ ──A2A tool──▶ triage-evaluation-agent   (score 0–10, all fields present?)
  → Argo workflow verifies controller history → GitLab ticket (carries the score)
```

Both sub-agents are mounted on the primary as native `type: Agent` tools — it
calls them exactly like an MCP server.

## Layout

```
network-showcase-e2e/
├── agents/        kagent Agents: primary (mounts eval + network), evaluator,
│                  network-flow (Hubble showcase), eval-gate WorkflowTemplate
├── pipeline/      Alloy → Vector → Kafka → Argo + eval settings (config snapshot)
├── smoke/         the network-specific signal + expected-outcomes
├── scripts/       verify-smoke.sh (read-only GitLab check)
└── kustomization.yaml   (agents + pipeline)
```

## Deploy order

```bash
CTX=<kube-context>

# 0. Prereqs (environment-owned, NOT in this folder):
#    - kagent + kagent-tool-server (RemoteMCPServer) Ready
#    - argo-events/gitlab-credentials Secret with url, token, project-id
#    - Kafka EventBus + argo-events-sa
#    (Hubble MCP is NOT required — the network agent degrades to k8s-only and
#     marks flow findings UNVERIFIED. See agents/12-network-flow-agent.yaml.)

# 1. Agents + pipeline:
kubectl --context "$CTX" apply -k .

# 2. Wait for agents Accepted/Ready and the WorkflowTemplate admitted, then
#    fire the network signal:
kubectl --context "$CTX" apply -k smoke

# 3. Watch it run: a workflow in argo-events, a triage A2A call, an (optional)
#    network-flow A2A call, an evaluation A2A call, then one GitLab issue.

# 4. Verify (read-only) — v2 path, scans open issues, matches by pod:
scripts/verify-smoke.sh --context "$CTX" --path v2

# 5. Tear the signal down after review:
kubectl --context "$CTX" delete -k smoke
```

## What to look for (the showcase)

1. **Ticket created** — one GitLab issue for `smoke-network-crossns-dns`,
   TL;DR-first, no `n/a`, human-approval boundary preserved.
2. **Score on the ticket** — the `| Evaluation | PASS (score X/10) |` row, from
   the evaluation agent. FAIL after 3 rounds → `triage::evaluation-failed`.
3. **Network A2A hop** — the primary agent's transcript / controller history
   shows a call to `aks-network-flow-triage`, because the signal is a
   cross-namespace DNS + refused-connection shape. That agent reports on flows
   beyond the pod's namespace (Hubble evidence where available; k8s-only +
   UNVERIFIED where not).

## The signal

`smoke/10-network-smoke.yaml` — one non-destructive pod in `platform-test-app`
(app-tier, already in the Alloy allow-list) emitting a cross-namespace DNS
failure + refused connection log. Deliberately network-shaped so the primary
agent chooses to consult the network-flow agent. Hardened (restricted PSA),
requests+limits set. Nothing is actually broken.

## How the primary agent knows to call the network agent

`agents/10-primary-triage-agent.yaml` systemMessage: *"If your diagnosis points
to connectivity, DNS, dropped or denied traffic, or a network-policy problem —
anything where cluster-wide or cross-namespace flow evidence would help — call
aks-network-flow-triage as an Agent tool… skip it otherwise."* Then it always
calls the evaluation agent before returning. So the routing is the agent's own
reasoning over the evidence, not a hard-coded Sensor branch.

## The evaluation gate — what it scores and how it reaches the ticket

The evaluation agent (`agents/11-evaluation-agent.yaml`, `triage-evaluation-agent`)
is an **independent, read-only gate between triage and GitLab**. It has NO tools
(`tools: []`) and treats the incident, diagnosis and tool-audit as untrusted
data — so it can't be steered by the workload's own logs. It returns JSON only:

```json
{"verdict":"PASS|FAIL","score":0-10,"failures":[...],
 "required_fields_present":true|false,
 "required_tool_server_calls_observed":true|false}
```

It PASSes only when the diagnosis carries every required field — TL;DR, overall
health, evidence used, likely cause, risks, exact human-approved next steps, and
confidence — AND includes non-empty tool evidence for the required tool server.
`score` is 10 only when all requirements pass; missing/weak fields drop it.

**How it runs (per incident):**
1. The primary triage agent forms a diagnosis, then calls the evaluator as a
   native A2A tool (`pipeline/03-argo.yaml` diagnose step).
2. If `FAIL`, the primary corrects and re-calls — up to **3 attempts**.
3. Argo independently checks the controller history proves a real tool call AND
   a real evaluator A2A call happened (not just prose) before trusting the verdict.
4. The verdict + score are written onto the ticket.

**How the score reaches the ticket** (`pipeline/03-argo.yaml`):
- Ticket table row: `| Evaluation | PASS (score X/10) |`
- Label: `triage::evaluation-passed` or `triage::evaluation-failed`
- The full evaluator JSON is embedded under `### Independent A2A evaluation`
- 3 failed rounds → the ticket is still created, labelled `evaluation-failed`,
  retaining the evidence for human review (no remediation is ever run).

### Confidence score vs evaluation score — they are different

The ticket carries **two** distinct signals; don't conflate them:

| | Confidence | Evaluation score |
|---|---|---|
| Who sets it | the **triage agent itself**, in its `## Confidence` section | the **independent evaluator** agent |
| What it means | how sure the triage agent is about ITS OWN diagnosis (self-reported) | an external quality grade 0–10: did the triage do its job — all fields present, real tool evidence |
| Trust model | self-assessment (can be optimistic) | adversarial, read-only, untrusted-input second opinion |
| On the ticket | inside the embedded triage body | `| Evaluation | PASS (score X/10) |` + label |

Confidence answers "how sure is the agent it's right?"; the evaluation score
answers "did the agent actually produce a complete, evidence-backed answer?" You
want both high. A confident-but-incomplete answer is exactly what the evaluator
is there to catch.

### Areas to improve the eval logic (candidates, not yet built)
- **Score-based gating:** a passing-but-low score (e.g. 6/10) still makes a
  normal ticket. Add a `triage::low-confidence` label or reviewer flag below a
  threshold so weak-but-passing answers get a human glance.
- **Cross-check confidence vs evidence:** have the evaluator compare the triage's
  self-reported confidence against the strength of its evidence, and fail
  "high confidence + thin evidence".
- **Structured failures feedback:** feed the evaluator's `failures[]` back into
  the retry prompt field-by-field, not just as a JSON blob, to make corrections
  more targeted.
- **Per-field subscores** instead of a single 0–10, so the ticket shows exactly
  which required field was weak.

## Full-coverage smoke (all namespaces)

`smoke/all-namespaces/` fires **one looping log + one Warning event per
Alloy-watched namespace** — full coverage, and it puts the evaluation gate
through varied incident shapes (the log category and event reason cycle across
namespaces: resource, identity, scheduling, network, availability). Expect
**two GitLab tickets per namespace**, each scored by the eval gate.

```bash
# Regenerate for YOUR cluster's Alloy allow-list (default = homelab list):
smoke/all-namespaces/generate.sh <ns1> <ns2> ...
# Fire the whole corpus (after agents/ + pipeline/ + GitLab creds):
kubectl --context <ctx> apply -k smoke/all-namespaces
scripts/verify-smoke.sh --context <ctx> --path v2   # point EXPECTED at all-namespaces/expected-outcomes.yaml
kubectl --context <ctx> delete -k smoke/all-namespaces
```

Same collection caveats as any signal: the log pods **loop** (one-shot lines get
missed), and Alloy must actually tail freshly-created pods — restart Alloy if the
first signals produce no workflows.

## Portability notes

- `pipeline/` is a **verbatim snapshot** of `../config` so this folder stands
  alone when copied to work. Source of truth stays `../config`; re-sync if it
  changes.
- **Work primary agent:** at work the primary is `aks-mcp-readonly-triage-agent`
  (per `../work-evaluation-overlay`), bound to `aks-mcp` not `kagent-tool-server`.
  Add the same two `type: Agent` tools (`triage-evaluation-agent`,
  `aks-network-flow-triage`) to it, and point `pipeline/05-*settings` at it.
- **Do not mix the v2 pipeline with the v3 specialist Sensors.** This showcase
  is the v2 eval-gate pipeline + a network A2A sub-agent (an agent tool call, not
  a payload-contract change), so there is no v2/v3 mixing here.
- Onboarding a real read-only Hubble/Cilium MCP (`hubble-mcp`) turns the network
  agent's flow findings from UNVERIFIED into verified. Do it via the normal MCP
  onboarding flow; keep it read-only.

## Lessons from the live homelab run (read before replicating at work)

Proven end-to-end on the `red` homelab. The pipeline works; these are the walls
that cost time, so pre-empt them:

1. **The Kafka eventsource placeholders MUST be rendered before apply.**
   `pipeline/03-argo.yaml` ships the eventsource with literal
   `{{CONFLUENT_BOOTSTRAP}}`, `{{CONFLUENT_TOPIC}}`, `{{TRIAGE_CONSUMER_GROUP}}`,
   and `deploy.sh` does **not** substitute them — the Argo Kafka `url` is a plain
   string with no `secretKeyRef` (unlike Vector). Left unrendered it crash-loops
   (`missing port in address`). Before applying, set on the eventsource:
   - `url` ← real broker (homelab: `confluent-credentials` secret, key `bootstrap`);
   - `topic` ← the SAME topic Vector publishes to (homelab: Vector's
     `CONFLUENT_TOPIC` env = `k8s-events`, not the placeholder);
   - `consumerGroup.groupName` ← any stable name.
   Confirm the eventsource pod is `Running` with 0 restarts before firing.

2. **Alloy must actually tail the signal pod.** A **one-shot** log line is missed
   by the tailer — the fixture here **loops** the line (keep it). And on this
   homelab Alloy did not pick up **freshly-created** pods (established pods
   collect fine); if the first signal never yields a workflow, restart the Alloy
   pod to re-discover targets and confirm the namespace is in its keep-regex.

3. **Vector dedups exact repeats** on
   `hash(cluster:namespace:pod:reason:log-line)`. Re-firing an identical line is
   suppressed. Use a unique token / new pod name when re-testing.

4. **A2A latency.** The primary agent chains up to three LLM turns
   (triage → network-flow A2A → evaluation A2A); that can exceed the workflow's
   240s `max-time` on network-shaped incidents. Bump the timeout, or use a direct
   A2A call to demo the hop fast.

5. **`k8s-events` is the whole-cluster firehose.** Once fixed the consumer
   triages every cluster warning/error, not just your smoke. Scope the consumer
   group; pause by scaling the eventsource deploy to 0 when not demoing.

6. **Network agent readiness.** The Hubble tools bind to a `hubble-mcp`
   RemoteMCPServer; without it the Agent fails to reconcile
   (`RemoteMCPServer "hubble-mcp" not found`). On a cluster without Hubble, drop
   the `hubble-mcp` binding — the systemMessage already degrades to k8s evidence
   with UNVERIFIED flow findings.

### What was proven on the homelab
- Pipeline → evaluation → ticket: real GitLab issues stamped
  `| Evaluation | PASS (score 10/10) |`, labelled `triage::evaluation-passed`.
- Network A2A hop: a network-shaped incident drove the primary agent to invoke
  BOTH `aks-network-flow-triage` and `triage-evaluation-agent` over native A2A —
  all three agent pods ran their turns in one session.
