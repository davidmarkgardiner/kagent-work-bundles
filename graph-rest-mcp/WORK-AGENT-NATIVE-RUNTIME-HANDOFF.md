# Resolve the Graph REST MCP native-agent runtime blocker

Use this file as the work-agent instruction. Read
[WORK-AGENT-START-HERE.md](WORK-AGENT-START-HERE.md) and the local workplace
instructions before changing anything.

## Preserve the verified MCP path

The owner reports that the application image is built, the adapter pod is
deployed, and the MCP path is verified. Native agent invocation is unverified.
Confirm the existing receipts and record their context, timestamp, image digest,
and whether they prove MCP initialize, list tools, and call tool.

Two clusters are available, described as alpha2 and alpha3. The active target is
believed to be alpha3. Confirm the context and installed APIs before selecting a
route. API versions and controller release versions are separate facts.

Preserve the deployed adapter, REST configuration, model route, authentication,
Gateway wiring, and delivery process. Do not rebuild the adapter image solely
because a Harness is missing. Do not run the bundle's lab setup or teardown.
This handoff authorizes discovery, preparation, and validation. It does not
authorize a new runtime installation, cluster upgrade, or workplace rollout.

## Identify what is missing

On the v1alpha3 route, an Agent references an AgentTemplate and a Harness.
The template supplies behavior, model, and tools. The Harness selects the engine
and its runtime settings. Agent Substrate manages execution, and the referenced
WorkerPool supplies runtime capacity. The Harness also carries snapshot settings
according to the installed schema.

The MCP adapter pod serves tools. It does not supply the agent execution engine
or WorkerPool. Creating a Harness object alone does not provision missing runtime
capacity.

Distinguish these findings explicitly:

- The Harness CRD is absent.
- The Harness CRD exists, but there are no instances in the relevant namespace.
- Instances exist, but the current identity cannot read them or the Agent cannot
  reference them under the installed namespace rules.
- A Harness exists, but its engine image, WorkerPool, storage, or runtime is not
  usable.
- The wrong context or an incompatible template was selected.

## Discover the installed platform without changing it

1. Record the selected context and confirm its intended purpose privately.
   Use explicit `--context` on every subsequent Kubernetes command. Do not switch
   the global context or export kubeconfig credentials.

   ```bash
   kubectl config current-context
   KUBE_CONTEXT='{{SELECTED_CONTEXT}}'
   kubectl --context "$KUBE_CONTEXT" api-resources
   ```

2. Identify the installed kagent controller image and release. Inspect the served
   versions and schemas for Agent, AgentTemplate, Harness, ModelConfig, and
   RemoteMCPServer. Discover the Substrate resource groups and their served
   versions through `api-resources`; do not guess them from this lab bundle.
   Use `kubectl explain` with the discovered resource and API version.

3. In the relevant namespaces, list Agent and Harness names and readiness
   conditions. For a cluster-wide inventory, first confirm that list permission
   exists. A Forbidden response is a visibility gap, not proof that no resource
   exists. Do not broaden RBAC to complete discovery.

4. Inspect one existing working agent, if available. Record its API version,
   template or declarative configuration, model reference, runtime reference,
   and MCP registration pattern. Inspect its referenced Harness on v1alpha3.
   Keep full manifests, private addresses, and credentials inside work.

5. For v1alpha3, inspect the referenced WorkerPool and the installed Substrate
   controllers and workers. Check their conditions, runtime compatibility,
   available capacity, engine image availability, and snapshot storage access.
   Inspect configuration and existing evidence without creating a test actor.
   List the exact missing dependency if no usable runtime exists.

6. If comparing the second cluster, repeat discovery with its explicit context.
   An MCP receipt from one cluster does not prove that the other cluster's agent
   runtime can reach the adapter. Review the permitted network route before
   proposing a cross-cluster connection or another adapter deployment.

## Prepare the smallest compatible change

Select the route from current evidence:

- **Existing v1alpha3 runtime:** reuse an approved compatible Harness in the
  permitted namespace. Prepare the AgentTemplate and Agent wiring with the
  existing ModelConfig and only `get_graph_context` allowed.
- **v1alpha3 runtime exists, Harness configuration is missing:** prepare a
  Harness using the approved engine image or installed release default, actual
  WorkerPool reference, and approved snapshot settings. Verify all fields against
  the installed CRD. Record any additional image import needed by workplace
  policy. Do not use the MCP adapter image as the agent engine image.
- **v1alpha3 runtime is missing:** return the exact platform dependency list and
  a focused proposal for the platform owner. Do not install Substrate, a lab
  worker, a model, or storage to bypass the blocker.
- **Existing v1alpha2 cluster selected:** use its working declarative Agent and
  MCP registration pattern. This route does not use the v1alpha3 Harness
  resource. Preserve the existing model and agent runtime. Do not apply
  `api.kagent.dev/v1alpha3` manifests to this route.

Do not remove a required `harnessRef`, invent a reference, or create an empty
Harness to make validation appear successful. Do not upgrade a cluster merely
to match the lab YAML.

Render the proposed manifests privately. Check name collisions, namespace rules,
tool permissions, registry access, and the actual installed schema. Run a
server-side dry-run against the selected context. Submit the focused diff through
the existing review and GitOps process. Keep the prior configuration for rollback.

## Verify invocation after approved rollout

After rollout authorization, verify readiness and actual invocation separately.
Use the invocation method supported by the installed release.

1. Confirm that the selected agent discovers exactly the approved graph tool.
2. Submit one approved graph question with a known expected answer. Capture
   evidence that the agent calls `get_graph_context` and receives its result.
3. Confirm that the answer uses the returned source, scope, facts, and relevant
   relationships. Do not use the bundle's synthetic fixture counts as workplace
   acceptance criteria.
4. Check an approved ambiguous or unsupported question and an upstream failure
   scenario. Require clarification or a data-unavailable response as appropriate.
   Use approved mocks for failure cases unless live fault injection is separately
   authorized.

Do not silently retry or change clusters or providers after a failed or uncertain
submission. Reconcile its outcome first. Record sanitized receipts without raw
private responses, credentials, or session identifiers.

## Return a concrete report

Return the following information:

- Selected context alias, controller version, and served resource APIs.
- Harness CRD presence, instance visibility, and the exact missing dependency.
- Existing runtime and MCP references, sanitized for any external report.
- Chosen route and why it is the smallest compatible change.
- Proposed manifest diff and server-side dry-run outcome.
- Any engine image import, WorkerPool, storage, permission, or network gate.
- Separate statuses for MCP verification, agent readiness, and native invocation.
- Rollback through the existing delivery process and any remaining approval.

Until an actual agent tool call and grounded answer pass on the selected target,
report `MCP VERIFIED; NATIVE INVOCATION UNVERIFIED`. Do not treat Agent Ready,
tool discovery, or historical lab evidence as native workplace proof.

## References

- [Bundle native example](deploy/kagent.yaml.template). This is the alpha17 lab
  example, not a universal workplace manifest.
- [Official v1alpha3 Harness documentation](https://kagent.dev/docs/kagent/1.x/agents/agent-harness/).
- [Official legacy MCP integration](https://kagent.dev/docs/kagent/0.x/getting-started/first-mcp-tool/).

Use the documentation for the installed release and the actual served CRDs when
they differ from these examples.
