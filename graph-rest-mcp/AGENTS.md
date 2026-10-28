# Work-agent contract

Start with `WORK-AGENT-START-HERE.md` and `IMAGE-IMPORT-SHEET.md`.
This package authorizes preparation and validation, not a workplace rollout.
Preserve existing kagent/Gateway objects, names, auth, models and delivery flow.
Do not run the lab setup/teardown scripts against the workplace cluster.

Read the actual private OpenAPI before changing the adapter. The suspected path
`/get_context/get_context` and absence of auth are unverified. No auth is supported
by leaving `GRAPH_AUTH_TOKEN_FILE` unset; it does not imply HTTP or public ingress.
Keep a fixed operator-owned URL/path, TLS verification, typed read-only arguments,
result/time/byte limits, source/scope/truncation metadata and sanitized errors.
Do not expose the entire Swagger API as tools, arbitrary SQL, caller-supplied
URLs/headers, automatic pagination, writes, or retry loops.

The fixture schema is deliberately strict. If the real service differs, implement
and test the smallest explicit DTO mapping in `app/adapter.py` (or a focused
mapper module). Never silently drop facts, invent provenance, mark partial data
complete, or loosen all models to make an incompatible response pass.
Test the real method/body/response mapping with synthetic examples. Keep private
OpenAPI, addresses, CA files, credentials and payloads outside this public bundle.

Historical native receipts use FastMCP 2.14.3 and alpha17. The handoff revision
upgrades the runtime dependencies; its new local proof is recorded separately.
Repeat discovery and native invocation on the target version before claiming
workplace success. Do not install a lab worker, Ollama, or a new model to do this.
