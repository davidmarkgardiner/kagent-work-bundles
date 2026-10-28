# Graph REST MCP: workplace handoff

Status: prepared for work-agent adaptation. Workplace connection and deployment
remain gated on the private API contract and target-platform checks below.
The existing REST API is the data source; deploy an MCP adapter in front of it.
The bundled FastAPI/DuckDB service is a synthetic test fixture only.

```text
Existing workplace agent → existing MCP/Gateway wiring → FastMCP /mcp
  → fixed approved REST URL → existing graph/context service
```

## Read first

1. This sheet, then [the image/import sheet](IMAGE-IMPORT-SHEET.md).
2. [API contract checklist](docs/WORKPLACE-CONTRACT.md).
3. [Current handoff review and proof](evidence/HANDOFF-REVIEW-2026-10-28.md).
4. [Original native proof](evidence/REPORT.md), clearly historical.
5. [Source](app/adapter.py), [typed contract](app/models.py), and
   [disabled remote template](deploy/remote.env.template).

## Inputs to collect privately

| Input | Required evidence / decision |
| --- | --- |
| OpenAPI JSON or YAML | Approved document/version/hash, actual operation, method, body and response schemas. Obtain inside work; do not commit it here. |
| Exact invocation URL | Swagger UI `/docs` and `/openapi.json` are documentation, not the operation. Suspected `/get_context/get_context` is unverified. |
| Authentication | Confirm document security and one approved synthetic request. The adapter already supports no auth when its token setting is absent. A 401/403 is a failed gate, never a reason to guess credentials. |
| TLS | HTTPS URL with valid hostname/chain. For private PKI mount a PEM trust bundle as `GRAPH_CA_CERT_FILE`. Plain HTTP requires a separate reviewed architecture decision or an approved TLS front door. |
| Data-owner scope | Approved environments/groupings/questions; read-only operation semantics; retention and model-data approval. A POST can retrieve data but its lack of side effects must be confirmed. |
| Platform | Installed kagent version/served CRDs, existing MCP registration/Gateway route, agent/tool allow-list, existing ModelConfig/Harness or legacy equivalent, execution namespace. |
| Supply | Node architecture, internal registry/repository, approved image tag/digest, pull identity, vulnerability-policy result and signature/SBOM requirements. |
| Network | DNS, fixed remote host/port, policy-enforcing CNI, approved ingress callers/egress and proxy requirement. Ambient proxies are intentionally ignored. |

Missing inputs block the dependent workplace step, not source review or offline
tests. Record an exact gap instead of filling it with a fixture value.

## Smallest implementation sequence

1. Preserve the deployed objects and delivery flow. Inventory them read-only.
   Use `kubectl --context "$KUBE_CONTEXT" api-resources` and inspect the installed
   CRDs; compare served versions with `deploy/kagent.yaml.template`. This bundle's
   native example is alpha17 `api.kagent.dev/v1alpha3`. It is not a universal YAML
   recipe and must not replace a legacy `kagent.dev/v1alpha2` Agent.
2. Complete [WORKPLACE-CONTRACT.md](docs/WORKPLACE-CONTRACT.md). Keep
   `get_graph_context(query, context_size)` as the narrow MCP front door. The current
   outbound call is **POST JSON `{query, context_size}`**. If work uses another
   method/field/schema, add an explicit mapping and synthetic contract tests first.
3. Configure the complete URL and identical `GRAPH_REST_PATH`, `remote` mode and
   approved expected source. Do not set the token-file variable for an open API.
   Mount a CA only if needed. No retry, redirect or TLS-verification bypass.
4. Reuse the current workplace adapter deployment when present; port the smallest
   reviewed delta. For a new adapter, adapt
   [remote-adapter.yaml.template](deploy/remote-adapter.yaml.template) privately.
   It creates no workers, models, REST fixture or native Agent. Replace every
   placeholder, check collisions, pull auth and CNI/DNS specifics, then submit it
   through the existing GitOps/review process. The egress CIDR must be approved and
   match actual resolution; use the platform's FQDN policy instead if appropriate.
5. Build and promote the image using [IMAGE-IMPORT-SHEET.md](IMAGE-IMPORT-SHEET.md).
   An imported Python base alone does not make a pip build offline. FastMCP is
   installed inside this application image; no separate FastMCP container is needed.
6. Run local automated checks. Render the intended workplace changes privately and
   run server dry-run against the selected context before approved rollout. Capture
   exact installed schema, image digest, resolved settings and policy evidence
   without secrets. Do not execute `scripts/setup.sh` or `scripts/teardown.sh` at work.
7. After rollout approval, prove REST → MCP → native agent in that order. Tool
   discovery and a green `/healthz` are insufficient; health checks configuration
   syntax, not backend reachability or certificate validity. Do one approved call
   per scenario and record categorized failures; do not silently retry or fail over.
8. Produce a separate workplace report and focused GitOps diff. Preserve the old
   image/config for rollback using the existing delivery system. Only remove new
   objects by reviewed exact name; never delete a shared namespace or runtime.

## Acceptance gates

| Gate | Required outcome |
| --- | --- |
| Offline source tests | Pytest, deployment/native-oracle unit tests and `pip check` pass with locked runtime dependencies. |
| Real API contract | Exact method/path/body mapped; approved source/scope; limits meaningful under the real API; no fake `fixture-v1` provenance. |
| TLS/auth | Verified chain/hostname; no credentials sent for no-auth mode; unexpected auth requirements stop the canary. |
| Upstream failures | Redirect, timeout, invalid JSON/schema, oversized body and broken edges fail closed with categories; no raw private body in logs or evidence. |
| MCP | Actual Streamable HTTP initialize/list/call; exactly the allowed tool; full client-visible response envelope within the configured budget. |
| Native invocation | Target agent calls the intended registration and grounds an approved answer in returned source/scope/relationships. Partial results warn, unsupported/ambiguous questions clarify, tool errors do not become facts. |
| Permissions/network | No write tools, no pod API token; allowed egress succeeds and unapproved destinations/callers are denied on the enforcing target CNI. No public ingress. |
| Supply | Target-architecture image pull/start succeeds; digest and SBOM/scanning evidence recorded under workplace policy. |

`scripts/mcp_acceptance.py` and `scripts/native_acceptance.py` contain **fixture
oracles**. Run them unchanged for the lab; adapt expected facts/questions privately
for the real API. Their hard-coded fixture counts are not production acceptance.

## Local verification (from this directory)

```bash
python3.12 -m venv /tmp/graph-work-review-venv
/tmp/graph-work-review-venv/bin/python -m pip install --require-hashes -r requirements.lock
/tmp/graph-work-review-venv/bin/python -m pip install --require-hashes -r requirements-test.lock
/tmp/graph-work-review-venv/bin/python -m pip check
/tmp/graph-work-review-venv/bin/python -m pytest -q -p no:cacheprovider
/tmp/graph-work-review-venv/bin/python -m unittest discover -s scripts -p 'test_*.py'
```

These commands use the package index; for disconnected verification prepare test
dependencies separately. The runtime wheelhouse covers runtime dependencies only.
The fixture tests start actual REST and MCP listeners and seed temporary data;
they need neither a model nor a cluster. No live workplace connection is made.

## Work-agent completion report

Return the exact code/config diff, contract mapping table, checks and sanitized
receipts, image registry/tag/digest/platform, remaining gates, rollback and a
clear `PREPARED`, `DEPLOYED`, or `VERIFIED` status. Historical lab proof is not
target-runtime proof. Do not claim token savings or lower hallucinations: the
[comparison](comparison/REPORT.md) did not establish either for workplace use.
