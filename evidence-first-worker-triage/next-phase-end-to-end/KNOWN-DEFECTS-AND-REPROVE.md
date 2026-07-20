# Known Defects — re-prove these BEFORE building anything new

The red proof's controlled stress test (`reference-config/STRESS-TEST-2026-07-13.md`)
found two **P0** defects. The config was patched the **same day** — the fixes
are in the `reference-config/` you have — and the patch has now been **re-proven
end to end**; see `evidence/phase0-reprove-redaction-and-correlation.md` and the
Phase 0 row of `ROLLOUT-TRACKER.md` (state: green).

**The re-proof also found and fixed a live regression not covered by either P0
below: the claim-refresh logic (`reference-config/03-argo.yaml`'s
`claim-24h-window`) used a non-atomic delete-then-create, letting two concurrent
workflows both win a claim for one incident (reproduced live as tickets
#446/#447). Fixed with a resourceVersion-guarded compare-and-swap plus retry
handling for a claim held with no recorded ticket — see
`evidence/phase0-reprove-redaction-and-correlation.md` and
`applied-config/03-argo-augmented.yaml`. `reference-config/03-argo.yaml` still
has the old, defective claim logic — do not apply it verbatim; use
`applied-config/03-argo-augmented.yaml` instead.**

## The two P0 defects (fixed in config, re-proven in run)

### P0-1 — evidence redaction failed before Kafka and GitLab
Secret-shaped values (password, token, Bearer) reached GitLab in plaintext, in
both `evidence.representative_log_lines` **and** the raw `message`. Fix applied:
`02-vector.yaml` now redacts, then builds an **allow-listed** envelope and drops
raw OTLP `message`/`attributes`; `03-argo.yaml` scrubs the agent diagnosis
before GitLab. Re-proven live: no secret-shaped value reaches Kafka, the agent
prompt, workflow logs, or GitLab — see `evidence/phase0-reprove-redaction-and-correlation.md`.

### P0-2 — local dedupe destroyed event correlation
The old worker key was `cluster:ns:pod` and let only the first candidate
through, so an early `Failed`/log record blocked the later actionable `BackOff`
— it never reached the Sensor. Fix applied: `delivery_key` now keys on
correlation key + reason + redacted evidence, so a different later event is not
suppressed. Re-proven live: a later `BackOff` appends to the original incident
instead of being dropped or opening a second ticket — see
`evidence/phase0-reprove-redaction-and-correlation.md`.

### P1 (also open)
- Event policy narrow/inconsistent (see `SIGNAL-COVERAGE.md`).
- Ticket embeds raw JSON envelope instead of a rendered safe contract; `service`
  showed empty on some fixtures (see `PAYLOAD-FIELD-PROOF.md`).

## Required regression — the gate before Phase 1 build work

```text
Re-run the equivalent fixtures on the demo namespace and prove ALL of:
1. No secret-shaped value (password, token, api-key, Authorization/Bearer,
   structured JSON, multiline, encoded) reaches Kafka, the agent prompt,
   workflow logs, or GitLab. A record whose redaction cannot be proved is
   quarantined, not shipped.
2. A crashloop / image-pull sequence (Failed -> ErrImagePull -> BackOff, and
   log-then-BackOff) yields exactly ONE correlated ticket in the window,
   carrying BOTH the log and the event evidence — the later BackOff appends to
   the original incident, it does not open a second ticket or get dropped.
3. Each supported event family routes by explicit policy; a rejected family
   shows a visible drop/quarantine metric, not a silent near-miss.
4. Tickets carry the rendered safe contract (fingerprint, cluster, workload/
   pod/container, reason+severity, first/last seen, redacted evidence, agent
   summary, confidence, ticket state) — not a raw payload.
5. Replay, concurrent delivery, agent failure, and GitLab post-create retry
   lose no evidence and create no duplicate ticket.
Use synthetic secret-shaped strings only. Never a real credential.
```

## Done when (blocks Phase 1)

```text
REDACTION_REPROVEN_NO_SECRET_LEAK: yes
CORRELATION_REPROVEN_LATER_BACKOFF_APPENDS: yes
EVENT_POLICY_DROPS_ARE_METERED: yes
TICKET_IS_RENDERED_SAFE_CONTRACT: yes
FAILURE_RETRY_NO_LOSS_NO_DUPLICATE: yes
STRESS_TEST_VERDICT_CHANGED_TO_PASS: yes
OUTPUT_SANITIZED: yes
```

This gate is green — see `evidence/phase0-reprove-redaction-and-correlation.md`
and `ROLLOUT-TRACKER.md` (Phase 0: green). The earlier PASS verdict applies and
Phase 1 onward has proceeded (see `ROLLOUT-TRACKER.md` for current phase states).
