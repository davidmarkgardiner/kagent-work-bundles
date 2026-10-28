# Workplace handoff review: 28 October 2026

Verdict: ready for a work agent to adapt and validate, with explicit workplace
gates. Not a claim that the private Swagger endpoint is connected or that a
workplace deployment is approved. The method/body/response schema, endpoint auth,
target kagent APIs and network policy still need work-side evidence.

## Intent and reviewers

Prepare the existing bounded Graph REST MCP proof for a work agent that has an
existing Swagger API, suspected `/get_context/get_context`, believed no auth.
Supply code, evidence, exact build/import prerequisites and a minimal port path.

Claude Opus, Cursor Composer 2.5 and Kimi were requested on a frozen source
snapshot. Cursor completed a review through the read-only pstack runner; its
model proof is pinned CLI argv, not a reported served revision. Kimi completed
its CLI review with the explicit `kimi-code/k3` selection; the served revision
was not independently reported. Claude's auth preflight returned signed out and
no model call/review occurred. **Two completed reviewers, one missing review.**
[Sanitized review receipts](review-receipts-2026-10-28.json) bind the input and
output hashes; raw prompts, tool transcripts, paths and provider state stay private.

Final Cursor follow-up reviewed the corrected frozen snapshot and found **no blocking findings for work-agent adaptation and validation**. Low-priority follow-ups are automated positive-CA/probe HTTP regressions; the positive CA path was actually exercised and recorded. The historical secondary review now has an explicit date/version disclaimer. Final container/extracted receipts were added after that static follow-up.

## Acted on

| Finding | Review agreement | Resolution |
| --- | --- | --- |
| Hard-coded `/get-context` rejects suspected work path | Cursor, Kimi, lead | Add operator-owned `GRAPH_REST_PATH`, exact matching URL, malformed-URL/path rejection and tests. Local fixture remains fixed. |
| Unknown method/body/response shape | Cursor, Kimi | Add explicit contract checklist and work-agent mapping task; no invented mapper for an unavailable schema and no permissive parsing. |
| Private PKI cannot be configured with `trust_env=False` | Cursor, Kimi, lead | Add explicit PEM trust setting, categorized CA failures and real HTTPS/no-auth synthetic canary. Verification stays enabled. |
| Air-gap build incomplete | Cursor, Kimi, lead | Pin base index/platform digests, lock/hash transitive dependencies, add target-arch wheel preparation and offline Dockerfile, test amd64 network-disabled RUN steps. |
| Original FastMCP/Starlette advisories | Lead dependency audit | Upgrade FastMCP 2.14.3 → 4.1.4 and FastAPI 0.124.4 → 0.162.0; lock the patched Starlette version. Update ToolResult imports and SDK annotation access. Fresh runtime audit has no known advisories. |
| Remote config is not a remote rollout template | Cursor, Kimi | Add disabled adapter-only template with no-auth default, hardened pod, narrow egress placeholders and existing namespace inputs. No worker/model/fixture installation. |
| Health passes invalid config | Cursor, Kimi | Health validates syntax of URL/path/mode/source config, returns 503 for invalid configuration. Actual REST reachability and CA-file validity still require a call. |
| Recipient lacks scanner / packaging guardrails | Cursor, Kimi | Include the unchanged repository scanner, documented heuristic allowlist, verifier and export-exclusion regression test. Exclude wheels, cert/key files and private/generated state. |
| Historical checkboxes imply workplace completion | Kimi | Label old checklist historical; add a new start sheet, acceptance matrix and separate current evidence. |

No auth was already supported in code; the old remote example misleadingly always
set a token file. It now leaves auth unset and marks the operation path unverified.
The adapter only adds Authorization when a token file is explicitly configured.

## Consider / remaining gates

- Real OpenAPI, synthetic examples, read-only semantics, scopes and expected source
  remain unavailable here. If the API differs, a reviewed typed mapper is a work
  prerequisite. The existing `POST {query, context_size}` assumption is explicit.
- Remote mode requires HTTPS. Plain HTTP, mTLS, Basic/API-key auth, proxy-only
  networks or a different HTTP method require an approved architecture/code delta.
- Installed kagent/CRD schema must be checked. The alpha17 native templates and
  CLI oracles are historical examples; do not upgrade the work cluster to fit them.
