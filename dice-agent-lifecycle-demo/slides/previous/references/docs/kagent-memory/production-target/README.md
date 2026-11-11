# Durable Agent Memory Production Target

This is the target design for giving kagent agents useful memory across
sessions, A2A handoffs, and recurring incidents. It is deliberately also the
**development target**: development proves the same durable, governed design
on synthetic data before it is connected to real operational signals.

It does not make an agent automatically correct or permit it to change its
own production behaviour. It lets an agent retrieve prior, attributable
evidence; verify whether it still applies; and propose a reviewed update after
the outcome is known.

## Outcome

Before taking a write-capable action, a triage agent can answer:

- Have we seen a materially similar incident before?
- What was the verified cause and outcome last time?
- Was the prior action approved, rejected, or later superseded?
- Which workflow, ticket, pull request, dashboard, and human approval support
  that conclusion?

The agent uses the result as a lead, not as authority. It must verify the
current state with read-only tools and follow a GitOps workflow or approved
remediation path for any change.

## Architecture

```text
Alert, chat request, or workflow event
  -> Argo Workflow / kagent A2A session
  -> build normalised incident fingerprint
  -> shared-memory MCP: exact + semantic search
  -> querydoc/RAG: retrieve cited runbook or policy
  -> read-only investigation of current state
  -> synthesis: prior evidence + live evidence + verdict
  -> HITL when change is proposed
  -> curator workflow: validate, deduplicate, and persist lesson
  -> scheduled evaluation: promote proven lessons to Git runbooks or skills
```

Use separate stores with clear ownership:

| Store | Holds | Does not hold |
|---|---|---|
| kagent controller PostgreSQL | Sessions and native per-agent/per-user memory | Shared incident history or canonical procedures |
| Shared-memory PostgreSQL | Incident fingerprints, lessons, decisions, relationships, outcomes, audit data, embeddings | Raw chat transcripts, secrets, or unreviewed procedures |
| Git repository | Runbooks, skills, agent prompts, WorkflowTemplates, policies | Mutable incident history |
| querydoc/RAG index | Searchable, cited view of Git-approved documentation | The only source of operational history |
| Argo workflow artifacts | Active evidence, A2A `contextId`, approval ID, proposed memory update | Long-lived organisational memory |

## Development and Production Shape

Use the same component boundaries in both environments.

| Area | Development proof | Production target |
|---|---|---|
| Database | Dedicated non-production PostgreSQL with `vector` extension | Managed PostgreSQL with private access, backups, HA, and retention policy |
| Data | Synthetic incidents and placeholder-safe evidence only | Sanitised operational records under agreed retention and classification rules |
| Memory MCP | Read-only search for agents; curator write path enabled for synthetic lessons | Read-only search for specialists; curator-only writes with audit and transactions |
| Knowledge retrieval | `querydoc` over this repo or an approved non-production Markdown KB | `querydoc` or enterprise search over approved, access-controlled docs |
| Remediation | Recommendation string or sandbox Git PR only | GitOps workflow/PR plus explicit human approval |
| Evaluation | Repeat-incident and negative-retrieval fixtures | Scheduled quality, safety, and regression evaluation |

Do not use an in-memory SQLite controller database or a file-backed graph as
the proof of cross-restart, cross-session learning. Those are useful local
experiments, but they do not prove the target durability or write safety.

## Shared Semantic Memory

Semantic information lives in the **shared-memory PostgreSQL database**. A
vector is an index for finding relevant records; it is not the record itself.
Each record has structured columns for filtering and audit, a human-readable
summary, and an embedding for similarity search.

Suggested schema:

```text
incident_memory
  id, status, severity, domain, cluster, namespace
  fingerprint_json                 -- reason, kind, error code, normalised message
  summary, root_cause, action, outcome
  confidence, valid_from, expires_at, supersedes_id
  embedding vector(768)            -- use the dimension expected by kagent today
  created_at, created_by, source_workflow, source_context, approval_id

memory_evidence
  memory_id, evidence_type, reference, captured_at

memory_relation
  from_memory_id, relation_type, to_memory_id
  -- e.g. caused_by, remediated_by, supersedes, owned_by

memory_audit
  memory_id, actor, action, before_json, after_json, occurred_at
```

The MCP surface should offer two retrieval modes:

1. `search_lessons`: filters by exact fingerprint fields, then performs vector
   search on the normalised symptom and returns a small ranked result set.
2. `open_lesson`: returns the full record, relationships, evidence references,
   confidence, and supersession state.

Use a database transaction or queue for every write. Do not let several agents
perform read-modify-write updates against a shared file or graph.

## MCP Is the Agent Boundary

Agents access shared memory through MCP, not through a direct database
connection. MCP is the preferred boundary for this platform because it gives
every agent the same narrow, auditable tool contract while the service retains
database credentials, query policy, embedding generation, and write controls.

```text
triage Agent
  -> RemoteMCPServer/memory-mcp
  -> shared-memory MCP service
       -> exact metadata filters
       -> embedding generation
       -> PostgreSQL + pgvector hybrid query
       -> evidence and audit lookup
```

