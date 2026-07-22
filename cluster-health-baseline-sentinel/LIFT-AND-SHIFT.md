# Lift and Shift — running this at work

## Recommended path: merge into `aks-certification`

Do this rather than deploying the standalone system. Three edits + a schedule:

```bash
# 0. PREREQUISITE — aks-certification cannot run today. Every check uses
#    bitnami/kubectl:latest, which no longer pulls. Fix that first or nothing
#    below works. 23 YAML manifests in this repo have the same reference.
grep -rl 'bitnami/kubectl' . --include='*.yaml'

# 1. The baseline check needs collect.py available in the workflow's namespace.
kubectl apply -f agents/cluster-health-sentinel/02-collector-configmap.yaml
#    ...and RBAC for whatever SA runs it (argo-events-sa on RED already had
#    configmap access in kagent; verify at work).
kubectl apply -f agents/cluster-health-sentinel/01-rbac.yaml

# 2. Apply the three edits to aks-certification. Diff against live first:
kubectl -n argo-events get workflowtemplate aks-certification -o yaml > current.yaml
#    then follow examples/aks-certification-baseline-patch.yaml:
#      EDIT 1 — add check-baseline to the DAG
#      EDIT 2 — generate-report gains baseline-result
#      EDIT 3 — add the check-baseline + escalate-to-agent templates

# 3. The orchestrator agent (dry-run first).
kubectl apply -f agents/cluster-health-sentinel/07-orchestrator-agent.yaml --dry-run=server
kubectl apply -f agents/cluster-health-sentinel/07-orchestrator-agent.yaml

# 4. The schedule — one CronWorkflow per target cluster.
kubectl apply -f examples/cronworkflow-certification.yaml
```

**Observe first.** Point `escalate-to-agent` at nothing (or leave the CronWorkflow
`suspend: true`) and run the workflow manually for a week. Read what
`check-baseline` reports before letting it page anyone. Every threshold in it is
a guess until your data says otherwise.

**Fire-once needs state.** `escalate-to-agent` writes
`cluster-health-cert-state-<cluster>` in the state namespace. Delete it and the
next run re-reports everything once — noisy, not wrong. Its SA needs configmap
get/create/update there.

---

## Standalone path (the reference implementation)

Source: `agents/cluster-health-sentinel/` (9 manifests + README). Proven
end-to-end on RED. Use this if the merge is blocked, or to understand the pieces.

## Variables to supply

| Placeholder | RED value | Notes |
|---|---|---|
| `{{KUBE_CONTEXT}}` | `red` | |
| `{{CLUSTER_NAME}}` | `red` | env var on the CronJob. **Set per cluster** — it labels every snapshot and is how a fleet agent tells workers apart |
| `{{KAGENT_NAMESPACE}}` | `kagent` | collector, snapshots, orchestrator |
| `{{ARGO_EVENTS_NAMESPACE}}` | `argo-events` | EventSource, Sensor, WorkflowTemplate |
| `{{ARGO_EVENTS_SA}}` | `argo-events-sa` | needs: get configmaps in kagent; list+patch workflows |
| `{{MODEL_CONFIG}}` | `default-model-config` | |
| `{{DELEGATION_AGENT}}` | `k8s-readonly-agent` | **must be genuinely read-only** — verify its `toolNames` |
| `{{GITLAB_SECRET_NAME}}` | `gitlab-credentials` | keys: `url`, `token`, `project-id` |
| `{{GITLAB_PROJECT_ID}}` | `68265584` | |
| `{{ADDON_NAMESPACES}}` | `kube-system,cert-manager,external-secrets,kyverno,kagent` | |

⚠️ **Secret name mismatch:** this bundle uses `gitlab-credentials`.
`agents/kagent-triage/02-workflow-kagent-triage.yaml` assumes `gitlab-token`.
Only `gitlab-credentials` exists on RED. Check which your work cluster has.

## Deploy order

