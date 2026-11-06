# agentgateway — kagent LiteLLM replacement

Replace LiteLLM with [agentgateway](https://agentgateway.dev) as the AI gateway
between kagent (worker cluster) and LLM providers (Azure OpenAI via UAMI,
KubeAI, vLLM-hosted Qwen). Includes Istio wildcard ingress, monitoring, and
secret-rotation-safe UAMI custom-scope workflow.

## Architecture

```
┌─ Worker cluster ────────────────────────────┐   ┌─ Management cluster ──────────────────────┐
│                                             │   │                                           │
│  kagent                                     │   │  Istio ingress (aks-istio-ingress)        │
│   ModelConfig: agentgateway-azure-openai    │   │     │ wildcard cert *.<domain>            │
│   baseUrl: https://agentgateway.<domain>    │───┼─►   │                                     │
│                                             │   │     ▼                                     │
└─────────────────────────────────────────────┘   │  VirtualService (istio-virtualservice)    │
                                                  │     │  hosts: [agentgateway.<domain>]     │
                                                  │     │  gateways: [shared-wildcard]        │
                                                  │     ▼                                     │
                                                  │  agentgateway (ai-gateway:80)             │
                                                  │     │  HTTPRoutes:                        │
                                                  │     │    /azure/v1   → azure-openai-bknd  │
                                                  │     │    /openai/v1  → kubeai-bknd        │
                                                  │     │    /qwen/v1    → vllm-qwen-bknd     │
                                                  │     │    /llm/v1     → priority failover  │
                                                  │     ▼                                     │
                                                  │  AgentgatewayBackends                     │
                                                  │     │  • azureopenai + UAMI (or CronJob)  │
                                                  │     │  • openai (KubeAI / vLLM)           │
                                                  │     ▼                                     │
                                                  │  Azure OpenAI / KubeAI / vLLM             │
                                                  └───────────────────────────────────────────┘
```

## Start Here

| Task | Read |
|---|---|
| Present the repo-wide Agentgateway MVP demo | [`../../DEMOS.md#2-agentgateway-mvp-control-plane-demo-set`](../../DEMOS.md#2-agentgateway-mvp-control-plane-demo-set) |
| Run the MVP demo schema gate | [`DEMO-SCHEMA-GATE.md`](DEMO-SCHEMA-GATE.md) |
| First-time deploy at work | `DEPLOY.md` |
| Validate mgmt cluster before worker | `VALIDATE-MGMT.md` |
| Check required CRDs | `./preflight-check.sh` |
| Configure agent authentication | [`AUTHENTICATION.md`](AUTHENTICATION.md) |
| Prepare the application-team onboarding meeting | [`APPLICATION-TEAM-ONBOARDING-FRONT-SHEET.md`](APPLICATION-TEAM-ONBOARDING-FRONT-SHEET.md) |
| Review the full onboarding security and delivery design | [`APPLICATION-TEAM-ONBOARDING-PLAN.md`](APPLICATION-TEAM-ONBOARDING-PLAN.md) |
| Understand why secret rotation is safe | `SECRET-ROTATION-TEST.md` |
| See what the Factory review flagged | `FACTORY-REVIEW.md` |
| TLS / connection errors from kagent | See [Troubleshooting](#troubleshooting) below |

## Files

### Management cluster — always apply

| File | Purpose |
|---|---|
| `gateway-resources.yaml` | GatewayClass, Gateway, HTTPRoutes for `/openai/v1` + `/azure/v1`, ReferenceGrant |
| `ai-policy.yaml` | AgentgatewayPolicy: timeouts, rate limits, PII guard |
| `istio-virtualservice.yaml` | VirtualService attaching specific host under the shared wildcard Gateway to agentgateway |
| `istio-authorization-policy.yaml` | Source IP allow-list (with optional API key / JWT upgrade paths) |

### Management cluster — pick one Azure backend

| File | Use when |
|---|---|
| `backend-azure-openai.yaml` | Azure OpenAI scope is the default `https://cognitiveservices.azure.com/.default` |
| `backend-azure-openai-customscope.yaml` | Custom AAD app audience (e.g. `api://at12345-xxxx/.default`). Uses a CronJob token refresher |

### Management cluster — optional backends

| File | Use when |
|---|---|
| `backend-kubeai.yaml` | KubeAI local model server available |
| `backend-kubeai-qwen.yaml` | KubeAI serves `qwen3-14b` and kagent should call it through `/qwen/v1` on agentgateway |
| `backend-vllm-qwen.yaml` | vLLM-hosted Qwen model — HTTPRoute at `/qwen/v1` with URL rewrite |
| `backend-llm-failover.yaml` | Priority-group failover endpoint at `/llm/v1`; primary provider first, fallback provider after the primary group is unavailable; route retry includes 429/5xx |

### Worker cluster — kagent model configs

| File | Use when |
|---|---|
| `modelconfig-default-qwen.yaml` | Existing agents use `default-model-config` and should route through agentgateway to local Qwen |
| `modelconfig-llm-failover.yaml` | Agents should use the `/llm/v1` gateway failover endpoint |
| `modelconfig-kubeai.yaml` | You want a separate `agentgateway-kubeai` ModelConfig |
| `modelconfig-qwen.yaml` | You want a separate `agentgateway-qwen` ModelConfig |

### Management cluster — optional infrastructure

| File | Requires |
|---|---|
| `networkpolicy.yaml` | CNI with NetworkPolicy support (Calico, Cilium) |
| `monitoring.yaml` | Prometheus Operator CRDs |

### MVP demo set — gateway-as-control-plane

Sequenced PRs. Read `DEMO-SCHEMA-GATE.md` first; nothing in this section
applies until that file's verdict table is filled in against a live cluster.

| File | Demo | Purpose |
|---|---|---|
| `DEMO-SCHEMA-GATE.md` | PR 0 | Read-only CRD/runtime support verdict for PRs 1-4 |
| `policy-prompt-enrichment.yaml` | PR 1 | Inject org-wide SRE system prompt at the gateway, no kagent edits |
| `backend-llm-failover.yaml` | PR 2 | Single `/llm/v1` endpoint with local model first, Azure OpenAI fallback, and route retry on 429/5xx |
| `FAILOVER-DEMO.md` | PR 2 | Safe failover test options + rollback |
| `backend-argo-openapi-mcp.yaml` | PR 3 | Argo Server REST OpenAPI → MCP tools (gated on schema verdict) |
| `policy-argo-openapi-mcp.yaml` | PR 3 | MCP CEL authz: read tools open, writes allowlisted |
| `argo-openapi-spec-configmap.yaml` | PR 3 | Version-pinned Argo Server REST OpenAPI document |
| `remotemcpserver-argo.yaml` | PR 3 | Worker-cluster `RemoteMCPServer` pointed at the gateway route |
| `ARGO-OPENAPI-MCP-DEMO.md` | PR 3 | Schema verdict, spec source, read-only and write-denial tests |
| `service-a2a-fleet-agent.yaml` | PR 4 | ReferenceGrant in `kagent` allowing agentgateway HTTPRoutes to reach `kagent-controller` (plan B — no `appProtocol: agentgateway.dev/a2a` because CRD doesn't support it) |
| `route-a2a-fleet-agent.yaml` | PR 4 | `HTTPRoute /a2a/fleet/` → URL-rewrite → `kagent-controller.kagent:8083/api/a2a/kagent/<fleet-agent>/` |
| `policy-a2a-fleet-agent.yaml` | PR 4 | Rate limit + request timeout for the A2A path. Identity gate lives at the Istio AuthorizationPolicy layer (CRD has no `backend.a2a.authorization`) |
| `A2A-FLEET-DEMO.md` | PR 4 | A2A identity model, manual + ingress tests, trailing-slash variants, rollback |

### Worker cluster

| File | Applies when |
|---|---|
| `modelconfig-azure.yaml` | Pointing kagent at Azure OpenAI backend |
| `modelconfig-llm-failover.yaml` | Pointing kagent at the gateway-controlled fallback backend |
| `modelconfig-kubeai.yaml` | Pointing kagent at KubeAI backend |
| `modelconfig-qwen.yaml` | Pointing kagent at vLLM/Qwen backend |
| `kagent-values-otel.yaml` | Want richer kagent → Alloy OTLP logs/traces (Helm values overlay) |

## Empirical Validation Status

Proven on the red cluster with agentgateway v1.1.0 (see `SECRET-ROTATION-TEST.md`):

- ✅ agentgateway v1.1.0 Helm install
- ✅ AgentgatewayBackend with `provider.openai` + `host` + `port`
- ✅ HTTPRoute with `URLRewrite` (`/qwen/v1` → `/openai/v1`)
- ✅ `secretRef` with `Authorization` key and `Bearer <value>` content
- ✅ End-to-end chat completion (2.5s, 20 tokens, real response)
- ✅ Native Prometheus token metrics emitted (`agentgateway_gen_ai_client_token_usage`)
- ✅ Secret rotation via `kubectl patch secret` → xDS push → data-plane pod picks up new value with **zero restarts and zero connection drops** (~1s propagation)

Current install baseline is agentgateway v1.3.1. Re-run the validation flow after upgrade before treating v1.3.1 as production-proven.

Not yet tested in production:

- Custom-scope UAMI CronJob against real Azure AD (schema validated; end-to-end needs real UAMI + Azure OpenAI)
- Istio VirtualService via wildcard Gateway (pattern documented; depends on your shared Gateway)
- Cross-cluster from worker kagent (end-to-end smoke depends on network path between clusters)

## Deploy Order — Minimum Viable

```bash
# 0. Preflight both clusters
./preflight-check.sh --context=<mgmt-cluster>
./preflight-check.sh --context=<worker-cluster>

# 1. Management cluster: install + apply
helm upgrade -i agentgateway-crds oci://cr.agentgateway.dev/charts/agentgateway-crds \
  --version v1.3.1 -n agentgateway-system --create-namespace
helm upgrade -i agentgateway oci://cr.agentgateway.dev/charts/agentgateway \
  --version v1.3.1 -n agentgateway-system

kubectl apply -f gateway-resources.yaml
kubectl apply -f backend-azure-openai.yaml     # or -customscope
kubectl apply -f ai-policy.yaml
kubectl apply -f istio-virtualservice.yaml
kubectl apply -f istio-authorization-policy.yaml

# 2. Management cluster: validate end-to-end (see VALIDATE-MGMT.md for full flow)
kubectl port-forward -n agentgateway-system svc/ai-gateway 8080:80 &
curl -s -X POST http://localhost:8080/azure/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<deployment>","messages":[{"role":"user","content":"ping"}],"max_tokens":5}' \
  | jq .choices[0].message.content

# 3. Worker cluster: dummy secret + ModelConfig + roll out
kubectl create secret generic litellm-key -n kagent \
  --from-literal=api-key="not-required" --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f modelconfig-azure.yaml
for agent in $(kubectl get agent -n kagent -o name | sed 's|agent.kagent.dev/||'); do
  kubectl patch agent "$agent" -n kagent --type merge \
    -p '{"spec":{"declarative":{"modelConfig":"agentgateway-azure-openai"}}}'
done
```

## Rate-Limit Fallback Pattern

kagent `ModelConfig` does not define a list of fallback models. It points to one
OpenAI-compatible endpoint. Put fallback in agentgateway instead:

1. Apply `backend-llm-failover.yaml` on the management cluster.
2. Apply `modelconfig-llm-failover.yaml` on the worker cluster.
3. Patch selected agents to `spec.declarative.modelConfig=agentgateway-llm-failover`.
4. Run `FAILOVER-DEMO.md`, including the 429 probe, before rolling it out fleet-wide.

`backend-llm-failover.yaml` includes route retry on
`429, 500, 502, 503, 504` plus priority groups. Keep the gateway's own local
`rateLimit` above expected kagent bursts; a gateway-generated 429 happens before
provider selection and is an overload protection signal, not a provider fallback
signal. If the installed CRD supports `AgentgatewayPolicy.spec.backend.health`,
add a backend health policy for `response.code == 429 || response.code >= 500`
after server-side validation; the `proxmox-k8s` CRD checked on 2026-06-03 did
not accept that field.

### Failover Configuration

| Placeholder | Meaning |
|---|---|
| `{{PRIMARY_MODEL}}` | Primary model served by the local/OpenAI-compatible provider. |
| `{{AGENTGATEWAY_HOSTNAME}}` | Worker-cluster reachable hostname for the management-cluster agentgateway ingress. |
| `{{AZURE_OPENAI_RESOURCE}}` | Azure OpenAI resource name without the `.openai.azure.com` suffix. |
| `{{AZURE_OPENAI_DEPLOYMENT}}` | Azure OpenAI deployment name used by the fallback provider. |
| `{{AZURE_OPENAI_API_KEY}}` | API key for the fallback path when using the mixed-provider demo manifest; prefer the UAMI/two-backend pattern where available. |

## Troubleshooting

### Layered test approach — isolate the failing layer

When anything goes wrong end-to-end, work from the outside in. Each layer
points at a different cause.

**Layer 0 — mgmt cluster port-forward** (proves agentgateway + backend work)
```bash
kubectl port-forward -n agentgateway-system svc/ai-gateway 8080:80 &
curl -s -X POST http://localhost:8080/azure/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<deployment>","messages":[{"role":"user","content":"ping"}],"max_tokens":5}' | jq .
```
Fail here → AgentgatewayBackend, UAMI, or Azure OpenAI issue. Check
`kubectl get agentgatewaybackend -n agentgateway-system` status and the
data-plane logs.

**Layer 1 — raw curl from a worker-cluster pod** (proves Istio + TLS + network path)
```bash
HOST=agentgateway.<wildcard-domain>
kubectl run tls-probe -n kagent --rm -it --restart=Never \
  --image=curlimages/curl --command -- \
  curl -sv https://$HOST/ -m 10 2>&1 | grep -iE 'SSL|TLS|subject|issuer|verify|HTTP/'
```
Fail here → DNS, network routing, or TLS trust. See TLS section below.

**Layer 2 — kagent A2A** (proves kagent + ModelConfig)
```bash
kubectl port-forward -n kagent svc/kagent-controller 8083:8083 &
curl -s -X POST "http://localhost:8083/api/a2a/kagent/$TEST_AGENT/" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send",
       "params":{"message":{"role":"user","parts":[{"kind":"text","text":"ping"}]}}}' \
  -m 120 | jq '.result.artifacts[0].parts[0].text, .error'
```
Fail here but Layer 1 works → kagent-specific: watch `kubectl logs -n kagent deploy/kagent-controller -f | grep -iE 'tls|x509|handshake|error'`

### TLS / certificate errors

| Symptom in curl -v or kagent logs | Cause | Fix |
|---|---|---|
| `unable to get local issuer certificate` | Corporate CA not in pod's trust store | Inject CA via ConfigMap + `SSL_CERT_FILE` env (see Helm overlay below) |
| `certificate signed by unknown authority` (Go) | Same as above | Same |
| `certificate is valid for X, not Y` | Wildcard cert doesn't cover the hostname | Use a hostname matching the wildcard; check cert SANs |
| `tls: handshake failure` / `EOF` | Istio sidecar intercepting or cipher mismatch | Check if kagent pod has an Istio sidecar; verify peer authentication policy |
| `connection refused` / `no route to host` | Network path broken (NSG, firewall, DNS) | `dig $HOST` from the pod; check AKS outbound routing |
| `context deadline exceeded` | Cold start or slow backend | Raise timeout on kagent / VirtualService |

**Corporate CA injection (Helm overlay):**
```bash
kubectl create configmap corp-ca-bundle -n kagent \
  --from-file=ca-bundle.crt=/path/to/corp-ca.pem

# kagent-values-ca.yaml:
# extraVolumes:
#   - name: corp-ca
#     configMap: { name: corp-ca-bundle }
# extraVolumeMounts:
#   - name: corp-ca
#     mountPath: /etc/ssl/certs/corp-ca.crt
#     subPath: ca-bundle.crt
#     readOnly: true
# env:
#   - name: SSL_CERT_FILE
#     value: /etc/ssl/certs/corp-ca.crt

helm upgrade kagent oci://ghcr.io/kagent-dev/kagent/helm/kagent \
  -n kagent -f kagent-values.yaml -f kagent-values-ca.yaml
kubectl rollout status deploy/kagent-controller -n kagent
```

### Ingress / VirtualService "route not found"

Almost always means: traffic reached Istio but no VS matched the Host header
OR traffic reached agentgateway but no HTTPRoute matches the path. See
`VALIDATE-MGMT.md` §11d test sequence to isolate.

```bash
# Verify the HTTPRoute is applied on the agentgateway side
kubectl get httproute -n agentgateway-system

# Verify Istio knows the VS
kubectl get virtualservice -n agentgateway-system agentgateway-vs -o yaml | yq .status
istioctl proxy-config route -n aks-istio-ingress \
  deploy/aks-istio-ingressgateway-external --name https.443 | grep -A5 "$HOST"
```

### Common gotchas

1. **`Route not found` / `failed to parse request: EOF`** — testing with GET or empty body. AI backends only accept POST with a valid chat-completions JSON body. Use `curl -X POST -H "Content-Type: application/json" -d '{"model":"...","messages":[...]}'`.

2. **`host`/`port` belong at `spec.ai.provider.*`, NOT inside `openai`/`azureopenai`** — webhook rejects nested. Always set them as siblings of the provider type object.

3. **Secret data key must be literally `Authorization`** — not `api-key`. Value is used verbatim as the `Authorization` HTTP header, so include the `Bearer ` prefix for AAD tokens.

4. **Envoy metrics port is 15020** (agentgateway-specific) — not 15090 (Istio default).

5. **AKS Istio add-on = separate mesh per cluster.** Worker reaches mgmt via HTTPS ingress, not mesh. AuthorizationPolicy must use source IP / API key / JWT — not ServiceAccount principals.

6. **Find the ingress IP for `--resolve` testing:**
   ```bash
   kubectl get svc -n aks-istio-ingress \
     aks-istio-ingressgateway-external \
     -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
   ```
   Then: `curl --resolve "$HOST:443:$IP" https://$HOST/...` to test before DNS is configured.

## Rollback

All agents back to the original ModelConfig (LiteLLM or whatever was there before):

```bash
for agent in $(kubectl get agent -n kagent -o name | sed 's|agent.kagent.dev/||'); do
  kubectl patch agent "$agent" -n kagent --type merge \
    -p '{"spec":{"declarative":{"modelConfig":"<previous-modelconfig-name>"}}}'
done
```

Leave agentgateway running during rollback — nothing routes to it once no
ModelConfig references it.
