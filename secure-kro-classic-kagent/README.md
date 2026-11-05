# Secure KRO agent with native kagent 0.x, without Substrate

This is a separate work bundle for the normal `kagent.dev/v1alpha2` declarative
Agent runtime. Kagent creates an ordinary Deployment and Service. This bundle
uses **KRO 0.9.4** and a **kagent 0.10.4 schema, controller and runtime**.
It does not require AgentTemplate, Harness, actors, snapshots, a 1.x CLI or a
custom agent runtime. Use the matching controller, CRD chart and runtime images.
The [image inventory](IMAGES.md) lists exact tags, digests and optional components.
Run the preflight against the actual work installation before using the manifests.

For the customer demonstration, start with [DEMO-WALKTHROUGH.md](DEMO-WALKTHROUGH.md)
and open [presentation.html](presentation.html). The bundle includes a customer
template, catalog, prompt-building skill, terminal driver, split graph YAML and
[YAML speaker notes](YAML-GUIDE.md). The HTML is an offline illustration with
dated receipts; the terminal driver reads real receiving-cluster state.

The customer deploys one [ClassicSecureAgent instance](examples/agent.yaml).
The platform installs the resource graph and security baseline once. The graph
creates the native Agent, restricted ServiceAccounts, NetworkPolicies, protected HTTPRoutes, JWT policies,
Golden configuration and Job.
Kagent owns the native runtime Deployment and its generated configuration Secret.

The [live evidence](evidence/live-classic-0.10.4-2026-11-04.json) records a real native
Deployment, successful Golden PONG, a separate caller PONG, missing-token HTTP 401
and verifier-on-caller HTTP 403. KRO reported the current instance Ready. The
existing Substrate installation uses a separate controller and API.

## What changes from the Substrate bundle

| Concern | This non-Substrate bundle |
| --- | --- |
| Native behavior | `Agent.spec.declarative`, using `systemMessage`, `modelConfig` and native MCP tool bindings |
| Runtime | Ordinary kagent-managed Deployment and Service |
| Skills | Native 0.x `Agent.spec.skills.refs` or `gitRefs`; kagent's own skills initialization loads `/skills` |
| Public front door | Agent Gateway routes directly to the agent Service's A2A endpoint |
| Extra runtime image | Only the small Golden verifier image; no security front-door adapter or native CLI image |
| Golden proof | Actual model-generated PONG over A2A, plus authentication controls |
| Opening caller access | KRO waits for successful Golden completion before creating the caller HTTPRoute |
| Approval ConfigMap | No mutable approval record or four-hour lease from the other bundle |

This is a different security composition, not a promise of identical approval,
revocation or identity-pinning semantics. JWT expiry and the protected routes
control access here. After changing platform dependencies or rerunning Golden,
retire the caller route first and verify again. A completed Job is a recorded
verification, not a continuous revocation service.

All graph-managed children are kept in the instance namespace. Backend Services
are in that namespace too, so no ReferenceGrant is needed. A Gateway can be
attached through an approved cross-namespace parent reference and allowedRoutes,
but its platform baseline is managed separately. The checked demo uses a
Gateway in the same dedicated namespace.

## Customer inputs

The instance has four fields:

```yaml
apiVersion: demo.kagent.dev/v1alpha1
kind: ClassicSecureAgent
metadata:
  name: demo
  namespace: classic-agents
spec:
  modelConfig: approved-model
  systemPrompt: Reply accurately and concisely. Use only approved tools.
  skills: []
  tools: []
```

The platform catalog resolves selected skill and tool IDs into the native 0.x
fields. For example, `tools: [kubernetes-readonly]` becomes a native
`type: McpServer` binding with an explicit `toolNames` list. Tool selection never
grants backend permission by itself. Existing workplace MCP authorization must
remain enforced at the gateway and backend.