This does **not** mean that MCP itself provides semantic search. The MCP
service must implement the hybrid query against PostgreSQL. Direct agent-to-
PostgreSQL access is not the target: it would distribute credentials and allow
each agent to make inconsistent, unaudited retrieval and write decisions.

### Current POC versus production contract

The current `memory-mcp` registration exposes knowledge-graph tools named
`search_nodes`, `open_nodes`, and `read_graph`. That proves MCP discovery and
read-only tool wiring, but it does not by itself prove pgvector-backed hybrid
semantic retrieval. The current graph also has a documented concurrent-write
limitation.

The production replacement should retain the `memory-mcp` service identity but
expose a purpose-built contract:

| Tool | Audience | Behaviour |
|---|---|---|
| `search_lessons` | Read-only triage and specialist agents | Exact fingerprint filters plus vector similarity; returns ranked, active, non-superseded summaries and evidence IDs |
| `open_lesson` | Read-only triage and specialist agents | Returns full lesson, relationships, evidence, audit summary, and supersession state |
| `propose_lesson` | Evidence/coordinator path only | Creates a proposal for the curator; does not write canonical memory directly |
| `curate_lesson` | Curator workflow only | Validates, redacts, deduplicates, commits transactionally, and writes audit records |

Do not expose direct create, update, delete, SQL, or database-admin tools to a
general or triage agent.

### Triage-agent read configuration

This is the target Agent shape. Its `McpServer` wiring is the same CRD pattern
already used by the current repository agents; the production tool names only
become deployable after the PostgreSQL-backed MCP service implements and
advertises them.

```yaml
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: {{TRIAGE_AGENT_NAME}}
  namespace: {{KAGENT_NAMESPACE}}
spec:
  type: Declarative
  description: Read-only triage agent with shared incident-memory retrieval.
  declarative:
    modelConfig: {{CHAT_MODEL_CONFIG}}
    systemMessage: |
      At the start of every investigation, build an incident fingerprint from
      source, service, namespace, resource kind/name, reason, error code, and
      normalised message.
      Call search_lessons before investigating. Treat any result as a
      hypothesis, verify it with current read-only evidence, and cite the
      lesson ID and evidence references in the verdict.
      Do not write or delete memory and do not mutate Kubernetes resources.
    tools:
      - type: McpServer
        mcpServer:
          apiGroup: kagent.dev
          kind: RemoteMCPServer
          name: memory-mcp
          toolNames:
            - search_lessons
            - open_lesson
      - type: McpServer
        mcpServer:
          apiGroup: kagent.dev
          kind: RemoteMCPServer
          name: kagent-tool-server
          toolNames:
            - k8s_get_resources
            - k8s_describe_resource
            - k8s_get_events
            - k8s_get_pod_logs
      - type: McpServer
        mcpServer:
          apiGroup: kagent.dev
          kind: RemoteMCPServer
          name: platform-kb-querydoc
          toolNames:
            - query_documentation
```

For the existing graph POC, use the current read-only tool names instead:
`search_nodes`, `open_nodes`, and `read_graph`.

## Memory Lifecycle

### 1. Retrieve before investigation

The agent builds a compact fingerprint from the event source, service,
namespace, resource kind/name, error code, alert reason, and normalised
message. It searches the shared-memory MCP before write-capable tools become
available.

### 2. Verify against live evidence

The agent treats a memory hit as a hypothesis. It gathers current logs,
events, traces, metrics, and Git state using read-only tools. A prior
`known-benign` result only applies if the current evidence matches its stated
conditions.

### 3. Propose, do not self-write

At completion, the agent emits a structured memory proposal containing the
fingerprint, observed evidence, proposed cause, action, outcome, confidence,
and links. It does not overwrite a prior lesson directly.

### 4. Curate and persist

A curator workflow validates the proposal, redacts prohibited data,
deduplicates it against existing fingerprints, and either creates, updates,
supersedes, or rejects the lesson. The workflow records the decision in the
audit trail.

### 5. Promote proven learning

Repeated, high-confidence lessons can become a versioned Git runbook, skill,
or WorkflowTemplate through a reviewed PR. This is the safe form of
self-evolution: experience improves retrieval first, then proven behaviour is
promoted through normal engineering controls.

## Access Model

| Principal | Shared-memory permission | Rationale |
|---|---|---|
| General chat agent | None or read-only | It should not create organisational facts |
| Triage specialist | Read-only search/open | It can use prior incidents as context |
| Evidence specialist | Observe + propose | It may submit a structured proposal, not persist it |
| Memory curator workflow | Create/update/supersede | It enforces validation, redaction, dedupe, and audit |
| Platform administrator | Retention/export/delete under policy | Operational and compliance control |

Execution permissions remain separate. A memory hit never grants Kubernetes
apply/delete, Git write, or cloud-management access.

## Build Plan

### Phase 0 — Agree the contract

