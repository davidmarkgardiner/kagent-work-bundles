# GitLab Ticket — paste onto the work Kanban

Copy the block below into a new GitLab issue. It is written as one epic with a
task checklist so it drops straight onto a board. The home-lab spike proving
this is native-kagent-only is **done**
([`evidence/RUN-2026-07-16.md`](evidence/RUN-2026-07-16.md)); this ticket carries
it to an approved non-prod work cluster.

---

**Title:** Enable durable native kagent agent memory (Postgres + pgvector)

**Labels:** `kagent`, `memory`, `platform-readiness`

**Description:**

Give kagent agents durable memory using the **native** kagent mechanisms only
(no custom memory MCP):

- **Session ("cache") memory** — conversation history for an A2A thread.
- **Long-term ("database index") memory** — per-agent+user facts with pgvector
  vector lookup, so an agent recalls prior facts in a brand-new session.

Both are durable only when the controller runs on **PostgreSQL + pgvector**; the
default SQLite-on-`emptyDir` loses them on pod restart. Home-lab spike proved
the full path (store, vector search, isolation, restart survival, cross-session
prefetch recall) on isolated kind — see `work-agent-bundles/agent-memory/`.

**Tasks:**

- [ ] Provision approved non-prod **managed PostgreSQL** (Azure DB for
  PostgreSQL Flexible Server) with `vector` in `azure.extensions`; restart;
  `CREATE EXTENSION vector;`. Creds via Key Vault / External Secrets — none in Git.
- [ ] Point kagent controller at it: `database.postgres.urlFile` (mounted
  Secret) + `database.postgres.vectorEnabled=true`,
  `database.postgres.bundled.enabled=false`. Confirm existing agents undisturbed.
- [ ] Add an **embedding-capable ModelConfig** (Azure OpenAI *embedding*
  deployment, not chat). kagent hardcodes 768 dims; fix the embedding model for
  the life of the data.
- [ ] Enable `spec.declarative.memory` on **one** low-risk agent.
- [ ] Prove: save in session 1 → recall in a fresh session 2; isolation
  (other user/agent see nothing); recall survives a controller restart.
- [ ] Run `work-agent-bundles/agent-memory/scripts/verify-memory.sh --context <ctx>`.

**Acceptance / proof markers:**

```
DATABASE_VECTOR_ENABLED: true
PGVECTOR_EXTENSION: present
NATIVE_MEMORY_WRITE: stored
NATIVE_MEMORY_LOOKUP: hit
NATIVE_MEMORY_ISOLATION: passed
SESSION_CACHE_RESTART_SURVIVAL: passed
NATIVE_MEMORY_RESTART_SURVIVAL: passed
```

**Gotchas (from the spike):**

- Bundled chart Postgres image has no pgvector — use an external pgvector-capable
  Postgres (or override the image for a throwaway).
- Native long-term memory keys rows by `{namespace}__NS__{agent_name}`, not the
  CR name — matters only for manual seeding / migration.
- Embedding route is mandatory; without it the memory tools silently no-op.

**Reference:** `work-agent-bundles/agent-memory/` (README, DEEP-DIVE, evidence,
scripts).
