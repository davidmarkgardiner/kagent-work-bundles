# The front door, Golden configuration and verification Job

This document explains the deployed native kagent demo so a work agent can
replicate its configuration and verification process. Use the installation steps
in [README.md](README.md) with the configuration relationships described here.

The Proxmox deployment passed a real native-agent scenario and an ordinary-caller
PONG test on **4 November 2026 at 11:28 UTC**. The model was `deepseek-flash`.
The evidence is in
[live-native-golden-2026-11-04.json](evidence/live-native-golden-2026-11-04.json).
This result applies to the lab composition and its fixed synthetic MCP operation.
A workplace deployment must produce its own receipt.

## What each component owns

| Component | File or key | Purpose | Writer |
| --- | --- | --- | --- |
| Native `AgentTemplate` | `spec.systemPrompt`, `modelConfig`, `skills`, `tools` | Defines what the agent does. Native kagent loads and runs it through the selected `Harness`. | KRO, from the approved customer instance |
| Front-door ConfigMap `demo-frontdoor` | `data.runtime.json` | Configures the security adapter that checks requests and forwards native invocations and model traffic. | KRO, from the platform profile |
| Golden ConfigMap `demo-golden-config` | `data.config.json` | Specifies the target agent, reviewed skill evidence, gateway and verification limits. | KRO |
| Approval ConfigMap `demo-approval` | `data.approval.json` | Holds the changing verification state, identity bindings, expiry and result receipt. | Platform creates `Pending`; the authorized verifier updates its own attempt |
| Golden Job `demo-golden` | `python3 -B /app/golden.py --config /golden/config.json` | Runs the checks against the real deployed resources and gateway. | KRO creates the Job; Kubernetes runs its Pod |

The system prompt and skill content stay in native kagent resources and immutable
skill artifacts. The front-door ConfigMap contains security-adapter settings.
Neither configuration ConfigMap contains the provider API key.

## What the front door does

The front door is a small security adapter in front of the native kagent runtime.
The adapter does not implement the agent or load its skills. Its Deployment runs
the bundled [server.py](runtime/server.py), with the native kagent CLI in the same
image for session creation and invocation.

The shared HTTPRoute points to `demo-frontdoor` Service, port 8080. Agent Gateway
checks JWT authentication and its authorization policy before forwarding a
request. The adapter then checks the live approval record and the Kubernetes
identities and resource specifications bound to that record.

The adapter exposes these paths:

| Path | Purpose |
| --- | --- |
| `GET /healthz` | Reports that the adapter process is alive. It does not prove model access or Golden success. |
| `POST /invoke` | Accepts a prompt, creates a native kagent session and invokes the agent through the native CLI. |
| `POST /v1/chat/completions` | Accepts the approved worker identity and forwards bounded model requests to the configured provider bridge. |
| `POST /mcp` | Provides the fixed, read-only demo MCP operation `get_demo_status`. It does not execute Kubernetes operations. |
| `POST /witness` | Returns adapter dispatch counters to an authorized identity so Golden can check that model and MCP traffic occurred. |

The `runtime.json` fields have these roles:

| Fields | Meaning |
| --- | --- |
| `namespace`, `agentName`, `request` | Select the protected `SecureAgent` and native `Agent`. |
| `approvalName` | Selects `demo-approval`, the live state record checked on requests. |
| `dependencyNames` | Names the exact AgentTemplate, Harness, ModelConfig and RemoteMCPServer whose UIDs and specification hashes are checked. |
| `requireGoldenProof: true` | Requires the bound Golden receipt before ordinary callers can invoke the agent. |
| `verifierSubject` | Names the exact verifier ServiceAccount used during the `Verifying` phase. |
| `kagentBinary`, `apiURL`, `gatewayURL`, `nativeUserID` | Configure the native CLI and its control-plane and A2A connection. |
| `modelName`, `modelMaxTokens` | Restrict the requested model and output-token limit. The demo limit is 1,200 tokens per model request. |
| `upstreamModelURL` | Selects the fixed model-provider bridge endpoint. |
| `upstreamModelKeyFile` | Reads the forwarding credential from a mounted Secret file. In this lab, `/credentials/token` is the worker JWT. The separate provider bridge supplies the actual DeepSeek key. |
| `verificationBudgets` | Bound one verification attempt to one native invocation, 12 model requests and four MCP calls. These are ceilings. The successful scenario used three model calls and one MCP call. |
| `upstreamURL` | Configures the alternative HTTP invocation transport. With `kagentBinary` configured, the native CLI transport takes precedence. |

**The two `gatewayURL` fields point to different services.** In front-door
`runtime.json`, `gatewayURL` is the native kagent A2A endpoint used by the CLI.
In Golden `config.json`, `gatewayURL` is the protected Agent Gateway invoke
listener. In the lab, the native controller handles both CLI endpoints on port
8083. Golden reaches the protected invoke listener on port 8081. Resolve each
placeholder according to its role; do not replace every URL with one address.

