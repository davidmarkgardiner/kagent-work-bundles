# Application onboarding acceptance checklist

Status values: `NOT_RUN`, `PASS`, `FAIL`, `BLOCKED`. Do not replace `NOT_RUN`
with `PASS` because a manifest rendered or a resource reported Ready.

## Phase 0 contract

| Check | Expected evidence | Owner | Status |
|---|---|---|---|
| Installed versions/CRDs recorded | Agentgateway, Gateway API, kagent, Istio and CNI versions plus server-side schema queries | `{{PLATFORM_AGENTGATEWAY_OWNER}}` | NOT_RUN |
| Caller identity contract | ServiceAccount, UAMI, exact federation subject, gateway audience and assigned roles; no secret/token value | `{{ENTRA_APPLICATION_ADMIN_OWNER}}` | NOT_RUN |
| JWKS path | Owner, DNS/egress, CA trust, cache, rollover and fail-closed alert | `{{PLATFORM_AGENTGATEWAY_OWNER}}` | NOT_RUN |
| Model Garden contract | Endpoint type, API shape, model, region, audience/scope, accepted backend identity and billing owner | `{{MODEL_GARDEN_OWNER}}` | NOT_RUN |
| MCP contract | Server/version, exact tools, backend identity and resource/data boundary | `{{POSTGRES_DATA_OWNER}}` | NOT_RUN |
| Network contract | Application-to-gateway allowed; direct provider/MCP bypass denied | `{{NETWORK_OWNER}}` | NOT_RUN |
| Data contract | Classification, prompt/result logging and audit metadata approved | `{{SECURITY_APPROVER}}` | NOT_RUN |

## Model route allow and deny

| Test | Expected result | Status |
|---|---|---|
| No bearer token | `401` before backend invocation | NOT_RUN |
| Invalid/wrong-audience token | `401` before backend invocation | NOT_RUN |
| Valid caller, approved route/model | Successful provider response attributed to caller and route | NOT_RUN |
| Valid caller, unapproved route/model | `403` or equivalent policy denial | NOT_RUN |
| Caller UAMI directly invokes Model Garden | Azure/provider authorization denial or network block | NOT_RUN |
| Backend UAMI obtains provider token | Approved route succeeds without application receiving provider credential | NOT_RUN |
| Fresh token after app-role removal | Role absent and new access denied after documented propagation | NOT_RUN |
| Cached token issued before role removal | Residual access matches documented expiry unless gateway caller deny is active | NOT_RUN |
| Immediate incident deny | Gateway caller deny blocks the already-issued token on every applicable route | NOT_RUN |

## MCP allow and deny

| Test | Expected result | Status |
|---|---|---|
| Gateway `tools/list` | Exactly `list_schemas`, `list_tables`, `describe_table` | NOT_RUN |
| `list_schemas` or `describe_table` | Successful metadata-only response | NOT_RUN |
| Unapproved tool such as `run_select` | Hidden from discovery and denied when called directly | NOT_RUN |
| Alternative database/resource target | Denied by MCP identity/backend authorization | NOT_RUN |
| Direct application-to-MCP Service | Network/identity denial | NOT_RUN |
| MCP credential exposure | Credential absent from application, Agent and evidence | NOT_RUN |

## Resilience and audit

| Test | Expected result | Status |
|---|---|---|
| Gateway restart/policy reload | Existing denials remain effective; no observed fail-open window | NOT_RUN |
| Token expires during established stream | Deterministic outcome recorded; client refresh/reconnect tested | NOT_RUN |
| Local rate limit | Limit/metric observed and replica-scoped behaviour documented | NOT_RUN |
| Audit record | Caller, route, model/tool, decision, usage, latency and outcome present | NOT_RUN |
| Redaction | No bearer token, credential, prompt, response, tool argument or tool result retained | NOT_RUN |
| Offboarding | Roles/routes/grants removed and both routine/immediate denial paths evidenced | NOT_RUN |

## Acceptance decision

```text
Decision: {{ACCEPTED|REJECTED|BLOCKED}}
Application owner: {{APPLICATION_OWNER}}
Platform owner: {{PLATFORM_AGENTGATEWAY_OWNER}}
Security approver: {{SECURITY_APPROVER}}
Evidence location: {{OWNER_APPROVED_EVIDENCE_LOCATION}}
Review/expiry date: {{ACCESS_REVIEW_DATE}}
Outstanding blockers: {{BLOCKERS}}
```
