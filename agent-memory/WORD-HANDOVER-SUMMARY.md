# Durable Native Agent Memory — Word Handover Summary

## Decision in one sentence

Use native kagent memory only for per-agent and per-user continuity; pilot it on one low-risk agent with managed PostgreSQL plus pgvector, while keeping shared incident lessons behind MCP and canonical procedures in Git/RAG.

## What this work proved

The isolated kind evaluation proved:

- long-term native memory writes and pgvector similarity lookup;
- strict agent and user isolation;
- survival of controller and Postgres pod restarts;
- session-cache durability on the same database; and
- retrieval during the first message of a fresh agent session.

It did not prove production operation, data governance, backup recovery or a full natural-language answer from the slow CPU-only lab model.

## Correct boundaries

| Need | Correct store/access path |
|---|---|
| A user's history with one agent | Native kagent memory, scoped per agent and user. |
| Cross-agent incident lessons | Governed memory MCP service backed by PostgreSQL and pgvector. |
| Approved runbooks and canonical facts | Git plus RAG/querydoc with citations. |
| Live operational state | Read-only platform tools and observability queries. |

Agents should call MCP for shared memory; they should not connect directly to its database.

## Required AKS pilot gates

1. Managed PostgreSQL with the pgvector extension, backup, encryption, retention and access ownership agreed.
2. Controller database credentials mounted from an approved Secret reference; never stored in Git or Helm command arguments.
3. A stable embedding ModelConfig whose output dimension is compatible with kagent native memory.
4. One low-risk agent, one named owner and an explicit memory data-classification rule.
5. A proof of write, new-session recall, cross-user/agent isolation and controller restart survival.
6. A clear retention/erasure process before storing any personal or sensitive facts.

## Current limitations

- Native memory is Preview/stabilising, not a production dependency yet.
- It is semantic per-agent/per-user memory, not shared team knowledge.
- Embedding model changes invalidate comparison with older vectors unless migration is planned.
- The current local proof observed retrieval but did not prove a fast end-user response from the CPU-bound chat model.

## Recommended next action

Create the non-production pilot using the bundle GitLab ticket. Run the strengthened verifier and attach the explicit proof markers before extending memory to another agent or considering shared-memory integration.
