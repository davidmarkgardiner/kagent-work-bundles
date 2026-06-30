# Prerequisites / Building-Blocks Checklist

Verify **every** row in the live cluster **before** building or deploying the
Vector normalizer. This is the agent's preflight inventory. Do not start
`prompts/02-deploy-vector-normalizer.md` until all `MUST` rows are confirmed.

All values below are derived from `../../observability/vector/manifests/`. The
agent must prove each one exists (or create it) in the target cluster.

---

## 0. Access & context

| # | Building block | Expected value | Verify command | MUST/SHOULD | Status |
|---|---|---|---|---|---|
| 0.1 | Kube context | `{{MGMT_KUBE_CONTEXT}}` (mgmt/dev cluster) | `kubectl config current-context` | MUST | TODO |
| 0.2 | Cluster reachable | API responds | `kubectl cluster-info` | MUST | TODO |
| 0.3 | Tools present | `kubectl jq yq confluent` + `docker`/`vector` | `which kubectl jq yq confluent docker` | MUST | TODO |

---

## 1. Namespace

| # | Building block | Expected value | Verify command | MUST/SHOULD | Status |
|---|---|---|---|---|---|
| 1.1 | Target namespace | `{{ARGO_EVENTS_NAMESPACE}}` | `kubectl get ns {{ARGO_EVENTS_NAMESPACE}}` | MUST | TODO |
| 1.2 | Same ns hosts Argo Events + Vector + Workflows | single ns deploy | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get deploy` | MUST | TODO |

> Decision: deploy Vector **into the same `{{ARGO_EVENTS_NAMESPACE}}` namespace** (matches
> manifests). If a separate Vector instance is wanted, change `metadata.name`
> and `group_id`/`consumerGroup` to avoid colliding with the running one.

---

## 2. Vector deployment

| # | Building block | Expected value | Verify command | MUST/SHOULD | Status |
|---|---|---|---|---|---|
| 2.1 | Existing Vector deploy | `{{VECTOR_DEPLOYMENT_NAME}}` | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get deploy {{VECTOR_DEPLOYMENT_NAME}}` | SHOULD | TODO |
| 2.2 | Vector image/tag | `{{VECTOR_IMAGE}}` | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get deploy {{VECTOR_DEPLOYMENT_NAME}} -o jsonpath='{..image}'` | MUST | TODO |
| 2.3 | Image pull works in cluster | no `ImagePullBackOff` | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get pods -l app.kubernetes.io/name={{VECTOR_DEPLOYMENT_NAME}}` | MUST | TODO |
| 2.4 | Vector config ConfigMap | `{{VECTOR_DEPLOYMENT_NAME}}-config` | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get cm {{VECTOR_DEPLOYMENT_NAME}}-config` | MUST | TODO |
| 2.5 | Vector API/health port | `8686` `/health` | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get svc {{VECTOR_DEPLOYMENT_NAME}}` | SHOULD | TODO |

> Note: if reusing the running Vector vs. standing up a second instance —
> confirm `group_id: {{VECTOR_DEPLOYMENT_NAME}}`. Two deployments with the
> same Kafka `group_id` **share** the partition load (consumer group). For an
> isolated test instance use a **new** `group_id`.

---

## 3. Secrets (names only — never print values)

| # | Building block | Secret name | Required keys | Verify command | MUST/SHOULD | Status |
|---|---|---|---|---|---|---|
| 3.1 | Confluent SASL creds | `{{CONFLUENT_CREDENTIALS_SECRET}}` | `bootstrap`, `key`, `secret` | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get secret {{CONFLUENT_CREDENTIALS_SECRET}} -o jsonpath='{.data}' \| jq 'keys'` | MUST | TODO |
| 3.2 | Confluent CA (for Argo EventSource TLS) | `{{CONFLUENT_CA_SECRET}}` | `ca.pem` | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get secret {{CONFLUENT_CA_SECRET}} -o jsonpath='{.data}' \| jq 'keys'` | MUST | TODO |
| 3.3 | Creds least-privilege | producer+consumer scoped to the 2 topics | review in Confluent Cloud SA/ACLs | SHOULD | TODO |

> `{{CONFLUENT_CREDENTIALS_SECRET}}.key`/`.secret` are reused by Vector (SASL user/pass)
> **and** by the Argo EventSource. Confirm one SA has read+write on both topics,
> or split principals per `request.safety.split_kafka_principals: true`.

---

## 4. Kafka / Confluent topics

