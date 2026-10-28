# Historical review record: 27 October 2026

This file describes the original FastMCP 2.14.3 / native alpha17 fixture run. It does not certify the upgraded handoff revision or workplace integration. Start with [the current handoff review](HANDOFF-REVIEW-2026-10-28.md).

# Independent review and resolutions

Cursor Composer 2.5 completed architecture review and a later source, test and evidence review. Its model was selected explicitly by the Cursor CLI; the CLI does not report the served model revision. Private provider receipts are retained outside this bundle. Native Claude Opus returned a session usage limit. Native Kimi returned a five-hour subscription limit. Neither supplied a review.

Cursor endorsed separate REST and MCP deployments over an in-process shortcut. The final review correctly withheld a completed-native-integration verdict while the native invocation was failing. That review occurred before subsequent runtime diagnosis and final report generation.

Accepted corrections:

- Pin the `PyYAML` dependency used by the deployment regression test explicitly.
- Clarify that setup waits for the RemoteMCPServer Accepted condition. Direct MCP calls and native acceptance remain separate commands.
- Record actual successful direct client tool calls separately from the discovery list.
- Pin the expected upstream source. Local mode requires `fixture-v1`; remote mode requires an explicit approved source ID.
- Finish the sanitized report and update the decision trail to reflect observed results.

The generic `retrieval_unavailable` REST response is retained deliberately. The service catches unexpected exceptions at its external boundary to avoid exposing database errors or data. This does not count as a successful retrieval; the HTTP status is 503 and the adapter rejects it. Tests prove known success and error paths.

The comment audit found no nonessential source comments requiring deletion. No comments were deleted, no application code was changed by the reviewer, and no constraint was left dependent on a code comment. NetworkPolicy enforcement remains conditional on the CNI and is stated in the architecture and report.

The reviewer highlighted the native gate and source/scope trust as the main risks. Final native results must be read in REPORT.md; the earlier review is not a claim that later tests passed. A source label checks routing consistency, not the truth of the remote data owner's assertions.


## Refusal contract review

After two prompt variants, the weather question still produced an explicit refusal, no tool call, Source none and Scope unspecified. Cursor independently judged accepting this behavior to be a legitimate correction to the user contract. The user required an explicit limitation on unsupported questions, not a data lookup for every unrelated utterance. The final policy preserves mandatory tool evidence for graph and ambiguous requests, and rejects false source attribution or data claims without retrieval. Original FAIL receipts remain preserved as tests of the superseded process rule.

The omitted truncation warning was treated differently. It was a real coverage-reporting gap. The final REST context begins with coverage, and the AgentTemplate requires a partial-graph warning before facts whenever truncated is true. This is tested again with the actual native agent.


## Relationship oracle review

Cursor independently reviewed the actual question, "Show production workload compliance relationships", and a response containing three correct graph triples. It confirmed that demanding unasked status sentences was an oracle mismatch. The corrected check requires a quoted ID/relation/ID triple from the returned graph, rejects parsed false triples and invented fixture IDs, verifies workload statuses on the MCP payload, and rejects contradictory statuses when stated in prose. Wrong-edge, invented-ID and contradictory-status regressions accompany the change. This proves the requested relationship answer, not universal natural-language correctness or status reporting when unasked.

## Explicit test inputs

The question “show 2 relationships” caused the local model to request context_size=2, a valid bounded call that did not satisfy the test's expected ten-node graph. The final positive scenarios explicitly specify context_size=10. The ambiguous API scenario names get_graph_context explicitly: an unprompted conflicting-scope question sometimes received a safe clarification without retrieval, which does not prove that API path. The original results remain in native-before-explicit-budget.json. No AgentTemplate, model or backend setting changed between those results and the corrected-input tests. This acceptance measures the explicit supported workflow; it does not claim unrestricted natural-language instruction compliance.

## Empty-result citation failure

An explicit conflicting-scope request called the correct tool and received its correct empty/ambiguous result, but the local model then incorrectly used the no-query refusal with Source none. This is a genuine source-reporting failure, retained in native-before-context-citation-fix.json. The v6 REST human context now includes source and scope even for empty results; the AgentTemplate instructs the model to copy that context for unsupported/ambiguous tool results. Its structured MCP fields and read-only contract remain unchanged. This change requires fresh native acceptance; an API-only pass does not close the model-output gap.

Final native acceptance passed all five cases on v6 with the simplified AgentTemplate and unchanged local model settings. Earlier review verdicts and failures are retained as historical evidence, not substituted for these final receipts.
