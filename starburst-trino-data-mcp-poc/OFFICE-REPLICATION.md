# Team presentation and office-replication guide

## Executive summary

The HomeLab proof is a **working integration model**, not a
production-equivalent Starburst proof.

It live-proved the important kagent integration seam:

    kagent Agent -> explicit RemoteMCPServer tools -> HTTP MCP service -> SQL engine

The live verifier proved synthetic SQL data, exact MCP discovery, and
Accepted=True, Ready=True for the kagent Agent. Read the
[run receipt](evidence/POC-RUN-2026-08-12.md) before presenting the result.

The recommended work implementation is different at the data endpoint:

    kagent -> explicit Starburst native MCP endpoint -> governed data product

Starburst Enterprise supplies that endpoint itself. Its JDBC driver does not
belong in a kagent pod for this option.

## What is close to the work design

| Layer | HomeLab implementation | Work target | Position |
|---|---|---|---|
| Agent/tool binding | Real kagent Agent and RemoteMCPServer CRs with a three-tool allowlist | Same | **Directly reusable** |
| MCP transport | Streamable HTTP MCP with tool discovery | HTTPS native Starburst MCP | **Same protocol; different endpoint** |
| SQL boundary | Official Trino Helm chart and synthetic memory catalogue | Starburst data product/curated views | **Same query-engine family; not the same governance feature** |
| Tool design | Discover -> metadata -> bounded aggregate; no write or arbitrary-SQL tool | Discover -> metadata -> Starburst parameterised-query tools | **Directly applicable design** |
| Evidence | Kubernetes readiness/discovery plus query receipt | Same, plus Starburst query ID/audit receipt | **Directly reusable gate** |
| Identity and network | No-auth lab internal HTTP | Work non-human identity, HTTPS, enterprise network policy | **Must be implemented and proven at work** |
| Agent Gateway | Not in the live data-call path | Optional policy/telemetry boundary after installed-release validation | **Not yet proven for this data path** |

## Important presentation statement

Use this wording:

> We have proven a safe, minimal kagent-to-SQL-MCP integration on Kubernetes:
> only three explicit read-only tools were discovered and mounted, synthetic data
> was queried successfully, and the Agent was Ready. We have **not** claimed that
> this proves Starburst Enterprise licensing, native MCP, work authentication,
> data-product governance, performance, or production data access. Those are the
> next joint validation gates with the Starburst/data team.

Do not call the fallback “Starburst in HomeLab.” It is **Trino-based rehearsal
of the integration pattern**.

## Images and offline preparation

The HomeLab run resolved these public images:

| Purpose | Tested source reference | Tested digest | Work action |
|---|---|---|---|
| Trino coordinator, worker, seed client | docker.io/trinodb/trino:477 | sha256:ada485e4bffb90f859b401dc04c393d147b5840846ef66b27110662eb2675854 | Mirror to the approved registry and pin by digest. |
| Temporary HomeLab adapter base | docker.io/library/python:3.12-slim | sha256:401f6e1a67dad31a1bd78e9ad22d0ee0a3b52154e6bd30e90be696bb6a3d7461 | Do **not** use the runtime pip-install deployment in an air-gapped office. Build the adapter image in CI from [adapter-image/](adapter-image/). |
| kagent runtime | Existing work-approved kagent image/version | Environment-owned | Use the same approved kagent release already installed at work; do not copy a HomeLab image tag blindly. |
| Starburst Enterprise | Starburst Harbor/enterprise registry | Customer/evaluation-specific | Obtain from Starburst with the SEP and MCP licences; do not substitute a public image and call it native Starburst. |

Example internal mirror/promotion sequence—replace placeholders and run it in an
approved connected build environment:

    docker pull docker.io/trinodb/trino@sha256:ada485e4bffb90f859b401dc04c393d147b5840846ef66b27110662eb2675854
    docker tag docker.io/trinodb/trino@sha256:ada485e4bffb90f859b401dc04c393d147b5840846ef66b27110662eb2675854 {{INTERNAL_REGISTRY}}/third-party/trino:477
    docker push {{INTERNAL_REGISTRY}}/third-party/trino:477

Build the lab adapter as an owned artefact, scan/sign it, then mirror it:

    docker build -t {{INTERNAL_REGISTRY}}/platform/trino-readonly-mcp:{{VERSION}} work-agent-bundles/starburst-trino-data-mcp-poc/adapter-image
    docker push {{INTERNAL_REGISTRY}}/platform/trino-readonly-mcp:{{VERSION}}

