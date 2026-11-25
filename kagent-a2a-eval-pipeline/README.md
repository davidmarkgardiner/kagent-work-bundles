# kagent A2A eval pipeline

A GitLab CI pattern that sends evaluation prompts to live kagent agents through
the **agentgateway A2A endpoint**, captures the answer plus the full tool
trajectory, and scores it with the existing deterministic scorer
(`observability/agent-evals/scripts/score-agent-run.py`, reused unchanged).

Visual explainer: [EVALUATION-EXPLAINED.html](EVALUATION-EXPLAINED.html).

## Assay and Warden

| Name | What | Where |
|---|---|---|
| **Assay** | Tests an agent before it ships: a GitLab pipeline sends seeded-fault cases through the gateway and scores the result (pass^3) | this folder |
| **Warden** | Signs off each run after it ships: an evaluator agent plus a deterministic check of the controller history gate delivery | `completion-gate/`, `verify_completion.py` |

**Handing this to a work agent?** Start at [FRONT-SHEET.md](FRONT-SHEET.md), complete [HUMAN-PREREQUISITES.md](HUMAN-PREREQUISITES.md), then give the work agent
[WORK-AGENT-PROMPT.md](WORK-AGENT-PROMPT.md). `./verify-bundle.sh` checks the bundle offline. The agents here are read-only investigators: they diagnose and report, they do not fix.
The folder name `kagent-a2a-eval-pipeline` is kept for stable paths.

## Why this shape

Earlier work in this repo built the scorer (for captured runs) and Promptfoo
skill-content suites. Both bundles flag the same gap: nothing called real agents
over A2A and captured trajectories. This bundle fills that gap and nothing more.

| Layer | AKS-Skills reference | Here |
|---|---|---|
| Routing / liveness | `tier: smoke`, skill-invocation | `tier: smoke` case, 1 call, gates the rest |
| Investigation | `tier: mock`, shimmed az/kubectl fixtures | `tier: full`, seeded fault + healthy decoy in a throwaway `eval-*` namespace |
| Trajectory | `tool-calls`, `tool-call-count` | required/forbidden tools, namespace, `maxToolCalls` |
| Quality | `g-eval` rubric | deterministic terms (gate) + `judge.py` rubric (advisory) |
| Skill content | promptfoo quality/routing/baseline | keep `../promptfoo-kubernetes` for that |

## Files

| File | Role |
|---|---|
| `a2a_capture.py` | Calls `message/send` via the gateway, classifies `completed` / `agent_error` / `infra_error`, writes run + raw receipt |
| `score_and_gate.py` | Runs the scorer, adds gate checks (missing tool, tool budget), pass^k verdicts, JUnit + summary |
| `judge.py` | Optional LLM rubric through an OpenAI-compatible route; never gates |
| `cases/` | `AgentEvalCase` YAML with `${EVAL_*}` placeholders |
| `fixtures/cluster/` | Seeded fault manifests (restricted PSA) |
| `gateway/route-a2a-eval.yaml` | Per-agent allowlisted HTTPRoute + rate-limit/timeout policy |
| `.gitlab-ci.yml` | validate → smoke → eval (matrix per agent) → report |
| `Dockerfile` | Runner image: python + PyYAML + kubectl |
| `tests/` | Offline contract tests with a real kagent A2A fixture and a mock A2A server |

## Run locally

```sh
pip install -r requirements.txt
python -m unittest discover -s tests -v        # offline, 216 tests
python tests/lint_cases.py cases

export AGW_BASE_URL=https://{{AGW_HOST}} AGW_TOKEN={{TOKEN}}
export EVAL_AGENT=k8s-agent EVAL_NAMESPACE=eval-local
kubectl create ns $EVAL_NAMESPACE && kubectl -n $EVAL_NAMESPACE apply -f fixtures/cluster/
python a2a_capture.py --cases-dir cases --out out/cap --repeat 3
python score_and_gate.py --capture-dirs out/cap --repeat 3 --out out/report
```

Exit codes: `0` pass, `1` quality failure, `3` errors/missing (inconclusive), `2` nothing scored.

## Two evaluation stages

| Stage | When | Question | Where |
|---|---|---|---|
| 1. Promotion eval | Pipeline, before an agent is promoted | Is this agent fit for purpose? Seeded faults, pass^3 | This bundle |
| 2. Completion gate | Every production run | Did this run finish properly? The agent has an evaluator agent check its output over A2A; a deterministic check of the controller history gates delivery | [`completion-gate/`](completion-gate/README.md) |

One contract file drives both. With `--contracts-dir`, stage 1 also fails an
agent that does not close its stage 2 loop, so the loop is proven before
promotion.

## Live verification

Verified end to end on a home-lab cluster (kagent 0.7.13, agentgateway 0.11.1)
on 23 November 2026, through the gateway route, not a port-forward. Smoke pass^1
and full pass^3 both passed at 1.0; every tool call in the raw A2A history was
captured. See `evidence/LIVE-PROXMOX-2026-11-23.md`.

Live findings now built in:

- kagent binds a `contextId` to the first agent that used it. A reused id
  returns `403` from the controller (surfaced as task `failed`) or leaks earlier
  history into the run. `a2a_capture.py` now makes every run id unique.
- A model backend outage returns HTTP 200 with `kagent_error_code=API_ERROR`.
  The pipeline reports it as `error` (exit 3), never as a quality fail.
- An agent can occasionally close its runner without answering. The call then
  hits `--timeout` and is recorded as `infra_error`, not retried.
- Set `EVAL_MODEL_LABEL` so results record which model was evaluated.

## Not yet verified

- Only kagent 0.7.13 has been checked for tool calls in A2A `history`; re-check
  after a kagent upgrade.
- The forbidden-tool check trusts A2A history. Proof needs a join with gateway
  or OTel audit data on the recorded `trace_id`.
- `judge.py` scores are uncalibrated; keep advisory.
- Receipts contain prompts, tool arguments and answers: keep artifact access at
  developer level and short retention; never commit raw receipts.

## Launch deck

`presentation/launch-deck.html`: the five-product launch deck (Sentinel, Assay, Warden, Guard, Overseer) with the two live demos and the evidence. One self-contained file: open it in Chrome, no network needed. Arrow keys or space to move, N for speaker notes, F for full screen, Ctrl+P prints one slide per page.