1. Define data classification, retention, deletion, and redaction rules.
2. Agree the incident fingerprint fields and allowed evidence references.
3. Define success and negative cases: hit, miss, stale lesson, false positive,
   conflicting lessons, rejected write, and restart survival.

### Phase 1 — Durable development substrate

1. Provision a dedicated `{{DEV_MEMORY_POSTGRES}}` PostgreSQL instance with
   the `vector` extension enabled.
2. Use a separate database or schema for kagent native memory and shared
   operational memory.
3. Store connection material in Key Vault/External Secrets or an approved
   secret mechanism; do not commit connection strings.
4. Restrict network access to the kagent namespace and curator workflow.
5. Deploy through Flux/Kustomize using placeholder-safe values.

### Phase 2 — Read path first

1. Implement or adapt a shared-memory MCP service with `search_lessons` and
   `open_lesson` backed by PostgreSQL.
2. Give the triage test agent only these read tools plus its existing read-only
   Kubernetes/observability tools.
3. Seed two synthetic incidents with distinct fingerprints and evidence links.
4. Prove that a new A2A session retrieves the right prior lesson and ignores a
   deliberately unrelated one.

### Phase 3 — Curated write path

1. Define `propose_memory_update` as a workflow artifact or queue message.
2. Add curator validation: schema, redaction, evidence presence, confidence,
   deduplication, and transaction-safe persistence.
3. Record `actor`, source workflow, A2A context, approval ID, timestamps, and
   before/after audit data for every accepted change.
4. Keep direct write and delete tools off specialist agents.

### Phase 4 — Native kagent memory

1. Configure the kagent controller to use durable PostgreSQL with vector
   support.
2. Create an embedding-capable `{{EMBEDDING_MODEL_CONFIG}}`.
3. Enable `spec.declarative.memory` only on a low-risk test agent.
4. Prove a per-agent/per-user memory write, new-session recall, isolation, and
   controller restart survival.

Native memory is for agent-local facts and preferences. It does not replace
the shared-memory MCP.

### Phase 5 — Documentation and promotion loop

1. Index approved Markdown documentation through querydoc/RAG.
2. Require cited source paths for runbook answers and `NO_RELEVANT_DOCS` when
   retrieval is inadequate.
3. Route proposed runbook or skill improvements to a sandbox PR with HITL.
4. Run evaluation fixtures before promoting any new procedure to Git.

## Proof Gates

Do not call the concept proven until development evidence includes all of:

```text
SHARED_MEMORY_WRITE: stored_by_curator
SHARED_MEMORY_LOOKUP: hit
SHARED_MEMORY_FALSE_MATCH: rejected
SHARED_MEMORY_AUDIT: present
SHARED_MEMORY_RESTART_SURVIVAL: passed
NATIVE_MEMORY_LOOKUP: hit
NATIVE_MEMORY_ISOLATION: passed
KB_CITATION: present
NO_RELEVANT_DOCS: passed
HITL_STATUS: resumed_or_rejected
REMEDIATION_MODE: recommendation_or_sandbox_gitops
```

Also measure whether retrieval actually helped: repeat-incident analysis time,
repeat-incident resolution time, false-match rate, memory proposal acceptance
rate, superseded-memory rate, human touches, and safety-gate failures.

## Configuration Placeholders

| Placeholder | Purpose |
|---|---|
| `{{DEV_MEMORY_POSTGRES}}` | Approved development PostgreSQL endpoint/service |
| `{{KAGENT_NAMESPACE}}` | Namespace containing kagent and memory MCP resources |
| `{{MEMORY_DB_SECRET}}` | Approved secret reference for shared-memory connectivity |
| `{{EMBEDDING_MODEL_CONFIG}}` | Embedding-capable kagent ModelConfig |
| `{{MEMORY_RETENTION_DAYS}}` | Policy-approved retention window |
| `{{CURATOR_WORKFLOW_NAME}}` | Argo WorkflowTemplate responsible for writes |
| `{{KB_SOURCE_PATH}}` | Approved Markdown source indexed for RAG |

## Existing Repo Starting Points

- [Platform memory architecture](../platform-memory/README.md) — the broader
  store boundaries and memory contract.
- [Native kagent memory reference](../../../a2a/memory-reference.md) — current
  kagent configuration and limits.
- [Shared memory MCP integration](../../memory-integration.md) — current graph
  POC and its concurrent-write limitation.
- [Platform memory showcase](../../../a2a/platform-memory-showcase-demo/README.md)
  — synthetic cross-agent recall and A2A/HITL continuity proof.
- [Work memory and KB handoff](../../../WORK-MEMORY-KB-NEXT-HANDOFF-README.md)
  — an execution-oriented evidence checklist.

## Non-Goals

- Training or changing model weights from incident outcomes.
- Treating vector similarity as proof of causality.
- Allowing an agent to self-approve a remediation, memory write, or runbook
  promotion.
- Storing secrets, private endpoints, tokens, personal data, raw credentials,
  or unrestricted conversation transcripts.
