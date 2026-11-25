# Assay and Warden: front sheet

**Assay** tests a kagent agent *before* it ships. **Warden** checks each run of an
agent *after* it ships and signs it off (or blocks it) before anything is ticketed.

```text
whisky app falls over → Sentinel alerts → agent investigates (read-only)
        → Warden checks the work → receiver writes the GitLab ticket
        → Assay is the test the agent passed before it was allowed to do this
```

The agents here **diagnose and report; they do not fix**. Remediation stays with a human or a
separately approved agent. Warden checks the investigation, not a repair.

## What is in this folder

| Need | File |
|---|---|
| Hand this to the work agent | [WORK-AGENT-PROMPT.md](WORK-AGENT-PROMPT.md) |
| Rollout order (one phase at a time) | [docs/rollout.md](docs/rollout.md) and the top of `WORK-AGENT-PROMPT.md` |
| What a human must supply first | [HUMAN-PREREQUISITES.md](HUMAN-PREREQUISITES.md) |
| Air-gap image inventory and pinned versions | [PREREQUISITES-AIRGAP.md](PREREQUISITES-AIRGAP.md) |
| What changes at work and what stays pinned | [VARIABLES.md](VARIABLES.md) |
| Explainer (open in a browser) | [EVALUATION-EXPLAINED.html](EVALUATION-EXPLAINED.html) |
| Presentation | [presentation/assay-warden-deck.pdf](presentation/assay-warden-deck.pdf) (source: `.html`) |
| Handbook pages | `mkdocs.yml` + `docs/`; build with `requirements-docs.txt` |
| Assay code and CI | `a2a_capture.py`, `score_and_gate.py`, `judge.py`, `.gitlab-ci.yml`, `cases/`, `fixtures/`, `gateway/` |
| Warden code and contracts | `verify_completion.py`, `completion-gate/` |
| Evidence | `evidence/LIVE-PROXMOX-2026-11-23.md`, `tests/fixtures/` (sanitized live receipts) |
| Guard (rogue-agent detector, block proposals, overseer intake) | `guard/`, `docs/alert-loop.md`, `evidence/GUARD-AND-LOOP-2026-11-24.md` |
| Independent review: claims, gaps, where to push | [REVIEW-HANDOVER.md](REVIEW-HANDOVER.md) |
| Check the bundle is intact | `./verify-bundle.sh` |

## Status: what is proven and what is not

| Claim | Status | Receipt |
|---|---|---|
| 216 offline tests, case lint, generated evaluator is current | PASS | `./verify-bundle.sh` |
| Assay: smoke and full pass^3 through the gateway on kagent 0.7.13 | PASS (1.0 each) | evidence file, stage 1 sections |
| Warden on kagent 0.7.13 (evaluator as a `type: Agent` tool) | 1 live PASS | evidence file, stage 2 section |
| Warden on kagent 1.0.0-alpha17 (evaluator as a `subAgent`), A2A 1.0 | 2 of 3 PASS; the third was a correct block | evidence file, 1.x section |
| Warden, three live passes in a row from a clean first attempt | **NOT ACHIEVED**: 3 of 3 came only after the prompt was tuned (a clean first run scored 0 of 3) | `evidence/GUARD-AND-LOOP-2026-11-24.md` |
| Warden FAIL → fix → retry loop live | **NOT POSSIBLE on 1.x** (handoff does not return); 0.7.x not re-run | |
| GitLab receiver write and read-back | **NOT RUN** | |
| Warden: 0 of 3, then 3 of 3 live after a stricter worker prompt (1.0.0-alpha17) | PASS 3 of 3 (the first prompt failed all three, and Warden caught it) | `evidence/GUARD-AND-LOOP-2026-11-24.md` |
| Guard detector run on live receipts, block proposal (server dry-run) and ticket | PASS (the detector is offline code run over real receipts, not a live deployment) | same |
| Direct block (`guard/enforce.py`): apply, read back, release on a real cluster; caps and kill switch | PASSED live on the lab again on 25 Nov 2026 after all hardening, through the full Guard path: the caller went **200 → 403 → 200** after `release`, and the same caller on another route stayed 200. Caps and kill switch are tested offline (fake kubectl, mutation-tested) | same |
| Overseer fix-it step (`guard/remediate.py`): switch a broken agent to an approved fallback ModelConfig | PASSED live on the lab, 25 Nov 2026: 429 failure → probes → switched and read back → the same question completed; ticket written; second apply refused. 15 offline tests, 5 safeguard mutations caught | lab |
| Live demo (`demo/run-demo.sh all`): lights, healthy, rogue blocked, broken fixed | PASSED end to end on the lab in 6 min 30 s (`docs/demo.md`) | lab |
| Overseer agent's own report through its Warden contract | PASSED live, 25 Nov 2026, after giving its tool server read access to Agents and ModelConfigs (the first run was rightly rejected for 9 tool calls > 8): 3 reads, evaluator PASS, verifier `ticket` | lab |
| Whole loop with Grafana (`demo/grafana-loop/`): failure → metric → Grafana → receiver → overseer → Warden → fix → alert resolves | PASSED live, 25 Nov 2026: one webhook, one overseer run (Warden PASS, `ticket`), resolved 105 s after the fix, 5 quiet minutes, replay suppressed, `down.sh` ALL STOPPED | lab |
| Model-route probe | PASS live (ok, and a closed port classified as a wait) | same |
| Overseer (agent-health) agent live | **NOT PASSING.** First 3 runs: model 400 (a 4.4 MB tool result), fixed. One follow-up run: no 400, but it wandered (14 calls, 245000 tokens) and wrote no report; Warden blocked it. Budget and prompt fixes are offline-tested only | same |
| Spend and retry guards for the loop (attempt cap, 400 hold, 429 backoff, breaker, token budget, kill switch) | PASS offline, 25 tests incl. a replay of a real failed run; not driven by a live scheduler | `guard/circuit.py` |
| Alert delivery (Alertmanager to agent), Tempo span-metric alerts | **NOT RUN** | |
| kagent 1.0.1 (the lab profile version) | **NOT RUN**; verified on alpha17 only | |

A gate with no receipt is NOT RUN, never PASS.

## Two things to know before you start

1. **kagent 0.7.x and 1.x differ.** URL, request shape, where tool calls appear, and how the
   evaluator is reached all changed. The code handles both; see `docs/kagent-versions.md`.
2. **Placeholders.** Values such as `{{AGW_HOST}}` and `{{MODEL_CONFIG}}` are filled in the work
   environment. Never commit real hosts, tokens or receipts. Raw receipts hold prompts and answers.
