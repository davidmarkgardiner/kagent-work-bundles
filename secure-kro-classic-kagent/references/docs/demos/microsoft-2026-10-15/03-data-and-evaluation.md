# Demo 3: bounded data and an evaluation failure

Time: about two minutes. These commands run locally without a database, credentials, model calls, containers or cluster access.

## A large synthetic result stays bounded

```sh
python3 docs/demos/microsoft-2026-10-15/demo.py data
```

Expected: `matching_fixture_rows=5000`, `returned_rows=50`, `truncated=true`, a `row_limit` reason and adapter JSON under 32 KiB. The command imports the actual Postgres adapter's result-budget code and passes synthetic rows through it. It does not call a database or MCP transport.

Say: “The adapter limits what enters model context. The policy lives in executable code, so the model cannot ask its way around the transport budget.” Database permissions, SQL bounds, statement timeouts and gateway access remain separate controls.

For the real historical transport measurement:

```sh
sed -n '1,85p' work-agent-bundles/postgres-fastmcp-entra-uami/evidence/TOKEN-EFFICIENCY-GEEKOM-POC-2026-09-08.md
```

That September test returned 50 of 5,000 matching rows through a complete Streamable HTTP envelope of 24,963 bytes. It did not involve a paid model, kagent or agentgateway. Do not call the row reduction a measured token saving.

## A plausible answer fails on unsafe tool scope

```sh
python3 docs/demos/microsoft-2026-10-15/demo.py eval
```

Expected: the labelled sample passes. The same answer with one tool argument changed to an unauthorized namespace fails the actual local scorer. The command expects that rejection, so its overall exit code is zero when the demonstration works. A failure to obtain the expected scorer result raises an error.

The command changes only a temporary copy, prints the report, and removes it on exit. This is evaluation of a synthetic run record. It does not send an unsafe request or demonstrate a runtime authorization denial. Production enforcement belongs in the tool / backend policy too.

## Denodo talking point

[The Denodo bundle](../../../work-agent-bundles/denodo-fastmcp-uami/README.md) uses its own JDBC adapter and approved VDP views. Its synthetic driver contract covers OAuth/TLS properties and bounded operations. A real Denodo JDBC driver, private CA/network, identity mapping and UAMI canary remain prerequisites. Keep that distinction visible.

Avoid the full Denodo container-build lab or Postgres Kubernetes fixture setup during the meeting. Those are preparation workflows and can require downloads, Docker, images and services.
