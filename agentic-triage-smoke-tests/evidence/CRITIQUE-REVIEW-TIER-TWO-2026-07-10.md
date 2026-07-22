# Critique Review: Tier 2 MCP Triage Proof — 2026-07-10

Independent read-only verification of `evidence/PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md`
against the committed repo state. Method: read the target doc, then check every
checkable claim against the actual files it cites (`git diff`, `find`, direct
reads) plus one external check (upstream `grafana/mcp-grafana` flag docs) for
the one claim the repo cannot settle by itself. No files were edited. Absent
evidence is treated as not proven, matching `prompts/CRITIQUE-PROMPT.md`'s
existing rule for this bundle.

```text
VERDICT: revise
```

## Verdict reason

Update: this review was re-run with live access to the `proxmox-k8s` cluster
(the same cluster the evidence doc describes). The core investigation claim is
now independently confirmed, not just internally consistent — see "Live
independent verification" below. Two claims originally marked `not_proven`
from repo-only analysis are now confirmed **true** by live cluster state. The
live check also surfaced a new, higher-severity gap the doc does not mention:
a stale `kubectl.kubernetes.io/last-applied-configuration` annotation on the
live `aks-mcp` Deployment that still encodes `--access-level=admin`.

Remaining reasons for `revise` rather than `pass`: one reusability claim is
still contradicted by the repo (no committed manifest wires the
`aks-mcp-readonly` `RemoteMCPServer`, even though it demonstrably exists and
works live); the doc itself still carries materially less raw evidence
(pasted command output, JSON, response bodies) than its same-day sibling
(`evidence/PROXMOX-LGTM-BRIDGE-LIVE-PREFLIGHT-2026-07-10.md`); and the newly
found stale last-applied-config / orphaned admin ClusterRole are real,
unresolved drift risks in the live environment.

## Live independent verification (cluster access, 2026-07-10)

Context `proxmox-k8s` was already the active `kubectl` context on this
machine — this is the same cluster the evidence doc describes. Verified
directly, without reusing anything from the doc's own narrative:

- **Task record fetch.** Queried `kagent-controller`'s API directly
  (`http://kagent-controller.kagent:8083/api/tasks/4c233da6-0083-4df5-af8b-a73031351bff`
  from an in-cluster debug pod) and got back the real task: `state: completed`,
  pod `podinfo-smoke-crashloop-7bc6cdb585-r74c9` in namespace
  `agentic-triage-event-smoke`, image `busybox:1.36` on node `k8s-worker1`.
  The returned tool-call history shows one real `query_loki_logs` call and
  three real `call_kubectl` calls, matching the doc's claimed shapes exactly,
  with `isError: false` on all four responses (the doc asserted this; the raw
  JSON confirms it).
- **Independent Loki query.** Queried Loki directly myself (not the cached
  task result) for `{...} |= "tier2-20260710112153"` and got back the same
  five `AGENTIC_TRIAGE_SMOKE_ERROR ... seq=1..5` lines, with the same stream
  labels (`cluster=proxmox-k8s`, `pod=podinfo-smoke-crashloop-7bc6cdb585-r74c9`,
  `source_type=logs`).
- **Independent pod-state read.** The task record's `call_kubectl` response for
  the pod-state read literally is `Running   CrashLoopBackOff   Error   42    8`
  — phase, waiting reason, last termination reason, exit code, and restart
  count all match the doc's narrated numbers exactly.

This confirms the doc's central claim (metadata-only investigation via
Grafana MCP + AKS MCP, correctly correlated) really happened as described, on
a real cluster, with a real task ID. The doc's weakness was never that it was
untrue — it's that it didn't paste this primary evidence itself.

## Claims audit

- claim: "`aks-mcp-readonly` was named read-only but the deployment used
  `--access-level=admin`" and the RBAC/values fix corrects this
  (PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md:95-108)
  status: proven
  evidence:
    - `examples/kagent/aks-mcp-readonly-values.yaml:9` — `accessLevel: readonly`
    - `platform/aks-mcp/chart/templates/deployment.yaml:51-52` — `--access-level {{ .Values.app.accessLevel }}` is the real CLI arg this value drives
  gap: none — the CLI flag and the values fix are real and connected.

- claim: "The read-only ClusterRole did not grant `pods/log`... The corrected
  state: its service account can get pods, `pods/log`, and events."
  (PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md:96-97,105)
  status: proven
  evidence:
    - `git diff platform/aks-mcp/chart/templates/rbac.yaml` adds
      `resources: ["pods/log"]` / `verbs: ["get"]` to the unconditional
      (all-access-level) rule block
  gap: none.

