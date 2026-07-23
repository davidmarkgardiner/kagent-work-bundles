# Open Gaps and Inefficiencies — Tier 2 MCP Triage — 2026-07-10

Companion to `CRITIQUE-REVIEW-TIER-TWO-2026-07-10.md`. That doc audits claim
truthfulness; this one lists what's missing or wasteful even where the claims
hold up.

## Update: live cluster verification (2026-07-10)

This bundle was re-checked directly against the live `proxmox-k8s` cluster
(already the active `kubectl` context on this machine). Two items below that
were originally "unverifiable from repo" are now confirmed **true** — the
Tier 2 investigation is real, reproducible, and the task record
(`4c233da6-0083-4df5-af8b-a73031351bff`) matches the doc almost verbatim
(same pod, same 5 Loki lines, same exit code 42 / restart count 8 / `BackOff`
event, fetched independently). But the live check also surfaced two new,
higher-severity findings the source doc never mentions — an orphaned admin
ClusterRole and a stale `last-applied-configuration` annotation that could
silently regrant admin access. These are now the top items in the table below.

## Still Open

| Gap | Status | Required close evidence |
|---|---|---|
| **Stale `last-applied-configuration` on live `Deployment/aks-mcp`** | `live_regression_risk` (new, found via cluster check) | The annotation still encodes `--access-level=admin` even though the running spec is `readonly` — the fix was a live edit/patch, not a re-`apply`. A future `kubectl apply -f` from whatever file produced that annotation silently reverts to admin. Re-apply the corrected manifest properly, or bring the Deployment under the same (currently nonexistent) Helm release as its RBAC. |
| **Orphaned `ClusterRole/aks-mcp-admin`** | `live_latent_risk` (new, found via cluster check) | The admin role (`verbs: ["*"]` on pods/secrets/deployments/etc.) still exists, just unbound. One new `ClusterRoleBinding` away from full admin again. Delete the ClusterRole, not just its binding. |
| **No Helm release backs the aks-mcp resources** | `live_gap` (new, found via cluster check) | ClusterRole/ClusterRoleBinding/ServiceAccount carry `app.kubernetes.io/managed-by: Helm` + `helm.sh/chart: aks-mcp-0.2.0` labels, but `helm history aks-mcp -n aks-mcp` returns "release: not found" and `helm list -A` has no `aks-mcp` entry. No rollback path exists for these objects today. |
| `aks-mcp-readonly` RemoteMCPServer manifest | `works_live_not_committed` | Confirmed live via `kubectl get remotemcpserver -n kagent`: `aks-mcp-readonly` exists, `ACCEPTED: True`, and successfully served the real `call_kubectl` calls in the task record. But no `kind: RemoteMCPServer` for it exists anywhere in the repo. Commit the manifest or a chart template for it. |
| Automatic Kafka/workflow dispatch into the Tier 2 agent | `not_proven` (doc says so itself) | Wire the alert consumer or Argo workflow to call this agent with the alert-metadata contract; record Kafka offset/workflow UID alongside the A2A task ID. |
| A2A non-streaming HTTP 500 root cause / version | `partially_proven` | Live check confirms the deployed version: `kagent` Helm release `kagent-v0.7.13`, images `ghcr.io/kagent-dev/kagent/{controller,app}:0.7.13`. The failure mode matches a known, already-mitigated bug class (`_agent_executor.py:175-200`, issue #1276), but this repo checkout has no tags to confirm whether 0.7.13 already ships that guard. |
| Raw tool-call evidence in the source doc | `not_pasted_but_now_independently_confirmed` | The doc itself still doesn't quote pod-state JSON, event text, or Loki response bodies. This is no longer a truth question — a direct fetch of task `4c233da6-...` from `kagent-controller`'s API, plus an independent Loki query for `tier2-20260710112153`, both reproduced the doc's exact numbers. It's still a self-containedness gap for readers without cluster access. |

## Now Addressed (confirmed correct)

| Item | Status | Evidence |
|---|---|---|
| `pods/log` RBAC grant | `proven` | `git diff platform/aks-mcp/chart/templates/rbac.yaml` adds the resource/verb cleanly; live `ClusterRole/aks-mcp` has it. |
| `--access-level` readonly wiring | `proven_live` | Live `Deployment/aks-mcp` actual args are `--access-level=readonly`, confirmed by direct `kubectl get`. |
| Admin ClusterRoleBinding removed | `proven_live` | Only live binding is `aks-mcp -> ClusterRole/aks-mcp` (readonly); no binding to `aks-mcp-admin` exists. (Role itself is orphaned, not deleted — see gap above.) |
| `--allowed-hosts` grafana-mcp flag works | `proven_live` | Live `Deployment/kagent-grafana-mcp` runs with this flag; pod is `1/1 Running`, 0 restarts, logs show continuous successful MCP session connects for the last hour. |
| Tier 2 investigation itself (core claim) | `proven_live` | Independently fetched task `4c233da6-...` from `kagent-controller` and re-ran the Loki query myself — both match the doc's narrated evidence almost verbatim. |
| Agent tool allowlist matches claimed call shapes | `proven` | `examples/kagent/tier-two-mcp-triage-agent.yaml:38-51`; live task record shows all four calls with `isError:false`. |
| Bundle file-presence gate | `proven` | `bash scripts/verify-bundle.sh` → exit 0, `ok`. |

## Inefficiencies (works today, but fragile or wasteful)

1. **No programmatic score for Tier 2 runs.** `scripts/score-smoke-run.py`'s
   `WEIGHTS` schema (`failure_injected`, `grafana_alert_firing`,
   `webhook_delivered`, `workflow_created`, `eval_published`, ...) models the
   alert→workflow→HITL chain and has no concept of a Tier 2
   investigation-only run. The doc's "Programmatic Gate 7/7" table is
   hand-typed prose, not machine-computed, and there's no
   `examples/score/*.json` artifact for it (compare
   `examples/score/proxmox-2026-07-09-smoke-run.json`, which exists for the
   07-09 runs). A future edit could silently change the "7/7" claim with
   nothing to catch it.

2. **`prompts/CRITIQUE-PROMPT.md`'s reading list is stale.** Its `Read:` block
   (lines 11-29) does not include
   `evidence/PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md`,
   `evidence/PROXMOX-LGTM-BRIDGE-LIVE-PREFLIGHT-2026-07-10.md`, or any
   `examples/kagent/*.yaml`. Running the bundle's own independent-review
   process today would silently skip auditing the RBAC security fix, the MCP
   host-allowlist claim, and the Tier 2 A2A reliability finding entirely.

3. **`scripts/verify-bundle.sh`'s content needles don't cover Tier 2.** The
   Python needle check (lines 60-68) only requires terms like
   `metric-crashloop`, `log-errorburst`, `agent_lifecycle_eval_score`. A future
   edit that guts the Tier 2 section's content (while leaving the file present
   for the file-existence gate) would still pass `verify-bundle.sh`.

