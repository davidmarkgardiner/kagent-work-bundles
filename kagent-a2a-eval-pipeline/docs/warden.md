# Warden: sign off every run

When a worker agent finishes, it hands its report to an evaluator agent over A2A. A deterministic check of the worker's controller history then decides
what happens next. The worker never writes the ticket.

```text
worker (read-only tools) → evaluator agent → {"verdict","contract","failures"}
        → verify_completion.py reads the controller history → route: ticket | evaluation_failed_ticket | reject
        → the receiver writes the GitLab issue and reads it back
```

**Why the receiver writes the ticket.** A ticket written before a failed check cannot be taken back, and the receiver already owns opt-in, destination binding and replay handling.

## What `verify_completion.py` checks

- Every call has exactly one response, after it. Identical streaming replays are tolerated; conflicting ones fail closed.
- Every tool called is on the contract's **allowlist** (there is no deny list to forget a tool in).
- Each required tool group has a **successful** response. `isError: true` never counts, even when a result is attached.
- The evaluator was called, at most `maxAttempts` times, and no tool ran after its last call.
- The evaluator's last verdict is PASS for this exact `contract@version`.
- **What is delivered is exactly what the evaluator judged.** By default the receiver delivers `approved_output`, the envelope the evaluator saw; a reworded final copy is a warning.
- The report has one non-empty envelope and the required sections, and nothing outside it.
- Optional: the deployed Agent declares only allowed tools (`--agent-crd`), and the ticket read back carries this run's incident key and labels (`--readback`).

Exit codes: 0 PASS, 1 FAIL, 3 UNDECIDABLE (task not completed or a kagent error code). `evaluation_failed_ticket` is used only when the protocol was
followed and the evaluator still said FAIL on its final allowed attempt; any protocol or scope break routes to `reject`.

The evaluator's PASS is a judgement, not proof. The deterministic check is what gates delivery.
