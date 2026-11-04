# One owner YAML, native kagent, KRO security composition

The owner supplies `modelConfig`, `systemPrompt`, `skills` and `tools` in one
`SecureAgent` instance. KRO passes those fields into a normal native kagent
`AgentTemplate`, creates the native `Agent`, and composes the reviewed security
resources from the platform profile. kagent owns the agent runtime and skill
loading. This extension adds no agent runtime, skill loader or operator.

Start with [the customer YAML](examples/secure-agent.yaml). The lab uses approved
OCI skills. Exact approved Git URLs and full commit IDs are also supported by the
schema; a GitLab fetch was not tested in this run.

The platform installs the RGD and security baseline once. The customer then
deploys just the instance:

```sh
kubectl create --validate=strict -f secure-agent.yaml
```

Select an existing approved model and MCP server. MCP operation lists must name
the permitted operations explicitly. An empty MCP operation list, which native
kagent can interpret as exposing every operation, is rejected. A top-level
`tools: []` means the agent has no MCP bindings. Prompts grant no permissions.

## Platform installation

This is a small extension of the existing native profile in
`../secure-byo-agent-composition/`. Preserve that deployment's approved images,
credentials, identities, Gateway endpoints and isolation. The protected profile
contains ordinary native resources plus its security boundary. Owner input is
never accepted as arbitrary resource templates, pod settings, credentials or
provider URLs.

1. Fill `examples/platform-profile.json` privately using the receiving platform's
   existing reviewed resources. Replace environment placeholders. Do not commit
   the private copy or credentials.
2. Render the RGD, admission policy, binding and customer example:

   ```sh
   python3 render.py --profile /private/reviewed-profile.json --output /private/rendered
   ```

3. Review and apply the platform files through the existing delivery flow:

   ```sh
   kubectl apply --validate=strict -f /private/rendered/resourcegraphdefinition.json
   kubectl wait --for=condition=Ready rgd/secure-byo-kro-secure-agent --timeout=60s
   kubectl apply --validate=strict -f /private/rendered/owner-policy.json
   kubectl apply --validate=strict -f /private/rendered/owner-binding.json
   ```

4. Give the customer only the generated `secure-agent.json` instance. JSON is
   valid YAML; the checked `examples/secure-agent.yaml` shows the readable form.

The profile controls allowed model names, exact immutable skill sources and
approved MCP server/operation selections. The generated schema and admission
policy reject selections outside that catalog and make intent immutable. Replace
an instance through the platform's retirement/reverification process to change
its intent. For the already-existing lab instance, retain legacy fields during
migration; dropping an immutable old `instructions` value is rejected.

## Security ownership

The current lab RGD composes native ModelConfig, Harness, RemoteMCPServer,
AgentTemplate and Agent objects, together with the existing authorization
frontdoor configuration, Service, Deployment and exact ReferenceGrant. That
frontdoor is the existing security adapter, not an agent runtime or skill loader.

HTTPRoutes, Agent Gateway JWT/authorization policies, NetworkPolicies and workload
admission remain the shared platform baseline. They were preserved, not recreated
by this extension. A Kubernetes MCP backend must enforce its own approved identity
and operation permissions; hiding tools from a model is not backend authorization.

The rehearsal is intentionally one `secure-byo-kro/demo` instance in its protected
namespace, because the existing profile has fixed shared dependency names. The
schema enforces that boundary. This is not a claim of arbitrary multi-instance
onboarding. Entra/UAMI remains a later extension.

## What was checked live

On 4 November 2026, KRO 0.9.4 compiled and activated RGD revision 8. The real
instance reconciled generation 2, its native AgentTemplate materialized all four
owner inputs, and native kagent 1.0.0-alpha17 reported the matching desired and
successful runtime revision Ready. The positive admission control and four
negative controls passed. See [the receipt](evidence/live-composition-2026-11-04.json).

These are live composition and admission results. No new provider inference,
caller lease, Golden success, Kubernetes MCP execution or Entra result is claimed.
The earlier standalone DeepSeek proof belongs to that separate implementation.

Run the portable checks with:

```sh
python3 -B -m unittest discover -s tests
```

Native API reference: https://kagent.dev/docs/kagent/1.x/reference/api-ref/

KRO schema reference: https://github.com/kubernetes-sigs/kro/tree/v0.9.4/pkg/simpleschema
