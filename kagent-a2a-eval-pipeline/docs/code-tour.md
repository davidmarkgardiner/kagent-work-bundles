# Code tour: what to point at during the demo

While you run a scene, show the YAML or Python behind it. `demo/show.sh <scene>` prints each excerpt from the real file, with the line to say, and `--step N`, `--pause` and `--list` help you pace it. This page is generated from `demo/show.py` (`demo/show.sh --markdown`), and a test keeps the two in step, so every excerpt below exists.

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

## `warden`

Run `demo/show.sh warden` (or `demo/show.sh warden --step 1`).

1. **Say:** The contract: which tools the worker may call, which it must call, how many calls it gets, what its report must contain, and which evaluator checks it.
   `completion-gate/contracts/sentinel-investigator.yaml`, the whole file
2. **Say:** The evaluator is itself an agent with no tools, generated from the contract, and told that the worker's text is untrusted. The worker never chooses the rules it is judged by.
   `completion-gate/manifests/completion-evaluator-agent.yaml`, from `s+systemMessage:`
3. **Say:** The verifier is plain code, no model. It reads the real tool calls in the saved run and compares them with the contract; the route (ticket, reject) comes from here.
   `verify_completion.py`, from `def verify(`

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

## `rogue`

Run `demo/show.sh rogue` (or `demo/show.sh rogue --step 1`).

1. **Say:** The rogue agent is given a delete tool it should not use. This stands in for a prompt-injection attack.
   `demo/lab/demo-agents.yaml`, from `name: demo-rogue`
2. **Say:** Before any block is applied, this code re-checks it independently: right kind of policy, right namespace, its own label, exactly one route, one single-expression Deny.
   `guard/enforce.py`, from `def validate`
3. **Say:** The rules for blocking: which findings may block at all, which may be applied automatically (only a forbidden tool from a real run), caps per hour, and a never-block list that includes the watchers themselves. A block does not expire; a person releases it.
   `demo/config/rules.demo.yaml`, from `blockSignals:`

## `broken`

Run `demo/show.sh broken` (or `demo/show.sh broken --step 1`).

1. **Say:** The broken agent's model route is this stub. It always answers 429, like a model that is out of quota.
   `demo/lab/broken-agent.yaml`, from `stub.py: |`
2. **Say:** The only switches the fix-it step may ever make: which agents, and which model configs a person approved in advance, plus caps and a never-touch list.
   `demo/config/fallbacks.demo.yaml`, the whole file
3. **Say:** The fix-it step is plain code, not an agent: kill switch, never-touch list, the agent must be listed, the failure must be a kind a fallback can fix, and the fallback must probe healthy.
   `guard/remediate.py`, from `def cmd_apply`

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
