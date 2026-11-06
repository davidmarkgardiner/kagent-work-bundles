# Live agent onboarding

This adds a live frontend to the existing classic-agent composition. The static
presentations and mock IDP stay available for the illustrated walkthrough.

## Start the local backend

Use the approved context explicitly. The baseline has one slot,
`classic-agents/demo`, with exact caller and verifier identities at its Gateway
listeners. The backend checks that identity configuration before onboarding or
connecting; it does not widen shared policies or install platform prerequisites.

```sh
python3 live_demo.py --context '{{APPROVED_DEMO_CONTEXT}}'
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
2. **Onboard now.** Send the displayed customer intent. The backend adds the
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
6. **Delete.** Type the connected agent name. The backend issues foreground
   deletion with a server-side UID precondition, clears chat access, and observes
   the owner and its captured/discovered descendants disappearing. These include
   Pods, ReplicaSets and native Secret **metadata**. It never returns Secret data
   or runs a namespace-wide delete. Shared Gateway/catalog/RGD resources remain.

To prepare before the meeting, use the existing [terminal walkthrough](DEMO-WALKTHROUGH.md)
to deploy the same slot and leave it running. In the frontend choose **Connect
existing agent**. It rechecks that instance and runs caller verification; it
does not claim that an earlier Golden was a fresh onboarding run.

After deletion is verified, edit the prompt/selections and onboard the next
instance into the same slot. It receives a fresh UID and Golden Job. Another
named slot requires its own reviewed listener identity. This backend does not
change the shared listener policy to make another name work.

## Tools, namespace reads and identity

For a reviewed, installed catalog integration, explicitly allow its IDs:

```sh
python3 live_demo.py --context '{{APPROVED_DEMO_CONTEXT}}' \
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

The API returned is the cluster-local **HTTPRoute through Agent Gateway**. An
Istio `VirtualService` is a separate integration and is not installed here.
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
