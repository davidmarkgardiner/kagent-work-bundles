# Phase 6 — One namespace at a time, routed to specialist agents

**Goal:** onboard one real application namespace at a time (start with
**external-dns** or **Kyverno**), smoke test it, and prove its incidents route
to the correct **specialist agent** and produce a good triage ticket.

## Why

Phase 5 proved the backend with the pilot namespace. Phase 6 starts hitting real
workloads, but deliberately **one namespace per step** so a bad specialist route
or a noisy source is caught in isolation, not fleet-wide. This is where real
triage quality gets tested.

**Golden-path model:** the demo namespace, once coverage is complete
(`SIGNAL-COVERAGE.md`) and fields are proven (`PAYLOAD-FIELD-PROOF.md`), is the
frozen template. Every later namespace duplicates the same collection/filter/
envelope recipe; only the specialist agent (its context/skills) changes per app.
The specialist makes the **diagnosis** deeper — it does not by itself grant the
agent write access. Auto-remediation stays a separate scope decision.

## Routing mechanics — this does not exist yet, design it

Today `reference-config/03-argo.yaml` hardcodes a **single** agent endpoint:
`http://kagent-controller.kagent:8083/api/a2a/kagent/k8s-readonly-agent/`. There
is no per-namespace routing. "Route to the specialist agent" is not a config
that exists — the work agent must build the selector. Pick one mechanism and
prove it:

- **Selector by namespace/label** — the workflow chooses the agent path from the
  envelope `namespace` (or a mapped label), e.g. `external-dns` →
  `external-dns-agent`, `kyverno` → `kyverno-agent`, default →
  `k8s-readonly-agent`. One workflow, a lookup step.
- **Per-namespace Sensor/trigger** — a Sensor whose filter matches one namespace
  and calls that namespace's agent. More objects, clearer isolation.

Whichever is chosen: an unmapped namespace must fall back to the generic
read-only agent (never fail silently), and the chosen agent must still be
read-only. Record the namespace→agent map as data, not hardcoded per copy.

## Order

Pick a low-blast-radius, well-understood namespace first. Suggested order:

1. `external-dns` — small, clear failure modes (DNS/provider auth, sync errors).
2. `kyverno` — policy admission failures, webhook timeouts.
3. then the next agreed namespace — **only after** the previous is green.

## Prompt

```text
Onboard exactly ONE namespace this step (start with external-dns, then
Kyverno). Scope Alloy/Vector collection to that namespace only. Identify the
specialist agent that should own its incidents and confirm the routing key
(label/namespace/signature) sends its evidence to that specialist, not the
generic agent. Smoke test 2-3 real failure modes for that app and confirm: the
right specialist agent runs, the triage is accurate and useful for that app,
and an idempotent ticket is created with app-appropriate labels. Do not onboard
the next namespace until this one is green with evidence. Keep everything
additive and reversible; the agent stays read-only.
```

## Do (repeat per namespace)

1. Scope collection to the one namespace; confirm no other namespace bleeds in.
2. Map namespace/signature -> specialist agent; verify the routing.
3. Trigger 2–3 real, controlled failure modes for that app.
4. Assert: correct specialist ran, triage is app-accurate, ticket idempotent
   with correct labels, replay suppressed.
5. Record green, then move to the next namespace.

## Evidence to capture (into `../evidence/`)

- `phase6-<namespace>.md` per namespace — routing proof, specialist output,
  ticket URL, failure modes tested, replay suppression.

## Done when (per namespace)

```text
NAMESPACE: <name>
COLLECTION_SCOPED_SINGLE_NS: yes
ROUTING_SELECTOR_BUILT: yes        # namespace->agent map exists, not hardcoded
UNMAPPED_NS_FALLS_BACK_TO_GENERIC: yes
SPECIALIST_ROUTING_PROVEN: yes     # correct agent, not generic
TRIAGE_ACCURATE_FOR_APP: yes
TICKET_IDEMPOTENT_LABELLED: yes
REPLAY_SUPPRESSED: yes
OUTPUT_SANITIZED: yes
NEXT_NAMESPACE: <name or none>
```
