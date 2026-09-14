# Teams approval relay contract

The bundle posts `incident.approval.v1` to `TEAMS_APPROVAL_URL`. The relay renders the Adaptive Card and keeps sensitive evidence behind the GitLab or Argo link.

On Approve or Reject, the relay must perform these two authenticated calls in order:

1. POST the decision to the coordinator's `decision_url` with `Authorization: Bearer <approval-token>` and JSON `{"decision":"approved|rejected","action_id":"<approval_id>","actor":"<resolved UPN>"}`.
2. Only if step 1 succeeds, POST the original workflow identity, decision, approval id, and approver to `argo_callback_url`. Argo Events resumes an approved Workflow or stops a rejected one.

A retry of step 1 receives a conflict after the first accepted decision and must be treated as already decided after reading the incident record. Never resume a Workflow when the coordinator rejected the action id, the approval expired, or the resource version changed.

The callback endpoint must be exposed through the existing private gateway, protected with TLS, relay authentication, and network policy. The sample EventSource itself does not authenticate HTTP; the gateway or service mesh must enforce this before production.
