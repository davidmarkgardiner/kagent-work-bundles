# Run the graph and flat-table pilot

This pilot compares two lossless representations of the same real MCP snapshots. It sends controlled questions directly to the lab's existing Ollama model. It leaves the accepted Kagent agent, REST service and MCP image unchanged.

Read [the measured results](REPORT.md). The [plan](PLAN.md) specifies the frozen questions, scoring and evidence boundary. The [case file](cases.json) contains the independent oracle. Both representations retain every relationship. This is an encoding comparison, not a graph-versus-missing-relationships comparison.

## Reproduce

From the bundle root, install requirements-test.txt into a Python 3.12 virtual environment and run the tests as described in the main README.

On a host with the native cluster's credentials, forward MCP and the local model in separate terminals. Keep the forwards on localhost:

```bash
kubectl --context "{{NATIVE_KAGENT_CONTEXT}}" -n graph-context-lab port-forward svc/graph-mcp 28800:8000
kubectl --context "{{NATIVE_KAGENT_CONTEXT}}" -n graph-context-lab port-forward svc/graph-model 28834:11434
```

If the coordinator is elsewhere, use SSH localhost tunnels and keep Kubernetes credentials on the executor. Verify the model's full digest with GET http://127.0.0.1:28834/api/tags. The tested digest is `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.

Run from the bundle root using the installed environment's Python:

```bash
python -m comparison.pilot \
  --mcp-url http://127.0.0.1:28800/mcp \
  --model-url http://127.0.0.1:28834 \
  --expected-model-digest 0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0 \
  --repetitions 5 \
  --output /tmp/graph-context-pilot-new-run.json
```

Use the current deploy/local-model.yaml resource settings, with a 4 GiB memory request and 6 GiB limit. The initial study at the old 4 GiB limit was OOM-killed. Its aborted receipt is retained separately. The runner fetches and validates four MCP snapshots against a temporary copy of the frozen fixture, proves lossless table conversion, checks the model digest and runs two unscored warm-ups. It then makes 40 sequential scored calls. Each request has a 360-second deadline. On CPU, allow several minutes or longer. It writes progress after each call and stops after transport or telemetry errors. Wrong answers remain in the result. It never retries a scored request or changes providers.

Generate a summary and report beside the receipt:

```bash
python -m comparison.summarize /tmp/graph-context-pilot-new-run.json
```

The default names follow the receipt filename, preserving reports from other runs. The report's guide links refer to this comparison directory.

A result path must be new. To repeat a study, choose another path. Do not overwrite the recorded run or tune its prompt after seeing failures. Stop both port-forwards with Ctrl-C when finished.

## Interpret measurements

`prompt_eval_count` and `eval_count` are actual counters returned by Ollama. They describe one post-retrieval model call. They exclude Kagent instructions, tool-selection calls, native history, gateways and retrieval costs. The common JSON answer schema constrains output and does not measure unrestricted conversational quality.

`reencoded_mcp_result_json_bytes` measures a compact reconstruction of the fetched MCP result with JSON-RPC ID zero. Each encoding also records a complete reconstructed result envelope. These sizes exclude HTTP/SSE framing and are not captured network-packet sizes. The model receives each evidence payload once, rather than the duplicated MCP envelope. Byte totals and input-token totals therefore measure different boundaries.

`score` records answer IDs, required supporting edges, source/scope, partial coverage and IDs/edges unsupported by the returned evidence. Expected answers are not sent to the model. Four synthetic questions repeated at temperature zero remain four distinct questions. A forty-call pass count is not an estimate of a production hallucination rate.

Cache counters are recorded when the server supplies them. Missing cache telemetry stays null. Timing is diagnostic because CPU scheduling and prefix caches are not fully controlled. No speed verdict follows from these timings.

Receipts contain hashes, identifiers, counters, durations and score flags. They exclude raw answers, prompts, tool payloads, private URLs and credentials. Synthetic fixture and oracle data remain inspectable in their separate source files. Re-scoring an old raw completion is deliberately unavailable; reproduce with a new run instead.

Ollama API reference: https://docs.ollama.com/api/chat