The Deployment mounts `demo-frontdoor` at `/config`, so `data.runtime.json`
becomes `/config/runtime.json`. It mounts the worker JWT Secret at `/credentials`.
The process reads its configuration at startup. After changing that configuration,
complete the adapter rollout before starting a new verification attempt.

## What the Golden ConfigMap contains

[examples/golden-config.json](examples/golden-config.json) is the input to the
renderer. [golden_graph.py](golden_graph.py) places that JSON under
`demo-golden-config.data.config.json` and injects the customer instance UID with
`${schema.metadata.uid}`. The Job mounts the ConfigMap read-only at `/golden`.

The Golden configuration contains these values:

| Fields | Meaning |
| --- | --- |
| `namespace`, `agentName`, `approvalName`, `request` | Identify the bounded target and its approval record. |
| `requestUID` | Binds verification to this instance, including when an object name is reused. KRO fills it; a customer does not edit it. |
| `dependencyNames` | Select the same four native dependencies named in the front-door configuration. |
| `gatewayURL` | Selects the protected Agent Gateway invoke listener. |
| `maxTTLSeconds: 600` | Limits the verification attempt to ten minutes. |
| `activeTTLSeconds: 14400` | Grants a four-hour access lease after successful scenario verification. |
| `skills[].source` | Requires the selected skills to match the reviewed immutable artifact sources. |
| `skills[].proofTerms`, `references[].path`, `references[].proofTerms` | Define the content and reference-document evidence required in paired native tool calls and responses. |

These are test instructions and expected evidence, rather than the result of the
test. Editing this ConfigMap cannot truthfully turn a failed run into a pass.
The verifier must execute the configured scenario and collect the evidence.

## How the Golden Job changes access

The Job uses the `approved-verifier` ServiceAccount, a non-root container, a
read-only root filesystem, dropped capabilities, `restartPolicy: Never`,
`backoffLimit: 0` and a 600-second active deadline. Its definition is in
[examples/golden-job.json](examples/golden-job.json). The shared runtime image
contains both `server.py` and [golden.py](runtime/golden.py), but the Job runs
`golden.py`, while the front-door Deployment runs `server.py`.

The verifier follows this sequence:

1. KRO waits for the current front-door Deployment rollout and creates the
   verifier configuration and Job. The Job validates its own Pod UID, controlling
   Job UID, ServiceAccount and instance labels.
2. The verifier reads the target instance and native dependencies. It records
   their UIDs and specification hashes, then atomically claims a fresh `Pending`
   approval as `Verifying`. Each later state update tests both the ConfigMap
   resource version and the complete previous approval JSON.
3. It requests short-lived caller, worker and verifier tokens for audience
   `secure-byo`. It rotates only the existing native worker JWT Secret, then waits
   for the native Agent's current desired revision to become Ready. The verifier
   needs this temporary phase because native MCP initialization needs worker
   access before the full scenario can run.
4. It proves that ordinary callers cannot invoke during verification, missing or
   wrong-audience tokens are rejected, caller and worker permissions remain
   separate, and a forbidden MCP operation is rejected without backend dispatch.
5. Through the protected gateway, it invokes the actual native agent. The agent
   loads both selected skills and their reference documents, calls
   `get_demo_status` and answers the synthetic documentation case through its
   configured model. The verifier requires a completed native task, paired tool
   calls and responses, expected document content, and positive model and MCP
   dispatch-counter changes.
6. It rechecks native readiness and the bound identities and specifications. It
   writes the scenario receipt and transitions its approval to `Active` with an
   expiry. Only then does it test a separate ordinary-caller invocation for PONG.
7. After PONG succeeds, it stores `callerSmoke.passed: true` and exits
   successfully. KRO requires `nativeGolden.status.succeeded == 1` before the
   parent instance reports the full graph Ready. A caught failure leaves the
   attempt failed or superseded and does not restore a revoked approval.

```text
Fresh Pending record
    -> Verifying: verifier can test; ordinary caller is denied
    -> Native scenario passes
    -> Active lease: ordinary caller can invoke
    -> Ordinary-caller PONG passes
    -> Job Complete and SecureAgent Ready

Failed check -> Failed, or leave a superseding record unchanged
Expired lease -> requests denied even if the stored state still says Active
```

There is a short `Active` phase before the PONG check completes. A caught PONG
failure changes the verifier's own Active attempt to Failed. Require both Job
completion and the caller-smoke result when accepting a run. If the verifier is
terminated externally, do not assume its exception cleanup ran; inspect the
approval and revoke or retire the incomplete attempt through the platform flow.

The receipt hash binds the stored receipt to its content. It is not a digital
signature. The authorization boundary also depends on RBAC, admission controls,
the permitted writers, gateway policies and network isolation.

