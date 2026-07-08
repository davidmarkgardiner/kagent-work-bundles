# Kagent / Agentgateway Cluster Smoke Tests

Purpose: decide whether a new or upgraded agentic cluster is healthy enough to
receive real alert traffic.

This is a completion-based smoke test. A cluster is not healthy just because
pods, Services, Agents, or HTTPRoutes exist. The gate is a completed request
through the same path real alerts use.

```text
synthetic alert or curl
  -> kagent A2A API
  -> kagent controller
  -> target agent
  -> agentgateway
  -> model/provider
  -> completed A2A response
  -> metrics/logs visible in Grafana/Prometheus/Loki
```

## Health Verdict

Use these labels during bring-up or blue/green cutover:

| Verdict | Meaning | Traffic action |
|---|---|---|
| `red` | control plane missing, endpoint unavailable, or single A2A request fails | no real alert traffic |
| `amber` | single A2A request completes, but monitoring, rate limits, or concurrency smoke is incomplete | synthetic or low-risk route only |
| `green` | single A2A request completes, 20-way smoke passes or has a documented lower limit, and monitoring proves the path | eligible for staged real alert traffic |

## Required Components

### Management cluster

| Component | Why it matters | Smoke check |
|---|---|---|
| Gateway API CRDs | HTTPRoute/Gateway objects can be reconciled | `platform/agentgateway/preflight-check.sh --context={{MGMT_KUBE_CONTEXT}}` |
| agentgateway CRDs/runtime | model gateway and policy layer | `kubectl --context {{MGMT_KUBE_CONTEXT}} get pods -n agentgateway-system` |
| agentgateway data-plane Service | reachable model endpoint | port-forward `svc/ai-gateway` and call `/azure/v1` or `/llm/v1` |
| AgentgatewayBackend | provider route is accepted | `kubectl --context {{MGMT_KUBE_CONTEXT}} get agentgatewaybackend -n agentgateway-system` |
| HTTPRoute/Gateway | route is programmed | `kubectl --context {{MGMT_KUBE_CONTEXT}} get gateway,httproute -n agentgateway-system` |
| Workload identity or token refresher | provider auth can work without static secrets | verify UAMI annotation/federated credential or token Secret shape |
| Provider backend | model can return a chat completion | curl `chat/completions` through agentgateway |
| Prometheus scrape | gateway health and token metrics visible | query `agentgateway_gen_ai_client_token_usage_count` |
| Logs | failed requests are diagnosable | gateway logs visible in Loki or via `kubectl logs` |

### Worker cluster

| Component | Why it matters | Smoke check |
|---|---|---|
| kagent CRDs/runtime | A2A and Agent resources exist | `platform/agentgateway/preflight-check.sh --context={{WORKER_KUBE_CONTEXT}}` |
| kagent controller Service | A2A endpoint is reachable | port-forward `svc/kagent-controller` on `8083` |
| target Agent | actual agent can run | `kubectl --context {{WORKER_KUBE_CONTEXT}} get agent -n kagent {{SMOKE_AGENT_NAME}}` |
| ModelConfig | agent points to the intended gateway endpoint | inspect `spec.declarative.modelConfig` and the referenced `ModelConfig` |
| agent Service/pod | controller can call the selected agent | check endpoint/pod logs for `{{SMOKE_AGENT_NAME}}` |
| Argo Events/Workflows | alert path can submit controlled work | synthetic event creates one Workflow, not a storm |
| Alertmanager/Grafana route | only test traffic is pointed at new cluster first | synthetic receiver/contact point only during amber |
| Prometheus scrape | controller/agent metrics visible | query kagent controller and fleet exporter metrics |
| Fleet exporter | agent inventory and readiness visible | query `kagent_agent_ready` |

## Smoke Test Order

### 1. Preflight both clusters

```bash
cd platform/agentgateway
./preflight-check.sh --context={{MGMT_KUBE_CONTEXT}}
./preflight-check.sh --context={{WORKER_KUBE_CONTEXT}}
```

Pass condition:

- required CRDs for the role are present;
- optional CRDs are explicitly accepted as missing or installed;
- the current contexts are the expected management and worker clusters.

### 2. Prove agentgateway can reach the model

Run from `platform/agentgateway`:

