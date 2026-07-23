# Lessons — seven defects, and what they cost to find

The design passed a codex review gate. The code passed 44 offline unit tests.
Then it met a real cluster.

**Zero of the seven defects below were caught by review or by those tests.** That
is the finding most worth carrying to work — more than any individual bug.

The seventh is the most instructive, because it was caught by a test — a test
written *after* the code, specifically to attack it. See §7.

---

## 1. Remote code execution in the workflow

**Severity: critical.** Argo does *literal text substitution* into the script
body:

```python
payload_raw = r"""{{inputs.parameters.trigger-payload}}"""
```

A payload containing `"""` closes the string; the remainder executes as Python
in a pod holding `argo-events-sa` credentials (which can patch workflows and read
ConfigMaps). The EventSource webhook is **unauthenticated**, so anything in-cluster
that can reach that Service could drive it.

**Fix:** the payload travels via an env var and is never interpolated into
source. **The unauthenticated webhook remains an open gap** — NetworkPolicy at
minimum, shared secret properly.

**Found by:** a hunch while drawing an architecture diagram, then proved by
compiling a hostile payload. Not by review, not by tests, and not by a successful
end-to-end run — because every payload up to that point was our own.

**Generalises to:** any Argo workflow that templates a parameter into a `script`
body. That is a common pattern in this repo.

---

## 2. Every advertised time window was a no-op

**Severity: high, and it silently corrupted our reported numbers.**

```python
def _parse_ts(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")  # whole seconds only
```

RED's events carry `eventTime` as an RFC3339 **MicroTime** —
`2026-07-15T10:27:13.173860Z` — with `lastTimestamp` **null on 1192 of 1192
events**. So `_parse_ts` returned `None` for every event. Then:

```python
ts = _parse_ts(ev.get("lastTimestamp") or ev.get("eventTime"))
if ts and ts < cutoff:   # None is falsy — never skips
    continue
total += 1               # counted regardless of age
```

The snapshot claimed `window_minutes: 15` while counting **all retained
history**. The `warning_rate_multiplier` check was therefore comparing an
API-retention artefact, not a rate — doubly dead, since its baseline was also
inflated by unfiltered Kyverno noise.

**Fix:** `fromisoformat`; an `_event_ts` helper that prefers whichever field is
actually populated; a **strict** window (undated ⇒ excluded, never counted); and
an `undated` counter so it cannot lie silently again. Proof: `excluded_total`
1078 → 134 against a ground truth of 140.

**Found by:** verifying a subagent's claim that the flood was bursty. Its number
disagreed with ours. **It was right — our instrument was mislabeling its own
output.** We had already reported the wrong figure to a human by then.

**Generalises to:** anything parsing Kubernetes event timestamps. Assume
`lastTimestamp` is null and `eventTime` has fractional seconds.

---

## 3. The exclusion a comment claimed but code never did

`SENSOR-SAFEGUARDS.md` mandates excluding `PolicyViolation`. Our sensor comment
said *"exclusions are enforced at the collector"*. They were not. 858 of 859
warning events were PolicyViolation, so the rate baseline sat at ~859 and the
spike check needed **2577 events** to fire. Dead on arrival.

**Fix:** exclusion at source, with excluded volume still visible under
`events.excluded` rather than silently dropped. Signal went 859 → 2.

**Found by:** reading the first real snapshot.

**Lesson:** a comment asserting a safety property is not the property. Test it.

---

## 4. The check that mattered most did not exist

RED's only node sits at **93.6% CPU commit**. We collected that number, displayed
it, and never thresholded it — the exact "brewing" case the whole system exists
to catch, silently ignored. It is now what fires on RED.

**Found by:** reading the snapshot by eye.

**Lesson:** collecting a signal and acting on it are different features. Enumerate
every collected field and ask "what fires on this?"

---

## 5. Silent cap on detection

`collect_nodes()` truncated the node list to `TOP_N=20` **before** the detector
ran, so node 21+ on a large cluster would never be commit-checked. Invisible on
a single-node cluster — catastrophic on a 200-node one.

**Fix:** derive a full-node `commit` list before truncating the display list.

**Lesson:** truncation for output size must never sit upstream of detection.

---

## 6. `bitnami/kubectl` is dead

Every workflow step used it. It no longer pulls — Bitnami retired their public
catalog (RED shows `bitnamilegacy/*` leftovers). Replaced with `python:3.11-slim`
+ urllib against the API, matching the collector and removing a whole image
dependency.

**⚠️ 23 other YAML manifests in this repo still reference it** and will ImagePullBackOff
on first run. Worth a sweep before anything ships.

**Found by:** ImagePullBackOff on the first real workflow run.

---

---

## 7. Fire-once silently swallowed new failures

**Severity: high.** In the merged design, the escalate step decides whether to
call the agent. First version:

```python
if failed and not transitioned and baseline.get("verdict") != "unknown":
    if baseline.get("previous_verdict") == baseline.get("verdict"):
        sys.exit(0)   # "already reported"
```

The intent was fire-once: don't re-alert every 15 minutes about a cluster that
is already known-degraded. The effect was different. Certification checks are
**stateless pass/fail** — nothing in the report says whether DNS was broken last
run or has just broken now. So the fire-once branch keyed on the *baseline's*
transition and applied that verdict to *everything*.

Result: **DNS breaks while the baseline happens to be steady → suppressed.** A
brand-new outage, never escalated, no error, no trace. The most dangerous class
of bug this whole system exists to prevent, sitting in the thing meant to
prevent it.

**Fix:** track the *set* of failing checks in a ConfigMap and escalate when the
set **changes** — the same "fire on change, not on state" rule the baseline uses
for its verdict, applied to both halves. New failure appears → escalate. Same
failures as last run → stay quiet. Fails open when state is unreadable: better a
duplicate report than a swallowed outage.

**Found by:** a test written to attack the logic, asking "what if a check fails
but the baseline doesn't move?" — a case that never occurs on a healthy cluster
and so would not have shown up in any amount of running it.

**Lesson, and it qualifies the whole table below:** tests *can* catch real bugs —
when they are written adversarially, after the code, to probe cases the happy
path never reaches. The 44 tests that caught nothing were written to confirm the
code did what I had just decided it should do. That is the difference between a
test and a check-mark.

---

## What the pattern says

| Found by | Count |
|---|---:|
| Real cluster data | 4 |
| Testing a hunch | 1 |
| Checking a teammate's disagreeing number | 1 |
| An adversarial test written after the code | 1 |
| Design review (codex, adversarial) | 0 |
| The 44 offline unit tests written alongside the code | 0 |

The tests passed because **they asserted our assumptions back to us**. Synthetic
events carried the timestamp format we imagined, not the one Kubernetes emits.
Synthetic payloads were well-formed because we wrote them. Review caught
reasoning errors — it was genuinely valuable, and it found the double-handling
flaw that would have been worst in production — but review cannot catch a wrong
assumption about the world.

**Implications for the work rollout:**

1. **Budget cluster time, not just review time.** A day on a real cluster found
   what a rigorous review plus a test suite did not.
2. **Distrust your own instrument first.** When a measurement disagrees with a
   colleague, check the instrument before the colleague.
3. **Observe mode is not bureaucracy.** Every number we picked by intuition was
   either wrong or unvalidated. `REPORT_MODE=log-only` for 1–2 weeks is the
   cheapest way to find out which.
4. **Fail-open guards hide bugs.** `if ts and ts < cutoff` and
   `verdict_of([]) == healthy` both failed open, and both turned an error into a
   confident wrong answer. Prefer explicit `unknown`/`undated` states that force
   the question.