The minimal profile exercises the model path with no skills or MCP operations.
[platform-profile-with-catalog.json](examples/platform-profile-with-catalog.json)
shows GitLab-hosted skills and Kubernetes, GitLab and Denodo tool catalogs.
The corresponding one-file examples are [Kubernetes](examples/agent-kubernetes.yaml),
[GitLab](examples/agent-gitlab.yaml) and [Denodo](examples/agent-denodo.yaml).
These use the same bounded demo slot, so apply only one reviewed alternative at a time. Fill
and validate those bindings against the receiving system. Git fetching and those
three backend reads are separate acceptance tests; PONG does not prove them.

The checked baseline is intentionally one `classic-agents/demo` slot. Gateway
listener policies name its exact verifier and caller identities. Do not assume
another instance name or namespace is supported by changing customer metadata.
Platform RBAC must let customers manage only this custom resource in their
approved namespace, rather than its child Agents, Jobs, policies or credentials.

## Check compatibility first

Run this with the actual classic controller and KRO deployment names:

```sh
python3 preflight.py --context '{{WORK_KUBECTL_CONTEXT}}' \
  --kagent-namespace '{{KAGENT_CONTROLLER_NAMESPACE}}' \
  --kagent-deployment '{{KAGENT_CONTROLLER_DEPLOYMENT}}' \
  --kro-namespace '{{KRO_NAMESPACE}}' --kro-deployment '{{KRO_DEPLOYMENT}}'
```

The preflight requires the pinned kagent 0.10.4 controller rollout to be complete,
served `kagent.dev/v1alpha2` Agent, ModelConfig and RemoteMCPServer schemas with
matching hashes, matching controller runtime settings, no Substrate endpoints,
and the pinned KRO 0.9.4 image. It rejects the previous 0.8.0-beta4 baseline and
the different 1.x API. Mirrored controller and runtime repositories are accepted
when their manifest digests match the lock. It does not establish model or MCP
connectivity; the live acceptance checks do that.

## Install matching versions without Substrate

As checked on 2026-11-04, upstream's latest overall release is `1.0.0-rc1`.
Its native agent lifecycle depends on Substrate ActorTemplates and snapshots.
Disabling installation of the runtime does not give that release the classic
Deployment backend. **0.10.4 is the latest released 0.10.x runtime** and supports
the normal declarative Agent without Substrate. Keep these API families separate:

| Installation | Native agent API | Agent runtime |
| --- | --- | --- |
| This bundle, kagent 0.10.4 | `kagent.dev/v1alpha2` | Kubernetes Deployment and Service |
| kagent 1.0.0-rc1 | `api.kagent.dev/v1alpha3` | Harness and AgentTemplate with Substrate |

Updating image tags alone does not migrate between these APIs. CRDs, controller,
normal/full runtime images and skills-init must match. This bundle's
[versions.lock.json](versions.lock.json) is the parity contract.

For an existing 0.x installation, export its Helm values and preserve its database,
model credentials, existing agents, MCP servers and identity settings. Back up the
PostgreSQL database before allowing the new controller to migrate it. If the old
installation uses SQLite, prepare PostgreSQL first; this bundle does not migrate
historical SQLite sessions. Do not point the controller at a different release's
live database. The reference lab uses a dedicated demo PostgreSQL database.

Use the approved installation's release name, namespace and private values. The
following commands are a reviewed installation sequence, not a blanket upgrade
of every kagent release on a cluster:

```sh
helm pull oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds --version 0.10.4
helm pull oci://ghcr.io/kagent-dev/kagent/helm/kagent --version 0.10.4
```

Check the downloaded OCI chart digests against the lock. Install or upgrade the
existing CRD release first, using its real release name and ownership. Disable
both CRD dependencies so the classic installation cannot downgrade an existing
Substrate CRD or take ownership of an existing kmcp CRD. The six classic API
resources and two optional kagent sandbox API resources are still included.
Those optional API definitions do not install a Substrate runtime. No kmcp
controller is needed for the RemoteMCPServer references used in this bundle.