| # | Building block | Topic name | Role | Verify command | MUST/SHOULD | Status |
|---|---|---|---|---|---|---|
| 4.1 | Raw alert topic | `{{ALERTMANAGER_RAW_TOPIC}}` | Vector source (input from Alertmanager) | `confluent kafka topic describe {{ALERTMANAGER_RAW_TOPIC}}` | MUST | TODO |
| 4.2 | Normalized topic | `{{ALERTMANAGER_TRIAGE_TOPIC}}` | Vector sink + Argo EventSource | `confluent kafka topic describe {{ALERTMANAGER_TRIAGE_TOPIC}}` | MUST | TODO |
| 4.3 | (Optional) K8s raw topic | `{{K8S_RAW_TOPIC}}` | Alloy events — only if testing that path | n/a | SHOULD | TODO |
| 4.4 | Bootstrap endpoint matches secret | `{{CONFLUENT_CREDENTIALS_SECRET}}.bootstrap` == Confluent cluster bootstrap | `confluent kafka cluster describe` | MUST | TODO |

> **New topic check (user question):** `{{ALERTMANAGER_TRIAGE_TOPIC}}` is the
> "new topic" Vector pushes to. If it does not already exist in Confluent,
> create it before deploy. The raw `{{ALERTMANAGER_RAW_TOPIC}}` already exists (proven
> in the earlier Alertmanager→Confluent→Argo run).

---

## 5. Argo Events plumbing

| # | Building block | Expected value | Verify command | MUST/SHOULD | Status |
|---|---|---|---|---|---|
| 5.1 | EventBus | `default` | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get eventbus default` | MUST | TODO |
| 5.2 | Service account | `{{ARGO_EVENTS_NAMESPACE}}-sa` | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get sa {{ARGO_EVENTS_NAMESPACE}}-sa` | MUST | TODO |
| 5.3 | SA RBAC creates Workflows | can `create workflows` | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} auth can-i create workflows --as=system:serviceaccount:{{ARGO_EVENTS_NAMESPACE}}:{{ARGO_EVENTS_NAMESPACE}}-sa` | MUST | TODO |
| 5.4 | EventSource | `vector-alertmanager-triage-kafka` (consumes `{{ALERTMANAGER_TRIAGE_TOPIC}}`) | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get eventsource` | SHOULD | TODO |
| 5.5 | Consumer group | `{{ALERTMANAGER_TRIAGE_CONSUMER_GROUP}}` | in EventSource spec | SHOULD | TODO |
| 5.6 | Sensors | `vector-alertmanager-triage`, `vector-routing-verification` | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get sensor` | SHOULD | TODO |
| 5.7 | WorkflowTemplates | `alertmanager-triage` (prod), `vector-routing-verification` (test) | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get workflowtemplate` | MUST | TODO |
| 5.8 | Argo Workflows controller running | controller pod ready | `kubectl -n {{ARGO_EVENTS_NAMESPACE}} get deploy workflow-controller` | MUST | TODO |

---

## 6. Routing targets (agents)

| # | Route | Target agent | Trigger condition | Status |
|---|---|---|---|---|
| 6.1 | application | `aks-sre-triage-agent` | `service != unknown` | TODO |
| 6.2 | platform | `platform-ops-agent` | ns `kube-*`/`istio-*`/`argo-*`/`monitoring`/`platform-tools` | TODO |
| 6.3 | security | `security-hardening-agent` | ns `security`/`platform-security` | TODO |
| 6.4 | fallback | `sre-triage-agent` | missing service owner | TODO |

> These are route-string values, not live CRDs the verification workflow calls.
> Confirm the real agent names match before the **production** workflow swap.

---

## 7. Test-path entry point (Grafana / Alertmanager)

| # | Building block | Expected value | Verify | MUST/SHOULD | Status |
|---|---|---|---|---|---|
| 7.1 | Grafana reachable + MCP | Grafana MCP can create test alert | confirm MCP connected | MUST | TODO |
| 7.2 | Alertmanager → Confluent path | already proven (raw topic receives) | reference prior run | MUST | TODO |
| 7.3 | Test marker honored | `routing_test: true` → route-verify sensor | inspect payload | MUST | TODO |

---

## Sign-off gate

Build/deploy may start only when:

- All section 0–5 `MUST` rows = OK.
- Topic `{{ALERTMANAGER_TRIAGE_TOPIC}}` exists or is created (4.2).
- Both secrets present with correct keys (3.1, 3.2).
- Decision recorded: **reuse** running Vector vs **new** isolated instance (2.x).

Record results in `evidence/EVIDENCE-TEMPLATE.md`. Print **names only** — no
secret values, no private endpoints.