- claim: "The admin ClusterRoleBinding was removed."
  (PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md:108)
  status: proven (live cluster check, upgraded from `not_proven`)
  evidence:
    - Live cluster has a `ClusterRole/aks-mcp-admin` (created
      `2026-02-17T11:13:01Z`, `verbs: ["*"]` on pods/secrets/deployments/etc,
      applied via raw `kubectl apply`, not Helm) — this is the original admin
      role the pre-fix Deployment ran under.
    - The only live `ClusterRoleBinding` touching `aks-mcp` is
      `clusterrolebinding.rbac.authorization.k8s.io/aks-mcp`, created
      `2026-07-10` (today, matching the fix timeline), bound to
      `ClusterRole/aks-mcp` (the readonly-tiered one), subject
      `ServiceAccount aks-mcp/aks-mcp`. No binding to `aks-mcp-admin` exists.
  gap: the claim is true — the binding to the admin role is gone — but
  `ClusterRole/aks-mcp-admin` itself was **not deleted**, only unbound. It's
  orphaned, not removed: anyone who later applies a `ClusterRoleBinding`
  referencing it (accidentally or otherwise) regrants admin instantly with no
  new review step. Recommend deleting the orphaned `ClusterRole/aks-mcp-admin`
  outright, not just its binding.

- claim: "Grafana MCP rejected the Kubernetes service Host header with HTTP
  403... Grafana MCP explicitly allows only its Kubernetes service hostnames"
  via `--allowed-hosts` (PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md:99,109;
  `examples/kagent/grafana-mcp-host-validation-values.yaml:7`)
  status: proven (live cluster check, upgraded from `not_proven`)
  evidence:
    - Grafana's own command-line-flags documentation for `grafana/mcp-grafana`
      does not list `--allowed-hosts` — public docs are incomplete here, not
      wrong; see live evidence below.
    - Live `kagent-grafana-mcp` Deployment's actual container args:
      `["--transport","streamable-http","--allowed-hosts","kagent-grafana-mcp.kagent:8000,kagent-grafana-mcp.kagent.svc:8000,kagent-grafana-mcp.kagent.svc.cluster.local:8000"]` —
      exactly the values from `examples/kagent/grafana-mcp-host-validation-values.yaml:7-8`.
    - Pod is `1/1 Running`, 0 restarts, and its live logs show a continuous,
      unbroken stream of `msg="connected to proxied MCP servers"` lines every
      ~60s over the last hour with no Host-header rejection errors — the
      binary accepts the flag and is not crash-looping or erroring on it.
  gap: none remaining on "does the flag work here." The only residual gap is
  that this behavior is undocumented upstream, so a future `mcp-grafana` image
  bump could silently drop or rename the flag with no compile-time or
  chart-level warning; worth a comment in the values file pointing at the
  actual working config (this comment) since the public docs won't back it up.