```sh
helm upgrade --install '{{KAGENT_CRD_RELEASE}}' ./kagent-crds-0.10.4.tgz \
  --namespace '{{KAGENT_NAMESPACE}}' \
  --set substrate.enabled=false --set kmcp.enabled=false
helm upgrade --install '{{KAGENT_RELEASE}}' ./kagent-0.10.4.tgz \
  --namespace '{{KAGENT_NAMESPACE}}' \
  -f /private/existing-kagent-values.yaml -f helm-values-no-substrate.yaml
```

The base values disable the Substrate subchart, controller integration and
WorkerPool creation. They disable bundled agents, bundled tools and kmcp, set UI
replicas to zero, and pin the runtime image family. Review those choices against
an existing shared installation before applying. Preserve any required shared UI
or bundled tools through explicit private overrides. Work MCP catalogs continue
to refer to the existing approved RemoteMCPServer objects.

PostgreSQL is required. The base values disable the development database and
expect the existing private values to provide `database.postgres.url` or
`urlFile`, with the corresponding approved Secret mounts. A clean lab may add
`-f helm-values-demo-db.yaml` as the last values file. That optional database uses
the official chart's public demo credentials and is not a workplace database
configuration. It is not required when the approved PostgreSQL service already
exists. Version 0.10.4 has charts and runtime images but no matching CLI binary;
use Helm, kubectl and query.py for this demonstration.

Reference source:
https://github.com/kagent-dev/kagent/tree/v0.10.4

Native deployment and skills documentation:
https://kagent.dev/docs/kagent/0.x/concepts/agents/

## Prepare the platform once

1. Establish kagent 0.10.4 using the matching chart, CRDs and image inventory.
   Keep `substrate.enabled`, `controller.substrate.enabled` and
   `substrateWorkerPool.create` false. The lab classic controller remains
   separate from the existing Substrate controller.
2. Create or reuse approved ModelConfig and RemoteMCPServer objects in the agent
   namespace. Their authentication stays in the existing Secrets. The graph
   selects those native objects by catalog entry; it does not copy provider keys
   into the instance or ConfigMap.
3. Build the verifier from an approved digest-pinned Python base, push it to the
   work registry and use its real manifest digest:

   ```sh
   docker build --build-arg PYTHON_BASE='{{APPROVED_PYTHON_IMAGE_AT_DIGEST}}' \
     -t '{{GOLDEN_IMAGE_TAG}}' runtime/
   ```

4. Fill a private copy of `examples/platform-profile.json`. Set the actual
   gateway addresses, Kubernetes service-account JWT issuer and JWKS, verifier
   image digest and exact model, MCP and controller egress paths. Set the
   controller path as well as the model path: classic agents need their native
   controller API for session and task storage. Skills initialization also needs
   the approved registry or Git egress when enabled.
5. Render the platform baseline, RGD and customer instance:

   ```sh
   python3 compose.py --profile /private/classic-profile.json \
     --output /private/classic-rendered
   ```

6. Review and install `platform.json` first. It creates the dedicated Gateway
   with separate verifier and caller listeners and strict listener-level JWT
   policies. Check the Gateway is Programmed and both policies are accepted
   before creating an owner instance. The per-route policies in the graph add
   exact route authorization; listener protection must already exist.
   If reusing a shared workplace Gateway, merge the reviewed listener and policy
   changes through its existing delivery flow. Do not replace its other listeners
   by applying this dedicated-Gateway example over it.
7. Apply `resourcegraphdefinition.json`, wait for its current generation to be
   Ready, and give the customer only the resolved `agent.json` or its YAML
   equivalent. JSON is valid YAML. KRO must have permission to manage the shown
   child resources in the agent namespace. The platform manages the Gateway and
   its listener policies.

The Kubernetes JWT issuer is used for the projected verifier token in this
version. Entra caller authentication is a later integration, not a reason to put
an Entra issuer into the verifier listener without also adapting verification.

## Apply one file, watch Golden, then query

After platform preparation:

```sh
kubectl --context '{{WORK_KUBECTL_CONTEXT}}' apply --validate=strict \
  -f /private/classic-rendered/agent.json
kubectl --context '{{WORK_KUBECTL_CONTEXT}}' -n classic-agents \
  get classicsecureagent,agents.kagent.dev,pods,jobs -w
```

