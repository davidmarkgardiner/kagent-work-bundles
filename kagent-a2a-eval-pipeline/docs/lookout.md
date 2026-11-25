# Lookout: security review on a merge request

Lookout gives a merge request a first, **advisory** security review. A GitLab CI job sends a pointer (project, merge request number, commit) to an agent on the cluster over A2A. The agent reads the merge request through a small GitLab tool server and leaves **one note**. A person still reviews and merges. It sits beside Assay and Warden and changes neither.

```text
merge request pipeline job -> A2A pointer -> agentgateway -> agent mr-security-review
                                                             reads the MR, posts ONE note
the job checks the agent's tool calls: "completed" is not "posted"
```

## What it cannot do

- The tool server's code has GET calls plus note create and update only. There is no approve, merge, push or delete call to be tricked into, and a test fails if one appears.
- The agent has seven tools. The server serves an eighth (a delta-only diff) that the agent is deliberately not given.
- The review is pinned to one commit. If the merge request moved on, the diff tool errors and the note tool refuses to post, so an older run never overwrites a newer review.
- Anything in the merge request (title, description, code, comments) is treated as untrusted data. An injected instruction is reported as a finding, not followed.
- Note text is sanitised: no images, raw HTML or @mentions.

## Review modes

| Mode | When | Cost seen in the lab |
|---|---|---|
| `up_to_date` | the existing note already covers this exact commit (a retried job) | about 7k input tokens, nothing posted |
| `full` | anything else: a new merge request, or a new commit | about 14k to 60k input tokens; about 40k for a 970-line merge request |

Delta-only (incremental) review is **switched off**. In a lab run it dropped two earlier findings from the note, because the note is overwritten in place. It can come back once findings are structured and the tool server refuses a post that omits an open one.

## Size

About 1,500 lines of diff fit in one review; a 970-line merge request was reviewed in full. Beyond the cap the note opens with "PARTIAL ... Reviewed X of Y files" and lists what it did not read. A 10,500-line, 150-file merge request was reviewed as 30 of 150 files. For very large changes, split the merge request or add scanners; Lookout is not a whole-repository scan.

## What is proven, and what is not

| Claim | Status |
|---|---|
| Note posted, same-commit retry, push, and an injection merge request, against a mock GitLab on kagent 1.0.0-alpha17 (`demo/run-demo.sh lookout`) | PASSED live in the lab, 4 of 4 checks |
| A real GitLab | PASSED once, on a gitlab.com sandbox merge request: posted, then updated in place |
| From a real CI runner, through the agentgateway route, on kagent 0.7.x, on a work GitLab, with a least-privilege token | NOT RUN |
| Independent code review | NOT DONE |

## Where things are

The code and manifests are in the bundle folder `lookout/`; its README has the deploy steps. `lookout/ci/run_local.py` replays the CI job on your own machine with no runner and no exposed endpoint. The evidence, with every defect found and fixed, is `evidence/LIVE-LOOKOUT-LAB-2026-11-25.md`. See also [Variables](variables.md), [Prerequisites and air-gap](prerequisites.md) and [Live demo](demo.md).