```bash
kubectl --context {{MGMT_KUBE_CONTEXT}} \
  port-forward -n agentgateway-system svc/ai-gateway 8080:80 &
PF=$!
sleep 2

curl -sS -m 60 \
  -X POST http://127.0.0.1:8080/{{MODEL_ROUTE_PREFIX}}/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"{{MODEL_DEPLOYMENT_OR_NAME}}",
    "messages":[{"role":"user","content":"Reply with exactly OK."}],
    "max_tokens":10
  }' | jq .

kill "$PF"
```

Pass condition:

- HTTP 200;
- response content is usable;
- token/request metric increments on the gateway.

Fail fast if this does not pass. Do not debug kagent until the gateway/model
path works independently.

### 3. Prove one A2A request completes

Run from the repo root:

```bash
KUBE_CONTEXT={{WORKER_KUBE_CONTEXT}} \
TOTAL=1 \
CONCURRENCY=1 \
AGENT_NAME={{SMOKE_AGENT_NAME}} \
PROMPT="reply with exactly: ok" \
OUT_DIR=/tmp/kagent-a2a-single \
platform/agentgateway/work-qwen-primary-gpt4-failover-handoff/bench-kagent-a2a.sh
```

Pass condition:

```text
status_counts=200:1
state_counts=completed:1
```

This is the minimum readiness gate. If this fails, inspect in this order:

1. `kubectl --context {{WORKER_KUBE_CONTEXT}} logs -n kagent deploy/kagent-controller --tail=100`
2. selected agent pod/service logs;
3. referenced `ModelConfig`;
4. management-cluster agentgateway route and logs;
5. provider auth/token path.

### 4. Run a small concurrency smoke

Start with 20 because the current harness defaults to alert-like burst testing:

```bash
KUBE_CONTEXT={{WORKER_KUBE_CONTEXT}} \
TOTAL=20 \
CONCURRENCY=20 \
AGENT_NAME={{SMOKE_AGENT_NAME}} \
PROMPT="reply with exactly: ok" \
OUT_DIR=/tmp/kagent-a2a-20 \
platform/agentgateway/work-qwen-primary-gpt4-failover-handoff/bench-kagent-a2a.sh
```

Pass condition:

```text
status_counts=200:20
state_counts=completed:20
```

If 20 fails but the single-call test passes, run the stepped sweep:

```bash
KUBE_CONTEXT={{WORKER_KUBE_CONTEXT}} \
CONCURRENCY_LEVELS="1 2 4 8 12 16 20" \
REQUESTS_PER_LEVEL=40 \
AGENT_NAME={{SMOKE_AGENT_NAME}} \
platform/agentgateway/work-qwen-primary-gpt4-failover-handoff/capacity-sweep-kagent-a2a.sh
```

Set the first operating limit below the measured ceiling:

```text
configured_limit = floor(highest_clean_completed_concurrency * 0.7)
```

### 5. Prove alert-path intake without real production traffic

Use a synthetic Alertmanager/Grafana route or a dedicated test receiver.

Pass condition:

- one synthetic alert creates one triage run;
- alert labels and annotations survive into the workflow/agent prompt;
- the resulting kagent run has a shared run ID/fingerprint;
- Teams/ticket notifications, if enabled, include the kagent run link and do not spam.

Do not point broad live alert routes at the cluster until this test is green.

## Monitoring Required Before Green

### Availability

| Signal | Example metric/query | Alert |
|---|---|---|
| agentgateway scrape exists | `up{job="agentgateway-metrics"}` | `AgentgatewayDown` |
| kagent controller scrape exists | `up{job="kagent-controller-metrics",namespace="kagent"}` | `KagentControllerDown` |
| agent inventory visible | `kagent_agent_info` | missing inventory is amber/red |
| agent readiness | `sum(kagent_agent_ready) / count(kagent_agent_ready)` | alert below expected ready count |

### Request success

| Signal | Example metric/query | Alert |
|---|---|---|
| A2A completion | benchmark `state_counts=completed` and workflow result metrics | non-completion is red for cutover |
| kagent errors | `rate(kagent_agent_requests_total{status="error"}[5m])` | `KagentHighErrorRate` |
| gateway 5xx | `rate(envoy_cluster_upstream_rq_5xx[5m])` | `AgentgatewayHighErrorRate` |
| route latency | gateway p95 and kagent p95 | warn before workflow deadline |
| provider token use | `agentgateway_gen_ai_client_token_usage_count` | no activity when traffic expected |

### Backpressure

