# Live agent onboarding

This adds a live frontend to the existing classic-agent composition. The static
presentations and mock IDP stay available for the illustrated walkthrough.
The downloaded HTML has no cluster connection by itself. The running backend
selects an explicit target: the Proxmox home lab for rehearsal, or AKS at work.

The [6 November home validation](evidence/live-onboarding-home-validation-2026-11-06.json)
records a live deploy, Golden/caller checks, interactive questions and teardown of
21 captured resources while preserving the shared platform. The home profile is
model-only. AKS/VirtualService mode is prepared but has not been connected or
validated at work; it requires the actual receiving context and HTTPS URL.

## AKS at work: use the existing VirtualService

There are two connections, with different purposes:

```text
Browser -> local demo backend -> AKS Kubernetes API (create/status/delete)
                             -> HTTPS VirtualService -> Agent Gateway -> Agent (chat/checks)
```

For the workplace invocation path, configure the actual HTTPS endpoint exposed
by the existing Istio VirtualService:

```sh
python3 live_demo.py --environment aks \
  --context '{{APPROVED_AKS_CONTEXT}}' \
  --agent-url 'https://{{WORK_AGENT_HOST}}/classic/classic-agents/demo/invoke'
```

The frontend displays this target and returns that same HTTPS endpoint after
verification. Caller rejection tests and the positive PONG use that exact
VirtualService URL. AKS mode requires the URL and does not use a lab port-forward
for invocation. The backend still uses the selected kubeconfig for Kubernetes
management operations; these do not pass through the agent's VirtualService.

This does not install or rewrite the workplace VirtualService, change ingress
authorization or configure AKS credentials. The receiving platform must have
the compatible secure-agent graph and approved runtime/model configuration.
The VirtualService must route the intended invoke path to the existing Gateway
caller listener, preserve its authentication contract and use an appropriate
request timeout. The returned path must match any approved URI rewrite.

