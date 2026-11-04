# Standalone composition and security boundaries

The previous KRO proof generated a native kagent Agent/Harness and used Substrate. This reference instead deploys a bounded standalone agent in an ordinary Deployment. It has no native controller/actor execution dependency.

The deployment reuses a compatible approved Python helper image. Application and reviewed content bytes come from immutable code ConfigMaps, with explicit approved file projections and a fixed Python entrypoint. A new custom image is not a KRO prerequisite. The separate optional builder is a packaging reference, not the main office deployment path.

Generic Python makes code delivery part of the security boundary. Admission must enforce the approved payload itself, its immutability, the exact volume source/projection/mount, command and role arguments, and reject executable hooks, environment injection and shadow mounts. The verifier checks the mounted/API payload and runtime source receipt against protected expected hashes before activation. An annotation claiming the expected hash is insufficient.

## Compose across namespaces correctly

A protected cluster-scoped KRO instance represents one immutable approved request. KRO places the runtime and destination grant in the fixed standalone namespace and its HTTPRoute/JWT policy in the fixed Gateway namespace. Namespaces and the shared Gateway/facade/verifier services remain platform prerequisites.

In KRO 0.9.4, child lifecycle is maintained through server-side apply and ApplySet inventory/finalization. It is not ordinary per-child ownerReference garbage collection. The ApplySet membership identity is based on names rather than request UID. The facade and verifier must independently pin the live request UID and reject deleting or recreated requests. Do not add invalid cross-namespace ownerReferences or assume a same-name request inherits authority.

The cluster-scoped request is a platform pipeline interface, not a grant of cluster administration to tenant owners. A namespace/profile change requires a reviewed platform contract. RGD authorship and the generic KRO controller remain privileged trust roots.

## Keep identities and traffic separate

An approved caller invokes the agent through the Gateway. The central route references an exact per-agent front Service in the standalone namespace; a destination ReferenceGrant consents to that reference. The Service reaches a platform-owned facade. Gateway JWT checks and facade TokenReview/authorization both apply.

This reference uses Kubernetes service-account JWTs with the configured audience and exact account identity/UID checks. Entra is deferred. Replacing the Gateway issuer alone does not establish Entra compatibility with the backend's TokenReview and account-pinning contract; that needs a reviewed identity adapter and its own tests.

The facade dispatches to the selected runtime. The runtime has only a projected audience-bound worker token and a private opaque handle for that authorized invocation. It uses those to request the fixed model operation and typed MCP capability through the Gateway. It has no provider key, API-audience token, kubeconfig or arbitrary shell/SQL/URL tool.

The route policy enforces Gateway JWT authentication/approved subjects. The facade and runtime enforce the reference's typed operation/tool restrictions. This is not evidence of Agent Gateway MCP aggregation, tool-catalog authorization or an external workplace MCP server; adapt and prove those capabilities when integrating the approved office backend.

The shared facade can inspect only the approved namespace/resource types and configured model destination. It receives no Secret-read or general execution permission. It checks current request, configuration, workload, route, grant, identity and approval pins before dispatch and completion. Lost authority, deletion, changed pins, expiry or revocation deny fresh operations. Already-dispatched provider work may finish; this is not an instantaneous cancellation claim.

A ReferenceGrant permits the exact destination Service and source resource kind/namespace. It cannot identify one source HTTPRoute by name. Protect the source Gateway namespace and route writers. Grant consent does not authenticate a caller.

## Verify before activation

KRO creates an approval ConfigMap shell without owning its data. A separate trusted verifier identity performs the scenario and supplies current pins/result/expiry through a compare-and-swap update. Admission protects those fields from direct composer/other writes and allows unchanged data during metadata reconciliation.

The verifier Job must not depend on approval readiness, even through a reference to the approval object's name. It derives names directly from the owner request. KRO 0.9.4 `readyWhen` expressions can reference only their own resource; expected request UID is therefore projected into approval metadata for comparison with its own data. Backend checks still compare against the live request.

The verifier and configured revoker identities may create or update ConfigMaps only when the name ends in `-approval`. A separate fail-closed admission policy confines their namespace-wide RBAC patch permission to those records. The existing approval-data policy then limits the permitted state transitions and fields. This also prevents those identities from updating the namespace API trust ConfigMap. Use separate platform-maintenance identities: an identity in a configured revoker group receives this restriction even when it has additional RBAC roles. The supplied verifier/revoker roles grant no ConfigMap delete permission; the writer-scope admission policy covers CREATE and UPDATE. Administrators with broader permissions remain trusted platform actors.

Every rendered Kyverno validation rule explicitly sets `allowExistingViolations: false`. Do not rely on the server's default, which allows already-violating resources to continue violating a policy. Current positive and negative admission tests remain required after installation.

During a bounded verification lease, only the verifier may invoke. A worker token alone cannot initiate model/MCP work; the facade must issue a live invocation handle. Ordinary callers become eligible only after the current scenario passes. A stale Job/receipt cannot approve a new UID. No automatic lease renewal or permanent session/task persistence is implied.

Resource readiness and current access authority remain separate checks. A historical Ready or completed Job does not waive a current lease, revocation or pin failure. The evidence view must display current expiry and freshness.

## Retain terminal audit Pods during cleanup

KRO 0.9.4 uses empty Kubernetes delete options. Job deletion therefore uses the Job default orphan behavior. Terminal verifier Pods can remain after the Job and owner request are removed. Admission permits removal of a matching Job owner reference only on an update of an already Succeeded or Failed Pod. It still validates the approved code, command, mounts, identity and execution shape. It does not admit an ownerless verifier Pod at creation.

Treat retained terminal Pods as historical audit records. They cannot authorize a new request or establish current health. After retaining the receipt, a platform operator may delete the exact terminal Pod by its recorded UID/name as a separate reset action. Do not delete every Pod with the same agent-name label during same-name recreation.

Kyverno reports a status-subresource advisory for this check because it reads the old Pod phase during ordinary metadata updates. This policy does not validate Pod status writes. Keep that advisory distinct from a CEL compilation failure and verify actual admission decisions.

## State the limits honestly

The local KRO controller has broad platform permissions, including impersonation and admission-policy changes. A direct self-approval guard does not establish resistance to a compromised cluster administrator or KRO trust root. Review and constrain controller/RGD authority through the approved platform model before broader onboarding; do not silently change shared KRO permissions and break other graphs.

This reference's model settings and content bindings are standalone configuration with exact packaged data hashes. Its GoldenScenario is a platform Job/receipt. Existing native ModelConfig, Skill, KnowledgeBase, HostedAgent and GoldenScenario controllers are neither replaced nor falsely marked Ready. Workplace integration of those contracts must be adapted and proved explicitly.

The documentation/status MCP case is synthetic and read-only. It does not prove Azure execution, vector retrieval, Entra integration, production sandbox isolation, cold registry delivery, HA, scale, automatic renewal or full OTel ancestry.
