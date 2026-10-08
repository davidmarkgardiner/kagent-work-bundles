# Independent review: scheduled namespace health job

Review the attached PLAN.md independently. The user wants a clean, succinct,
efficient job that checks namespace state, logs and Events and forwards a useful
summary to Kafka for Argo. Challenge the architecture and scope, not just wording.

This is a design review. Do not implement, deploy, contact a cluster, send
messages, install packages or read another review. The supplied source excerpts
and inventory are evidence only within their stated limits. If reviewing the
attached text without repository tools, identify the result as a supplied-material
review; never claim a live test or a source inspection you did not perform.

Return Markdown, approximately 800–1,400 words:

1. Verdict: ACCEPT, ACCEPT WITH CONDITIONS, or REVISE BEFORE BUILD.
2. Is one stateless scheduled job appropriate? Identify any smaller design that
   still satisfies state, Events and application-only log-error detection.
3. P0/P1/P2 findings with exact plan section, concrete failure scenario, smallest
   correction and acceptance test. Focus on score semantics, sampled-log bias,
   temporal evidence, scope, cost, first-valid-report behavior, retries and Argo.
4. Dependencies or operational machinery that can be removed; guarantees that
   cannot honestly be provided without retained state.
5. Whether one cluster envelope with namespace findings fits the user's need,
   and the exact required receiver change versus the legacy v2 incident path.
6. Five strongest home-lab falsification tests and workplace prerequisites.
7. A short recommended build order, identifying what must be decided before code.

Do not insist on lossless history, exactly-once Kafka records, a database,
ticketing or autonomous recovery unless necessary for the stated contract.
Also do not approve a proposal that quietly drops log-only faults, calls sampled
counts namespace-wide rates, assumes a log store exists, or claims duplicate-free
effects without a concrete boundary. Keep requirements proportional to the goal.

State reviewer/model identity only when actually known. Agreement between models
does not replace implementation and live end-to-end evidence.
