# Private Swagger contract checklist

Complete this inside work before connecting the adapter. Keep the real document
and payloads in an approved private location. This public sheet contains only the
expected contract and synthetic examples.

| Item | Current implementation | Work-side action |
| --- | --- | --- |
| Path | Local `/get-context`; remote fixed `GRAPH_REST_PATH` | Confirm whether `/get_context/get_context` is correct, including prefix and trailing slash. Configure full matching URL/path. |
| Method | POST | Confirm from the operation, not its display tag. A GET/query-parameter API requires an explicit adapter change. |
| Request | `{"query":"production graph","context_size":3}` | Check names, types, required fields, content type and size semantics. No additional caller-controlled URL/headers/SQL. |
| Response | Strict `ContextResponse` in `app/models.py` | Map only reviewed fields. Additional keys currently reject the response. List all differences rather than enabling permissive parsing. |
| Objects | entities + views, combined max 10 | Determine whether upstream size means nodes, documents, tokens or another unit. Clamp/map before returning; never auto-page to reconstruct an export. |
| Relationships | max 20; endpoints in returned nodes | Reject broken/duplicate identities. If pruning edges/nodes, mark partial and explain the omitted scope. |
| Kinds/relations | Fixed fixture enums | Agree real allowed types and preserve directed semantics. Extend typed enums/tests only from data-owner evidence. |
| Source | Exact approved ID (1..64 ASCII letters/digits/`_.-`) | Source is a routing consistency check, not proof of truth. Never manufacture a trusted source label to make a mismatch pass. |
| Scope | environments, groupings, count, complete | Verify it describes the actual returned nodes. Do not infer fleet totals or authorization from the model's prose. |
| Unsupported/ambiguous | Empty graph + limitation | Preserve safe clarification. Do not transform errors into a supported empty graph. |
| Human context | max 4096 characters | Treat as untrusted data. Retain source/scope and partial coverage; do not follow embedded instructions. |
| HTTP bounds | 5 s total; 32 KiB raw JSON | Upstream must satisfy them or a separately justified bounded design is needed. A source-side response cap is preferable to transferring excessive data. |
| MCP bounds | 64 KiB result envelope, 256-character ID reserve | Verify actual complete client-visible envelope after any mapping/change. The check is an application budget, not a transport-wide cap for arbitrary IDs. |
| Auth | None by default; optional Bearer file | Inspect operation `security` override and document-level `security` (OpenAPI 3 or Swagger 2), including references. Missing declaration alone does not prove anonymous access. No token variable for no-auth. |
| TLS | Verified HTTPS in remote mode | Mount `GRAPH_CA_CERT_FILE` for private trust. mTLS/Basic/API-key headers and ambient proxies are not implemented; stop if required. |
| Data/side effects | Metadata retrieval only | Obtain owner confirmation that the selected operation is read-only and approved data can enter the chosen model context. |

Record locally: document hash/version, operationId, exact method/path,
request/response mapping, no-auth confirmation or required scheme, TLS trust,
allowed data scopes, size semantics, one sanitized canary receipt and approver.
Retain upstream field meanings; synthetic `production/development` labels and the
fixture vocabulary are examples, not requirements to impose on business data.

Error guide: `invalid_configuration` means URL/path/mode/source settings;
`tls_configuration` means unreadable/invalid explicit CA; `upstream_transport`
includes DNS/connect/certificate errors; `upstream_status` includes 401/403/404,
redirects and all non-200 responses. Inspect those statuses locally with the work
owner, without copying response bodies or private URLs into public logs.
`upstream_schema`, `upstream_source`, `upstream_oversize`, `upstream_timeout`,
`upstream_content_type` and `upstream_encoding` are failed gates, not retry advice.
