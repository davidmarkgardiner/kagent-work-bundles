# Compare the same evidence in two representations

Claim under examination: with identical synthetic facts and directed relationships, structured graph objects may change answer grounding or post-retrieval model input tokens compared with flat tables. The result cannot establish a production hallucination rate or end-to-end Kagent savings.

## Ground

The accepted native Kagent path calls get_graph_context through MCP, then a separate REST service over read-only DuckDB. Its response contains structured entities, views and edges plus a redundant human-readable summary. This study retrieves actual MCP snapshots and uses only their structured fields. Removing the prose summary from both representations prevents it from giving both arms the same textual answer cues.

The model is the existing local Qwen route. The working AgentTemplate, MCP server and image remain unchanged. An initial run at the old 4 GiB model-memory limit was OOM-killed after four completed comparisons. Its aborted receipt is retained, no comparative verdict is accepted, and the model-only deployment now requests 4 GiB with a 6 GiB limit. The replacement study restarts every case with unchanged questions, prompts, model weights and options. Both representations share the new memory setting. Direct Ollama calls expose actual prompt and output token counters. They omit Kagent orchestration, tool selection, native prompt overhead and repeated retrieval. The endpoint is reached through temporary localhost SSH and Kubernetes forwards. No new cluster objects or credentials are needed.

## Sketch and agree

Two independently requested design perspectives, a native Codex agent and Cursor Composer 2.5, considered two whole designs. New paired native agents would measure the full workflow but need isolated MCP routes and reliable token metering. A replay of the same MCP snapshot isolates representation with fewer moving parts. Both recommended replay for this bounded pilot. A fresh read-only reviewer checked the code and oracle before scored inference. It confirmed the four expected answers, chose replay on the five stated criteria, and found fixes now covered by regression tests. Cursor model selection has pinned-argv evidence, not a provider-reported served revision.

Case contains a retrieval request, natural-language question and independently specified expected answer. Answer contains status, IDs, source, environments and partial coverage. Trial contains only identifiers, hashes, counters, durations, completion/error fields and deterministic score flags. Raw answers and tool records remain in memory.

Graph JSON contains entity/view objects and edge objects. Flat tables have column names once and ordered value rows. Both retain identical metadata and relationships. Restoring the tables must equal the canonical graph fields exactly before any inference. Live facts must also match the frozen local fixture exactly.

## Implement

Four reviewed questions cover one-hop ownership, two-hop policy linkage, development non-compliance and a policy question that cannot be answered from a partial graph. Five paired repetitions produce 40 scored calls. Pair order alternates within each question, and question order rotates. A regression test verifies per-question 3/2 first-arm balance across five repetitions. Temperature is zero. Repetitions check repeatability and are not independent samples of a population hallucination rate.

A shared system prompt and generic JSON answer schema apply to both arms. Oracle answer IDs are never included in model instructions or schema. Relationship answers must also provide the supporting directed edges, checked against both the returned evidence and an independently specified path. This prevents a guessed policy ID alone from passing. Model digest, context size 8192, generation cap 256, repeat penalty 1.1 and temperature 0 are held constant. No prompt or oracle changes follow observed scored answers. Two unscored warm-up calls precede the study. Timing is diagnostic because prefix cache state is not fully controlled.

The study records actual Ollama prompt_eval_count and eval_count. A missing counter is an error, never a token estimate. It records full serialized JSON-RPC result-envelope sizes separately from model-call input tokens. Envelope sizes omit HTTP/SSE framing and do not claim exact packet-byte totals. Both representations include topology facts, so their difference is encoding, not relationships versus no relationships.

The expected verdict is either an observed pilot difference or no observed difference. Production benefit remains inconclusive. Flat tables can use fewer tokens because column names occur once. That is a serialization result, not evidence against graph retrieval.

## Throughput checkpoint

Host capacity was checked before the run. The VM has four cores and 11 GiB RAM, with low load and several GiB available. The model is CPU-only with a three-CPU pod limit. Only one inference runs at a time. The coordinator owns source and evidence. Reviewers have read-only access. The accepted lab resources are shared read-only, and no other agent or worker is restarted.

## Verify and scrap

Tests prove lossless representation conversion, matched settings, balanced ordering, incorrect-answer/source/coverage rejection and missing-telemetry failure. The real model supplies scored calls. A transport or telemetry failure stops the run without retries. Completed wrong answers remain failures. New runs require new output files.

If representation equality or oracle grounding cannot be established, stop before inference. If the small deterministic question set cannot separate the arms, report that result without tuning the questions into a win. A larger preregistered dataset and native paired-agent metering are separate follow-on work.

## Pre-run review resolutions

The reviewer found that rotating question order cancelled arm alternation within each question. The scheduler now uses the original question index, with explicit per-question regression checks. The oracle now requires supporting edges for relationship answers. MCP and malformed HTTP envelopes produce fixed error categories and an aborted receipt. Live MCP facts are compared with a separately seeded copy of the frozen fixture. Re-encoded JSON-RPC sizes are labelled as reconstructed bodies with synthetic ID zero. These changes were made before any scored inference.

Model the Domain led to explicit Case and Answer schemas. Prove It Works requires actual MCP snapshots, actual model counters and independent answers. The benchmark checklist keeps errors and token counts separate from diagnostic CPU timings.
