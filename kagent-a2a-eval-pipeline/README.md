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
| **Lookout** | Reviews each merge request for security: a GitLab job sends a pointer over A2A, an agent reads the MR through a read-only GitLab MCP and leaves one advisory note | `lookout/` |

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
python -m unittest discover -s tests -v        # offline, 362 tests
python tests/lint_cases.py cases

export AGW_BASE_URL=https://{{AGW_HOST}} AGW_TOKEN={{TOKEN}}
export EVAL_AGENT=k8s-agent EVAL_NAMESPACE=eval-local
kubectl create ns $EVAL_NAMESPACE && kubectl -n $EVAL_NAMESPACE apply -f fixtures/cluster/
python a2a_capture.py --cases-dir cases --out out/cap --repeat 3
python score_and_gate.py --capture-dirs out/cap --repeat 3 --out out/report
```

Exit codes: `0` pass, `1` quality failure, `3` errors/missing (inconclusive), `2` nothing scored.

## Lookout: security review on every merge request

A third feature in this bundle, separate from Assay and Warden and changing neither. A GitLab MR pipeline job (`lookout/ci/lookout.gitlab-ci.yml`) sends a pointer (project, MR iid, head sha) over A2A through agentgateway to the `mr-security-review` agent. The agent reads the MR through a eight-tool GitLab MCP and leaves one advisory note for the human reviewer. It never approves or merges, and the job never blocks the pipeline. Start at [`lookout/README.md`](lookout/README.md).

Status (incremental review is switched off pending a fix; every new commit gets a full review): proven on a home-lab kagent 1.0.0-alpha17 with GLM against a mock GitLab (including a prompt-injection MR and a stale-SHA case that exposed and fixed a real overwrite bug) and once against a real gitlab.com sandbox MR (one note, updated in place on re-run). Not proven from a real CI runner, through agentgateway, on kagent 0.7.x, or with a least-privilege token. See [`evidence/LIVE-LOOKOUT-LAB-2026-11-25.md`](evidence/LIVE-LOOKOUT-LAB-2026-11-25.md).

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

## Presenting the demo

- `docs/presenter-card.md` (or `demo/show.sh --card`): one page per scene giving the command, what you should see, the sentence to say and what to point at.
- `demo/show.sh map`: which folder does what, for the start.
- `demo/show.sh <scene>`: the YAML or Python behind a scene (`--pause` steps through it). `demo/show.sh <scene> --live`: what that scene just wrote under `$RUN` (finding, block policy, ledger, ticket, note, run record).
- `docs/walkthrough.md`: the full script. `docs/code-tour.md`: every excerpt.
- The `sentinel` scene (part of `all`) runs Sentinel live: detection code, the read-only investigator, Warden on the real run, a ticket only on PASS.
- On kagent 0.9 only the `warden` and `lookout` scenes run (`LOOKOUT_KAGENT_API=0.7`); the other scenes need kagent 1.x.

## Launch deck

`presentation/launch-deck.pdf` is the same deck as a 24-page PDF. `presentation/launch-deck.html`: the five-product launch deck (Sentinel, Assay, Warden, Guard, Overseer) with the two live demos and the evidence. One self-contained file: open it in Chrome, no network needed. Arrow keys or space to move, N for speaker notes, F for full screen, Ctrl+P prints one slide per page.
