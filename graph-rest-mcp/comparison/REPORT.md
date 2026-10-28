# Graph objects and flat tables on the same evidence

This is a four-question synthetic pilot at the model boundary. Both representations contain the same nodes, attributes, views and directed relationships retrieved through the working MCP server. It does not compare graph retrieval with missing relationship evidence.

The practical result is to keep the current integration and its explicit source/coverage text. Neither representation was reliable across this question set on the small local model. The graph format passed only the ownership question, while both formats failed the policy-chain, compliance-filter and partial-context questions.

The study completed 40 scored calls, five repetitions per question and representation. Graph JSON passed 5/20 calls. Flat tables passed 0/20 calls.

Flat-table prompts used 17.47% fewer input tokens in this exact workload. Ollama reported 12795 graph input tokens and 10560 flat input tokens. These are post-retrieval model-call totals. They exclude Kagent orchestration, tool selection, gateway overhead and retrieval.

| Question | Representation | Passes | Input tokens, median and range | Output tokens, median and range | Error calls |
| --- | --- | --- | --- | --- | --- |
| owner | graph_json | 5/5 | 733 (733 to 733) | 92 (92 to 92) | 0 |
| owner | flat_tables | 0/5 | 586 (586 to 586) | 96 (96 to 96) | 5 |
| policy_chain | graph_json | 0/5 | 740 (740 to 740) | 95 (95 to 95) | 5 |
| policy_chain | flat_tables | 0/5 | 593 (593 to 593) | 93 (62 to 93) | 5 |
| development_compliance | graph_json | 0/5 | 736 (736 to 736) | 156 (156 to 156) | 5 |
| development_compliance | flat_tables | 0/5 | 589 (589 to 589) | 60 (60 to 60) | 5 |
| partial_policy | graph_json | 0/5 | 350 (350 to 350) | 62 (62 to 62) | 5 |
| partial_policy | flat_tables | 0/5 | 344 (344 to 344) | 61 (61 to 61) | 5 |

## What was held constant

Model `qwen3:4b-instruct-2507-q4_K_M`, full digest `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`, Ollama `0.40.11`. Both arms used the same instructions, questions, response schema and options `{"num_ctx": 8192, "num_predict": 256, "repeat_penalty": 1.1, "temperature": 0}`. Both received the same snapshot for each question. Table-to-graph equality and agreement with the frozen local fixture were checked before inference. Script, oracle, fixture, prompt and request hashes are recorded in [the receipts](results-2026-10-27.json).

The two representations use graph object records or column-and-row tables. Their human-readable context summary was omitted from both arms. Metadata, limitations, source, scope and every relationship remain. The model received the evidence payload once. Reconstructed MCP JSON-RPC envelope sizes are separate byte measurements with synthetic ID zero and exclude HTTP/SSE framing.

The oracle requires the correct answer IDs, supporting directed edges for relationship answers, source/scope and partial coverage. It rejects IDs and edges unsupported by the returned context. The generic JSON output schema contains no expected answer IDs. Its supporting-edge objects use named source, relation and target fields, so flat rows must be converted into that object shape. This can favor graph-object input and limits generalization. The study scores observable evidence support, not hidden reasoning or unrestricted conversational quality. Zero unsupported-ID or unsupported-edge flags do not imply correctness. Choosing the wrong existing object or misstating partial coverage fails separate checks.

## Repetition, errors and timing

Five paired repetitions were interleaved within each question, with question order rotated. Two unscored warm-ups preceded the run. Every scored request used a fresh one-turn message array. Temperature zero means repetitions check repeatability; these are four distinct questions, not forty independent questions. No scored request was automatically retried within a study, and no prompt or oracle was tuned after scored inference began.

Graph error categories: `{"answer_mismatch": 15}`. Flat error categories: `{"answer_mismatch": 20}`. An answer_mismatch is a scored wrong answer, not a transport failure. Raw answers, prompts and tool responses were not retained. Missing token telemetry aborts a run instead of estimating tokens.

Input/output counts come from Ollama prompt_eval_count and eval_count. Cache counts are recorded if available, otherwise null. CPU timings are diagnostic. Prefix caching, scheduler noise and shared host activity are not fully controlled, so no speed claim is made. The [startup observation](host-profile.json) records the four-core VM and the model pod’s three-CPU limit.

## Memory recovery

The first attempt at the former 4 GiB model-container limit was OOM-killed after four completed scored calls. Its [aborted receipt](aborted-memory-limit-2026-10-27.json) retains two warm-ups, four completed scored calls and one interrupted call. Those calls contribute no comparative verdict. After checking VM headroom, only the model deployment memory changed to a 4 GiB request and 6 GiB limit. The full replacement study started from the beginning. Questions, prompt, oracle, model digest and inference options stayed unchanged. [Recovery record](memory-recovery.json).

## Interpretation and limits

Flat tables repeat field names less often, so fewer input tokens can be an encoding effect. Both arms retain topology. This pilot cannot establish whether relationship evidence improves answers compared with entity-only data, whether Apache AGE retrieval is better, or whether a private remote endpoint is correct.

The fixture has few paths and only one policy per environment. Requiring supporting edges prevents a policy-ID guess alone from passing, but the dataset remains weak evidence for general multi-hop reasoning. Four synthetic questions on one small local model do not establish a hallucination-rate improvement or workplace productivity gain.

Production benefit remains inconclusive. Preserve the accepted bounded MCP integration and its explicit human-readable source and coverage warnings. Those prose cues were deliberately omitted from both arms here, so these quality counts do not describe the accepted native AgentTemplate workflow. Any recommendation to change workplace response encoding needs a broader independent question set and native Kagent input-token metering.

Read [the frozen plan](PLAN.md) and [reproduction instructions](README.md). Ollama counter definitions are documented at https://docs.ollama.com/api/chat.

## Native integration after the memory change

A [fresh native Kagent canary](native-after-memory-change.json) passed after the study. It invoked get_graph_context and returned 8 entities, 2 views and 11 relationships with fixture-v1 and production scope. This checks the original AgentTemplate workflow after the model rollout, independently of the replay scores above.

The first canary attempt failed before tool execution because the old local controller port-forward had exited. The [failed control-channel receipt](native-after-memory-transport-failed.json) is retained. A fresh owned port-forward restored the local API connection. No controller or shared worker was restarted.

The expanded source and extracted bundle pass 70 tests and 5 subtests. The public-safety scan is clean. No publication, Git push or private-service connection was performed.
