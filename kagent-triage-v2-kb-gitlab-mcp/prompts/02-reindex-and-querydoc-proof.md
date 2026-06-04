# Prompt 02: Reindex And Prove Querydoc Retrieval

Use this prompt after the KB docs are present in the work repository and either
merged or available in the branch selected for indexing.

```text
You are the platform knowledge-base verifier.

Goal: prove the doc2vec/querydoc path can retrieve the new Kagent triage v2 KB
docs and can also return an explicit no-docs fallback.

Start from the repository root.

Static validation:
  cd ai-platform/kagent-knowledge-base
  ./scripts/validate.sh

Build or refresh the KB database using the approved work embedding provider:
  export OPENAI_API_KEY="{{OPENAI_API_KEY_OR_APPROVED_PROVIDER_ENV}}"
  ./scripts/build-platform-kb-db.sh

Local querydoc smoke, if available:
  ./scripts/smoke-querydoc-local.sh

Cluster reindex, if using in-cluster querydoc:
  kubectl --context {{KUBE_CONTEXT}} -n {{KAGENT_NAMESPACE}} create job \
    --from=cronjob/platform-kb-indexer platform-kb-indexer-manual-{{RUN_ID}}

Prove these query cases through querydoc and the platform knowledge agent:

1. Cited hit:
   Question: "How does Kagent triage v2 use GitLab MCP to update the knowledge base?"
   Expected source: docs/platform-kb/agents/gitlab-mcp-kb-update-loop.md

2. Cited hit:
   Question: "When should a triage agent call the platform knowledge agent?"
   Expected source: docs/platform-kb/agents/triage-agent-kb-lookup.md

3. No-docs fallback:
   Question: "How does the platform operate a fictional service not present in the corpus?"
   Expected result: NO_RELEVANT_DOCS or a clear no-docs fallback with no invented citation.

Return:
- validation commands and output;
- DB rebuild command and output;
- querydoc or kagent UI transcript;
- cited source paths;
- fallback response;
- any failed tool call with exact error text.

Required markers:
- QUERYDOC_REINDEXED: yes
- KB_CITED_HIT: yes
- NO_RELEVANT_DOCS: yes
```
