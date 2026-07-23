# GitLab Configuration Sheet — Agent Feedback Loop

Use this sheet in the approved private GitLab environment. Fill in values in
the approved secret manager or deployment configuration; do not commit them.

## 1. Information to Collect

| Setting | Value to provide |
|---|---|
| GitLab base URL | `{{GITLAB_BASE_URL}}` |
| Project path or ID | `{{GITLAB_PROJECT}}` |
| Private ingress hostname | `{{GITLAB_FEEDBACK_HOSTNAME}}` |
| Webhook endpoint | `https://{{GITLAB_FEEDBACK_HOSTNAME}}/gitlab-agent-feedback` |
| Allowlisted GitLab usernames | `{{GITLAB_ALLOWED_USERNAMES}}` |
| Feedback agent service | `{{READ_ONLY_FEEDBACK_AGENT_SERVICE}}` |
| Inbound webhook secret | stored outside Git |
| Issue reader token | stored outside Git |
| Writer bot token | stored outside Git |

## 2. Create the GitLab Reader Token

Project access tokens create project-scoped bot users. Use them rather than a
personal access token. The bot is scoped to this one project, but its effective
abilities are still the combination of its selected role and token scope.

1. Open the target project.
2. Go to **Settings → Access tokens**.
3. Select **Add new token**.
4. Use name `agent-feedback-reader` and a short, documented expiry date.
5. Select role **Reporter**. This avoids repository push permission and can
   read private/confidential Issue context where permitted.
6. Select only scope **read_api**.
7. Select **Create project access token**.
8. Copy the token immediately into the approved secret manager. GitLab shows
   it once only; do not paste it into chat, tickets, terminals, or Git.

The reader is used only for `GET /projects/:id/issues/:iid` and
`GET /projects/:id/issues/:iid/notes`.

## 3. Create the GitLab Writer Token

Repeat **Settings → Access tokens → Add new token** with:

| Field | Value |
|---|---|
| Name | `agent-feedback-writer` |
| Expiry | short, documented, and monitored |
| Role | **Reporter** initially; raise only if the target GitLab version rejects issue-note creation |
| Scope | **api** |

GitLab's `api` scope is broad within the project token's project boundary.
Reporter prevents repository push, but it does **not** make the token endpoint
limited to Issue-note creation; do not claim that it does.

For this POC, record the role/scope and prove the bot identity posts the note.
For production where the writer must be technically unable to perform other API
writes, deploy a small writer adapter: the workflow sends it a validated agent
response, the adapter owns the project token, rejects every operation except
`POST /projects/:id/issues/:iid/notes`, and emits an audit record. Keep the
token out of the Argo workflow namespace in that model.

Do not use a personal CLI token. Do not grant repository push, merge-request
approval, project-settings, group-management, or administrator permissions.

Store its API token in the approved secret manager as the value later mounted
into the `gitlab-agent-feedback-writer` secret.

## 4. Create the Webhook

In the target GitLab project:

1. Open **Settings → Webhooks**.
2. Set the URL to the webhook endpoint above.
3. Leave SSL verification enabled. The internal ingress certificate must chain
   to a CA trusted by the GitLab host.
4. Enable **Comment events** (called Note events by some GitLab versions).
5. Configure a custom HTTP header:

   ```text
   Authorization: Bearer {{GITLAB_WEBHOOK_SECRET}}
   ```

6. Save the webhook, then use GitLab's test/delivery view to confirm it reaches
   the endpoint.

If the GitLab version cannot add a custom `Authorization` header, do not weaken
the EventSource. Put a small authenticated/signature-verifying adapter in front
of it that converts the GitLab request into the required bearer-authenticated
internal request.

The current EventSource uses bearer authentication because the installed Argo
Events CRD supports `authSecret`. If the private GitLab version offers a
different webhook signing mechanism, place a signature verifier in front of
the EventSource before changing the authentication model.

## 5. Configure the Cluster-side Secret References

Create these secrets through the approved secret-management process, never in
Git:

```text
namespace: argo-events
secret: gitlab-agent-feedback-webhook
key: secret
value: {{GITLAB_WEBHOOK_SECRET}}

namespace: argo
secret: gitlab-agent-feedback-writer
key: api-token
value: {{GITLAB_NOTE_WRITER_TOKEN}}

namespace: argo
secret: gitlab-agent-feedback-reader
key: api-token
value: {{GITLAB_ISSUE_READER_TOKEN}}
```

Configure the workflow's `allowed_users` value and feedback-agent service name
through the approved overlay/replacements mechanism. Keep the source
placeholders intact.

## 6. Configure the Ticket-producing Workflow

When an agent creates an Issue for human feedback, it must:

1. Write a bounded state record named `agent-feedback-run-{{RUN_ID}}` in the
   `argo` namespace, using the source `run-state.example.yaml` contract.
2. Put `agent-run-id: {{RUN_ID}}` on its own line in the Issue description.
3. Apply label `agent:waiting-for-human`.
4. End its workflow; it must not remain suspended waiting for a human.

Each later eligible comment starts a fresh workflow. That workflow reads the
Issue, newest bounded notes, and the matching run-state record before invoking
the read-only agent.

## 7. Prepare a Test Issue

1. Create an Issue.
2. Add label `agent:waiting-for-human`.
3. As an allowlisted person, add:

   ```text
   @platform-agent provide a concise read-only recommendation.
   ```

Expected result: one workflow runs and one bot note appears. The note must say
that it did not execute remediation or GitOps changes.

The workflow finishes rather than suspending. Each eligible new comment starts
a fresh workflow, which reads the Issue and newest bounded notes before it
calls the read-only agent. An originating agent may include
`agent-run-id: {{RUN_ID}}` in the Issue description and its originating
workflow must write the bounded `agent-feedback-run-{{RUN_ID}}` ConfigMap in
the `argo` namespace. The feedback workflow reads that record when it exists;
do not place raw logs or credentials in either record.

## 8. Verify Safety and Replay Behaviour

| Test | Expected result |
|---|---|
| No or wrong bearer header | EventSource returns HTTP 401 |
| Note without `@platform-agent` | no agent workflow |
| Author not allowlisted | no agent workflow |
| Issue lacks `agent:waiting-for-human` | no agent workflow |
| Accepted Issue note | one workflow and one bot response |
| Same payload redelivered | no second agent call or bot response |

Capture sanitized delivery, workflow, and Issue-note evidence in
`evidence/EVIDENCE-TEMPLATE.md`.

## 9. Rotation and Revocation

- Record reader and writer token expiry dates in the team secret inventory.
- Rotate each token before expiry through **Settings → Access tokens**.
- Update only the matching Kubernetes secret through the approved secret flow.
- Trigger a new synthetic Issue comment to prove the new secret is used.
- Revoke the old project token after the new-token proof succeeds.
- Immediately revoke and replace any token that appears in terminal output,
  chat history, a ticket, a commit, or an artifact.

## 10. Private-network Checks

- GitLab webhook workers can resolve and reach the internal ingress or
  VirtualService.
- GitLab trusts the ingress certificate chain.
- The proxy preserves the `Authorization` header.
- Only `POST /gitlab-agent-feedback` routes to the EventSource service.
- The feedback agent has no write-capable tools.