Record the resulting immutable digest and update the office manifest to use it.
The adapter-image directory is source-only; it does not contain credentials.

Also mirror the exact Helm chart dependency:

    helm pull trino/trino --version 1.41.0
    # Publish the resulting chart archive to the approved internal Helm/OCI repository.

For the actual Starburst-native route, the Starburst team owns the equivalent
Harbor-chart/image preparation and licence placement.

## Office POC: preferred native Starburst route

### Inputs owned by the Starburst/data team

1. A non-production Starburst Enterprise endpoint or approved evaluation.
2. Confirmation that the native MCP feature is licensed and enabled.
3. An HTTPS /mcp endpoint, authentication method, and CA trust chain.
4. One synthetic or masked published data product, plus one narrow question.
5. A dedicated non-human identity with only the intended data-product/view
   privileges.
6. Query-history/audit access and expected result/execution limits.

### Inputs owned by the kagent/platform team

1. A non-production kagent namespace and approved model route.
2. A purpose-specific Agent with an explicit tool allowlist.
3. Network policy/Agent Gateway design, if required by the installed releases.
4. A secret/identity mechanism that does not put credentials in Git.
5. A read-only evidence collector and a cleanup owner.

### Minimal manifests

Use the existing RemoteMCPServer pattern, replacing every placeholder only in
the work environment:

    apiVersion: kagent.dev/v1alpha2
    kind: RemoteMCPServer
    metadata:
      name: starburst-data-mcp-readonly
      namespace: {{KAGENT_NAMESPACE}}
    spec:
      description: Approved read-only Starburst native MCP endpoint.
      protocol: STREAMABLE_HTTP
      url: https://{{STARBURST_COORDINATOR}}/mcp
      timeout: 45s
      headersFrom:
        - name: Authorization
          valueFrom:
            type: Secret
            name: {{STARBURST_MCP_AUTH_SECRET}}
            key: authorization-header

The authentication header shape is illustrative. Use it only if Starburst
confirms that it matches the chosen supported authentication flow. Prefer
workload identity/token exchange where supported. Do not copy an interactive
user token into a Kubernetes Secret.

After discovery, create the Agent with the exact names reported by
.status.discoveredTools. Begin with:

    searchDataProducts
    getDataProductDetails
    listParametrizedQueryTools
    parametrizedQuery

Do not mount queryReadOnly for the first governed office run unless the data
owner specifically approves arbitrary read-only SQL. Parameterised queries
provide the stronger control: Starburst administrators define the SQL, tables,
typed parameters, and constraints.

## Office execution sequence

1. Mirror images/charts and verify digests in the air-gapped registry.
2. Deploy kagent and validate its existing model route with a no-tool smoke
   Agent.
3. Have the data team expose one synthetic/masked data product, native MCP, and
   a constrained non-human identity.
4. Apply the RemoteMCPServer. Verify Accepted=True; record the discovered
   tool names.
5. Apply a single purpose-specific Agent with only the approved discovery and
   parameterised-query tools. Verify Accepted=True, Ready=True.
6. Run one discover -> details -> parameterised query journey. Record the
   sanitised request, tool names, Starburst query ID, result summary, and audit
   event.
7. Independently prove an out-of-scope dataset is denied. Do not test DML.
8. Remove the Agent/RemoteMCPServer and revoke the temporary identity, or
   explicitly transfer it to a named platform owner.

## Acceptance checklist

- [ ] Every external image/chart is mirrored and digest-pinned.
- [ ] No runtime package downloads are required in the air-gapped cluster.
- [ ] No real endpoint, token, tenant, server, or data appears in Git.
- [ ] The native Starburst MCP endpoint is authenticated over HTTPS.
- [ ] Tool discovery exactly matches the mounted allowlist.
- [ ] The Agent is Accepted=True, Ready=True.
- [ ] One parameterised query returns the expected redacted result and a
  Starburst query/audit receipt.
- [ ] Out-of-scope access is denied.
- [ ] There are no write tools in the Agent manifest.
- [ ] Cleanup/revocation is evidenced.

## If Starburst cannot supply native MCP yet

Use the committed Trino fallback only as a **platform integration rehearsal**.
Before moving it beyond a lab, replace the ConfigMap-plus-runtime-pip pattern
with the internally built adapter image above, HTTPS, an explicit identity,
network policy, audit logging, and a data-owner-approved query contract.

The POC's verify.sh is a good starting point for the status/discovery gate, but
it must be extended with Starburst query-ID and audit assertions for the office
native-MCP route.
