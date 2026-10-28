# Sanitized home-lab acceptance report

Date: 2026-10-27. Data source: deterministic synthetic `fixture-v1` only.

## Result

**PASS for the local integration:** REST/MCP discovery, six direct MCP scenarios and all five native-agent scenarios pass on Proxmox. [Final native receipts](native-acceptance.json) cover production, development, unrelated-question refusal, conflicting-scope clarification and partial results. The lab agent is left running on the configuration below.

The implementation supplies a FastAPI `/get-context` REST endpoint with Swagger, a separate FastMCP Streamable HTTP adapter, DuckDB fixtures, native Kagent resources, container/Kubernetes packaging, automated tests and portable setup/teardown instructions. Exactly one tool, `get_graph_context`, is exposed. No arbitrary SQL or write operation is available.

## Reproducible configuration

| Component | Tested configuration |
| --- | --- |
| Kubernetes | v1.35.0, dedicated namespace on the existing Proxmox native Kind lab |
| Kagent | 1.0.0-alpha17, `api.kagent.dev/v1alpha3` |
| Runtime | Substrate v0.6.0-alpha3, dedicated bundle-owned WorkerPool and Harness |
| REST/MCP image | `graph-rest-mcp:lab-20261027-v6` |
| Image ID | `sha256:98c5f509b55b74f41d6bc452e130c9c59f18dddd8f7dfe8e965f9cb980fef784` |
| Local reasoning | Ollama 0.40.11, `qwen3:4b-instruct-2507-q4_K_M`, model ID `0edcdef34593` |
| Model options | 8,192 context tokens, 256 generation tokens, temperature 0, repeat penalty 1.1; CPU inference |
| Native Agent | `kagent/graph-context-lab`, Ready; one allowed MCP tool |
| Agent revision | `9ba236107f30712995482e0a8e34d7b030d239bcd9da36f6b8fb691bffe99a4d` desired and latest successful |

The production image built with successful production imports and fixture seeding. Both deployed entrypoints became available with non-root users, read-only filesystems and no Kubernetes service-account tokens. RemoteMCPServer reported `Accepted=True`, reason `DiscoverySucceeded`, and discovered `get_graph_context`.

## Automated proof

- **63 tests and 5 subtests pass**, including real HTTP/MCP listeners, deterministic facts, closure at every context limit, schema/byte/time bounds, source mismatch rejection, deployment routing and native-answer regression checks. Two dependency deprecation warnings occurred; no test failed.
- [Six direct MCP cases pass](proxmox-mcp-acceptance.json): production, development, truncated, unsupported, conflicting scope and SQL denial. Both full graphs return 8 entities, 2 views and 11 relationships. Size three returns 3 entities and 2 closed relationships. Unsupported, ambiguous and SQL cases return zero objects with explicit limitations.
- Native tests inspect actual A2A function-call/function-response parts in memory. The final summary combines separately invoked cases on the same final image, model settings and Agent revision; it is not represented as one uninterrupted five-case invocation. Supported answers require a returned relationship, correct source/scope and correct workload facts in the tool response. Parsed false relationships, invented fixture IDs and contradictory stated statuses are rejected. Truncated answers require a coverage warning. Weather requires a no-source refusal; conflicting scope explicitly requests the tool and must receive its limitation.
- The exported archive is extracted and tested from its new path with a separately installed dependency environment. `pip check` is clean. The public-safety scanner reports zero matches. Export checks reject private network addresses, generated databases, caches, logs and raw model/provider output.

Metadata counts are not fleet totals. Timing fields are single-run diagnostics, not speed or efficiency benchmarks. These checks are bounded fixture acceptance, not a general hallucination-rate evaluation.

## Runtime diagnosis and preserved failures

The initial native request failed before any tool call. Read-only diagnostics found the default worker's stored address differed from its live pod, and the router dialled the stale address. A new dedicated WorkerPool/Harness supplied a fresh registration. Shared workers were not restarted or modified. The shared discrepancy remains open. [Initial transport receipt](native-supported-failed.json).

The next invocation reached the existing Kimi route and returned a provider quota error. The script did not switch providers or retry. A separately configured local Qwen route supplies the native proof in this report; it does not establish Kimi success. The native CLI made internal transport attempts before acceptance during the initial routing failure. [Kimi quota receipt](native-supported-provider-quota.json).

Earlier local runs exposed both real model limitations and over-specific test assertions. Original sanitized failures remain in this directory. Equivalent prose/edge formatting and unasked status sentences were corrected in the oracle after independent review. A missing partial-coverage warning was a real gap; the service now puts coverage first and the prompt requires it. A 600-token model answer timed out; the final profile caps generation at 256 tokens. Finally, the test's “show 2 relationships” phrasing led to a valid two-node request, so final positive questions explicitly state `context_size=10`. The conflicting-scope API test explicitly names the tool because an unprompted question sometimes received a clarification without a call. That explicit request still exposed a real false Source none answer after retrieval. In v6 the empty-result human context includes source/scope and the simplified prompt copies it; the fresh native ambiguity case passed on this revision. This is not a claim that the small model follows every natural-language instruction reliably. See [review decisions](REVIEW.md) and [decision trail](decisions.tsv).

## Independent review

Cursor Composer 2.5 completed architecture, source/evidence, runtime and acceptance-oracle reviews. Cursor CLI pinned that requested model; the served model revision was not independently reported. Claude Opus and Kimi plan reviewers both hit subscription limits and supplied no review. They are missing reviews, not approvals. Private provider receipts stay outside the portable bundle.

## Limits and remote integration

This is metadata retrieval over synthetic nodes and edges. It does not reproduce Apache AGE retrieval, execute Text-to-SQL/Denodo queries, connect to the new private endpoint, or prove reduced hallucinations or token use. The [evaluation design](../docs/EVALUATION.md) describes a matched comparison for those hypotheses.

Kind's `kindnet` does not enforce the supplied NetworkPolicies. Network denial is unproved. The internal local-model API is unauthenticated and has no selecting NetworkPolicy, so other cluster workloads can reach it even on an enforcing CNI; no public ingress was added. The native runtime retains synthetic conversation history under its own retention policy. The harness exports only request ID, agent/tool names, completion, duration, counts, source/scope and error category.

The actual OpenAPI document, synthetic request/response examples, authentication method, approved scopes and TLS requirements are needed for the remote step. The adapter requires HTTPS, a fixed endpoint and expected source ID, no redirects, a five-second deadline and a 32 KiB response ceiling before parsing. Bearer-file authentication is implemented; a different schema or auth scheme requires a reviewed mapping. Keep credentials and rendered private configuration out of this bundle.

The bundle is saved locally. No Git push, public publication or private-service deployment was performed.

## Later representation comparison

The [40-call model-boundary comparison](../comparison/REPORT.md) is separate from this original native-integration acceptance. It tested harder questions with shared prose summaries omitted. A repeated workload exposed the former 4 GiB model-container memory limit. The current model manifest requests 4 GiB and limits memory to 6 GiB. Model weights, inference options, adapter image and AgentTemplate stayed unchanged. The expanded suite has 70 tests and 5 subtests.
