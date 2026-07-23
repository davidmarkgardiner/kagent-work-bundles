# Private Deployment Checklist

## Before deployment

- [ ] GitLab webhook workers can resolve and reach the private ingress.
- [ ] The ingress certificate chains to a CA trusted by GitLab.
- [ ] The ingress preserves the `Authorization` header.
- [ ] Only `POST /gitlab-agent-feedback` is routed to the EventSource.
- [ ] Inbound webhook secret, reader token, and writer bot token are stored outside Git.
- [ ] Reader token can only read target-project Issues and notes.
- [ ] Writer bot is project-scoped; its `api` scope and role are documented.
- [ ] A notes-only writer adapter is planned or deployed if endpoint-level
  no-other-writes enforcement is required.
- [ ] Feedback agent has no write tools.

## Proof

- [ ] Wrong/missing bearer secret returns HTTP 401.
- [ ] Unmentioned, wrong-label, and non-allowlisted notes create no agent call.
- [ ] Accepted note creates one successful workflow and one Issue reply.
- [ ] Agent input contains the current Issue, latest bounded notes, and any `agent-run-id` marker.
- [ ] An agent-originated ticket loads its bounded `agent-feedback-run-{{RUN_ID}}` state record.
- [ ] Replay of the same note ID creates no second reply.
- [ ] Response states that no remediation or GitOps action was executed.

## Stop conditions

Stop and escalate if TLS trust, header forwarding, bot-token scope, agent tool
scope, or duplicate suppression cannot be proven.
