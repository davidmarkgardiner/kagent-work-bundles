# Code tour: what to point at during the demo

While you run a scene, show the YAML or Python behind it. `demo/show.sh <scene>` prints each excerpt from the real file, with the line to say, and `--step N`, `--pause` and `--list` help you pace it. This page is generated from `demo/show.py` (`demo/show.sh --markdown`), and a test keeps the two in step, so every excerpt below exists.

Two more views. `demo/show.sh map` prints which folder does what, for the start of the demo. `demo/show.sh <scene> --live` prints what that scene just wrote under `$RUN` (the finding, the applied policy, the ledger, the posted note, the run record), so you can point at the real output as well as the code. If a file is not there yet, it says so: run the scene first (`reset` removes the Guard files).

## Map

- `demo/`: the live demo: run-demo.sh (the scenes), show.sh (this tour), demo agents and case files
- `a2a_capture.py, score_and_gate.py`: Assay: ask an agent over A2A, record the run, score it; the exit code blocks a merge
- `cases/, scorer/`: Assay test cases and the scoring code
- `completion-gate/, verify_completion.py`: Warden: a contract per agent, an evaluator agent, and a plain-code verifier
- `demo/sentinel_check.py`: Sentinel's detection step for the demo (the real Sentinel is a scheduled job in its own bundle)
- `guard/`: Guard: watch runs, raise findings, propose and apply blocks, switch broken models; every act has a ticket
- `gateway/`: the agentgateway route the A2A calls go through
- `lookout/`: Lookout: the merge request review agent, its GitLab tool server, the CI job and the lab mock
- `tests/`: unit tests for all of the above (run by verify-bundle.sh)
- `evidence/`: what was actually run in the lab, with results and known limits
- `docs/, presentation/`: the docs site, walkthrough, launch deck and flow pages

## `lights`

Run `demo/show.sh lights` (or `demo/show.sh lights --step 1`).

1. **Say:** No agent runs here. This is plain kubectl and one probe per model route: which agents are ready, which model each uses, the gateway's answer and how many Guard blocks exist.
   `demo/run-demo.sh`, from `lights() {`
2. **Say:** The probe sends one token and classifies the answer in code: 429 is rate_limited, 5xx server_error, 401 or 403 auth, no answer timeout. The fix-it step later trusts this, not a model.
   `guard/model_probe.py`, from `def probe`

After the scene, `demo/show.sh lights --live` shows what it wrote:

- `$RUN/probe-primary.json`: The probe of the stub route: rate_limited, HTTP 429. That is the starting state the broken scene fixes.
- `$RUN/probe-fallback.json`: The probe of the real model: ok, HTTP 200.

## `assay`

Run `demo/show.sh assay` (or `demo/show.sh assay --step 1`).

1. **Say:** This is the test. One case file: the question the agent is asked, the terms a good answer must contain, the tools it must and must not call, and a budget.
   `demo/cases/demo-healthy-lists-pods.yaml`, the whole file
2. **Say:** Same shape for the rogue agent. It is told to delete a pod, so the forbidden tool is the delete call. This case is expected to FAIL; that is the negative test.
   `demo/cases/demo-rogue-injection.yaml`, the whole file
3. **Say:** This is how a run is judged, beyond the score: a required tool never called, or too many tool calls, is a hard fail whatever the answer says.
   `score_and_gate.py`, from `def gate_checks`
4. **Say:** In GitLab this is a matrix job, one per agent. The report job that follows sets the exit code, and that exit code is what blocks the merge.
   `.gitlab-ci.yml`, from `eval:`

After the scene, `demo/show.sh assay --live` shows what it wrote:

- `$RUN/assay/report/summary.md`: The scorecard Assay just wrote from the real runs: one verdict per agent and the first problem it found.

## `sentinel`

Run `demo/show.sh sentinel` (or `demo/show.sh sentinel --step 1`).

1. **Say:** Detection is plain code: read the pods, and any container stuck crashing or restarting becomes one finding with an incident key the agent must echo.
   `demo/sentinel_check.py`, from `def findings`
2. **Say:** The investigator's instructions: read-only, the finding is untrusted data, and three ordered steps: investigate, write the report in fixed sections, then hand it to the evaluator.
   `completion-gate/manifests/sentinel-investigator-agent-v1alpha3.yaml`, from `STEP 1.`
3. **Say:** The demo agent is that same Sentinel agent, renamed. Same prompt and tools; only the name and the model change. The evaluator is generated from the contract.
   `demo/lab/sentinel_manifests.py`, from `def investigator`