In another terminal, inspect the Job's actual receipt:

```sh
kubectl --context '{{WORK_KUBECTL_CONTEXT}}' -n classic-agents \
  logs job/demo-golden
```

The Golden Job mounts its configuration and a projected verifier JWT. It has no
Kubernetes API token audience, no Role or RoleBinding, no provider key and no
native kagent CLI. It fetches the native AgentCard through the verifier-only
listener until the backend is ready. Then it checks missing and invalid tokens
are denied and the verifier cannot use the caller listener. Finally it makes one
A2A `message/send` request asking for exactly PONG and checks the completed native
task's assistant output. It never treats the user's echoed prompt as a pass.

KRO's ordinary resource dependency links the caller route to the Golden Job,
whose `readyWhen` requires `status.succeeded == 1`. Only after that dependency is
ready does KRO create the caller route. The instance reports Ready after the full
resource graph reconciles. The Job has no automatic retries. Its startup polling
fetches only the AgentCard, not model inference.

Use the caller listener to send your own query with an approved caller token:

```sh
kubectl --context '{{WORK_KUBECTL_CONTEXT}}' -n classic-agents \
  port-forward service/classic-demo 18080:8080
```

```sh
umask 077
kubectl --context '{{WORK_KUBECTL_CONTEXT}}' -n classic-agents \
  create token demo-caller --audience=secure-agent-classic --duration=15m \
  > /private/classic-caller.jwt
python3 query.py --url http://127.0.0.1:18080/classic/classic-agents/demo/invoke \
  --token-file /private/classic-caller.jwt --prompt 'Reply with exactly PONG. Do not call any tool.'
```

Only an operator authorized to mint the demo caller's token can use that mint
command. Preserve the receiving platform's approved caller-identity process.

PONG is a real model-generated reply through the native agent. It proves that
this route and runtime can reach the configured model. It does not prove skill
loading, MCP behavior or application-data correctness. Run those scenario checks
separately before demonstrating a Kubernetes, GitLab or Denodo capability.

## Operating boundaries

- The native controller creates and owns the runtime Deployment and Service.
  KRO owns the Agent and its security resources. The runtime ServiceAccount has
  token automount disabled. kagent separately projects a controller token with
  audience `kagent`; this is visible in the recorded native Deployment. The verifier mounts only a JWT with the custom
  Gateway audience.
- NetworkPolicy allows gateway-to-agent traffic and approved egress. Do not expose
  the native Service or controller APIs as an alternate customer front door.
  Apply a receiving-platform controller ingress policy so untrusted pods cannot
  use its session, task or A2A API directly.
  The reference receipt does not prove NetworkPolicy traffic enforcement. Verify
  the receiving CNI and explicit ingress/egress denial tests separately from PONG
  and JWT rejection before claiming blocked network access.
- Native 0.x skills can add file and shell tools. An OCI or Git skill is executable
  behavior, not only reference text. Keep reviewed immutable sources, non-root
  execution, filesystem restrictions, backend permissions and network boundaries.
  Kubernetes container isolation is the containment mechanism here.
- The public profile is configuration to review and resolve. It does not contain
  a provider key or complete workplace endpoints. The lab's kind-local verifier
  image tag is not a portable registry image.
- To change immutable owner intent, retire the previous instance through the
  platform process. To rerun Golden, first remove caller access, preserve the
  failed or completed receipt and create a deliberate fresh attempt. Do not
  delete a completed Job while leaving the previously opened route available.

The lab verification also caught an empty `NetworkPolicy.ingress` list that
caused repeated SSA updates and kept KRO NotReady. The final verifier policy
includes `Ingress` in `policyTypes` and omits the empty list, which still denies
all ingress and lets reconciliation converge. Do not reintroduce the empty list
when copying the manifests.

Run the local behavior checks with:

```sh
python3 -B -m unittest discover -s tests
```
