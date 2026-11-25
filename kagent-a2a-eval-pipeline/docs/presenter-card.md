# Presenter card

One page to keep beside the terminal. Generated from `demo/show.py` (`demo/show.sh --card`); a test keeps it in step with the code tour.

Before the first scene: `demo/show.sh map` (which folder does what).

## 1. `demo/run-demo.sh lights` (instant)

- **See:** three agents ready; demo-worker on demo-stub-429; stub route rate_limited 429, real model ok 200; gateway 200; guard blocks active: 0
- **Say:** This is the starting state. One agent is set up to fail on purpose; we fix it later.
- **Point at:** `demo/show.sh lights`, then `demo/show.sh lights --live`

## 2. `demo/run-demo.sh assay` (about 3 min)

- **See:** demo-healthy pass, demo-rogue fail with 'forbidden tool used: k8s_delete_resource', gate exit code 1
- **Say:** No agent merges without passing its test, and the test checks the tools it really called, not just its answer.
- **Point at:** `demo/show.sh assay`, then `demo/show.sh assay --live`

## 3. `demo/run-demo.sh warden` (instant)

- **See:** good run and overseer: PASS route=ticket; extra tool and too many calls: FAIL route=reject; evaluator said FAIL: route=evaluation_failed_ticket
- **Say:** The agent never decides whether its own work is good enough; a contract and plain code do.
- **Point at:** `demo/show.sh warden`, then `demo/show.sh warden --live`

## 4. `demo/run-demo.sh healthy` (about 1 min)

- **See:** the agent lists pods, then 'clean: nothing flagged, nothing blocked'
- **Say:** A normal run raises no alarm. Guard is quiet when nothing is wrong.
- **Point at:** `demo/show.sh healthy`, then `demo/show.sh healthy --live`

## 5. `demo/run-demo.sh rogue` (about 2 min)

- **See:** finding forbidden_tool [k8s_delete_resource]; gateway BEFORE 200, then BLOCKED 403; a ticket for a person
- **Say:** The agent used a tool it should not have. Guard blocked that one caller on that one route, and wrote a ticket.
- **Point at:** `demo/show.sh rogue`, then `demo/show.sh rogue --live`

## 6. `demo/run-demo.sh release` (under 1 min)

- **See:** Gateway timeline: BEFORE 200 -> BLOCKED 403 -> RELEASED 200
- **Say:** Blocks never lift themselves. A person read the ticket and released it.
- **Point at:** `demo/show.sh release`, then `demo/show.sh release --live`

## 7. `demo/run-demo.sh broken` (about 3 min)

- **See:** stub 429, fallback 200; demo-worker switched from demo-stub-429 to the approved fallback; a ticket
- **Say:** Its model was out of quota. Code switched it to a fallback a person had approved in advance, after checking that fallback works.
- **Point at:** `demo/show.sh broken`, then `demo/show.sh broken --live`

## 8. `demo/run-demo.sh reset` (instant)

- **See:** 'reset done'; run lights again and it shows the starting state
- **Say:** Everything the demo changed is put back, through the same audited paths.
- **Point at:** `demo/show.sh reset`

## 9. `demo/run-demo.sh lookout` (about 4 min (optional))

- **See:** four checks: the note names the planted flaws; the retry is up_to_date; after a push the note lists every finding; the injection run calls no forbidden tool
- **Say:** The agent reviews a merge request and leaves one advisory note. It has no tool that can approve or merge.
- **Point at:** `demo/show.sh lookout`, then `demo/show.sh lookout --live`

If a result is not what this card says, stop and read it; do not re-run in a loop. `reset` removes the Guard files, so show `--live` before you reset.
