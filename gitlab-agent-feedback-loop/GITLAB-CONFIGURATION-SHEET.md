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
| Writer bot token | stored outside Git |

## 2. Create the GitLab Writer Identity

Create a dedicated project bot or service account. It must only be able to add
notes to Issues in this project.

Do not use a personal CLI token. Do not grant repository push, merge-request
approval, project-settings, group-management, or administrator permissions.

Store its API token in the approved secret manager as the value later mounted
into the `gitlab-agent-feedback-writer` secret.

## 3. Create the Webhook

In the target GitLab project:

1. Open **Settings → Webhooks**.
2. Set the URL to the webhook endpoint above.
3. Enable **Comment events** (called Note events by some GitLab versions).
4. Configure a custom HTTP header:

   ```text
   Authorization: Bearer {{GITLAB_WEBHOOK_SECRET}}
   ```

5. Save the webhook, then use GitLab's test/delivery view to confirm it reaches
   the endpoint.

The current EventSource uses bearer authentication because the installed Argo
Events CRD supports `authSecret`. If the private GitLab version offers a
different webhook signing mechanism, place a signature verifier in front of
the EventSource before changing the authentication model.

## 4. Configure the Cluster-side Secret References

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
```

Configure the workflow's `allowed_users` value and feedback-agent service name
through the approved overlay/replacements mechanism. Keep the source
placeholders intact.

## 5. Prepare a Test Issue

1. Create an Issue.
2. Add label `agent:waiting-for-human`.
3. As an allowlisted person, add:

   ```text
   @platform-agent provide a concise read-only recommendation.
   ```

Expected result: one workflow runs and one bot note appears. The note must say
that it did not execute remediation or GitOps changes.

## 6. Verify Safety and Replay Behaviour

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

## 7. Private-network Checks

- GitLab webhook workers can resolve and reach the internal ingress or
  VirtualService.
- GitLab trusts the ingress certificate chain.
- The proxy preserves the `Authorization` header.
- Only `POST /gitlab-agent-feedback` routes to the EventSource service.
- The feedback agent has no write-capable tools.