- No workplace egress/pull identity/registry manifest digest, image OS scan, SBOM
  policy acceptance or native canary has been established. Record those privately.
- An adapter-only smaller image could remove fixture dependencies later. One
  tested shared image is retained to avoid adding an unproved second build path.
- The optional lab Ollama service has no selecting NetworkPolicy. It is not part
  of the workplace handoff and must not be deployed there. The original report's
  reachability wording has been corrected; no lab runtime was changed today.

## Noted / dismissed

- Rejecting extra fields, non-JSON types, off-graph edges and unexpected sources is
  deliberate. Compatibility requires a mapper, not globally weakening the schema.
- Kimi's assertion that no real response could ever match the schema exceeds the
  evidence. The real contract is unknown. Under-filled results are also legitimate
  because `context_size` is a maximum, not a required exact row count.
- Fixture lexical retrieval, edge ordering and long-label summary construction are
  not the production retrieval engine. Keep immutable fixture data for local proof;
  the work port reuses the adapter/tool boundary and tests real mapped limits.
- Broad fixture exception handling is retained at its public error boundary to
  sanitize failures. Work-side diagnostics should capture status/category/counts
  without private response dumps; a green probe never substitutes for acceptance.
- `ate.dev` APIs and namespace names are public platform examples, not private
  hostnames or credentials. Their compatibility still needs target validation.
- The graph/table comparison is retained as background, with its quality and
  telemetry limitations. It does not justify workplace token-saving claims.

## Current verification

- Python 3.12: **80 tests, five subtests and eight unittest checks pass**, including
  real REST/MCP listeners, fixed remote-path/no-auth requests, CA rejection, limits,
  remote-template safety and export exclusions. `pip check` passes. Runtime and
  test environments have hash-checked locks.
- [Real synthetic HTTPS canary](private-ca-canary-2026-10-28.json): POST to
  `/get_context/get_context`, Authorization absent, explicit private CA accepted,
  missing trust rejected, three-object bounded result. This is local proof only.
- [Dependency audit](dependency-audit-2026-10-28.json): 67 runtime distributions,
  no known vulnerabilities at scan time. This is a Python advisory scan, not an
  image OS scan. The initial audit of old pins found FastMCP, Starlette and
  transitive diskcache advisories; it was not reported as clean.
- The public-safety heuristic passes with explicit exclusions for generated
  dependency-lock/audit/wheel-manifest version strings and the scanner's own patterns. Whole-bundle
  gitleaks reports no leaks. Detect-secrets reported 81 recorded digest and synthetic request-identifier fields
  and one deliberately rejected synthetic Basic-auth URL, all reviewed false
  positives; it was not an unqualified zero-finding scan.
- [amd64 image build](container-build-2026-10-28.json) succeeds with network-disabled RUN steps and Python 3.12.16. Both services run non-root with read-only roots, dropped capabilities, no new privileges and 512 MiB limits on a dedicated internal Docker network with no published ports. [Six direct MCP cases](container-mcp-acceptance-2026-10-28.json) pass on that image. amd64 runs via emulation on this arm64 host; this is not AKS proof.
- The [wheelhouse manifest](wheelhouse-amd64-manifest-2026-10-28.json) records the exact successfully installed amd64 runtime wheels. Only amd64 has fresh image/runtime proof; arm64 has a verified base digest and preparation option, and still requires its own build/test. [Extracted-package validation](handoff-validation-2026-10-28.json) passes in a fresh hash-locked dependency environment: 80 tests, five subtests, eight unittest checks, pip check and public-safe scan. Same adapter source as the final image. Fresh native-agent acceptance on the upgraded
  dependencies has not been run; the old native proof is not relabelled.

## Reproduce and retain

Use `GRAPH_PYTHON=/path/to/python bash scripts/verify-bundle.sh` from an environment
installed with `requirements-test.lock`. `scripts/public-safe-scan.sh` is a byte
copy of the source repository helper. The five allowlist entries explain generated version
string/self-pattern false positives; gitleaks covers the entire bundle separately.

Read `WORK-AGENT-START-HERE.md` for the actual handoff, `IMAGE-IMPORT-SHEET.md` for
the supply route and `docs/WORKPLACE-CONTRACT.md` for the private contract record.
Keep historical native failures as historical evidence; do not treat them as
failures of this source revision or treat source tests as workplace proof.
