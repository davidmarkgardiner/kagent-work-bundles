# Recovery comparison scorecard

Status: unfilled template. All trial results are `NOT_RUN`.

The [specification](README.md) defines the cases, limits, and adoption criteria. The [runbook](RUNBOOK.md) defines the execution procedure.

## Admission

| Requirement | Result | Receipt |
| --- | --- | --- |
| Exact cluster and version pair | NOT_RUN | Missing |
| Equivalent model route and generation settings | NOT_RUN | Missing |
| Common fixture and independent ledger | NOT_RUN | Missing |
| Native approval and TaskStore admission | NOT_RUN | Missing |
| Pi adapter and decision admission | NOT_RUN | Missing |
| Single writer and restored database writeability | NOT_RUN | Missing |
| Scope and model budget | NOT_RUN | Missing |

Admission result: NOT_RUN.

## Trial results

Each arm and case requires two repetitions. A cell contains both repetition IDs and their receipt paths after execution.

| Case | Native kagent | Pi Durable | Paired conclusion |
| --- | --- | --- | --- |
| C0: normal completion | NOT_RUN | NOT_RUN | None |
| C1: observer disconnect | NOT_RUN | NOT_RUN | None |
| C2: interrupted safe read | NOT_RUN | NOT_RUN | None |
| C3: uncertain external mutation | NOT_RUN | NOT_RUN | None |
| C4: restart while awaiting approval | NOT_RUN | NOT_RUN | None |
| C5: denial and invalid decisions | NOT_RUN | NOT_RUN | None |
| C6: actor suspend and restore | NOT_RUN | NOT_RUN | None |

Each trial record contains these independent fields:

| Field | Permitted values or measurement |
| --- | --- |
| Execution status | NOT_RUN, BLOCKED, UNSUPPORTED, or EXECUTED |
| Evidence completeness | COMPLETE or MISSING, with the missing receipts listed |
| Safety | PASS or FAIL, with attempted and committed effect counts |
| Task completion | COMPLETED, FAILED, DECLINED, or UNRESOLVED |
| Recovery mode | automatic, supported-resume, manual, or blocked |
| Identity continuity | Original and recovered context, task, conversation, and decision IDs |
| Mutation effects | Expected count, attempt count, and committed count |
| Recovery time | Seconds after process availability; operator wait reported separately |
| Requests | Model and tool counts before and after the fault |
| Operator intervention | Action, target identity, purpose, and outcome |
| Storage integrity | Actual command or API, exit status, and state readback |

An execution with missing receipts has no passing overall conclusion. `UNSUPPORTED` describes a capability gap; it is not a substitute for executing a supported fault case.

## Implementation cost

| Measurement | Native kagent | Pi Durable |
| --- | --- | --- |
| Harness-specific executable lines | Not measured | Not measured |
| Engineer hours | Not measured | Not measured |
| New operational services | Not measured | Not measured |
| Measured model charges | Not measured | Not measured |
| Unresolved lifecycle or storage issues | Not reviewed | Not reviewed |

Line counts include the Pi BYO adapter and exclude the shared fixture and test runner. Existing framework code is excluded from both counts. A dependency upgrade or custom patch is identified separately.

## Decision

Decision: UNDECIDED.

The final report states whether Pi adds a demonstrated recovery advantage, a measured implementation advantage, or neither. The report names every unresolved safety issue and incompatible capability.

If both arms perform equivalently and Pi adds maintenance work, retain the native runtime. If Pi adds a measured benefit and satisfies every safety invariant, propose one limited pilot. An incomplete comparison produces no adoption recommendation.
