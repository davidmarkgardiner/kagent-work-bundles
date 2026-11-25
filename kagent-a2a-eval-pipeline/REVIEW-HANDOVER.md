# Review handover: Assay, Warden, Guard and the monitoring loop

For an independent reviewer. The author has been marking their own homework, so this lists what is claimed, what evidence backs it, what was **never independently reviewed**, and where to push.
Be sceptical. A claim without a receipt below is not proven.

## 1. What this is

Four parts for kagent agents, plus an overseer:

| Part | Purpose | Main files |
|---|---|---|
| **Assay** | Test an agent before it ships: GitLab pipeline, seeded fault, pass^3, through the gateway | `a2a_capture.py`, `score_and_gate.py`, `judge.py`, `.gitlab-ci.yml`, `cases/`, `fixtures/cluster/`, `gateway/` |
| **Warden** | Sign off each run: an evaluator agent plus a deterministic check of the controller history | `verify_completion.py`, `a2a_shapes.py`, `completion-gate/` (contracts, generator, manifests) |
| **Guard** | Detect rogue agents (long runs, token burn, tools outside the allowlist, non-200s, oversized tool output); propose a block and a ticket; **apply a block directly for definite offences** (`forbidden_tool`) with caps; probe a model route | `guard/detect.py`, `guard/propose.py`, `guard/enforce.py`, `guard/model_probe.py`, `guard/rules.yaml`, `guard/alerts/`, `guard/manifests/guard-agent.yaml` |
| **Overseer intake + spend guards** | Alertmanager alert to an agent-health request; attempt caps, backoff, circuit breaker, token budget, kill switch | `guard/alert_to_a2a.py`, `guard/circuit.py`, `guard/loop-limits.yaml`, `guard/manifests/agent-health-agent.yaml` |
| **Packaging** | What a work agent needs to replicate it | `FRONT-SHEET.md`, `WORK-AGENT-PROMPT.md`, `HUMAN-PREREQUISITES.md`, `PREREQUISITES-AIRGAP.md`, `VARIABLES.md`, `docs/` + `mkdocs.yml`, `presentation/`, `EVALUATION-EXPLAINED.html`, `verify-bundle.sh`, `SHA256SUMS` |

Branch `feat/kagent-agent-eval-two-stage`, based on `main`. Commits, oldest first: `17a18cd3` (Assay and Warden), `5ad8a18f` (packaging), `732b2725` (Guard, overseer intake, Warden hardening),
`81b89bb2` (air-gap, variables, Guard page), `834a27c3` (overseer root cause, tool-call budget), `6e14395b` (429 as a wait), `8c4e6e20` (lessons from the factory handoff). Not pushed.

Start here: run `./verify-bundle.sh` (needs `pip install -r requirements-docs.txt` for the MkDocs check). It must print `BUNDLE_OK: yes`. It currently runs 224 tests.

## 2. Claims against evidence

Evidence files: `evidence/LIVE-PROXMOX-2026-11-23.md` and `evidence/GUARD-AND-LOOP-2026-11-24.md`. Sanitized live receipts are `tests/fixtures/*-live.json` and `a2a-v1x-*.json`. Raw receipts stay private (gitignored `out/`).

| Claim | Evidence | Reviewer check |
|---|---|---|
| Assay passes live on kagent 0.7.13 through the gateway (smoke and pass^3, score 1.0, 4 of 4 tool calls captured) | evidence file, stage 1; fixture `a2a-live-agent-tool-completed.json` | Is the captured trajectory complete? Is a score of 1.0 too easy (key-term scoring)? |
| A reused `contextId` returns 403 across agents; fixed with unique ids | evidence file | Is a random suffix enough, given Substrate session mapping on 1.x? (1.x rejects a supplied `contextId` altogether) |
| Warden: Sentinel worker **0 of 3** with a loose prompt, **3 of 3** with an ordered-steps prompt (1.0.0-alpha17) | `GUARD-AND-LOOP` evidence | n = 3 is small. Is 3 of 3 luck? |
| A deliberately misbehaving worker is rejected for exactly its extra tool | fixture `a2a-v1x-rogue-extra-tool-live.json` | |
| Guard detector: clean on 3 real runs, flags the rogue run, fires on real data when budgets are lowered | tests in `tests/test_live_replay.py`, `tests/test_guard.py` | Budgets were lowered on purpose to make rules fire: that proves the rule, not the threshold |
| A block-policy proposal is accepted by the lab API under server dry-run; nothing applied | evidence file | Dry-run proves schema, not that the CEL expression blocks only the intended caller |
| Guard agent's ticket passes its own Warden contract 3 of 3 | fixture `a2a-v1x-guard-ticket-live.json` | |
| The overseer's model 400 was a 4.4 MB `k8s_get_events` result | fixture `a2a-v1x-overseer-400-live.json`; gateway log | |
| Spend guards and the 429-as-a-wait rule behave as documented | `tests/test_circuit.py` (offline, 22 tests) | Never driven by a live scheduler |