```bash
# Phase 1 — snapshots only. No agent, no alerts, useful immediately.
kubectl apply -f 01-rbac.yaml -f 02-collector-configmap.yaml -f 03-cronjob.yaml

# Force a run instead of waiting for the schedule
kubectl -n kagent create job --from=cronjob/cluster-health-collector chc-manual-1

# Read the cluster picture
REF=$(kubectl -n kagent get cm cluster-health-snapshot-latest \
  -o jsonpath='{.data.pointer\.json}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["ref"])')
kubectl -n kagent get cm "$REF" -o jsonpath='{.data.snapshot\.json}' | python3 -m json.tool

# Phase 2 — detection + routing, OBSERVE MODE (no tickets)
kubectl apply -f 04-eventsource-webhook.yaml -f 05-sensor-cluster-health.yaml \
              -f 06-workflow-cluster-health-triage.yaml -f 08-alertmanager-route.yaml

# Phase 3 — the orchestrator. Dry-run FIRST.
kubectl apply -f 07-orchestrator-agent.yaml --dry-run=server
kubectl apply -f 07-orchestrator-agent.yaml
kubectl -n kagent wait --for=condition=Ready agent/cluster-health-orchestrator --timeout=120s
```

## Go live — the one switch

Phase 2 ships in **observe mode**: the workflow runs, the agent is called, the
verdict lands in the workflow log, and nothing else happens. Run it that way for
**1–2 weeks**, read the verdicts, tune `cluster-health-baselines` until the
breaches it reports are ones you'd actually want to wake someone for. Then:

```bash
# live
kubectl -n argo-events patch cm cluster-health-report-mode --type merge \
  -p '{"data":{"mode":"ticket"}}'

# rollback — no redeploy, no manifest surgery
kubectl -n argo-events patch cm cluster-health-report-mode --type merge \
  -p '{"data":{"mode":"log-only"}}'
```

## Stand it down

```bash
kubectl -n kagent patch cronjob cluster-health-collector -p '{"spec":{"suspend":true}}'
kubectl -n argo-events delete sensor,eventsource cluster-health-sentinel
```

Suspending the CronJob stops everything downstream — no snapshots, no
transitions, no workflows, no agent calls. The orchestrator Agent consumes zero
tokens while idle.

## Must fix before work deployment

1. **Authenticate the webhook.** The EventSource endpoint is open — anything
   in-cluster that reaches the Service can POST a fake breach and drive the
   agent. NetworkPolicy at minimum.
2. **Watch the watcher.** If the CronJob stops, snapshots stop and the system
   reports nothing — indistinguishable from a healthy cluster. Add a staleness
   check on the pointer's `capturedAt`.
3. **Sweep `bitnami/kubectl`.** 23 other YAML manifests in this repo still reference
   it; it no longer pulls.
4. **Verify the delegation target is read-only.** Check its `toolNames` for
   `k8s_apply_manifest`, `k8s_patch_resource`, `k8s_delete_resource`,
   `k8s_execute_command`.
5. **Right-size the agents.** kagent agents inherit a **100m CPU / 384Mi**
   controller default unless `spec.declarative.deployment.resources` is set.
   RED runs 31 agents = 3830m = 51% of the cluster. At fleet scale this is real
   money. Several agents already set it (`k8s-agent` 50m,
   `cluster-health-orchestrator` 10m) — it is a supported one-line CR edit.

## Work-environment differences to expect

| | RED | Work |
|---|---|---|
| Nodes | 1 (kind) | many — **multi-node paths are untested** |
| metrics-server | **absent** | probably present → `ip_capacity` and usage data become viable |
| Azure | none | AKS-MCP + workload identity → `ip_capacity` can be implemented |
| Alertmanager | untested here | route in `08-alertmanager-route.yaml` is unproven |
| Event volume | 858/859 Kyverno noise | different noise; **re-derive the exclusion list** |
| Scale | 3.9 KB snapshot | larger; watch the 200 KB cap and `truncated` |

**The exclusion list is environment-specific.** Do not copy RED's blindly — run
observe mode and find out what your clusters actually emit.

## Azure IP capacity

`collect_ip_capacity()` currently raises deliberately, so the section reports
`unavailable` rather than a misleading zero. To implement: give the collector SA
workload identity with reader on the subnet, then query via AKS-MCP or
`az network vnet subnet show`, returning free-IP count and percentage. The
`ip_free_pct` baseline (default 10) is already wired.

## Multi-cluster

See `ARCHITECTURE.md`. The short version: **run the collector and orchestrator on
every worker**; only verdicts cross to the management fleet agent, via
agentgateway `/a2a/fleet/*` with identity at Istio. Do not centralise the
orchestrator — `kagent-tools` is in-cluster only and will silently query the
wrong cluster.
