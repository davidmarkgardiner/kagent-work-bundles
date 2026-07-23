# Durable Agent Memory on kagent — Work Bundle

Give kagent agents **long-term memory that survives restarts** — so an agent can
recall what it learned in a previous, unrelated session. Backed by
**PostgreSQL + pgvector**, not the ephemeral in-memory SQLite a stock lab
install uses.

This bundle is a reproducible package to stand it up, prove it works, and adapt
it to a work cluster. **It has been run live** on an isolated kind cluster
2026-07-16 — full durable store, cross-restart survival, and cross-session
agent self-recall: [`evidence/RUN-2026-07-16.md`](evidence/RUN-2026-07-16.md).

- Upstream concept: https://kagent.dev/docs/kagent/concepts/agent-memory
- In-repo reference (ground truth vs source): [`../../a2a/memory-reference.md`](../../a2a/memory-reference.md)
- Production/architecture target: [`../../docs/kagent-memory/production-target/README.md`](../../docs/kagent-memory/production-target/README.md)

---

## Two native memory scopes (both proven)

kagent has two **native** memory mechanisms — this bundle proves both, and
deliberately ignores any custom memory-MCP:

- **Session ("cache") memory** — the conversation history of one A2A thread
  (`session` + `event` tables). "What did we just discuss?"
- **Long-term ("database index") memory** — per-agent+user facts with a pgvector
  similarity lookup (`memory` table). "What has this user ever told me?" — recalled
  in a brand-new session.

Both are only durable when the controller runs on Postgres+pgvector; the default
SQLite-on-`emptyDir` loses both on pod restart. The rest of this file focuses on
the long-term path (the harder, more valuable one); session-cache durability is
evidenced in [`evidence/RUN-2026-07-16.md`](evidence/RUN-2026-07-16.md).

## What it is

kagent has **native long-term memory**: enable it per-agent with a
`spec.declarative.memory` block, and the runtime automatically adds
`save_memory`, `load_memory`, and `prefetch_memory` tools plus an auto-save
callback that summarises the session every 5 user turns. On the **first message
of every new session**, `prefetch_memory` embeds the user's question, runs a
pgvector similarity search, and injects matching prior facts into the context.

That is the "self-learning autonomy" loop: **the agent looks up what it did /
was told before, in a brand-new conversation.**

```
Classic agent                       Memory-enabled agent
-------------                       --------------------
Each session starts blank.          New session -> prefetch_memory embeds the
Forgets everything between chats.   question -> pgvector search -> prior facts
                                    injected -> agent answers with continuity.
```

## Why Postgres + pgvector matters (the durability point)

| | Stock lab kagent (`red`) | This bundle |
|---|---|---|
| Store | SQLite on an in-memory `emptyDir` | PostgreSQL + pgvector on a PVC |
| Survives controller restart | ❌ memory evaporates | ✅ memory persists |
| Survives DB pod restart | n/a | ✅ (proven: killed both, memory recalled) |
| Vector search | SQLite (dev) | pgvector HNSW, cosine |
| Durable database shape | No | Yes with managed Postgres, pgvector, backup and access controls; native memory itself remains Preview/stabilising |

A memory an agent forgets when its pod recycles is not memory you can build on.
Durable Postgres is what turns "remembers until restart" into "remembers across
restarts and failover."

## Two things you must get right

1. **A vector-capable database.** `database.postgres.vectorEnabled=true` **and**
   a Postgres that actually has pgvector. The chart's bundled default
   (`postgres:18.3-alpine`) does **not** — override it to `pgvector/pgvector`
   (see [`examples/values-pgvector.yaml`](examples/values-pgvector.yaml)). For
   work, use an external managed Postgres with the `vector` extension.
2. **An embedding-capable `ModelConfig`.** `spec.declarative.memory.modelConfig`
   must point at a model that emits embeddings. kagent hardcodes **768
   dimensions** — Ollama `nomic-embed-text` is a native-768 exact match with no
   external key ([`examples/modelconfig-embedding-ollama.yaml`](examples/modelconfig-embedding-ollama.yaml)).
   For work, use Azure OpenAI embeddings.

> ⚠️ Native memory is Preview/stabilising in kagent. Treat as an
> evaluation / platform-readiness exercise, not a prod dependency yet.

## Quickstart (isolated kind, fully local, no keys)

```bash
# 1. cluster + kagent on bundled pgvector Postgres
bash scripts/install-memory.sh

# 2. Level A — durable store + cross-restart survival (no embedding model needed)
bash scripts/memory-durability-test.sh

# 3. embedding + chat via Ollama (local), then the memory agent
kubectl apply -f examples/ollama-embeddings.yaml
kubectl -n kagent exec deploy/ollama -- ollama pull nomic-embed-text
kubectl -n kagent exec deploy/ollama -- ollama pull qwen2.5:1.5b-instruct
kubectl apply -f examples/modelconfig-embedding-ollama.yaml \
              -f examples/modelconfig-chat-ollama.yaml \
              -f examples/agent-memory.yaml

# 4. Level B — agent self-recall across a fresh session
bash scripts/agent-recall-test.sh
```

## Verify (any cluster, read-only)

```bash
bash scripts/verify-memory.sh --context <kube-context>
```

Checks the controller's vector setting, controller wiring, bundled pgvector
extension and memory-enabled agents. For managed/external Postgres, run the
extension query from an approved database-admin path; this verifier deliberately
fails rather than claiming it has inspected a database it cannot reach.

## What's in this bundle

| Path | Purpose |
|---|---|
| `README.md` | This file |
| `GITLAB-TICKET.md` | Paste-ready GitLab issue for the work Kanban |
| `WORD-HANDOVER-SUMMARY.md` | Concise, paste-ready decision and implementation summary |
| `DEEP-DIVE.md` | How native memory works: tools, prefetch, embeddings, pruning, keys |
| `evidence/RUN-2026-07-16.md` | Live proof: backend, Level A durability, Level B recall |
| `scripts/install-memory.sh` | kind + kagent on bundled pgvector Postgres |
| `scripts/memory-durability-test.sh` | Level A: store/search/isolation + restart survival |
| `scripts/agent-recall-test.sh` | Level B: fresh-session self-recall via Ollama |
| `scripts/verify-memory.sh` | Read-only wiring check (works on AKS too) |
| `scripts/teardown.sh` | Delete the kind cluster |
| `examples/values-pgvector.yaml` | Helm values (bundled + external Postgres shapes) |
| `examples/ollama-embeddings.yaml` | In-cluster Ollama (nomic-embed-text + chat) |
| `examples/modelconfig-embedding-ollama.yaml` | Embedding ModelConfig (768-dim) |
| `examples/modelconfig-chat-ollama.yaml` | Chat ModelConfig (local) |
| `examples/agent-memory.yaml` | The memory-enabled Agent CR |

## Taking it to work (AKS)

1. Provision managed PostgreSQL (Azure Database for PostgreSQL Flexible Server)
   with the `vector` extension; add `vector` to `azure.extensions` and restart
   before `CREATE EXTENSION vector;`.
2. Point kagent at it: `database.postgres.urlFile` (mounted Secret) +
   `vectorEnabled=true`, `bundled.enabled=false`.
3. Create an embedding `ModelConfig` on Azure OpenAI embeddings.
4. Enable `spec.declarative.memory` on **one** low-risk agent; run
   `verify-memory.sh` + a recall test; only then widen.

See [`../../docs/kagent-memory/production-target/README.md`](../../docs/kagent-memory/production-target/README.md)
for the store-ownership boundaries (native memory vs shared incident memory vs
Git runbooks) — do not collapse them.
