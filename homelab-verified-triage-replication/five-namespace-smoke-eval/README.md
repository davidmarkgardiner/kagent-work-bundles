# Five-namespace smoke + evaluation

One self-contained folder to prove the triage pipeline end-to-end: drop one
non-destructive signal into each of **five real, allow-listed namespaces** (2
application-tier, 3 system-tier) and confirm **five GitLab tickets** come out
the other side, correctly routed and human-safe. Copy this folder down to work
and point the work agent at the overlay you want.

```
Alloy (collect) -> Vector (redact + classify) -> Kafka -> Argo Sensor
  -> kagent read-only triage (single agent, or one of four specialists)
  -> [optional] a2a evaluation gate -> GitLab ticket -> SRE review
```

## What deploys

| File | Purpose |
|------|---------|
| `base/10-smoke-signals.yaml` | 5 signals across 5 namespaces (4 synthetic Warning Events + 1 ERROR pod log). One distinct signal per namespace — clean 1:1, no duplicate-ticket storm. |
| `base/expected-outcomes.yaml` | The 5 expected tickets: pod → namespace → tier → signal → v3 domain. |
| `overlays/v2-home-replication/` | Deploy against the proven v2 single-triage path (this bundle's `config/`). |
| `overlays/v3-specialists/` | Deploy against the v3 four-specialist path (`../aks-platform-triage-specialists`). |
| `scripts/verify-smoke.sh` | Read-only GitLab check: one labelled ticket per pod + TL;DR / no-`n/a` / human-approval contract. |

## The five signals

| Namespace | Tier | Signal | Reason / log | v3 specialist |
|-----------|------|--------|--------------|---------------|
| `platform-test-app` | application | Event | `FailedScheduling` | scheduling-placement |
| `agentic-triage-proof` | application | Pod log | `ERROR ... control-plane dependency unavailable` | platform-health |
| `cert-manager` | system | Event | `FailedMount` | identity-certificate |
| `external-dns` | system | Event | `NetworkNotReady` | infrastructure-outage (network) |
| `monitoring` | system | Event | `OOMKilled` | platform-health |

All five namespaces are already in the **v2** worker Alloy allow-list
(`../config/01-alloy.yaml`), so v2 needs no collection change. Covers all four
specialist domains, exercising A2A routing (network specialist included).

## Deploy — v2 (proven, simplest)

```bash
# 1. Ensure the v2 flow is deployed:  kubectl apply -k ../config
# 2. (optional) evaluation gate:      kubectl apply -k ../a2a-evaluation-gate
# 3. Fire the corpus:
kubectl --context <ctx> apply -k overlays/v2-home-replication
# 4. Wait for the pipeline, then verify (read-only). v2 has no single smoke
#    label, so the verifier scans all open issues and matches by pod:
scripts/verify-smoke.sh --context <ctx> --path v2
# 5. Tear the fixtures down after SRE review:
kubectl --context <ctx> delete -k overlays/v2-home-replication
```

## Deploy — v3 (four specialists + network routing)

```bash
# Prereqs (see overlays/v3-specialists/kustomization.yaml):
#  - apply aks-platform-triage-specialists/agents.yaml (4 Agents Ready)
#  - extend the templated worker Alloy allow-list to all 5 namespaces
#    (overlays/v3-specialists/alloy-allowlist-snippet.yaml)
#  - deploy manifests/management (4 Sensors + A2A workflow) + GitLab creds
kubectl --context <ctx> apply -k overlays/v3-specialists
scripts/verify-smoke.sh --context <ctx> --path v3
kubectl --context <ctx> delete -k overlays/v3-specialists
```

## Evaluation status (read this)

- **v2 + evaluation gate: proven and included.** Apply `../a2a-evaluation-gate`
  alongside the v2 overlay. The triage caller delegates to the read-only
  `triage-evaluation-agent` over native A2A; Argo independently verifies the
  controller history holds a real tool call **and** a real evaluator Agent-tool
  call before accepting the verdict. PASS → normal ticket; three failed
  correction rounds → a `triage::evaluation-failed` ticket preserving evidence.
- **v3 specialists + evaluation gate: NOT yet wired.** The gate currently wraps
  the single v2 caller, not the four specialists. Combining them (add
  `triage-evaluation-agent` as an Agent tool to each specialist + a
  controller-history check in each Sensor) is real design work — see Next steps.

## Do not mix v2 and v3

The bundles use different payload/dedupe/fingerprint contracts and the repo
explicitly warns against copying templates between them. Deploy **one** overlay
per environment. This folder keeps them side by side only so work can choose.

## Verifying "N in = N out"

`scripts/verify-smoke.sh --path v2|v3` counts the expected pods from
`base/expected-outcomes.yaml` and requires one open GitLab issue whose
description contains `` `<pod>` `` (both paths wrap the pod name in backticks) for
each. Up to five expected; a missing one is a hard fail. It also enforces the
human-safety contract per path (TL;DR-first, no `n/a`, and the boundary string:
v2 "no change has been made", v3 "Plan only: human review"). v2 has no single
smoke label so it scans all open issues; v3 defaults to label `aks-triage-smoke`.
Strictly read-only.

Gotchas that break the 1:1:
- A namespace missing from the **collector allow-list** → its signal is never
  collected → missing ticket. (v2: all five already listed. v3: slot them in.)
- The single **pod-log** signal is only collected where the log allow-list
  selects that workload. On v3 (pod logs scoped to named platform workloads),
  confirm selection or treat that signal as v2-only.
- Adding a second signal to one pod ("both a log and an event") may dedupe to
  one ticket or produce two depending on the `incident_fingerprint`; keep it one
  signal per pod for a clean count.

## Next steps (not built here)

1. **Wire evaluation into the v3 specialists** so specialist tickets also pass
   the independent gate.
2. **Automate daily**: wrap the apply → wait → verify → delete cycle in a
   CronJob / Argo Workflow on the management cluster.
3. **Observability**: emit a smoke-pass metric + alert on missing/late tickets
   and on evaluation-failed volume, so a broken pipeline pages instead of going
   silently quiet.
