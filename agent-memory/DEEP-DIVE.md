# Deep Dive — How Native kagent Memory Works

The mechanics behind "the agent looks up what it did before," cross-checked
against the kagent source and proven live 2026-07-16
([`evidence/RUN-2026-07-16.md`](evidence/RUN-2026-07-16.md)).

## The three scopes — don't conflate them

| Scope | What | Lifetime | Store |
|---|---|---|---|
| A2A session memory | one conversation thread (`contextId`) | that session | `session` table |
| **Native long-term memory** | per-agent + per-user facts across sessions | TTL (default 15d) | `memory` table + pgvector |
| Shared incident memory | cross-agent lessons | curated | separate MCP service ([production-target](../../docs/kagent-memory/production-target/README.md)) |

This bundle is about the **middle** one: native long-term memory. It is
per-agent and per-user isolated by design — not a shared knowledge base.

## What "enable memory" actually turns on

Adding `spec.declarative.memory.modelConfig` to an Agent (no `enabled` flag —
presence of the block is the switch) makes the runtime add three tools and one
callback automatically:

| Mechanism | When it fires | What it does |
|---|---|---|
| `prefetch_memory` | **first user message of every new session** | embeds the prompt (split into sentences), pgvector similarity search, injects top matches into the first LLM turn |
| `load_memory` | when the model decides mid-reasoning it needs more | embedded query → similarity search → compact JSON back |
| `save_memory` | when the model decides a fact is worth keeping | stores the fact verbatim + embedding |
| auto-save callback | every 5 user turns (async) | summarises the session, embeds, writes to `memory` |

`prefetch_memory` is the one that delivers cross-session recall without the
model having to do anything — it runs before the agent even "thinks."

## The retrieval path (proven)

```
new A2A session, first message
  -> prefetch_memory
       -> embed(question) via memory.modelConfig   [Ollama nomic-embed-text, 768-dim]
       -> POST /api/memories/search {agent_name, user_id, vector, limit:5, min_score:0.3}
       -> controller: pgvector cosine search (HNSW, vector_cosine_ops)
       -> top matches injected into the LLM context
  -> agent answers with the recalled fact
```

Measured on the lab run: question-vs-stored-fact cosine **0.85** (threshold
0.3), and the runtime logged `Successfully retrieved memories` for a brand-new
session that had never seen the fact.

## Storage facts

- **Embedding dimension is hardcoded to 768.** Pick a model that emits 768
  (nomic-embed-text is native-768) or accept truncation/normalisation. Do **not**
  change embedding models mid-life — existing vectors live in the old model's
  space and cosine becomes meaningless.
- **pgvector index:** HNSW, `vector_cosine_ops`.
- **TTL + popularity:** default 15 days; a pruning job runs ~every 24h. Memories
  with `access_count >= 10` get their expiry bumped and count reset (useful
  memories survive by natural selection); the rest are deleted at expiry.
- **Isolation:** every row is keyed by `agent_name` + `user_id`. A different
  agent or user sees nothing. Proven: cross-agent and cross-user reads returned
  `[]`.

## The internal agent_name key (a real gotcha)

The runtime does **not** key memory by the Agent CR's `metadata.name`. It uses
an internal app identifier:

```
agent_name = {namespace}__NS__{name_with_hyphens_replaced_by_underscores}
# CR  kagent/memory-selflearn-agent
#  -> kagent__NS__memory_selflearn_agent
```

`save_memory` and the auto-save callback write this key automatically, and
`prefetch_memory`/`load_memory` search it — so normal operation just works. It
only bites you when you **pre-seed or migrate** memories through the REST API:
seed under the plain CR name and the agent's own search returns `No memories
found` even though the vector is a 0.85 match. Match the `{ns}__NS__{name}` form.

Discover the exact value from inside the agent pod:

```bash
kubectl exec -n kagent <agent-pod> -- \
  python3 -c "from kagent.core import KAgentConfig as C; print(C().app_name)"
```

## Durability: why the DB choice is the whole point

The controller stores sessions and memory in whatever DB it's configured for.
A stock lab install uses SQLite on an in-memory `emptyDir` — fast, zero-setup,
and **gone when the controller pod restarts**. Switching the controller to
PostgreSQL + pgvector (a PVC-backed or managed DB) is what makes memory durable.

Proven on the lab run: after storing a memory, **both** the Postgres pod and the
controller pod were destroyed and rolled back — the memory was still retrievable
(and its `access_count` incremented, confirming a fresh query hit durable
storage). That is the line between "remembers until the pod recycles" and
"remembers across restarts and failover."

## Embedding provider reality

Native memory is dead without an embedding route. On the lab, the only
OpenAI-shaped key available was actually an OpenRouter key (401 against
`api.openai.com/embeddings`), and the free chat model was 429-throttled — so the
proof used **Ollama in-cluster** (`nomic-embed-text` + a small chat model), which
needs no external key and is the right posture for an air-gapped work cluster.
In work, point `memory.modelConfig` at **Azure OpenAI embeddings** (an embedding
deployment, not a chat one) and keep the model stable for the life of the data.

## Where native memory stops

- **No cross-agent sharing** — per-agent by design. For shared incident lessons
  use a purpose-built MCP service (see
  [production-target](../../docs/kagent-memory/production-target/README.md)).
- **No SQL/structured filters** — semantic search only.
- **No compliance-grade audit** — out of scope; keep sensitive/audited data in a
  dedicated MCP-fronted store, not native memory.
- **Not the canonical knowledge base** — runbooks/docs belong in Git +
  doc2vec/querydoc with citations, not in remembered facts.
