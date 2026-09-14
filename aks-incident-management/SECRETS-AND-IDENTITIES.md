# Secret and identity contract

Create these through the organisation's approved secret manager. Do not put the values in this repository.

| Secret | Namespace | Required keys | Consumer |
|---|---|---|---|
| `incident-postgres-auth` | incident namespace | `username`, `password` | Postgres |
| `incident-runtime-auth` | incident and Argo Workflows namespaces | `database-url`, `read-token`, `intake-token`, `approval-token`, `executor-token` | coordinator and Workflow |
| `incident-integration-auth` | incident namespace | `teams-token`, `servicenow-token` | coordinator |
| `incident-gitlab-executor` | incident namespace | `token` | merge executor only |
| Kafka credentials secret | Argo Events namespace | `key`, `secret`, `ca.pem` | EventSource |

Use separate values for read, intake, approval, and executor. The Teams relay receives the approval token; the Workflow receives read, intake, and executor tokens. The read-only investigator receives none of them.

Prefer External Secrets plus workload identity for production. If direct Secrets are used for a non-production smoke test, create them interactively and exclude the command history and rendered output from evidence.
