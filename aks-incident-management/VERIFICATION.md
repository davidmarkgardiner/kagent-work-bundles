# Verification record

Date: 2026-09-13

## Passed locally

- `npm test`: 16/16 application and lifecycle tests passed.
- The tests cover normalization, stable ids, duplicate delivery, approval binding, expired approval, exact-action execution, post-change verification, merge-request approval, read-only tool inventory, persistence failure recovery, HTTP authorization, and serialized kagent calls.
- `docker build -t aks-incident-coordinator:work-bundle-check image`: passed. Final local image manifest was built successfully.
- Postgres 17 container smoke: schema initialization, first claim, duplicate claim, and delivery count passed with `POSTGRES_STORE_OK`.
- `envsubst` plus Ruby YAML stream parsing: all seven rendered manifest files passed.
- The live `red` pass found and fixed unrestricted `envsubst` expansion of Workflow runtime variables. Rendering now substitutes only the declared installation variables.
- Kubernetes server-side dry-run with conflict takeover simulated against context `red`: all seven rendered manifest templates were accepted by the installed Kubernetes, Argo Workflows, Argo Events, and kagent APIs. Existing client-side field ownership produced non-fatal migration warnings; no dry-run change was persisted.
- Repository public-safe scan against the bundle: passed.
- `git diff --check`: passed.

## Passed in the `red` local lab

- Installed the runtime into the isolated `incident-management-lab` namespace with Postgres, coordinator, a dedicated harmless target, Argo Workflow/EventSource/Sensors, and separate read-only and write-capable kagent identities.
- Used the existing local Redpanda broker as the Kafka-compatible ingress. The successful synthetic event was produced to `incident-approval-demo`, partition `0`, offset `11`.
- Argo created Workflow `incident-local-p8j9c`; incident intake resolved to `inc_b7e9802b41aa` and a live `k8s-readonly-agent` investigation confirmed the missing label without changing the cluster.
- The Workflow suspended at `human-approval`. `lab-responder` approved action `733a2700-f80b-469b-92aa-4ccec4d65036`, after which the Argo Events callback resumed that exact Workflow as `system:serviceaccount:argo-events:argo-events-sa`.
- The separate `incident-action-executor` loaded one MCP toolset, called the read tool and then the bounded write tool, and changed only `incident-management-lab/deployment/label-remediation-target`.
- Live authorization checks showed the executor ServiceAccount can patch that named target but cannot patch `incident-coordinator`; the coordinator ServiceAccount cannot patch Deployments.
- The execution receipt records the label as absent before and `checkout-worker-lab` afterwards on both Deployment and pod template, with resource version `440975256`, `executed=true`, and `idempotent_replay=false`.
- Independent read-only post-change verification completed. Workflow `incident-local-p8j9c` reached `Succeeded`, the incident reached `resolved`, Deployment generation `2` was observed, and the replacement pod was Ready with the expected label.
- External GitLab, Teams, ServiceNow, and Confluent endpoints were deliberately disabled; the lab run made no external ticket, notification, or merge-request write.

## Failures retained as evidence

- `incident-local-x4vmg` failed because unrestricted `envsubst` consumed shell variables inside the Workflow template. The renderer now has an explicit installation-variable allow-list.
- `incident-local-vtfmr` stopped when its ServiceAccount could not create Argo `workflowtaskresults`. The Workflow template now supplies the required namespaced RBAC.
- `incident-local-mkgqg` reached and resumed the approval gate but failed closed before mutation because the executor agent had started without an MCP toolset. The MCP process was also inheriting the coordinator image's port `4173` while the Service targeted `8080`. The manifest now pins `PORT=8080`, and executor infrastructure and Agent are separate install steps so the MCP rollout is proven Ready before kagent starts.

## Not claimed

- No image was pushed to a registry.
- No manifest was applied to a work cluster.
- Confluent, Teams, ServiceNow, and GitLab MCP were not exercised against work endpoints.
- The local lab exercised kagent and Kubernetes MCP behavior only; this does not prove work-cluster connectivity, credentials, policy, or relay behavior.
- The approval callback still requires the work gateway or service mesh to authenticate the Teams relay.
- No work issue or merge request was created.

## Required work acceptance evidence

Capture all of the following from a non-production run before enabling the executor in production:

1. Kafka produced and consumed topic/partition/offset.
2. Argo Workflow node table showing the 72-hour suspend and authenticated resume or stop.
3. Coordinator incident record and audit rows.
4. Read-only kagent tool inventory and complete investigation trace.
5. GitLab issue and, for the GitOps flow, draft MR and exact approved SHA.
6. Resolved Teams approver identity and callback receipt.
7. Bounded executor input, tool call, output, and Kubernetes resource version or GitLab merge commit.
8. Independent read-only post-change verification.
9. ServiceNow record update on the same incident id.
10. Negative tests for stale action id, expiry, changed Kubernetes state, changed MR SHA, failed pipeline, duplicate delivery, and rejected approval.