| Signal | Why | Alert |
|---|---|---|
| provider 429s | model path saturated or quota-limited | warn after sustained 429s |
| gateway timeout/reset logs | provider/network instability | warn after sustained resets |
| Argo queued/running workflows | work is backing up before kagent | warn above configured limit |
| Kafka/EventHub consumer lag | alert intake is exceeding processing | warn on growing lag |
| repeated alert dedupe misses | noisy alert creates workflow spam | warn on high duplicate run count |

### Audit and safety

| Signal | Why | Required before live traffic |
|---|---|---|
| HITL pending count | risky remediation must pause visibly | yes for write-capable paths |
| failed tool calls | agents may be missing permissions or tools | yes |
| prompt/skill version labels | weak runs need traceable fixes | yes |
| run ID/fingerprint correlation | Teams, ticket, workflow, and agent output must join up | yes |

## Existing Repo Assets

| File | Use |
|---|---|
| `platform/agentgateway/preflight-check.sh` | CRD and prerequisite check on both clusters |
| `platform/agentgateway/VALIDATE-MGMT.md` | management-cluster agentgateway/model validation |
| `platform/agentgateway/monitoring.yaml` | base PodMonitor/ServiceMonitor/PrometheusRule resources |
| `platform/agentgateway/work-qwen-primary-gpt4-failover-handoff/bench-kagent-a2a.sh` | single-call and 20-way A2A smoke test |
| `platform/agentgateway/work-qwen-primary-gpt4-failover-handoff/capacity-sweep-kagent-a2a.sh` | stepped A2A capacity sweep |
| `platform/agentgateway/work-qwen-primary-gpt4-failover-handoff/82-WORKFLOW-RATE-LIMITING-PATTERNS.md` | Argo/Kafka/Alloy throttling controls |
| `observability/agent-evals/fleet-exporter/` | read-only agent inventory/readiness exporter |
| `observability/grafana/dashboards/k-agent-agentgateway-public-ready.json` | dashboard surface for kagent/agentgateway readiness |
| `work-agent-bundles/kagent-agentic-cluster-high-level-checklist.md` | broader rollout and operating-model checklist |

## Cutover Rule

Only route real alert traffic to the new cluster when all are true:

- management-cluster gateway/model smoke passes;
- worker-cluster single A2A request returns `completed`;
- selected concurrency smoke passes or has a documented configured limit;
- synthetic alert creates exactly one traceable triage run;
- dashboard and alerts cover availability, success, latency, 429s/timeouts, backlog, and HITL;
- rollback is one routing change away at Alertmanager/Grafana, Kafka/EventHub, DNS, or ingress.

## Monthly Rebuild Cadence

Run a monthly rebuild exercise for the agentic stack. The goal is to prove the
cluster can be recreated from GitOps, values, identity, and smoke tests without
manual reconstruction.

Use this cadence:

| Cadence | Action | Required proof |
|---|---|---|
| monthly | build a fresh non-prod agentic cluster or namespace-equivalent stack | all smoke tests in this file pass |
| monthly | compare live cluster state with GitOps source | drift report has owner or accepted exception |
| monthly | rotate or re-issue non-prod tokens/certs where supported | gateway/model smoke still passes |
| monthly | replay synthetic alert scenarios | one alert creates one correlated triage run |
| monthly | run A2A single-call and burst smoke | completed state is the success signal |
| quarterly | rehearse blue/green route cutover and rollback | route move and rollback are both timed and evidenced |
| after major upgrade | rebuild green stack before broad traffic shift | same green gate as cutover rule |

Do not force a monthly production rebuild unless the platform has proven
blue/green cutover, rollback, and data-retention behavior. For production, the
monthly bar should be:

- prove a fresh stack can be built in non-prod from the same manifests;
- prove production drift is understood;
- prove rollback still works;
- apply production rebuild only when there is a driver such as AKS upgrade,
  CRD/runtime upgrade, security patching, identity change, or unrecoverable
  drift.

Monthly rebuild evidence should include:

- cluster/context name using `{{PLACEHOLDER}}` values in public docs;
- Git revision and values bundle used;
- preflight output for management and worker clusters;
- gateway/model smoke output;
- single-call A2A summary;
- burst or capacity-sweep summary;
- synthetic alert run ID/fingerprint;
- dashboard links or query snippets for gateway, kagent, backlog, and HITL;
- rollback command or route-change evidence.