## 3. NOT proven (do not let a green test suite hide these)

- **The overseer agent has no passing live run.** After the 400 fix it wandered (14 tool calls, 245000 tokens, no report). The tool-call budget and the new prompt have **not been re-run live**.
- Alert delivery (Alertmanager to the overseer), Tempo span-metric alerts firing, and the gateway actually exporting token and tool span attributes. The alert rules use an **unverified metric-name mapping**; `promtool` was not available.
- The GitLab receiver write and read-back (`--readback`). Never run.
- A live evaluator FAIL taking the quarantined-ticket route. Never run live.
- kagent **1.0.1**. Only 1.0.0-alpha17 was run; the lab profile in the repo targets 1.0.1.
- Three live Warden passes were achieved **only after** editing the prompt in response to failures. That is tuning, not a clean trial.
- ~~That a Deny policy actually blocks the offending caller.~~ Proven 25 Nov 2026 on a throwaway JWT route: 200 → 403 → 200 after release (see `docs/demo.md`).
- A block never expires by itself (by decision); there is no expiry job. A repeat apply of the same finding (fixed after review: a repeat apply is now idempotent and uses no cap slot).
- The overseer shares a model route with the agents it watches (a design flaw; see the prerequisites).

## 4. Never independently reviewed

A Codex review covered the plan, an early version of `verify_completion.py` (0.7 path) and the original Stage 1/Stage 2 design; its findings were fixed. These were **written after and not reviewed by anyone else**:
**`guard/enforce.py` (the highest-risk code: it writes to a cluster)**, `guard/model_probe.py`, the whole 1.x path in `verify_completion.py` (`_verify_v1`), `guard/detect.py`, `guard/propose.py`, `guard/alert_to_a2a.py`, `guard/circuit.py`, `a2a_shapes.py`, `render_evaluator.py` (per-contract evaluators), and the alert rules.

## 5. Where to push hardest

1. **Can Warden be fooled on 1.x?** `_verify_v1` reads one flat list of artifact parts and cannot attribute text to an author. The verdict is accepted only as the evaluator's whole final reply as bare JSON, after the handoff. Look for a worker that can emit a forged verdict, hand off to a different agent name, or arrange parts so the "final text" is its own.
2. **`enforce.py` and the `propose.py` trust boundary.** Start with `enforce.py`: it applies to a cluster. Try to make it apply something other than a single-subject Deny: tampered policy files, label/namespace tricks, the cap and ledger under concurrency or a corrupt ledger, a kill switch bypass, `--now` abuse. Then Identity comes only from `--identity-map`. Try: a subject with CEL metacharacters, unicode lookalikes, a route name matching the never-block list by prefix, the same finding under a different dedupe key, state-file races, a `neverBlock` bypass through `completion-evaluator-*` naming.
3. **False negatives in the detector.** Hung runs are only found through an inventory the caller supplies; if the inventory is empty, nothing is found. Per-hour token counting needs timestamps. A tool name that is in the allowlist but used on a forbidden resource is invisible to it.
4. **Circuit breaker.** Clock changes, concurrent writers (there is no file lock on the breaker state, unlike the Warden emitter), a state file that grows without bound, and whether `rate_limited_wait` can be used to starve a legitimate retry forever.
5. **Prompt dependence.** Two agents went from failing to passing by prompt wording alone. Is the gate measuring the agent or the prompt? What is the failure rate over 20 runs?
6. **Docs honesty.** Compare `FRONT-SHEET.md`'s status table, the deck and the explainer with the evidence files. The explainer (`EVALUATION-EXPLAINED.html`) was written before the Guard work and only had its counts updated.
7. **Rollout order and phase gates.** `WORK-AGENT-PROMPT.md` now opens with six phases (0 readiness, 1 Warden, 2 Assay, 3 Guard detection, 4 LGTM integration, 5 direct blocking) with a gate after each. Check that each step is in the right phase, that no step quietly needs something from a later phase (for example telemetry in Phase 1), and that a work agent given only Phase 1 could not drift into the rest.
8. **Replicability.** Could a work agent follow `WORK-AGENT-PROMPT.md` (16 steps, in six gated phases) with only the prerequisites listed? Note anything assumed but unwritten.

