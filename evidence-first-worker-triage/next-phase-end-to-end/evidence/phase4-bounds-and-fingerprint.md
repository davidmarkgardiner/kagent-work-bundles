# Phase 4 — Bounds, redaction, and fingerprint proof

## Bounds enforced

- **Per-line/total cap**: `truncate(safe_message, 4096, suffix: "…")` — the
  only free-text evidence field (`evidence.representative_log_lines`) is
  capped at 4096 characters. There is no separate "per-line" vs "total" cap
  because the envelope carries a single representative line/summary, not a
  multi-line buffer — the cap **is** the total bound for this field.
- **Redaction pack**: applied to `message` *before* truncation and *before*
  the allow-list is built (`redact()` with password/token/api-key/secret,
  `Authorization: Bearer`, and cookie/set-cookie patterns) — proven with zero
  leaks across two independent fixture fires and two independent Vector
  process lifetimes (tickets #448, #451; see `phase0` §2).
- **Allow-list**: raw OTLP `message`/`attributes` never reach the envelope at
  all — only the 16 named fields in `normalize`'s `. = {...}` block survive
  (see `phase4-payload-contract.md`'s field table for the full list; one
  field, `source_type`, is flagged there as an unused orphan but is not itself
  a bounds/redaction risk — it's a constant).
- **Ticket-side second scrub**: `create-gitlab-issue`/`append-correlated-evidence`
  re-apply the same three redaction patterns to both the safe-incident fields
  and the agent's own diagnosis text before it reaches GitLab — this exists
  specifically because a read-only agent can independently rediscover
  sensitive-looking content through its own Kubernetes tool calls (the
  second-scrub risk flagged in `STRESS-TEST-2026-07-13.md`). No leak observed
  in any of the ~15 tickets reviewed this session.

## Fingerprint — discriminating power: proven; stability under churn: real gap (see `phase4-payload-contract.md`)

- **Two distinct signatures → two distinct fingerprints**: true for every
  distinct fixture fired this session (each of ~15 fixtures got its own
  `dedupe_key` and its own ticket, with zero unintended collisions).
- **Pod churn → one incident**: **fails today.** Full evidence, root cause,
  and why it was not fixed this pass are in `phase4-payload-contract.md`
  ("Fingerprint stability under pod churn"). Summary: two `Pod` objects with
  the same `app.kubernetes.io/name` label and identical failure signature but
  different pod names produced two different `dedupe_key`s and two separate
  tickets (#480, #481) — a real reproduction of the DS-04 gap, not a
  theoretical one.
- **Node events → node class**: not tested — `red` is single-node; degrading
  the cluster's only node was judged out of scope for a reversible,
  non-destructive proof exercise (see `phase4-payload-contract.md`).

## Bytes/envelope

See `phase2-efficiency.md` Snapshot C: ~840 bytes/record average, both for
the raw OTLP input and for what reaches the Kafka sink in the sampled window.

```text
BOUNDS_ENFORCED: yes
FINGERPRINT_STABLE_DISCRIMINATING: no   # discriminating: yes; stable-under-churn: no (real gap, evidenced, fix recommended not applied)
ENVELOPE_BYTES_RECORDED: yes
OUTPUT_SANITIZED: yes
```
