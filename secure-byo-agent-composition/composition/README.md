# Composition adapters

Both adapters consume the same protected JSON profile. Its shape is:

```json
{
  "name": "approved-readonly-v1",
  "namespace": "secure-byo-hosted",
  "resources": []
}
```

`resources` contains the complete reviewed namespace-local objects for the selected runtime and capability. The owner cannot supply these objects. Fields may contain `{{NAME}}`, `{{NAMESPACE}}` and `{{INSTRUCTIONS}}`. The first two derive from the validated request metadata. Instructions are content and confer no permission.

An owner request contains only:

```yaml
apiVersion: secure.platform.kagent.dev/v1alpha1
kind: HostedSecureAgent
metadata:
  name: reader
  namespace: secure-byo-hosted
spec:
  profileRef: approved-readonly-v1
  instructions: Read the supplied skill, knowledge reference and approved MCP evidence.
```

For KRO use `kro.run/v1alpha1` and kind `SecureAgent` in that adapter's protected namespace. Both approaches materialize the same profile resources. Kyverno must constrain request namespace, immutable spec and profileRef for the KRO API. Only platform owners can change RGDs or profiles.

`generate(profile, request, owner=True)` is the pure Hosted renderer. `rgd(profile)` emits the KRO ResourceGraphDefinition. `crd()` emits the Hosted request API. They have no Kubernetes side effects. The renderer rejects unsupported kinds, duplicate names, cross-namespace children and owner metadata in the protected templates.

Use native `api.kagent.dev/v1alpha3` resources. The inspected alpha17 Agent shape is `spec.template.ref.name`, not older `templateRef`. Native AgentTemplate MCP wiring is `spec.tools[].mcp.server.{kind,name}` with `mcp.tools` operation names. Target-cluster schema admission remains required.

The Hosted controller is dependency-free Python using the mounted Kubernetes account. Give it a namespaced Role only for its request API and the exact managed resource kinds. Credentials, approval publication, token review permission and shared platform resources are separate prerequisites. A controller needs no Secret reads, arbitrary cluster RBAC writes or namespace writes.

The first Hosted reconcile adds a finalizer. Later reconciles preflight every desired name, reject foreign ownership, create or repair only owned children, and record their UIDs. Deletion removes HTTPRoutes before Agents and pins every deletion to the observed child UID. Cleanup completes only after the children disappear. Kubernetes ownerReferences are only namespace-local. Shared gateway or destination-owner resources require separately owned prerequisites or a separate explicit inventory; never attach cross-namespace ownerReferences.

The common front door must independently check protected approval, exact request UID and current request deletionTimestamp on every operation. The composer's Ready condition observes native runtime health only. It does not activate caller access, establish network enforcement or prove token refresh. Reconciliation and route deletion are not the runtime revocation mechanism.

KRO graph nodes express the same reviewed desired resources; they do not claim transactional application or authenticated access by themselves. A parent platform baseline must already isolate traffic and deny inactive/unapproved requests. The same verifier must test both paths.
