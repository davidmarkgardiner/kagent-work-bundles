# Implement verified fleet kubeconfig refresh for AKS-MCP

## Outcome

Replace request-time kubeconfig mutation with a morning, fail-closed fleet
refresh. One workflow publishes one multi-key Secret; Argo routes each approved
`clusterAlias` to a fixed-target read-only Agent/AKS-MCP pair that mounts only
that alias's single-context key.

## Scope

- Approve an immutable refresh image containing Azure CLI, kubectl, kubelogin,
  jq, Bash, and coreutils.
- Populate the private 10–12 cluster registry and sanitized agent routing map.
- Configure Azure Workload Identity for cluster-user credential retrieval.
- Bootstrap the named destination Secret and narrow Role/RoleBinding.
- Install the morning Argo CronWorkflow and one read-only AKS-MCP shard per alias.
- Configure Flux field-level ignore for workflow-owned Secret data/hash.
- Install one RemoteMCPServer/Agent pair per alias and the Argo routing template.
- Add workflow, Secret-age, and rollout alerts.
- Run one manual refresh and one A2A request against every approved alias.

## Acceptance criteria

- [ ] No running AKS-MCP container invokes `az aks get-credentials` or writes to
      `/home/mcp/.kube/config`.
- [ ] Candidate creation starts from an empty ephemeral directory on every run.
- [ ] Aliases are unique and match the private registry exactly; each published
      key contains exactly one cluster/user/context and that alias is current.
- [ ] Every AKS user uses kubelogin workload identity; no token, client key,
      client certificate, or password is embedded.
- [ ] Every context passes the bounded namespace and `auth can-i get pods`
      checks before publication.
- [ ] A failed cluster check preserves the previous Secret and pods.
- [ ] An unchanged hash performs no Secret update and no rollout.
- [ ] A changed hash atomically updates the named Secret and completes a
      zero-unavailable rollout of every named AKS-MCP shard.
- [ ] Unknown or conflicting aliases return `BLOCKED_UNKNOWN_CLUSTER` without
      an MCP call.
- [ ] AKS-MCP tool calls never contain context, kubeconfig, server, token, or
      certificate redirection flags.
- [ ] Each successful A2A result records the routed alias and fixed Agent/MCP
      pair without credential or endpoint data.
- [ ] Refresh failure, stale-success, and failed-rollout alerts are proven.
- [ ] Image digest, chart version, CRD schemas, Git commit, and redacted receipts
      are attached to this issue.

## Rollback

Suspend the CronWorkflow, roll AKS-MCP back to its prior values/image, restore
the previous Secret from the approved secret backup path, and restart the
Deployment. Do not restore kubeconfig data from Git, a ticket, or an agent
transcript. Verify one context at a time before re-enabling the schedule.

## Evidence to attach

- Render/lint/public-safety verifier output.
- Manual Argo Workflow name, phase, start/finish time, and non-secret hash.
- Failed-candidate drill showing the Secret resourceVersion/hash did not change.
- Unchanged-candidate drill showing no new ReplicaSet.
- Changed-candidate drill showing rolling rollout completion.
- RemoteMCPServer Accepted/discovered-tool status.
- One sanitized A2A receipt per cluster alias and one rejected unknown alias.