## 6. Known rough edges

- `docs/prerequisites.md` and `docs/variables.md` are copies of the root files (`verify-bundle.sh` checks they match).
- Doc edits to `agent-platform-mkdocs/docs/operations.md` and `byo-sentinel-whisky/docs/implementation-handoff.md` live in untracked folders outside this bundle and are **not** in these commits.
- The Sentinel itself is not in this bundle (the whisky/baseline-sentinel bundles hold it). The eval feeds a Sentinel-style finding about a synthetic crash-looping deployment; it is not the real app.
- The test fixtures are sanitized by pattern substitution; confirm none contains real hostnames or tokens (`verify-bundle.sh` runs a private-address scan, which is not proof).

## 7. Rules for the reviewer

- Read-only on the code unless asked to fix. Do not push, merge or open a PR.
- **Do not run agents in a loop.** One live agent run once cost 245000 tokens. Prefer the offline tests and the recorded receipts. Stop at the first live failure and diagnose from the receipt.
- Do not run `enforce.py apply` against any real cluster; the tests use a fake kubectl, so use those. Do not touch the lab or any production context.
- Report findings ranked, each with a file and line and a concrete failing input. Say plainly if something you could not check.

## 8. Review round 1 (an independent Codex pass, 24 Nov 2026) and what was done

| # | Finding | Status |
|---|---|---|
| 1 | Critical: `enforce.py` trusted editable `proposals.json` for the signal, subject and route | **Fixed**: it now needs `--findings` and `--identity-map`; signal and agent come from the detector finding; the policy must match the map (tests) |
| 2 | High: caps bypassable (optional ledger, caller-supplied `--now`, corrupt lines skipped, repeat apply uses a slot, failed read-back recorded as failed, kill switch only in one place, no lock) | **Fixed**: ledger required, clock only overridable in test mode, corrupt ledger fails closed, idempotent re-apply, `applied_unverified` counts, kill switch checked per proposal in three places, file lock |
| 3 | High: Warden accepted a verdict after an errored `transfer_to_agent` | **Fixed and reproduced first** (PASS before, FAIL now, three error shapes) |
| 4 | High: circuit breaker not concurrency-safe, unbounded state | **Fixed**: lock in the intake, unique temp file, pruning. **Open:** `maxToolCalls` only checks a finished receipt, so it cannot stop a run in progress |
| 5 | Medium: detector reports clean when no inventory is supplied | **Open**: not changed |
| 6 | Medium: Phase 1 prerequisite conflicts; step 14 asked for a live failure while saying stop at the first failure | **Fixed** (rows corrected, phases split, step 14 now offline only) |
| 7 | Medium: docs said the code never auto-applies; FRONT-SHEET contradicted itself on the Warden passes | **Fixed** |

Not checked by that reviewer: its sandbox blocked temp directories and local servers, so it could not run most tests. Round 2 should be run with a reviewer that can.

## 9. Review round 2 (Opus, 24 Nov 2026): verdict REQUEST CHANGES, and what was done

Its test run: 175 passed, verifier OK. Findings and status (CONFIRMED FIXED / PARTIAL / OPEN):