- claim: "AKS MCP made three bounded read-only calls" / Grafana MCP made "one
  bounded call" and all four returned `isError: false`
  (PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md:47-66)
  status: proven (live cluster check, upgraded from `partially_proven`)
  evidence:
    - `examples/kagent/tier-two-mcp-triage-agent.yaml:38-51` — the Agent's tool
      allowlist matches (`query_loki_logs` from `kagent-grafana-mcp`,
      `call_kubectl` only from `aks-mcp-readonly`).
    - Live task record `4c233da6-0083-4df5-af8b-a73031351bff` (fetched
      directly from `kagent-controller`'s API) contains the raw
      `function_call`/`function_response` pairs for all four calls, each with
      `"isError":false` present in the actual JSON, not just asserted.
  gap: none in truth. Process gap remains: the source doc itself still doesn't
  paste this JSON (contrast
  `evidence/PROXMOX-LGTM-BRIDGE-LIVE-PREFLIGHT-2026-07-10.md:153-164`, which
  does paste raw stream labels/JSON) — it's independently verifiable by
  someone with cluster access, but not self-contained on the page.

- claim: intermittent "HTTP 500 after completion because kagent raised a
  cleanup `CancelledError`" during non-streaming A2A calls
  (PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md:16,158-161)
  status: plausible / partially_proven
  evidence:
    - `kagent/python/packages/kagent-adk/src/kagent/adk/_agent_executor.py:175-200`
      — a top-level guard exists specifically because "CancelledError can
      escape from multiple places... This top-level guard ensures
      CancelledError never propagates... which would produce a 500 Internal
      Server Error."
    - `kagent/python/packages/kagent-adk/src/kagent/adk/_agent_executor.py:280-309`
      (`_safe_close_runner`) references a known issue,
      `github.com/kagent-dev/kagent/issues/1276`, for exactly this
      "MCP session cleanup... anyio CancelScope violations" class of bug.
  gap: this claim matches a real, already-mitigated bug class in this repo, so
  it is credible. Live check found the actual deployed version: `kubectl get
  deploy kagent-controller -n kagent` and the agent pod both run
  `ghcr.io/kagent-dev/kagent/app:0.7.13` / `controller:0.7.13` (helm release
  `kagent`, chart `kagent-v0.7.13`). This repo checkout has no tags to diff
  `_agent_executor.py`'s guard against that specific release, and I don't have
  a way from here to confirm whether upstream issue #1276's fix shipped in or
  before 0.7.13. Either way, the doc should have stated "0.7.13" itself —
  that's a one-line addition that turns "unknown vintage" into "checkable."

- claim: "Reusable configuration is in:" lists four files as sufficient to
  reproduce the fix (PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md:113-120)
  status: not_proven
  evidence:
    - `examples/kagent/tier-two-mcp-triage-agent.yaml:45-51` references
      `kind: RemoteMCPServer, name: aks-mcp-readonly`.
    - `find platform/aks-mcp` shows only `deployment.yaml`, `service.yaml`,
      `ingress.yaml`, `rbac.yaml`, `secret.yaml`, `serviceaccount.yaml` — no
      `RemoteMCPServer` template.
    - By contrast `kagent/helm/tools/grafana-mcp/templates/remotemcpserver.yaml`
      *does* commit a `RemoteMCPServer` for the Grafana MCP side.
  gap: confirmed live — `kubectl get remotemcpserver -n kagent` shows
  `aks-mcp-readonly` really exists and is `ACCEPTED: True`, pointing at
  `http://aks-mcp.aks-mcp.svc:8000/mcp`, and it demonstrably works (the task
  record shows successful `call_kubectl` calls through it). So the *live
  system* is fully wired and functioning — but there is still no committed
  manifest anywhere in the repo that creates this `RemoteMCPServer`. Someone
  replaying this proof from exactly the four listed files cannot reproduce
  the tool wiring; that CRD was hand-applied live and isn't in the "reusable
  configuration" list. Add it (or a chart template that generates it).

- claim (not in source doc — found during live verification): the AKS MCP
  Deployment's fix is durable across redeploys.
  status: not_proven / contradicted
  evidence:
    - `kubectl get deploy aks-mcp -n aks-mcp -o jsonpath='{.metadata.annotations}'`
      shows `kubectl.kubernetes.io/last-applied-configuration` still containing
      `"args":["--access-level=admin","--transport=streamable-http",...]` —
      the **pre-fix** manifest — even though the Deployment's actual live
      `spec.template.spec.containers[0].args` is
      `["--access-level=readonly",...]`.
    - The Deployment carries no Helm labels at all (`{"app":"aks-mcp"}` only),
      while the ClusterRole/ClusterRoleBinding/ServiceAccount do carry
      `app.kubernetes.io/managed-by: Helm` + `helm.sh/chart: aks-mcp-0.2.0`
      labels — yet `helm history aks-mcp -n aks-mcp` returns `Error: release:
      not found` and `helm list -A` has no `aks-mcp` entry anywhere.
  gap: the readonly fix was applied by an imperative edit/patch (not
  `kubectl apply -f`), so the last-applied-configuration annotation was never
  updated. If anyone runs `kubectl apply -f` again using whichever local file
  produced that stale annotation, it will silently revert the Deployment to
  `--access-level=admin` with no diff to review, no PR, and no Helm release to
  roll back against (there isn't one). This is a live, currently-latent
  regression risk in the cluster today, not just a documentation gap. See
  `OPEN-GAPS-TIER-TWO-2026-07-10.md` for the recommended fix.

## File-level checks (all confirmed)

- `bash scripts/verify-bundle.sh` → `agentic triage smoke bundle verification: ok` (exit 0).
- All three `examples/kagent/*.yaml` files referenced by the doc exist and
  match the doc's description of their contents.
- `evidence/PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md` and the three
  `examples/kagent/*.yaml` files are already in `scripts/verify-bundle.sh`'s
  `required_files` list (lines 18, 31-33), so the bundle check would fail if
  any were deleted.

## Recommended patches

- path: live cluster, `ClusterRole/aks-mcp-admin`
  change: delete the orphaned admin ClusterRole outright — unbinding it was
  not enough, it's still one `ClusterRoleBinding` away from full admin again.
- path: live cluster, `Deployment/aks-mcp -n aks-mcp`
  change: re-apply the corrected manifest via `kubectl apply -f` (not a live
  edit/patch) so `last-applied-configuration` stops encoding
  `--access-level=admin`, or bring the Deployment under the same Helm release
  as the RBAC objects so there's one source of truth and a rollback path.
- path: `evidence/PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md:108`
  change: cite the live before/after (`ClusterRole/aks-mcp-admin` unbound,
  not deleted) instead of the current unqualified "removed."
- path: `evidence/PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md:113-120`
  change: add the `RemoteMCPServer` manifest for `aks-mcp-readonly` (it exists
  and works live, confirmed via `kubectl get remotemcpserver`, but nothing
  commits it) to the reusable-configuration list.
- path: `evidence/PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md:158-161`
  change: record the kagent image tag under test (`0.7.13`, confirmed live)
  and link `github.com/kagent-dev/kagent/issues/1276`.
