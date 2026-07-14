# Signal Coverage — are we missing anything that should fire?

Goal: make sure the golden-path namespace catches **everything that means the
app is going wrong** — at log level and at event level — before we duplicate it
to other namespaces. A signal that never enters Vector, or that Vector/Argo
filters drop, never reaches a workflow and never reaches a specialist agent.

Two filters decide what gets through today. **Both are narrower than "anything
suggesting something is wrong."** Widen and re-prove them on the golden
namespace, then every other namespace inherits the corrected set.

---

## 1. Log-level coverage

Current log filter (`reference-config/02-vector.yaml`, `incident_signals`):

```text
(?i)(error|exception|fatal|failed|back-off|crashloop)
```

That catches classic error words but **misses** common "something is wrong"
signals:

| Should fire | Caught today? |
|---|---|
| `error`, `exception`, `fatal`, `failed`, `crashloop` | ✅ |
| `panic`, `segfault`, `traceback`, `stack trace` | ❌ |
| `timeout`, `timed out`, `deadline exceeded` | ❌ |
| `connection refused`, `refused`, `unreachable`, `unavailable` | ❌ |
| `denied`, `unauthorized`, `forbidden`, `403`/`401` | ❌ |
| `OOM`, `out of memory`, `killed` | ❌ |
| `deadlock`, `cannot`, `unable to` | ❌ |
| HTTP `500`/`502`/`503`/`504` | ❌ |
| structured levels: `level=error`, `"level":"error"`, `severity=critical` | ❌ |

Recommended widened log regex (tune per app — too broad = noise):

```text
(?i)(error|err|exception|fatal|panic|failed|fail|crashloop|back-?off|segfault|
traceback|timeout|timed out|deadline exceeded|refused|unreachable|unavailable|
denied|unauthorized|forbidden|deadlock|out of memory|oom|killed|
"level"\s*:\s*"(error|fatal|critical)"|level=(error|fatal|critical)|
severity=(error|critical)|\b(500|502|503|504)\b)
```

---

## 2. Event-level coverage

Current event allow-lists — and they do **not** match each other:

| Layer | Reasons allowed |
|---|---|
| Vector `incident_signals` | `BackOff, Failed, FailedScheduling, OOMKilled, OOMKilling, Unhealthy` |
| Argo event sensor | `BackOff, Failed, FailedScheduling, OOMKilled, Unhealthy` |

**Bug:** Argo drops `OOMKilling` that Vector permits — an OOMKilling event
passes Vector then dies at Argo. Align the two lists.

Common actionable **Warning** events not covered today:

| Should fire | Class |
|---|---|
| `Evicted` | node pressure |
| `FailedMount`, `FailedAttachVolume` | storage |
| `FailedCreatePodSandBox`, `NetworkNotReady` | CNI / runtime |
| `ErrImagePull`, `ImagePullBackOff` | registry |
| `NodeNotReady`, node-condition events | node health (DS-04 wants a node class) |
| `Preempted` | scheduling |
| `ProbeWarning`, `Unhealthy` (have) | health checks |
| `FailedSync`, `FailedKillPod`, `FailedCreate` | controller |

Recommended widened, **aligned** event reason list (Vector == Argo):

```text
BackOff, Failed, FailedScheduling, OOMKilled, OOMKilling, Unhealthy,
Evicted, FailedMount, FailedAttachVolume, FailedCreatePodSandBox,
NetworkNotReady, ErrImagePull, ImagePullBackOff, NodeNotReady,
Preempted, ProbeWarning, FailedSync, FailedKillPod, FailedCreate
```

Keep the **Warning-only** rule — Normal lifecycle events must stay filtered out
(the red proof confirmed Normal events correctly do not match).

---

## What the work agent must do (golden namespace, before duplicating)

```text
On the demo namespace, prove coverage is complete, then freeze it as the golden
path other namespaces copy:
1. Widen the Vector log regex and the Vector+Argo event reason lists to the
   recommended sets above; keep them identical between Vector and Argo.
2. For EACH log class and EACH event reason in the tables, fire a controlled
   fixture and confirm it reaches an Argo workflow with full fields
   (see PAYLOAD-FIELD-PROOF.md). A class that never produces a workflow is a
   coverage hole — fix the filter, do not ship the hole.
3. Record any reason intentionally excluded as noise, with the reason (no
   silent drops).
4. Confirm Normal events still do NOT trigger.
Duplicate to the next namespace only after this set is green.
```

## Done when

```text
LOG_COVERAGE_WIDENED_AND_PROVEN: yes
EVENT_COVERAGE_WIDENED_AND_PROVEN: yes
VECTOR_ARGO_REASON_LISTS_ALIGNED: yes
EVERY_CLASS_REACHES_A_WORKFLOW: yes
NORMAL_EVENTS_STILL_SUPPRESSED: yes
EXCLUSIONS_LOGGED_NOT_SILENT: yes
GOLDEN_NAMESPACE_FROZEN: yes
OUTPUT_SANITIZED: yes
```

---

## Note on "the agent will fix it"

This path is **read-only** by design (`automation_allowed: false`, the agent has
no write/apply tools). The specialist agent's job here is to **diagnose and tell
you how to fix** — the remediation steps land in the GitLab ticket as advice a
human runs. It does **not** execute changes on the cluster. Auto-remediation is
a separate, deliberately out-of-scope decision (needs its own authority, guard
rails, and scope sign-off). Adding specialist skills makes the *diagnosis*
deeper; it does not by itself grant write access. Decide that separately before
any agent is allowed to act.
