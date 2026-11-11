# Our skill test, explained simply

We built a practice test for an AI helper.

We give the helper a question, watch what it actually does, and check its work. This helps us decide whether a particular set of instructions is ready to use more widely.

## Think of a classroom

| The real name | Think of it as |
| --- | --- |
| **Agent** | The helper doing the work. |
| **Skill** | An instruction sheet the helper can read. |
| **Golden scenario** | A practice question with a checklist of what a good attempt must include. |
| **Cluster** | The classroom where the helper already works. |
| **Operator** | The organiser that starts the test and checks the evidence. |
| **Job** | A short task that runs the test and then finishes. |

The helper does the work. A separate checker decides whether it meets the checklist. The helper cannot pass itself by saying, “I did a good job.”

## What happens during a test?

Imagine the instruction sheet says:

> Open our troubleshooting guide. Read the right section. Explain the problem and include the source link.

The test works like this:

1. **We ask for a test.** We choose the practice question and the exact version of the instructions.
2. **The organiser checks the labels.** It makes sure we are testing the intended helper and files.
3. **A short task asks the real helper the question.** This happens inside the cluster.
4. **We collect evidence.** Did the helper actually open the skill and read the required reference? We check the recorded actions and returned text.
5. **The organiser marks the work.** It checks that evidence against its own copy of the instructions and the agreed checklist.
6. **We save the result.** The record includes digital fingerprints of the files, so we know which version was tested.

If we change the instructions, the old result does not prove that the new version works. The new version needs its own test.

## There are three possible results

| Result | What it means |
| --- | --- |
| **Passed** | The helper met this test's checklist. |
| **Failed** | The test worked, but the answer missed something required. |
| **Error** | We could not trust or complete the test. For example, it selected the wrong version or the model was unavailable. |

“Passed” means this particular test passed. It does not mean every answer the helper gives will be correct.

## Why run it on the cluster?

Your idea was to test the helper where it actually works.

That lets us exercise the real agent, its real skill files and its real reading tools. We do not need a cloud CI pipeline to start the test. A pipeline could request the same test later if useful.

## What have we proved?

In the recorded lab run on **11 November 2026**, the system correctly handled all three results:

- A complete answer passed.
- An answer missing a required item failed.
- A request naming the wrong version produced an error before a test task started.

We also restarted the organiser during a test. It found the existing task and finished checking that task's evidence.

The question was a made-up troubleshooting exercise. The model, agent and document reads were real. This first proof used one documentation skill on kagent 0.7.13.

## What is still a future step?

**Automatic testing when we add a skill.** Today, someone must request the test. Adding a skill alone does not start one yet.

**DeepEval.** Think of this as an extra marker that could help judge the meaning and quality of an answer. We have not connected it. Today's checker uses the agreed steps, required words and source link.

**GitLab.** After a passing test, the future plan is for an authorised agent to prepare a repository change for review. Today, the bundle can write a local handoff note. It does not push to GitLab or open a merge request.

For the technical details, use the [main README](README.md), [design](DESIGN.md) or [recorded proof](evidence/proof.json).
