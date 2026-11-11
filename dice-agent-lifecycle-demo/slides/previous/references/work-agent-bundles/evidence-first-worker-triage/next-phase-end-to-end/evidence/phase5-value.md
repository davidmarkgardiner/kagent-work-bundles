# Phase 5 — Value: what a human saved

Take ticket [#453](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/453)
as the representative example. A pod (`scheduling-failure-confluent`) failed
to schedule due to a bad `nodeSelector`. Without this pipeline, an on-call
engineer would first have to notice the failure (via whatever alerting
exists), then run `kubectl describe pod`/`kubectl get events` themselves to
find the `FailedScheduling` reason, then read the raw scheduler message to
understand *why* (node affinity mismatch), then decide if it's worth a
ticket, then write one by hand. With this pipeline, by the time a human opens
the ticket it already contains: the exact reason and severity, the redacted
raw scheduler event, and a complete read-only agent diagnosis that already
did the "describe the pod, check the node, read the event" legwork and
concluded *"Likely Cause: ... 1 node(s) didn't match Pod's node
affinity/selector"* with a recommended next step and a confidence score — the
same triage a human would have spent several minutes reconstructing by hand,
already done and time-stamped at the moment the ticket was created (`First
seen` / `Last seen` fields, not "sometime before I noticed it").

The bounded-concurrency drill (`phase5-backend-drills.md`) demonstrates the
same value under load: 8 simultaneous incidents did not overwhelm the
on-call queue with 8 partial/racing investigations — they queued cleanly (5
processed at a time) and each still arrived pre-triaged, in order, with none
lost or duplicated.