| # | Finding | Status |
|---|---|---|
| H1 | The hourly cap and lock hang off a caller-chosen ledger path | **Fixed**: the cap is also counted from `applied-at` annotations on the cluster, so a fresh ledger cannot reset it. The lock is still tied to the ledger path (**partial**) |
| H2 | One trace can mix agents, so a sub-agent's tool is charged to the parent; agent names come from the agent's own runtime | **Partial**: findings now carry a `source`; trace-sourced and aggregate findings **cannot auto-block** (`autoApplySources`, default receipt and run). Per-span attribution from gateway-emitted spans is **not done** |
| H3 | The errored-handoff check misses a string-shaped error | **Partial**: string errors are now caught. The reviewer's `_ok()` fix was **rejected**: the real `transfer_to_agent` response has no `response` key at all, so `_ok()` would fail every genuine pass. An absent or null response is therefore still accepted, because the real error shape is unknown |
| H4 | Never-block checked the policy and not the agent | **Fixed** (the agent name is checked too) |
| M1 | A `429` inside a message overrode a real 404 | **Fixed** |
| M2 | The policy name hashed the time bucket, so duplicates | **Fixed** (name is `agent|subject|route`) |
| M3 | Prerequisite rows missing for Phases 1, 3 and 5; step 13 mixes phases | **Open**: not yet updated in the prompt |
| M4 | Crashes leave no audit record | **Partial**: no crash on missing annotations; a wrapper prints a structured error. No ledger line on a crash |
| L1 / L3 / L4 | Trailing newline, kill-switch values, apply-failed-but-persisted | **Fixed** |
| L2 / L5 | Temp files not deleted; spans without a spanId | **Open** |
| Round 1 #1 | The trust anchor moved, not gone: `--findings`, `--identity-map`, `--rules` are caller-chosen paths | **Open by nature**: run `enforce.py` under its own identity with those files owned and writable only by that identity, ideally mounted read-only |
| Round 1 #2 | `GUARD_TEST_MODE` and `--now` still give the caller the clock | **Open**: an environment override is operator-controlled; `alert_to_a2a.py` still accepts `--now` and uses a fixed `.tmp` for `--state` |
| D1-D5 | Stale or overstated docs | **Mostly fixed** (counts, "live" wording, "counts twice", the auto-apply question); re-check |

Also still open from round 1: the detector reports clean when no inventory is supplied, and `maxToolCalls` is checked only after a run finishes. Not checked by the Opus reviewer: the real kagent error shape for a failed handoff, whether gateway traces mix agents in practice, the CEL behaviour of a Deny, `model_probe.py`, the alert rules, the explainer HTML, and the mutation tests were not re-run.

## 10. Review round 3 (Opus, 24 Nov 2026): the alert receiver and Grafana files. Verdict REQUEST CHANGES, and what was done

Scope: commits b500c838 and f13bd541 only. **Fixed, each with a test (one mutated to confirm the test fails):**
- H1: a permanent model error returned as HTTP 200 (kagent's usual shape) was classed `unknown` and retried; the receiver now passes no status so the breaker reads the message and holds it for 24 hours.
- H2: negative, missing or non-numeric Content-Length (unbounded read before the token check), no socket timeout on a single-threaded server, uncaught subprocess timeouts; now 411/413 before reading, a 10 s handler timeout, a threaded server (work still serialised by the lock), subprocess failures return a bare 500.
- M1: Grafana's `DatasourceError` and `DatasourceNoData` alerts inherit `guard=true` and would have gone to the agent; a human route matches them first.
- M2: `maxAlerts` truncation and unsent-but-deduped requests; the policy groups per offender, and requests over the send cap are `deferred_over_cap`, not marked handled.
- M3: a send that times out or fails in transport sets the kill switch (the agent may still be running; spend unknown).
- M4: a failed breaker record sets the kill switch.
- M5 (row 13 wording), the breaker key mismatch when an alert has no fingerprint, the false "import Prometheus rule files" claim, row order, and the weak 400 test (now asserts `held_after_permanent_error`).

**Left open:** the intake does not drop the self-test rule (by design: it is the proof the path works; the guide says delete it, and it would run the agent every 4 hours otherwise); an empty `--inventory []` still reads `clean` (a person chose to say nothing was started); the spool keeps every payload with no cleanup; the real kagent error shape for a failed run and Grafana 11.6's labels on `DatasourceError` were taken from documentation, not reproduced.
