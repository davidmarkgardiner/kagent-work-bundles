# Phase 4 — Prove the payload, prove it is efficient

**Goal:** prove the workflow receives the **exact** payload triage needs — no
missing field, no unbounded/unredacted field, no dead weight — and prove it is
as lean as it can be while still sufficient.

## Why

"It arrived" (Phase 1) is not "it arrived correctly and efficiently." This phase
pins the contract: the envelope carries everything the agent needs to triage and
the backend needs to ticket, and nothing it does not.

**Read `PAYLOAD-FIELD-PROOF.md` first.** It already documents, from the red
proof, exactly which fields reach the agent (cluster, message type, actual
message, reason, pod, service, namespace, timestamp) and the two that do not yet
(`severity` was never added; `container` is dropped in the Vector allow-list).
The field table there is the required-vs-present baseline for this phase — do
not re-derive it, extend it and close the two gaps.

## Prompt

```text
Prove the payload contract end to end. Capture a real sanitized envelope at
three points: as Vector produces it, as Argo consumes it, and as the agent
receives it. Show they match. For every field, state which downstream consumer
needs it (agent triage, fingerprint, or ticket). Flag any field no consumer
uses and remove it. Prove the bounds hold: per-line cap, total evidence cap,
and redaction pack all applied. Prove the fingerprint is stable and
discriminating: pod churn in one incident yields one key; two distinct
signatures yield two keys. Report bytes/envelope and the required-vs-present
field diff. If anything is truncated or dropped, log it explicitly.
```

## Do

1. Capture the envelope at produce / consume / agent-input; diff them.
2. Build a field table: `field -> consumer that needs it`. Delete orphans.
3. Re-run the bound/redaction checks (DS-05) and fingerprint checks (DS-04):
   - same incident, pod churn -> one fingerprint;
   - two distinct signatures -> two fingerprints;
   - node events -> node class.
4. Record bytes/envelope and confirm no field carries a secret/PII.

## Evidence to capture (into `../evidence/`)

- `phase4-payload-contract.md` — the field table + required-vs-present diff.
- `phase4-envelope-samples.md` — sanitized samples at all three points, matched.
- `phase4-bounds-and-fingerprint.md` — cap/redaction proof + fingerprint tests.

## Done when

```text
PAYLOAD_CONTRACT_PROVEN: yes
NO_ORPHAN_FIELDS: yes              # every field has a named consumer
BOUNDS_ENFORCED: yes              # per-line + total caps + redaction applied
FINGERPRINT_STABLE_DISCRIMINATING: yes
ENVELOPE_BYTES_RECORDED: yes
OUTPUT_SANITIZED: yes
```