For a model invocation route, configure and inspect `retries: {attempts: 0}`
through the workplace delivery process; a single backend request must not turn
into hidden proxy-level model retries. Check the effective proxy configuration,
not only a template. The [Istio HTTPRetry reference](https://istio.io/latest/docs/reference/config/networking/virtual-service/#HTTPRetry)
documents the zero-attempt setting. This demo does not alter shared retry rules.

The bundled reference caller uses a Kubernetes service-account JWT. If work has
another issuer, audience or an additional Entra ingress gate, the receiving
authentication configuration must be reviewed and tested there. Selecting AKS
mode does not implement an Entra token exchange or bypass that gate. Home-lab
success is not AKS, VirtualService or workplace identity proof.

## Start the local backend

Use the approved context explicitly. The baseline has one slot,
`classic-agents/demo`, with exact caller and verifier identities at its Gateway
listeners. The backend checks that identity configuration before onboarding or
connecting; it does not widen shared policies or install platform prerequisites.

```sh
python3 live_demo.py --environment home-lab --context '{{APPROVED_HOME_CONTEXT}}'
```

Open the loopback launch URL printed by the process. Its fragment contains a
fresh local session key. Keep the process running while presenting. Kubernetes
credentials and short-lived caller/verifier JWTs stay in the backend; they are
never returned to the browser. A raw `file://` page cannot deploy anything.

If the installed controller names differ, provide the existing names with
`--kagent-namespace`, `--kagent-deployment`, `--kro-namespace` and
`--kro-deployment`. This uses the same pinned parity checks as `preflight.py`.
The documented reference is kagent 0.10.4, KRO 0.9.4 and agentgateway 1.7.0.

## Demonstrate the journey

1. **Check platform.** Read the installed graph, native runtime and approved
   model catalog. The frontend offers only installed tool/skill IDs that the
   operator explicitly allowed at launch. The default is model-only.
2. **Deploy agent.** Send the displayed customer intent. The backend adds the
   fixed namespace/name, performs server validation, then creates one
   `ClassicSecureAgent`. It never overwrites an existing instance. KRO and kagent
   reconcile the graph, runtime and boundary resources.
3. **Watch real checks.** The UI reads current resources. It requires all graph
   resources, current Agent/runtime readiness, and a successful Golden receipt
   tied to this owner UID. The caller HTTPRoute must be accepted and resolved,
   point at this Agent's Service, and have the strict JWT/exact-subject policy.
4. **Receive the API.** The local backend sends four rejection checks and one
   caller PONG. Chat opens after all checks pass. Golden itself sends one model
   PONG; caller verification sends one more. Failures stop without automatic
   model retries, provider substitution or Job recreation.
5. **Ask about the agent.** Use the preset questions or enter a short prompt.
   Each click sends one actual native A2A request through the caller Gateway.
   The question includes a fresh platform configuration snapshot. Inspect the
   snapshot beside the answer and retain the native task/context IDs.
6. **Tear down agent.** Type the connected agent name. The backend issues foreground
   deletion with a server-side UID precondition, clears chat access, and observes
   the owner and its captured/discovered descendants disappearing. These include
   Pods, ReplicaSets and native Secret **metadata**. KRO's instance-UID labels
   identify graph members; native owner references identify runtime descendants.
   The live test found a completed Golden Pod whose owner reference was removed
   during Job deletion. A bounded cleanup worker therefore normally deletes
   previously captured, now-orphaned Pods by their exact UID after the owner has
   gone. It does not select unrelated Pods by label/name, force-delete, remove
   finalizers or silently retry a failed mutation. It never returns Secret data
   or runs a namespace-wide delete. Shared Gateway/catalog/RGD resources remain.

To prepare before the meeting, use the existing [terminal walkthrough](DEMO-WALKTHROUGH.md)
to deploy the same slot and leave it running. In the frontend choose **Connect
existing agent**. It rechecks that instance and runs caller verification; it
does not claim that an earlier Golden was a fresh onboarding run.

After deletion is verified, edit the prompt/selections and onboard the next
instance into the same slot. It receives a fresh UID and Golden Job. Another
named slot requires its own reviewed listener identity. This backend does not
change the shared listener policy to make another name work.

## Make the security conversation interactive

Example questions are visible before deployment, with buttons disabled until the
agent passes its checks. Clicking one then sends the selected question and shows
the returned answer. Answers use larger text, short paragraphs and formatted
bullets; technical task details stay collapsed under **Response receipt**. The
message requests at most 80 words and preserves unproven security limits.

Use **Try a curveball** for the nightclub-bouncer explanation, a request for keys,
a question about extra tools/another namespace, or the emergency shortcut. These
are real model responses with native task receipts; a refusal is not scored as
proof that a permission boundary is enforced. Answers receive a fresh platform
snapshot including configured hardening and the actual caller-check results.

Use **Challenge the caller gate** for the enforcement demonstration: no JWT,
a different identity, or the wrong audience. Each button sends one fixed,
bodyless request through the configured front door and shows its actual HTTP
status, with zero model calls. An unexpected allowed result revokes chat access.
The tool picker uses installed catalog IDs explicitly allowed by the operator;
changes take effect only on the next deployment, not through a prompt.

## Tools, namespace reads and identity

For a reviewed, installed catalog integration, explicitly allow its IDs:

```sh
python3 live_demo.py --environment home-lab --context '{{APPROVED_DEMO_CONTEXT}}' \
  --allow-tool '{{REVIEWED_READONLY_TOOL_CATALOG_ID}}' \
  --allow-skill '{{REVIEWED_SKILL_CATALOG_ID}}' \
  --read-namespace '{{APPROVED_READ_NAMESPACE}}'
```

IDs must also be accepted by the installed owner CRD. The model-only reference
graph accepts no tools or skills; passing flags does not install them or grant
backend access. A real agent MCP read needs its own receiving-system adapter,
credentials, RBAC, egress and tool receipt.

**Count namespace resources** is an explicitly labelled platform read: the local
backend counts Pods, Deployments and Services in the single configured read
namespace, then supplies that observation to the model. It is not an MCP call
made by the agent, and it does not grant Kubernetes credentials to the agent.

The caller identity in this reference is a Kubernetes service-account subject
with the configured JWT audience. It is not Entra/OBO or proof that a particular
application process is the only possible token holder. Strict Gateway rejection
checks and a NetworkPolicy object do not prove that every alternate controller,
Service or API path is blocked. The UI and agent snapshot keep that gap explicit.

In home-lab mode the API returned is the cluster-local **HTTPRoute through Agent
Gateway**, reached by a lab port-forward. In AKS mode it is the configured
workplace **VirtualService HTTPS invoke URL**, and all caller checks/chat use
that front door. The existing Istio `VirtualService` is not installed here.
Deployment uses the Kubernetes API; progress uses actual Kubernetes observations.
OpenTelemetry is for visibility, not the payload transport. OTLP trace export
is not configured in this first demo.

## Validation boundary

Run local backend/transport checks with:

```sh
python3 -B -W error::ResourceWarning -m unittest discover -s tests
```

Local tests and fixture browser interactions do not prove a live cluster
deployment, provider response, garbage collection or MCP operation. Keep those
separate from the historical live evidence already in this bundle.
