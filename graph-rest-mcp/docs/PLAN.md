# Graph REST to MCP lab plan

## Ground

Existing PostgreSQL and Denodo adapters expose named read-only operations with row, byte and timeout limits. This bundle adds graph metadata retrieval, not SQL generation or execution. Native lab inspection confirms Kagent 1.0.0-alpha17 and api.kagent.dev/v1alpha3 Agent, AgentTemplate and RemoteMCPServer resources. Existing unrelated workloads stay intact.

## Sketch

Caller usage is get_graph_context(query, context_size=10). A ContextRequest contains 1..512 characters and a strict integer context_size in 1..10. A typed ContextResponse contains status, entities, views, relationships, human context, source, scope, truncated and limitations. Entities and views share stable IDs. Every relationship references returned IDs. Scope names the selected environments and groupings, returned count and completeness. Counts describe metadata objects, never an inferred fleet total.

Separate Python REST and MCP processes exercise the real HTTP boundary. DuckDB is seeded from synthetic JSON at image build and opened read-only for retrieval. The service uses fixed parameterized SQL, deterministic lexical intent matching and explicit unsupported or ambiguous results. It is a controlled fixture, not an embedding service, Apache AGE implementation or full text-to-SQL agent.

## Agree

Cursor Composer 2.5 recommended the separate REST deployment over an in-process shortcut because it exercises HTTP limits and validation. Retain closure checks, strict models, no redirect following, no retries, response caps before JSON parsing, explicit scope and actual tool traces. Correct its final shorthand API typo using the installed CRDs. Claude Opus returned usage_limit_reached. Native Kimi returned a 5-hour quota error. These are missing reviews, not approvals. Private provider receipts stay outside this bundle.

## Implement

1. Build the DuckDB retrieval service and one-tool FastMCP adapter. Prove deterministic facts, bounded results and explicit limitations over actual HTTP and MCP.
2. Build one image with two entrypoints. Deploy separate services into a dedicated lab namespace. Register the RemoteMCPServer and a new AgentTemplate/Agent with one tool, reusing approved lab model and harness references.
3. Verify target CRDs, server-side dry-run, deployment readiness and actual discovery. Use native invocation appropriate to installed alpha17. Capture no raw response in exported evidence.
4. Validate supported, unsupported, ambiguous and truncated cases. Independently inspect tool calls, source, scope and expected facts. Provider quota or runtime errors remain failed or blocked criteria.
5. Export a self-contained archive, inspect its contents, run tests from the extracted archive and provide setup, teardown and remote adaptation instructions.

## Scrap

If native tool binding or transport cannot be proved, report that specific gate. Do not substitute legacy Kagent or fake model answers. Identify a local-model fallback explicitly and accept it separately from a failed hosted route. Revisit the contract if the real OpenAPI differs.

## Throughput checkpoint

- Blocking first steps. Inspect lab CRDs and obtain available plan reviews before implementation. No private service access.
- Independent workstreams. Backend source/tests/image have one owner. Coordinator owns manifests, live verification and handoff docs.
- Shared mutable state. Each writer owns disjoint bundle paths; existing repo changes are untouched. Live changes use new names only.
- Smallest safe decomposition. One backend owner avoids competing edits to the response contract. Deployment proceeds after backend tests.

## Later remote service

The actual OpenAPI schema, authentication, authorization, TLS trust and approved scopes are not supplied. Keep its configuration disabled. A later approved configuration can reuse the MCP contract if the REST schema matches; otherwise implement and review a mapping inside the adapter. A URL change alone does not establish compatibility.

## Evidence boundary

Lab success proves integration mechanics against deterministic synthetic data. Lower hallucination, token savings, production data correctness, real Denodo compatibility and remote authorization need separate evidence.


## Premise check after native refusal tests

Premise under test: every question, including an unrelated weather question, must call the graph tool for the user's requirements to be met. Two instruction variants produced the same safe behavior on weather: no tool call, an explicit limitation, source none and scope unspecified. Supported and ambiguous graph questions did call the tool. The distribution contradicts a general inability to use MCP; it isolates a conservative domain refusal. Direct MCP unsupported-query behavior is independently tested. Cursor independently confirmed that the every-utterance call rule was an added process constraint, not a user requirement. The corrected rule requires lookup for graph/uncertain-scope questions and permits only an honest no-source refusal for clearly unrelated questions. Regression tests still reject fake source attribution, fabricated weather facts, unknown tools and unsupported use of the no-query path for graph or ambiguous questions. Original failure receipts remain retained.
