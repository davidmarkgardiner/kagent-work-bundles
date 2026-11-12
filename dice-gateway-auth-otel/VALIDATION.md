# Validation on 12 November 2026

[The sanitized home-lab receipt](evidence/homelab-2026-11-12.json) records the final tested profile. Raw native responses, credentials, exporter responses, and traces remain private. The original recording Agent's spec was read back unchanged.

| Gate | Observed result |
| --- | --- |
| Offline behavior tests | 12 passed |
| Official agentgateway v1.7.0 JSON schema | Passed |
| Kubernetes server dry run | Passed for final manifests and dashboard provisioning |
| Final workloads | Gateway, native agent, MCP, collector, and Tempo ready |
| Protected semantic check | Exact PONG returned |
| Caller authentication | Missing, invalid, wrong audience, swapped, and expired tokens returned 401. Wrong subject returned 403. |
| Agent-to-MCP authentication | Missing, invalid, wrong audience, and swapped tokens returned 401. Wrong subject returned 403. |
| Denied execution | Backend audit unchanged across all eleven probes. Each received denial trace contained only gateway spans. |
| Direct bypass | Agent and MCP Service/Pod-IP connections blocked from a separate namespace. Agent-to-MCP direct access blocked. Gateway caller port reachable. Rogue access to the MCP gateway listener and collector blocked. |
| Debug endpoint | Gateway did not expose `/thread_dump`. |
| Two consecutive skill/MCP requests | Distinct native tasks and trace IDs. Each had matched native MCP call/result IDs and successful server spans. |
| Received flow | Parent chains proved caller gateway → runtime → MCP gateway → MCP for both requests. |
| Backend completion | Two audit completions matched execution IDs, received traces, result hashes, and independent ConfigMap UID/version/data reads. |
| Trace privacy | Request privacy markers absent from received traces. Collector keeps allowlisted attributes and drops span events. |
| Credential preparation/renewal | Private files had mode 0600. Generated native config matched the renewed agent credential and dedicated gateway URL. |
| Grafana | Dashboard/datasource readback, Tempo/Loki health, six metric queries, trace lookup, and correlated completion-log query passed. Two annotations saved and read back. |
| Browser render | Not run. The browser access host was unavailable. API checks do not prove visual layout. |

The lab's collector image is tagged `0.146.0` and pinned to its observed digest. Its startup banner reports service version `0.145.0` while the spanmetrics component reports `v0.146.0`. The receipt identifies the actual image rather than inferring binary version from a tag.

The first exact-PONG attempt encountered the recorded owner's mandatory demonstration instructions. The clone now has an explicit semantic-health-check exception, and its subsequent exact PONG passed. No failing model request was silently retried by the caller.

The lab initially lacked scheduling headroom. Temporary demo workloads on the control plane were removed after memory pressure delayed reconciliation. The final profile runs on a dedicated worker placement with conservative memory limits and deliberately low rehearsal scheduling reservations. Those reservations are not production sizing guidance. The helper Deployments use `Recreate`; the generated native Deployment also received a scoped `Recreate` strategy for this saturated lab. The receiving platform must reserve normal rollout capacity or review its equivalent strategy.

The caller uses a loopback port-forward to the gateway's authenticated listener. This does not test public HTTPS ingress or workplace CA/authentication. The MCP data is a fixed synthetic record. Its Kubernetes read and protocol execution are real; it is not a live AKS investigation.

Workplace deployment, Entra Agent ID enforcement, production credential refresh, and integration into the existing workplace LGTM ownership remain untested. Preserve the workplace's current names, grants, identity process, exporter destinations, and delivery flow. Adapt the small producer/gateway/dashboard delta and repeat the same acceptance checks there.
