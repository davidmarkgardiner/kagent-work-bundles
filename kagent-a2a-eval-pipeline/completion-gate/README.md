# Warden: the completion gate (evaluation stage 2, runtime)

Assay (stage 1, the parent bundle) answers *is this agent fit for purpose?* before
promotion. Stage 2 answers *did this agent finish this job properly?* every
time it runs in production.

```text
worker agent ── investigates with read-only tools
     │
     │  native kagent A2A (`type: Agent` tool)
     ▼
completion-evaluator-agent ── {"verdict":"PASS|FAIL","contract":"name@version","failures":[...]}
     │  FAIL → worker fixes and re-sends (max 3)
     ▼
worker returns <result>…</result><evaluation>{…}</evaluation>
     │
     ▼
verify_completion.py ── reads the worker's controller history, not its prose
     │  route = ticket | evaluation_failed_ticket | reject
     ▼
Argo / receiver writes the GitLab issue, reads it back (--readback)
```

The worker never writes the ticket itself. A ticket written before a failed
check can't be taken back, and the Sentinel receiver already owns opt-in,
destination binding and replay handling. So "did it write to the ticket?"
becomes "did the receiver write the right ticket?". The receiver reads the
issue back and the gate checks it carries this run's incident key and labels.

## One contract, three places

`contracts/<agent>.yaml` is the single source of truth:

| Where | What enforces it | Proves |
|---|---|---|
| Evaluator agent (runtime, LLM) | `render_evaluator.py` generates its instructions from the contract | Semantic review: evidence backs claims, read-only, next steps actionable |
| `verify_completion.py` (runtime, deterministic) | Argo step or receiver check, on the worker's A2A task | What actually ran, and that the verdict covers the delivered text |
| Stage 1 CI (`score_and_gate.py --contracts-dir`) | Every captured eval run | The agent closes the loop before it is promoted |

The LLM evaluator's PASS is a judgment, not proof. The deterministic check is
what gates delivery.

## What `verify_completion.py` checks

FAIL unless all of these hold:

- Every call has exactly one response, with the same name, appearing after
  the call. Identical streaming replays are tolerated; conflicting ones fail
  closed.
- Every tool called is in `allowedTools` / `allowedAgents`, plus the evaluator.
  This is an allowlist; there is no deny list to forget a tool in.
- Each `requiredTools` group has at least one successful response.
  `isError: true` never counts, even when a result is attached. The July Argo
  `jq` check accepted that case.
- The evaluator was called at most `maxAttempts` times, and no tool ran after
  its last call.
- The last evaluator response is JSON with `verdict: PASS` for this exact
  `contract: name@version`.
- **What gets delivered is exactly what the evaluator judged.** The last
  evaluator request must hold exactly one envelope. By default, that envelope
  is returned as `approved_output` for the receiver to deliver, and the
  contract is checked against it. With `deliver: final`, the worker's final
  text must equal it instead. Either way, a draft can't be approved while
  something else ships, and the real text can't be hidden as "quoted evidence".
- The delivered text (every artifact) holds exactly one non-empty envelope.
  Nothing may appear outside it except the `<evaluation>` block.
- The output has the required sections.
- Optional `--agent-crd`: the deployed Agent declares only allowed tools, plus
  the evaluator. An McpServer with no `toolNames`, or an unknown tool type,
  fails.
- Optional `--readback`: the ticket read back from GitLab carries this run's
  incident key and the required labels.

Exit codes: `0` PASS, `1` FAIL, `3` UNDECIDABLE (task not completed, or a
kagent error code). `evaluation_failed_ticket` is used only when the protocol
was followed and the evaluator still said FAIL on the final allowed attempt.
Any protocol or scope break routes to `reject`. In CI, a receipt counts only if
its JSON-RPC id is the scored run's id.

## Files

| File | Purpose |
|---|---|
| `contracts/sentinel-investigator.yaml` | BYO Sentinel investigation agent |
| `contracts/k8s-triage.yaml` | Matches the red A2A evaluation gate (`homelab-verified-triage-replication/a2a-evaluation-gate`) |
| `render_evaluator.py` | Contract(s) → `manifests/completion-evaluator-agent.yaml`; CI fails if the checked-in copy is stale |
| `manifests/completion-evaluator-agent.yaml` | Generated, no tools, strict JSON verdict |
| `manifests/sentinel-investigator-agent.yaml` | Example worker: read-only tools, plus the evaluator as a `type: Agent` tool and the loop prompt |
| `../verify_completion.py` | Deterministic verifier (CLI and library) |

## Use it

```sh
# 1. Write or extend a contract, then regenerate the evaluator.
python completion-gate/render_evaluator.py completion-gate/contracts/*.yaml \
  --model-config {{MODEL_CONFIG}} > completion-gate/manifests/completion-evaluator-agent.yaml

# 2. Add the evaluator tool and the "completion check" prompt block to the worker
#    (copy from manifests/sentinel-investigator-agent.yaml).

# 3. Gate delivery on the worker's A2A response.
python verify_completion.py --contract completion-gate/contracts/sentinel-investigator.yaml \
  --receipt response.json --agent-crd agent.yaml          # route decides what the writer does
python verify_completion.py --contract ... --receipt response.json --readback issue.json   # after the write

# 4. Make promotion depend on it (stage 1).
python score_and_gate.py --capture-dirs out/eval-* --repeat 3 \
  --contracts-dir completion-gate/contracts --require-contracts --out out/report
```

## Live verification (23 November 2026, home lab)

Ran once end to end through agentgateway on kagent 0.7.13 with Kimi. The
Sentinel worker made 5 read-only tool calls, called the evaluator over native
A2A, and got PASS. The verifier returned `route=ticket`. Two things were learned
and are now built in:

- An Agent-tool response in controller history is `{"result": "<verdict JSON string>"}`;
  its call `args` is `{"request": "<text>"}`.
- The worker reworded its report after PASS, despite being told not to. So
  contracts default to `output.deliver: approved`: the receiver delivers
  `approved_output`, the exact text the evaluator judged, and drift is a
  warning. `deliver: final` keeps the strict rule.

Details: `../evidence/LIVE-PROXMOX-2026-11-23.md`. The sanitized receipt is the
regression fixture `../tests/fixtures/a2a-live-agent-tool-completed.json`.

## Not yet verified

- Repeatability. Runs 3 and 4 hit cluster degradation (kagent-controller lost
  its MCP servers), so live pass^3 is still open.
- The evaluator FAIL → correct → retry loop live (it passed first time),
  `evaluation_failed_ticket`, and a real GitLab receiver write with `--readback`.
- The July evaluator prompt does not echo `contract: name@version`, so swap in
  the generated evaluator before enforcing `contracts/k8s-triage.yaml` there.
- Replaying the July Argo step with this verifier is the migration path. The
  `evaluation_failed_ticket` route maps to its `triage::evaluation-failed` label.
