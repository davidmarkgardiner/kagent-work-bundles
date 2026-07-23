# Evidence Record

| Check | Evidence reference | Result | Sanitized |
|---|---|---|---|
| Private route and TLS | `{{REFERENCE}}` | pass_or_fail | yes |
| Invalid webhook auth rejected | `{{REFERENCE}}` | pass_or_fail | yes |
| Invalid note rejected | `{{REFERENCE}}` | pass_or_fail | yes |
| Issue/thread context hydration | `{{REFERENCE}}` | pass_or_fail | yes |
| Accepted note workflow | `{{REFERENCE}}` | pass_or_fail | yes |
| Read-only agent call | `{{REFERENCE}}` | pass_or_fail | yes |
| Single GitLab reply | `{{REFERENCE}}` | pass_or_fail | yes |
| Replay deduplicated | `{{REFERENCE}}` | pass_or_fail | yes |

Markers:

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