4. **Same-day sibling docs aren't wired into the bundle gate yet.**
   `LGTM-EVIDENCE-BRIDGE-GAP.md`, `evidence/PROXMOX-LGTM-BRIDGE-LIVE-PREFLIGHT-2026-07-10.md`,
   and `examples/monitoring/promtail-smoke-namespace-values.yaml` are new,
   untracked files from the same work session but are absent from
   `scripts/verify-bundle.sh`'s `required_files` list — unlike the Tier 2
   files, which were correctly added. Low risk today (nothing deletes them),
   but inconsistent with how the Tier 2 files were handled.

5. **No image/version pinning anywhere in the evidence doc.** Neither the
   kagent runtime, the AKS MCP image, nor the grafana-mcp image tag under test
   is recorded. Live check closed this for kagent itself (`0.7.13`,
   confirmed via `kubectl get deploy`/`helm list`) — but the doc should have
   stated it, not left it for a reviewer with cluster access to go find.

6. **The live fix has no GitOps/Helm safety net.** (new, found via cluster
   check) The `aks-mcp` Deployment's `last-applied-configuration` annotation
   is stale (still says `--access-level=admin`) and the RBAC objects that do
   carry Helm ownership labels aren't backed by an actual Helm release
   (`helm history aks-mcp -n aks-mcp` → not found). There is currently no
   single command that reliably reapplies "the corrected state" to this
   cluster — everything from here depends on remembering to `kubectl edit`
   the right field by hand again.

## Claim Discipline

Matching this bundle's existing convention. Live cluster verification upgraded
several items from "not independently verifiable" to "proven" — the honest
current claim is now:

```text
metadata-only investigation via Grafana MCP + read-only AKS MCP is proven for one
  run, independently reproduced (task 4c233da6-..., matching Loki query, matching
  pod-state read);
the RBAC pods/log grant, the admin-binding removal, and the Grafana MCP
  host-allowlist fix are all proven live, not just in committed chart source;
the orphaned admin ClusterRole and the stale last-applied-configuration on the
  live Deployment are new, unresolved regression risks this proof did not surface;
the AKS MCP tool has no committed RemoteMCPServer manifest, so this proof is not
  yet reproducible from the repo alone, even though it works live today;
automatic alert/Kafka dispatch into this agent remains open;
the deployed kagent version (0.7.13) is now known, but whether it already
  contains the CancelledError fix for the intermittent A2A HTTP 500 is not.
```
