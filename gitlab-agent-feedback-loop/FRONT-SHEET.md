# GitLab Agent Feedback Loop

## One-Line Ask

Let an allowlisted human give bounded feedback to a read-only kagent through a
GitLab Issue comment, with one auditable response and no duplicate replies.

## Start Here

1. `WORK-AGENT-START-PROMPT.md`
2. `CHECKLIST.md`
3. `GITLAB-CONFIGURATION-SHEET.md`
4. `requests/gitlab-agent-feedback-request.yaml`
5. `payload/REFERENCE.md`
6. `evidence/EVIDENCE-TEMPLATE.md`

## Target Path

```text
Private GitLab -> internal DNS / ingress / VirtualService -> Argo EventSource
-> Sensor -> Workflow -> read-only kagent -> GitLab Issue note
```

The EventSource is the only inbound endpoint. A VirtualService or internal
ingress must route only `POST /gitlab-agent-feedback` to the EventSource
service. Do not use a public Funnel in production.

## Required Markers

```text
PRIVATE_ROUTE_REACHABLE: yes
TLS_TRUST_CONFIRMED: yes
WEBHOOK_AUTH_CONFIRMED: yes
ALLOWLIST_AND_LABEL_GATES_CONFIRMED: yes
DEDUPLICATION_CONFIRMED: yes
READ_ONLY_AGENT_CONFIRMED: yes
GITLAB_REPLY_CONFIRMED: yes
NO_GITOPS_ACTION_EXECUTED: yes
EVIDENCE_CAPTURED: yes
OUTPUT_SANITIZED: yes
```

## Boundaries

- Only Issue notes from allowlisted users, with `agent:waiting-for-human` and
  an explicit `@platform-agent` mention are accepted.
- The EventSource bearer secret is an inbound authentication control; it is not
  a GitLab token.
- The writer is a dedicated project bot token, limited to creating Issue notes.
  Never use a personal CLI credential.
- The agent must have no write-capable MCP tools. Any remediation goes to a
  separate GitOps MR/approval path.

Static verification proves package consistency. The markers require a real
private GitLab, ingress, Argo Events, and kagent environment.