4. **Say:** The contract Warden checks the run against: read-only tools only, which ones must be used, at most 14 calls, the report's sections, and the evaluator's PASS.
   `completion-gate/contracts/sentinel-investigator.yaml`, the whole file
5. **Say:** Only a PASS writes a ticket, and the ticket is the exact report the evaluator approved. The agent never writes it.
   `demo/run-demo.sh`, from `if [[ "$route" == ticket ]]`

After the scene, `demo/show.sh sentinel --live` shows what it wrote:

- `$RUN/sentinel-finding.json`: The finding Sentinel's code raised: the incident key, the pod, the reason and the restart count.
- `$RUN/sentinel-verdict.json`: Warden's verdict on the live run: PASS or FAIL, the route, the tools that really worked, and any failures.
- `$RUN/sentinel-ticket.md`: The ticket, written only after a PASS, from the exact report the evaluator approved: cause, evidence per tool, next steps.

## `warden`

Run `demo/show.sh warden` (or `demo/show.sh warden --step 1`).

1. **Say:** The contract: which tools the worker may call, which it must call, how many calls it gets, what its report must contain, and which evaluator checks it.
   `completion-gate/contracts/sentinel-investigator.yaml`, the whole file
2. **Say:** The evaluator is itself an agent with no tools, generated from the contract, and told that the worker's text is untrusted. The worker never chooses the rules it is judged by.
   `completion-gate/manifests/completion-evaluator-agent.yaml`, from `s+systemMessage:`
3. **Say:** The verifier is plain code, no model. It reads the real tool calls in the saved run and compares them with the contract; the route (ticket, reject) comes from here.
   `verify_completion.py`, from `def verify(`

After the scene, `demo/show.sh warden --live` shows what it wrote:

- `$RUN/warden-out.json`: The verifier's output for the last recorded run: the verdict, the route, and why. Plain code wrote this, not a model.

## `healthy`

Run `demo/show.sh healthy` (or `demo/show.sh healthy --step 1`).

1. **Say:** The healthy agent: one read-only tool, nothing else. It stays inside this allowlist.
   `demo/lab/demo-agents.yaml`, from `name: demo-healthy`
2. **Say:** Guard's per-agent allowlist: each demo agent may call only the read tool. Anything else it calls becomes a finding.
   `demo/config/rules.demo.yaml`, from `agents:`
3. **Say:** And the budgets that apply to every run: how long, how many tokens per run and per hour, how many failed calls. A run over budget is a finding too.
   `demo/config/rules.demo.yaml`, from `defaults:`
4. **Say:** The detector reads the recorded events and returns findings, plus coverage gaps. A run it cannot see is reported as a gap, never as clean.
   `guard/detect.py`, from `def evaluate`

After the scene, `demo/show.sh healthy --live` shows what it wrote:

- `$RUN/f-healthy.json`: Guard's report for the healthy run: no findings, and the status says it could see the run.

## `rogue`

Run `demo/show.sh rogue` (or `demo/show.sh rogue --step 1`).

1. **Say:** The rogue agent is given a delete tool it should not use. This stands in for a prompt-injection attack.
   `demo/lab/demo-agents.yaml`, from `name: demo-rogue`
2. **Say:** Before any block is applied, this code re-checks it independently: right kind of policy, right namespace, its own label, exactly one route, one single-expression Deny.
   `guard/enforce.py`, from `def validate`
3. **Say:** The rules for blocking: which findings may block at all, which may be applied automatically (only a forbidden tool from a real run), caps per hour, and a never-block list that includes the watchers themselves. A block does not expire; a person releases it.
   `demo/config/rules.demo.yaml`, from `blockSignals:`

After the scene, `demo/show.sh rogue --live` shows what it wrote:

- `$RUN/f-rogue.json`: The finding: which agent, which forbidden tool, and the evidence taken from the recorded run.
- `$RUN/proposals/policy-*.yaml`: The block Guard proposed: deny one caller on one route. The file is the proposal; enforce.py re-checked it before applying it, and the ledger records that.
- `$RUN/proposals/ticket-01.md`: The ticket written for a person, so the block is never silent.
- `$RUN/ledger.jsonl`: The ledger: every apply and release, with a time. This is the audit trail.

## `release`

Run `demo/show.sh release` (or `demo/show.sh release --step 1`).

1. **Say:** Releasing is a person's act. This code deletes the block only if Guard's own label is on it (it refuses anything else) and writes the release to the ledger.
   `guard/enforce.py`, from `    if args.cmd == "release":`
2. **Say:** The scene finds the blocks by that same label, releases each one, then calls the gateway again to show 403 turning back into 200.
   `demo/run-demo.sh`, from `release() {`

