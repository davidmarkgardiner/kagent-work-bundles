# Budget proxy candidate

This isolated stdlib service is for a new native kagent ModelConfig pointed at an existing approved gateway. It does not change or discover existing Kubernetes resources. Keep streaming disabled in that new ModelConfig and reuse the intended client Secret reference. Native runtime/gateway instrumentation supplies telemetry; this proxy emits no synthetic spans.

Run with Python 3.11+ on Linux/macOS:

```sh
HOST=0.0.0.0 PORT=8082 python3 budget_proxy.py --config /config/budget.json --db /data/model-budget.sqlite
```

Required strict configuration:

```json
{
  "upstream_base_url": "http://{{GATEWAY_SERVICE}}.{{GATEWAY_NAMESPACE}}.svc.cluster.local:8080",
  "model": "{{APPROVED_MODEL}}",
  "run_id": "{{FIXED_RUN_ID}}",
  "max_requests": 32,
  "max_input_bytes": 524288,
  "max_output_tokens": 1200
}
```

Mount `/data` durably for the whole run. The process does not reset or renew the database. Do not delete, replace or restore an older database to retry a run. Keep config immutable. Startup refuses a changed identity/hash and concurrent serving processes using the same DB. The `.lock` file carries an OS lease; its presence alone does not prevent restart.

`POST /v1/chat/completions` requires `Content-Type: application/json`, one Content-Length, no Transfer-Encoding/Content-Encoding and a body at most 64 KiB. It preserves only Authorization and a valid incoming traceparent. The fixed model is supplied when omitted; a different model is rejected. Streaming must be false. Missing max_tokens becomes the configured output ceiling; zero, booleans, negative values and over-ceiling values are rejected. Only the documented top-level allowlist in DESIGN.md is accepted. No per-request upstream URL, redirects, retries or alternative model/provider exists.

All classifier, specialist, reviewer and verification calls using this one proxy share its run budget. Rejected/failed completion attempts use a request reservation; in-flight declared body bytes remain charged after ambiguous reads. Exhaustion returns 429. Transport timeout returns 504. Other transport or invalid/oversized upstream results return 502. Provider JSON error statuses/bodies pass through. Success means the actual upstream JSON object/status; the proxy does not manufacture model output.

`GET /healthz` returns only aggregate request, input-byte and terminal-status counters. The SQLite rows retain digests/status and actual numeric upstream usage when supplied; no headers, bodies, URLs, model names or run identifiers are persisted or logged. A missing provider usage object remains absent.

Local verification uses HTTP clients against the proxy plus a deterministic transport stub; it makes no real model or gateway calls:

```sh
python3 -m unittest -v test_budget_proxy.py
```

Deployment review must still validate the approved model name/base URL, persistent-volume behavior, real native SDK compatibility, and native telemetry. These tests establish local guard behavior only.
