# Radar and linked guidance: live runtime comparison

Date: 2026-10-01. Scope: approved Proxmox lab and existing local kind lab.
No AKS or workplace objects, authentication, delivery pipelines or real
certificate workloads were changed. Cert Manager examples used a disposable
pause Deployment, not an installed cert-manager controller or a real incident.

## Result

**PASS for the tested local kagent 0.10.1 Go path:** the Agent used actual MCP
tools to resolve a Pod's ownership, find linked guidance, read selected excerpts,
and return a completed A2A artifact citing graph evidence and guidance revisions.
Replacement-Pod and stale-guidance cases also completed successfully.

**Partial on Proxmox kagent 0.7.13 Python:** Radar and guidance transport,
ownership evidence, read permissions and Calico ingress checks passed. Full
guidance cases saved correct model responses but returned HTTP 500 during A2A
request cleanup. Sequential tool calls did not resolve it. A nonblocking attempt
did not reach a terminal state within the test timeout; a no-binding case did
return a completed artifact. The underlying runtime failure has not been fixed
or conclusively attributed to a particular library. Schema compatibility,
readiness and saved responses are insufficient to promote that path.

## Evidence

| Gate | Proxmox lab | Local kind lab |
|---|---|---|
| Cluster | User-authorized startup of control-plane plus two worker VMs; all three Ready, Kubernetes 1.31.14. Existing VMs left running; no VM configuration changed. | Existing cluster used; existing Agent and model configuration objects preserved. |
| Versions | Radar chart/image 1.15.0; kagent 0.7.13. `--runtime legacy` omits unsupported Agent runtime field. | Radar chart/image 1.15.0; kagent 0.10.1, Go runtime. |
| Images | Guidance built/imported for amd64 without publishing to a registry. Radar Pod imageID matched reviewed registry index SHA256. | Guidance built/imported for arm64; digest-pinned image and catalog volume. |
| Scheduling | Workers hit CPU/Pod scheduling limits. Only new test components used spare control-plane capacity with bounded requests/limits and explicit lab placement. | Dedicated test namespace; no existing workloads rescheduled. |
| Schema and readiness | Server dry-runs passed; both MCP services and both Agents Ready/API-listed. | Server dry-run passed; guidance Agent Accepted/Ready/API-listed. |
| Catalog | Radar discovered 25 read-only tools, Agent allowed only two topology tools. Guidance discovered exactly two typed tools. | Four allowed Agent tools: get_neighborhood, get_topology, find_guidance, read_guidance. Typed guidance kind enum verified over HTTP. |
| Current graph | Service → Deployment `exposes`; Pod → ReplicaSet → Deployment through `manages` edges. Full ownership required two hops. | First positive trace used one two-hop neighborhood, three nodes/two ownership edges, no truncation. |
| Guidance lookup | Exact stable Deployment mapping returned four references; skill and fictional incident were read with revision/source metadata. | Trace confirmed get_neighborhood → find_guidance → two read_guidance calls. Final response cited both revisions and separated fictional history from current cause. |
| Pod replacement | Deleted only the disposable fixture Pod; replacement had a different name and the same stable owner/binding. Saved Agent response preserved that identity, but A2A returned 500. | Replaced only the fixture Pod; fresh A2A returned completed artifact with the same Deployment and procedure revision, in 20 seconds. |
| Missing binding | Actual Agent trace returned no_binding for an unmapped Deployment, refused to borrow another workload's incident, and returned completed artifact in 15 seconds. | Direct HTTP negative probe also passed. |
| Stale guidance | Store tests enforce metadata-only review_required. | Temporarily expired the lab snapshot, rolled guidance, and ran a real Agent request. find_guidance flagged all four references stale; read_guidance returned metadata only. Agent withheld instructions and proposed no restart. Completed in 17 seconds; current catalog then restored. |
| Permissions | Dedicated Radar ServiceAccount: list Pods=yes, patch Deployments=no, read Secrets=no. Guidance has no API token or RBAC grants. | Guidance security/profile validated; kind is not policy-enforcement proof. |
| Network | Calico: client in kagent reached both services; client in default resolved both DNS names but both HTTP connections timed out. Neither client namespace had another NetworkPolicy. Temporary clients removed. | No claim of enforced NetworkPolicy on kind. |

## Measurements

The successful first local A2A response completed in **28 seconds**, with four
tool calls and four model requests. The persisted Go ADK events report:

| Model request | Input tokens | Output tokens |
|---|---:|---:|
| 1 | 1754 | 278 |
| 2 | 2511 | 110 |
| 3 | 3385 | 239 |
| 4 | 4214 | 311 |
| Total | 11864 | 938 |

These are cumulative per-request context counts, not unique prompt size or a
billing receipt. They are actual runtime event telemetry, not estimated from
character count. The earlier Proxmox first attempt used six calls, including a
kind-casing retry; the tool schema now enumerates canonical Kubernetes kinds.
The guidance Agent now requests two hops for Pods to resolve stable ownership
in one bounded read. Those changes address observed redundant calls.

The final direct guidance probe's eight complete JSON-RPC response bodies were
2756, 1183, 1153, 1191, 1172, 356, 147 and 388 bytes: **8346 total**, max 2756.
This includes content/structuredContent and JSON-RPC framing, excludes HTTP
headers, and describes the direct probe rather than the Agent's whole context.

No controlled baseline or five-repetition comparison was run. Differences
between these runtime tests are not evidence of token savings. Useful linked
guidance and bounded transport are proven for the stated fixture; savings,
real-incident correctness, fleet scaling and workplace acceptance remain open.

## Handoff and retained state

- Proxmox Kubernetes VMs remain running. Only the new test namespace, Helm
  release, access objects, Agents/MCP servers and disposable fixtures were
  removed from Proxmox; existing workloads were preserved.
- The working local demo remains in its dedicated namespace, with the current
  catalog restored. It is an isolated synthetic evaluation with no public ingress.
- Raw traces, responses and generated environment files remain outside Git in
  owner-restricted local temporary evidence directories. This receipt contains
  sanitized observations rather than cluster inventories or credentials.
- Ten adapter/render tests passed, including legacy/Go field rendering, fixed
  permissions and image-digest rejection. Strict shared public-safety scan and
  Git whitespace check passed.

Follow [GUIDANCE-INTEGRATION.md](GUIDANCE-INTEGRATION.md) for the image/chart,
Helm/Flux, MCP wiring, reviewed catalog and workplace acceptance path. Preserve
the workplace's existing delivery/auth/model routing and require a fresh,
client-visible completed response on its actual runtime before promotion.
