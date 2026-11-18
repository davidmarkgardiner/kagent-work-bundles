# Knowledge, skills and bounded tools

Reviewed guidance is a releaseable input to investigations. Conversation memory, shared knowledge, executable skills and incident records have distinct ownership and retention.

| Asset | Ownership and publication |
| --- | --- |
| Skill | Reviewed procedure/package, pinned release and permission scope |
| Knowledge article | Source, owner, applicability, review date, access entitlement and withdrawal path |
| Incident lesson | Sanitised evidence-linked proposal approved by the service owner |
| Conversation memory | Session/user scope, retention, explicit sharing and deletion policy |
| Evaluation fixture | Representative case with expected evidence and failure criteria |

Use the cycle: resolved incident -> proposed lesson -> owner review -> evaluation -> approved versioned release. An agent may propose an article or skill; it cannot promote untrusted incident content into trusted instructions itself.

The experimental Skills/KnowledgeBase/four-CRD work is an extension/design bundle. Do not label those custom APIs as native kagent 1.0 resources. Port the smallest reviewed delta to the native AgentTemplate/Harness/Agent model and validate the extension's controller and artifact lifecycle separately. RAG must enforce the caller/workload's data entitlement and return bounded, cited results.

## Tool contract

Expose fixed, typed operations over approved scope. A generic arbitrary-SQL, shell, apply/delete or result-dump tool is outside the read-only profile. Enforce limits at the backend adapter before tool data enters model context; model context compaction is a backstop.

For the existing PostgreSQL FastMCP pattern, defaults are 50 rows, 32 KiB/result, 512 characters/cell and 5 seconds; compiled ceilings are 100 rows, 64 KiB, 2,048 characters and 30 seconds. Use `fetchmany(max_rows + 1)`, read-only transactions, bounded statement timeout and explicit truncation. Do not auto-page to reconstruct an export in chat.

The password and AKS Workload Identity/UAMI profiles share typed tools. The UAMI path needs the matching Entra PostgreSQL principal, least-privilege grants and TLS. The separate MCPg/password bundle is legacy reference. The workplace MCP already exists: preserve deployed names, authentication, approved views/grants and wiring; port only the reviewed adapter/test/instruction delta.

## Evidence and evaluation

Compare complete client-visible MCP envelope bytes and per-call/cumulative Gateway/kagent input-token telemetry on representative cases before claiming workplace savings. A 5,000-to-50-row fixture proves bounded transport only. Track retrieval relevance, stale guidance, source correctness, denial behaviour, tool failure and quality of the SRE handoff.
