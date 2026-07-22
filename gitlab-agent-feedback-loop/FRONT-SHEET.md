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
-> Sensor -> short Workflow -> bounded Issue/thread hydration
-> read-only kagent -> GitLab Issue note
```

The EventSource is the only inbound endpoint. A VirtualService or internal
ingress must route only `POST /gitlab-agent-feedback` to the EventSource
service. Do not use a public Funnel in production.

The workflow does not remain suspended while waiting for a person. It completes
after its current action; each eligible GitLab comment starts a new short
workflow that rehydrates bounded context. `agent-run-id: {{RUN_ID}}` in the
Issue description maps to `agent-feedback-run-{{RUN_ID}}` in the `argo`
namespace, written by the originating workflow and read by the feedback
workflow. See the source POC's `run-state.example.yaml`.

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
- A separate reader token may only read the target Issue and notes; it supplies
  bounded thread context to the agent.
- The direct POC writer is a dedicated project bot token. GitLab `api` scope is
  project-scoped but not endpoint-scoped; use a notes-only writer adapter when
  the production boundary must be technically enforced. Never use a personal
  CLI credential.
- The agent must have no write-capable MCP tools. Any remediation goes to a
  separate GitOps MR/approval path.

Static verification proves package consistency. The markers require a real
private GitLab, ingress, Argo Events, and kagent environment.
