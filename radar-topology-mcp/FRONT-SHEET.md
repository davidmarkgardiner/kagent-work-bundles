# Start here — Radar topology workplace trial

For the workplace OCI snapshot registry, start with
[AIRGAPPED-OCI-HANDOFF.md](AIRGAPPED-OCI-HANDOFF.md).

**Goal:** one approved development cluster, a browser topology map, and one
kagent Agent querying a known resource's connections through read-only MCP.

Start with [README.md](README.md). Review the [local proof](VERIFICATION.md)
and [known coverage gaps](README.md#what-is-proven-and-what-remains).

1. Choose the approved cluster/context, dedicated Radar namespace, kagent
   namespace, existing accepted ModelConfig, and approved image/chart source.
2. Fill `config.local.json`, render, verify the chart and permissions, and check
   the workplace CRD schemas. Keep generated workplace files outside public Git.
3. Deliver through existing Flux for permanent installation, or the README's
   Helm path for an approved development trial. Use no external ingress initially.
4. Prove readiness, RBAC denials, NetworkPolicy enforcement, UI navigation,
   a direct bounded MCP query, kagent discovery, and one real Agent tool call.
5. Record scope/errors and classify the result. A ready Agent alone is not a
   completed triage proof. Do not enable writes on this Agent.

**Included now:** standard inventory collection, relationship UI, current graph
queries, inline investigation instructions/rubric, and install/verification assets.

**Preferred knowledge integration:** reuse the existing vector KB via
[KNOWLEDGE-INTEGRATION.md](KNOWLEDGE-INTEGRATION.md) and `knowledge/agent.yaml.tmpl`.
See [live KB evidence](KNOWLEDGE-VERIFICATION-2026-10-01.md).

**Earlier experimental prototype:** [GUIDANCE-INTEGRATION.md](GUIDANCE-INTEGRATION.md) adds a
bounded snapshot guidance MCP and a separate four-tool Agent. Full A2A passed
on kagent 0.10.1 Go; Proxmox 0.7.13 has a response-cleanup failure. Read the
[live receipt](LIVE-VERIFICATION-2026-10-01.md) before workplace adaptation.

**Next phase:** guidance lookup using the existing approved KB/querydoc service,
versioned skill packaging, custom AgentgatewayBackend relationships, and fleet
availability/scaling decisions. The `knowledge/` catalog is a proposed format.

## Work-agent handoff prompt

```text
Use this Radar topology MCP bundle on the approved development cluster.
Inspect the existing delivery pipeline, installed kagent CRDs/runtime, model
configuration, image restrictions, and namespace policies before adapting files.
Keep permanent changes in the workplace's GitOps repository. Preserve existing
Agent/ModelConfig/Gateway objects and create the bundle's separate read-only Agent.
Render only non-secret inputs and reject unresolved placeholders. Review selected
inventory reads and enforce the ingress policy before giving the Agent access.
Run the documented checks and inspect a real get_neighborhood tool trace.
Report live proof, missing scope, unsupported edges, and provider failures separately.
Do not claim installed knowledge lookup or runtime skills: those are a next phase.
Do not enable apply/delete/exec tools or broaden the Agent's tool allowlist.
Stop before an unapproved workplace deployment or external publication.
```

Use [GITLAB-TICKET.md](GITLAB-TICKET.md) for the team's installation work item.
