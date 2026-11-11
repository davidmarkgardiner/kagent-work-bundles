# Annotated board poller — live evidence, 2026-09-27

## Scope and runtime

The existing Proxmox Kubernetes cluster and one Kimi model route were reused.
The control-plane VM ran the PM, builder, tester, reviewer, GitLab MCP, and
board poller. Both Kubernetes worker VMs remained off. At final check the
Proxmox host had 34 GiB available memory and zero swap use. The six rig
Deployments were 1/1 available. The poller Job requests 25m CPU and 48Mi
memory; its container limit is 250m CPU and 128Mi memory.

`CronJob/sdlc-board-poller` ran at 11:36 UTC and advanced issue #40 from
`agent:build` to `agent:test`. After the two issues finished, a scheduled
11:48 and 12:24 UTC Jobs exited with `{"event":"idle"}`. The CronJob was left enabled
with a two-minute schedule and `Forbid` concurrency. Manual Jobs accelerated
the other checkpoints. These receipts prove scheduled pickup and idle, but
the full two-issue completion was supervised and accelerated manually.

## Issue receipts

| Parent and child | Branch and pipeline | Draft MR and review | Final state |
|---|---|---|---|
| [#40](https://gitlab.com/davidmarkgardiner/debt-payoff-calculator-agentic-factory/-/work_items/40), child #42 | `agentic/sdlc-rig-40`, `2db22445`, [pipeline 2886845024](https://gitlab.com/davidmarkgardiner/debt-payoff-calculator-agentic-factory/-/pipelines/2886845024) success | [!10](https://gitlab.com/davidmarkgardiner/debt-payoff-calculator-agentic-factory/-/merge_requests/10), review note 3912377782 PASS | `agent:accepted` |
| [#41](https://gitlab.com/davidmarkgardiner/debt-payoff-calculator-agentic-factory/-/work_items/41), child #43 | `agentic/sdlc-rig-41`, `f30bf3ba`, [pipeline 2886925839](https://gitlab.com/davidmarkgardiner/debt-payoff-calculator-agentic-factory/-/pipelines/2886925839) success | [!11](https://gitlab.com/davidmarkgardiner/debt-payoff-calculator-agentic-factory/-/merge_requests/11), review note 3912505721 PASS | `agent:accepted` |

GitLab API was checked independently after the agent turns: each parent had
exactly one matching child, the latest branch commit matched the successful
pipeline and open draft MR SHA, and the tagged review note named that same
parent and full SHA. The branch diff in each case changed only `.gitlab-ci.yml`,
`package.json`, and `tests/calculator.test.mjs`. The MRs remained open drafts;
neither was merged.

Issue #41's first [pipeline 2886848238](https://gitlab.com/davidmarkgardiner/debt-payoff-calculator-agentic-factory/-/pipelines/2886848238)
failed. The poller moved the issue from `agent:test` to `agent:changes`; the
builder used the CI trace and repaired it. Review then revealed that the test
searched beyond the Verification section. The issue was deliberately returned
to rework. Review notes 3912482215 and 3912491271 requested a bounded section
assertion, and the board kept that finding through further CI failures. A
line-based extraction of the Verification section finally passed pipeline
2886925839. Reviewer note 3912505721 is PASS for the final SHA. The poller's
PM acceptance prompt needed a precise final-line format; two attempts stayed
in `agent:review`, then the corrected prompt returned `PM_VERDICT: ACCEPT`.
An independent local mutation check ran the final Node test against the
original README (pass), then moved the phrase from Verification to Approval
boundary (fail). This confirms the section requirement is enforced.

During a later rework turn, PM A2A timed out after 150 seconds. The builder
had already written a new commit. The poller found the branch SHA in GitLab
and advanced from that verified artifact; this is a live timeout recovery
receipt. The same run exposed a state bug where a failed CI SHA was compared
to an older review SHA. The poller now prioritizes the latest failed pipeline
and carries both CI and outstanding review findings into rework. Three local
regression tests cover existing-child resumption, one-turn MR creation, and
failed-CI rework after an older review.

## Recovery finding

A manually started builder Job overlapped the 11:36 scheduled Job just before
the CronJob was suspended. Both PM turns reached the builder. GitLab shows
several repair commits on issue #40's branch; the final SHA passed CI and the
label transition was not duplicated. The CronJob's `Forbid` policy serializes
its own scheduled Jobs, not separately created manual Jobs. Operationally,
suspend the CronJob and wait for an active scheduled Job to finish before a
manual run; re-enable it afterwards. A shared lease would be needed for safe
concurrent manual and scheduled control.

## Local and deployment checks

- Python syntax compiled; three regression tests passed for resumption and
  stage boundaries.
- The poller authenticated to the GitLab REST API with the project token in
  the Kubernetes Secret. No token value was printed or saved in this bundle.
- Public safety scan returned `{"clean":true,"hits":0}`.
- Final six rig Deployments were available, the Kubernetes control plane was
  Ready, and the CronJob was enabled with no active Job.

This is a bounded GitLab sandbox proof. The provider token expires
2026-10-27. General project profiles, cross-cluster assignment, gateway
policy for MCP, and fully unattended multi-issue soak remain outside this
verified run.
