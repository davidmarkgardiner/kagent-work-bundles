# Test the graph-context hypothesis

This is a follow-on evaluation design, not a result from the integration run.

The current acceptance proves transport, bounds, known fixture facts and agent grounding. It cannot establish that a graph reduces hallucination or token use.

Use the same model, model version, instructions, data snapshot, tools, timeout and result budget for both comparison arms. Separate two questions:

1. Does structured topology improve use of the same facts? Compare the graph representation with a flat representation containing the same entities and relationship facts.
2. Does supplying relationship evidence help? Compare a context with relationships against entity-only context. Label this as an information-availability comparison, because the arms contain different facts.

Build a reviewed question set containing relationship chains, environment ambiguity, missing objects, compliant and non-compliant cases, truncation, unsupported data questions and misleading instructions embedded in retrieved text. Keep expected facts and applicable scopes in an independent oracle. A correct limitation is better than an invented answer.

Run at least five repetitions per question and arm, interleaving the arms. Start with ten questions per comparison. Keep retrieval failures, native routing failures, provider quota and model refusals distinct from wrong factual answers. Never count an unexecuted tool call or an incomplete task as a correct answer.

Score factual correctness, relationship correctness, source/scope citation, unsupported-question handling, invented claims, and truncation handling. Verify actual tool calls and compare answers with the oracle; do not rely only on an LLM judge.

Measure the complete client-visible MCP envelope, per-call and cumulative gateway/model input tokens, output tokens, request count and total elapsed time. A smaller tool JSON object is not a proven model-token saving. Keep run counts, distributions and error totals with every comparison. With local CPU inference, separate initial model load and warm inference; do not compare a cold arm with a warm arm.

The remote stage needs a new approved synthetic canary and reviewed ground truth. Lab fixture results do not establish real service semantics, data quality, permission enforcement or productivity at work.

A bounded four-question implementation is available in [the pilot guide](../comparison/README.md). It isolates encoding at the model boundary and uses five repetitions per arm. It is smaller than the ten-question follow-on design above and excludes native Kagent orchestration tokens.
