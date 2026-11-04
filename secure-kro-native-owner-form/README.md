# One YAML to deploy a secure native kagent agent

**Live native demo passed on 4 November 2026 at 11:28 UTC.** The customer provides
`systemPrompt`, `modelConfig`, `skills` and selected MCP `tools` in one KRO
`SecureAgent`. KRO creates ordinary native kagent resources and their security
front door. kagent runs the agent and loads the skills. The front door image
contains authorization, bounded model/MCP forwarding and the native CLI adapter.

Start with [the customer YAML](examples/secure-agent.yaml). After the platform
installation below, the customer deploys only this file:

```sh
kubectl create --validate=strict -f secure-agent.yaml
kubectl wait --for=condition=Ready secureagent/demo -n secure-byo-kro --timeout=600s
kubectl logs job/demo-golden -n secure-byo-kro
```

The live Golden Job loaded both native OCI skills and their reference documents,
made three DeepSeek model calls, called `get_demo_status`, and verified a separate
ordinary-caller invocation returned exactly `PONG`. Authentication, caller/worker
separation and forbidden-operation controls passed before any backend dispatch.
The approved caller lease expires at **15:28 UTC on 4 November 2026**. The actual
receipt is [here](evidence/live-native-golden-2026-11-04.json).

## What the customer can select

The owner YAML uses normal kagent field shapes. The platform profile defines the
approved model names, immutable skill sources, MCP servers and named operations.
Select from that catalog; prompts cannot grant permissions. Empty MCP operation
lists are rejected because native kagent can interpret them as all operations.
A top-level `tools: []` selects no MCP bindings. Intent is immutable after creation.

OCI skill loading was exercised live. Exact Git URLs with full immutable commit
IDs are supported by the schema, but GitLab downloading was not tested. The MCP
backend in this proof returns fixed synthetic status. Actual Kubernetes MCP
operations and Entra/UAMI integration remain future work.

## Platform installation, once

Use this folder with the existing `../secure-byo-agent-composition/` platform
baseline. It requires native kagent 1.0.0-alpha17, KRO 0.9.4, Agent Gateway 1.7.0,
working Substrate, policy enforcement, reviewed skill artifacts and credentials.
This is one agent per protected namespace; the current contract intentionally
uses `secure-byo-kro/demo` and fixed approved dependency names.

1. Build the security adapter and verifier image from approved, staged inputs.
   The native CLI checksum and Python base digest are in `versions.lock.json`.
   No dependency download occurs during the build.

   ```sh
   python3 build.py --base '{{APPROVED_PYTHON_IMAGE_AT_DIGEST}}' \
     --cli /private/kagent-linux-amd64 --image '{{APPROVED_IMAGE_TAG}}'
   ```

   Push through your approved registry flow and record the real registry manifest
   digest. The Proxmox lab used a kind-local image alias; that alias is not a
   portable registry image.

2. Fill private copies of `examples/platform-profile.json`,
   `examples/golden-config.json`, `examples/golden-platform.json` and, if using
   DeepSeek, `examples/model-provider-bridge.json`. Replace all environment
   placeholders, endpoints, API-server CIDRs, JWKS and image references. Keep
   the same skill sources in the profile, Golden configuration and owner YAML.
   The provider bridge reads its key from the existing
   `agent-flow-demo/standalone-deepseek-model` Secret, key `api-key`. Credentials
   stay outside this bundle. Owner input cannot supply provider URLs or tokens.

3. Merge the reviewed `golden-platform.json` changes into the receiving platform
   baseline. This file includes namespace-scoped verifier RBAC, exact workload
   exceptions, network rules, the invoke Gateway policy and a Pending approval.
   Its ClusterPolicies contain the existing lab baseline as context; preserve
   receiving-platform ownership and permissions when integrating the delta.
   **Do not reapply Pending to an Active or running verification.**

4. Render the RGD, owner admission contract and customer instance privately:

   ```sh
   python3 render.py --profile /private/platform-profile.json \
     --golden-config /private/golden-config.json --output /private/rendered
   kubectl apply --validate=strict -f /private/rendered/resourcegraphdefinition.json
   kubectl wait --for=condition=Ready rgd/secure-byo-kro-secure-agent --timeout=60s
   kubectl apply --validate=strict -f /private/rendered/owner-policy.json
   kubectl apply --validate=strict -f /private/rendered/owner-binding.json
   ```

5. Give the customer only the generated `secure-agent.json` or its YAML
   equivalent. JSON is valid YAML. New instances need no manual UID editing:
   KRO injects the instance UID into the verifier configuration and Job labels.
   For the migrated existing lab owner, retain its legacy immutable fields.

## Security and Golden ownership

The 11-node graph creates ModelConfig, Harness, RemoteMCPServer, AgentTemplate,
Agent, front-door configuration/Service/Deployment, exact ReferenceGrant,
verifier configuration and Golden Job. Shared HTTPRoutes, Gateway
JWT/authorization policies, NetworkPolicies and admission are installed by the
platform baseline. The instance uses those preinstalled boundaries. This bundle
includes their verification-specific changes; it does not claim each owner
instance creates a separate Gateway or arbitrary cross-namespace routes.

The verifier waits for the current front-door rollout. It claims a fresh Pending
record using compare-and-swap, binds the owner/agent/dependency identities and
native revision, and rotates only the native worker JWT Secret. Ordinary callers
stay denied during verification. Only real native tool results plus positive
model/MCP witnesses can promote the record to Active. Failure leaves it closed.
Revocation or replacement cannot be undone by a stale verifier.

The live run exposed and fixed an old adapter entrypoint, a plain-text gateway
rejection parser issue and a rollout ordering race. The isolated native worker
also needed replacement after its router returned connection-refused errors.
Six failed attempt receipts remain in the private lab evidence. A successful
fresh attempt then completed the scenario and caller smoke. External reviews
were stopped at David's request after provider quota failures.

For a deliberate rerun, archive the terminal Job receipt, remove the Job from
reconciliation temporarily, retire the old Job, restart the front door to reset
its bounded in-memory attempt budget, wait for rollout completion, create a fresh
Pending approval, then restore the Job node through the delivery flow. Never
manually set Active. Do not use the older baseline's manual approval helpers to
claim native Golden success.

Run the portable checks:

```sh
python3 -B -m unittest discover -s tests
```

Native API reference: https://kagent.dev/docs/kagent/1.x/reference/api-ref/

KRO schema reference: https://github.com/kubernetes-sigs/kro/tree/v0.9.4/pkg/simpleschema
