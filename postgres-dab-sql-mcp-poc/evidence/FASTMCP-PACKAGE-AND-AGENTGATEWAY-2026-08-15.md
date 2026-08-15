# FastMCP package and Agent Gateway route — live evidence

Date: 2026-08-15

## Verdict

**PASS for the bounded HomeLab package and Agent Gateway route.** The custom
FastMCP service was package-smoke-tested as an image, and the existing
synthetic FastMCP service was called successfully through the installed
Agent Gateway route by a kagent Agent.

This is not a claim that the locally built image was pushed, signed, or
deployed to the cluster; the cluster route intentionally targeted the already
running synthetic FastMCP fixture while registry delivery remains environment
owned.

## Packaged image check

The image was built from [fastmcp-postgres](../fastmcp-postgres/) with the
non-root runtime user and dependencies installed at build time. The first
image smoke exposed a missing direct `packaging` dependency, which had been
masked by the original runtime `pip install` command. Adding
`packaging==25.0` corrected that gap.

The rebuilt local image had ID:

```text
sha256:773e01a4411f3599227ec8665e1694ec466e4c21267a229adc6c3951168b6adb
```

It successfully imported `fastmcp 2.14.3` and `psycopg 3.2.12`. A local
Streamable HTTP protocol smoke initialized `/mcp` and discovered exactly:

```text
get_kubernetes_inventory_data_product_details
get_namespace_workload_summary
get_namespace_container_images
get_image_risk_summary
FASTMCP_PACKAGED_IMAGE_PROTOCOL_SMOKE_OK
```

No database query was attempted in that local image smoke. The database path
was separately proven through the HomeLab fixture below.

## Agent Gateway route check

The manifest [fastmcp-agentgateway-spike.yaml](../fastmcp-agentgateway-spike.yaml)
was server-dry-run and applied against the installed Agent Gateway v1.1.0
CRDs. The following runtime states were observed:

| Resource | Result |
|---|---|
| `AgentgatewayBackend/fastmcp-postgres-poc` | `Accepted=True` |
| `HTTPRoute/fastmcp-postgres-poc` | `Accepted=True`, `ResolvedRefs=True` |
| `AgentgatewayPolicy/fastmcp-postgres-poc` | `Accepted=True`, `Attached=True` |
| `RemoteMCPServer/fastmcp-postgres-gateway-spike` | `Accepted=True`; all four typed tools discovered through Gateway |
| `Agent/fastmcp-postgres-gateway-spike-agent` | `Accepted=True`, `Ready=True` |

The Gateway policy is fail-closed and allowlists only the four tool names. It
adds a 30-requests-per-minute local rate limit and a 60-second request timeout.

A fresh A2A request through the Gateway asked for high/critical `payments`
images. Its final answer began `FASTMCP_AGENTGATEWAY_REPLY_OK`; it returned two
synthetic rows and recorded successful function responses from the metadata and
parameterised risk-summary tools. The trimmed receipt is
[FASTMCP-AGENTGATEWAY-A2A-RECEIPT-2026-08-15.json](FASTMCP-AGENTGATEWAY-A2A-RECEIPT-2026-08-15.json).

## Work gates still open

- **Registry/signing:** a local image ID is not an immutable registry digest,
  signed image, SBOM, or provenance. The organisation CI/registry is required.
- **Database authentication:** HomeLab used a synthetic reader/password.
  Work username/password or Microsoft Entra/UAMI support remains unknown until
  confirmed by the database team.
- **Private networking/TLS:** not proven against the work private endpoint.
- **Network boundary:** the direct lab MCP Service remains reachable; a
  NetworkPolicy must restrict steady-state ingress to Agent Gateway after the
  direct probe is removed.
- **Data/model governance:** actual approved views, field masking, model-egress
  permission, and negative tests are still needed before real data is used.

## Handoff

Use [fastmcp-postgres-image.yaml](../fastmcp-postgres-image.yaml) as the
private-overlay deployment template and [fastmcp-postgres/README.md](../fastmcp-postgres/README.md)
for the build/sign/release contract. Do not deploy it until the work gates
above have owners and evidence.