## What PONG proves

PONG is a model-generated smoke-test response, not a Kubernetes ping, a health
endpoint response or a hard-coded reply from the adapter. The verifier sends the
following prompt through `/invoke` using the ordinary approved caller token:

```text
Reply with exactly PONG. Do not call any tool.
```

The verifier requires HTTP 200, `TASK_STATE_COMPLETED`, a native task ID, a
context ID and exactly `PONG` in an agent output or artifact. A copy of the user's
prompt in the conversation history does not satisfy the check.

This confirms that an ordinary approved caller can pass the gateway and adapter,
invoke native kagent, reach the configured model and receive a completed reply.
The earlier Golden scenario separately proves skill loading, reference reads and
the selected MCP call. PONG alone does not prove those capabilities.

## What was deployed and verified

The successful native run used KRO 0.9.4, kagent 1.0.0-alpha17 and Agent Gateway
1.7.0 on the Proxmox lab. The following results are in the stored receipt:

| Check | Recorded result |
| --- | --- |
| Native documentation scenario | Completed successfully |
| Native `load_skill` calls | 2 |
| Native `load_skill_resource` calls | 2 |
| Model requests during that scenario | 3 |
| Approved fixed MCP calls | 1 |
| Authentication and forbidden-operation controls | Passed |
| Separate ordinary-caller PONG | Passed at 11:28:14 UTC |
| Access lease expiry | 4 November 2026 at 15:28:12 UTC |

At the read-only cluster check on **4 November 2026 at 13:01:51 UTC**, the Golden
Job remained Complete, the SecureAgent remained Ready, one front-door replica was
available, and the recorded access lease was still valid. See
[the state-check receipt](evidence/documentation-state-check-2026-11-04.json).
That check did not make another provider request.

The live run exercised OCI skills and the fixed synthetic MCP status tool.
GitLab fetching, real Kubernetes MCP operations, Entra or UAMI authentication,
arbitrary multi-instance deployment and workplace security acceptance were not
verified by this run. The approved-worker Pod needed replacement after native
router connection-refused errors before the successful attempt. Earlier failed
attempt receipts remain in private lab evidence.

## What the work agent must preserve

Use [the platform installation procedure](README.md#platform-installation-once)
to stage the image, fill private configuration copies, install the shared
security baseline and render the graph. Preserve these relationships during
replication:

- The current implementation targets `secure-byo-kro/demo` with fixed approved
  dependency names. Both verifier and adapter enforce that bounded profile.
  Renaming the namespace is a code-and-policy change, not only YAML substitution.
- Keep the native skill sources, Golden skill catalog, selected model and named
  MCP operation consistent. The current Golden scenario requires selected skills
  and `get_demo_status`; it is not a generic verifier for an agent with no tools.
- Keep `requireGoldenProof: true`, the exact verifier identity, dependency checks,
  bounded verification budgets and the separate caller and worker permissions.
- Preserve the native CLI entrypoint, ConfigMap mount paths, worker JWT Secret,
  verifier Role and RoleBinding, gateway audience, exact ReferenceGrant, model
  route and network-policy paths. Keep provider keys in the provider bridge's
  Secret. Do not place credentials in ConfigMaps or customer YAML.
- Preserve the KRO dependency on the current front-door rollout. Native Agent
  Ready or an available adapter alone does not establish model-backed success.
  The installed kagent runtime also uses the term Golden for its prepared actor
  snapshot; that snapshot is separate from this bundle's verification Job.
- Collect a new successful Job receipt and ordinary-caller smoke result on the
  receiving cluster. Check the lease expiry and compare the native revision and
  resource bindings before accepting the deployment.

For a deliberate rerun, archive the terminal receipt and follow the rerun process
in [README.md](README.md#security-and-golden-ownership). Temporarily remove the
Job node from reconciliation before retiring its Job. Restart and finish the
front-door rollout to reset its bounded in-memory attempt budget, create a fresh
Pending approval and restore the Job node. Recreating a terminal Job alone does
not reset the approval or the adapter's attempt budget. Never manually set Active
or reapply Pending over a running or valid approved attempt.

## Inspect a deployed instance

These commands read configuration and evidence. They do not rotate credentials,
renew a lease or rerun the model:

```sh
kubectl -n secure-byo-kro get configmap demo-frontdoor -o yaml
kubectl -n secure-byo-kro get configmap demo-golden-config -o yaml
kubectl -n secure-byo-kro get configmap demo-approval -o yaml
kubectl -n secure-byo-kro get job demo-golden -o yaml
kubectl -n secure-byo-kro logs job/demo-golden
kubectl -n secure-byo-kro get secureagent demo -o yaml
```

The ConfigMaps contain no provider credentials, but a receiving platform may
consider service endpoints and verification metadata internal. Sanitize any
export before placing it in a public work bundle.
