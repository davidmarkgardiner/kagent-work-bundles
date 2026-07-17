# Copyable GitLab Ticket

## Title

Deploy bounded GitLab Issue-comment feedback loop for read-only kagent

## Description

Implement the private GitLab webhook path:

```text
GitLab -> internal ingress / VirtualService -> Argo EventSource -> Sensor
-> Workflow -> read-only kagent -> GitLab Issue note
```

Acceptance criteria:

- Only allowlisted users may trigger through `@platform-agent` on an Issue with
  `agent:waiting-for-human`.
- The EventSource accepts only authenticated `POST /gitlab-agent-feedback`.
- The workflow deduplicates by GitLab note ID.
- The feedback agent has no write tools and executes no remediation.
- A dedicated least-privilege project bot posts one response note.
- Tests prove reject, accept, and replay/no-duplicate behaviour.
- Evidence is sanitized and includes ingress, EventSource, workflow, and Issue
  note proof.

Source POC: `platform/argo-events/sources/gitlab/agent-feedback/`.