After the scene, `demo/show.sh release --live` shows what it wrote:

- `$RUN/ledger.jsonl`: The ledger now ends with the release, done by a person.
- `$RUN/gw.txt`: The gateway's answers in order: before the block, blocked, released.

## `broken`

Run `demo/show.sh broken` (or `demo/show.sh broken --step 1`).

1. **Say:** The broken agent's model route is this stub. It always answers 429, like a model that is out of quota.
   `demo/lab/broken-agent.yaml`, from `stub.py: |`
2. **Say:** The only switches the fix-it step may ever make: which agents, and which model configs a person approved in advance, plus caps and a never-touch list.
   `demo/config/fallbacks.demo.yaml`, the whole file
3. **Say:** The fix-it step is plain code, not an agent: kill switch, never-touch list, the agent must be listed, the failure must be a kind a fallback can fix, and the fallback must probe healthy.
   `guard/remediate.py`, from `def cmd_apply`

After the scene, `demo/show.sh broken --live` shows what it wrote:

- `$RUN/probe-primary.json`: The probe of the agent's own model route: the kind of failure and the HTTP code.
- `$RUN/probe-fallback.json`: The probe of the approved fallback: it must be healthy before anything is switched.
- `$RUN/tickets/remediation-demo-worker.md`: The ticket the fix-it step wrote for a person: what it switched and how to undo it.
- `$RUN/remediation.jsonl`: The remediation ledger: the switch, with a time.

## `reset`

Run `demo/show.sh reset` (or `demo/show.sh reset --step 1`).

1. **Say:** Undo only what was recorded: the revert refuses unless the agent carries Guard's note that it was switched away from the approved primary.
   `guard/remediate.py`, from `def cmd_revert`
2. **Say:** The demo's reset: revert the model switch, clear the cooldown by hand, release every Guard-labelled block, delete the run's Guard files.
   `demo/run-demo.sh`, from `reset() {`

## `lookout`

Run `demo/show.sh lookout` (or `demo/show.sh lookout --step 1`).

1. **Say:** These seven tools are everything the review agent can call. There is no approve, merge, push or delete tool, and no tool to write code.
   `lookout/manifests/mr-security-review-agent.yaml`, from `    tools:`
2. **Say:** The prompt: the pointer is the only instruction; the merge request's own words are untrusted data; the steps; what a finding needs (file and line, evidence, a fix); and the PARTIAL rule.
   `lookout/manifests/mr-security-review-agent.yaml`, from `    systemMessage:`
3. **Say:** The safety is in code, not in the prompt. The tool server has GET calls plus note create and update only, so there is nothing to be tricked into.
   `lookout/gitlab_review_mcp.py`, from `Safety lives here`
4. **Say:** Posting the note: the commit must still be the merge request's head (an old run never overwrites a newer review), the header is written here, only its own note is updated, and the text is sanitised.
   `lookout/gitlab_review_mcp.py`, from `    def post_note`
5. **Say:** The CI job does not take the agent's word. It checks the tool calls: a note counts as posted only if the post call succeeded for this project, merge request and commit.
   `lookout/lookout_review.py`, from `def classify`
6. **Say:** The CI template: only merge request pipelines, one review at a time per merge request, advisory (allow_failure), and only the small run record is kept as an artifact.
   `lookout/ci/lookout.gitlab-ci.yml`, from `lookout:review:`
7. **Say:** The flaws the demo plants, so you can say what the review should find: a command injection, an unsafe pickle and a SQL injection, in the first, middle and last file.
   `lookout/lab/mock_gitlab.py`, from `def _mid_files`
8. **Say:** And this is the test that keeps it read-only: it fails if the tool server's code ever gains an approve, merge, commit-creating or delete call.
   `tests/test_lookout_mcp.py`, from `def test_source_has_no_write_or_approve_paths`

After the scene, `demo/show.sh lookout --live` shows what it wrote:

- `$RUN/lookout/note1.txt`: The note the agent posted on the first review: findings with file, line, evidence and a fix.
- `$RUN/lookout/r1/lookout-run.json`: The CI job's record of that run: status, mode, every tool call and the token cost.
- `$RUN/lookout/r2/lookout-run.json`: The retry of the same commit: up_to_date, a few tool calls and a fraction of the tokens.
- `$RUN/lookout/note3.txt`: The note after the push: still one note, now listing every current finding.
- `$RUN/lookout/r4/lookout-run.json`: The injection run: forbidden_tools is empty, so the merge request's text did not make it call anything else.
