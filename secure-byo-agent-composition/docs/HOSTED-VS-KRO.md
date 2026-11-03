# HostedAgent and KRO comparison

For the work handoff, continue the existing HostedAgent operator and four CRDs. [The continuation instructions](EXISTING-HOSTEDAGENT.md) map that source to the new protections and preserve its no-Substrate path. The separate HostedSecureAgent lab adapter is not a completed port into the old operator. KRO remains an alternative for a compatible, approved native target.

Both POCs give the agent owner one small, immutable request. Both produce the same approved native Kagent agent and use the same independent security controls. The choice changes how the platform maintains the generated resources, and how much controller code the team owns.

For this fixed resource inventory, KRO is the first option to evaluate if the workplace already approves and operates KRO. A dedicated HostedAgent controller becomes more attractive when agent-specific lifecycle, migration, status, or cleanup needs substantial imperative logic. This is an architectural recommendation. The lab does not establish a performance, availability, or upgrade winner.

## What the two POCs actually compare

The Hosted POC introduces `secure.platform.kagent.dev/v1alpha1 HostedSecureAgent`. It is a small new Python controller inspired by the existing HostedAgent pattern. It does not upgrade or replace the earlier `skills.platform.kagent.dev/v1alpha1 HostedAgent` operator. That earlier implementation remains separate, including its content verification and onboarding contracts.

The KRO POC uses KRO 0.9.4 and a generated ResourceGraphDefinition to expose `kro.run/v1alpha1 SecureAgent`. It uses KRO's reconciliation engine rather than a second agent-specific reconciliation loop. [The shared renderer](../composition/compose.py) defines both request APIs and materializes equivalent protected profiles.

The request spec contains only `profileRef` and `instructions`. The platform fixes the images, skill and knowledge digests, model, MCP capability, identities, and network destinations. Instructions grant no permissions. The current deployment is a bounded demo with fixed resource names and one agent in each protected namespace. General onboarding of arbitrary names, multiple agents per namespace, or arbitrary BYO containers needs another reviewed contract. [The deployment driver](../scripts/deploy.py) and [profile builder](../lab_resources.py) show those assumptions.

## Benefits and limitations

| Decision area | HostedSecureAgent POC | KRO SecureAgent POC |
| --- | --- | --- |
| Owner experience | One namespaced request selects the protected profile and instructions. The spec is immutable. | The same request shape and immutability, exposed through KRO's generated API. |
| Main benefit | Direct control of agent-specific behavior, errors, ownership checks, and retirement in a small dedicated controller. | A declarative resource inventory maintained by an existing general composition engine. No bespoke reconciliation loop for these children. |
| Main cost | The platform owns the Python controller, API behavior, Kubernetes default handling, retries, tests, and future migrations. | The platform owns the RGD, CEL expressions, generated API contract, KRO compatibility, chart lifecycle, and its controller permissions. |
| Shared platform prerequisite | The dedicated native Kagent controller, gateway, identity, approval, policy, and network baseline remain necessary. | Exactly the same common platform prerequisites. Installing KRO does not replace them. |
| Resource creation | The controller preflights every expected name before child writes, adds ownership, and creates or repairs children. | KRO reconciles the templates in the RGD. The graph specifies desired resources and readiness expressions. |
| Atomicity and ordering | Several Kubernetes operations occur over multiple reconciles. Partial creation is possible. | A resource graph also reconciles over time. Applying one request is not a transaction across Kubernetes objects. |
| Readiness | The parent checks five native Agent conditions for the current generation and matching desired and successful revisions. It records child UIDs and the profile hash. | The graph checks the same native conditions and revision equality. It also checks generated Deployment availability and observed generation. |
| Readiness limit | The parent condition alone does not establish gateway policy attachment, network enforcement, authorization, or a completed model call. | KRO readiness has the same limit. CEL readiness expressions are not an access-control mechanism. |
| Foreign ownership | The custom controller explicitly rejects a pre-existing child owned by another request. Each write or deletion remains bound to the observed identity. | Collision and adoption behavior belongs to the pinned KRO release. Test it against the exact graph and installed version before asserting equivalent behavior. |
| Retirement | A custom finalizer uses the current profile and recorded UID inventory. Deletions use UID preconditions, and the finalizer waits for children to disappear. | Child ownership and retirement use KRO's lifecycle behavior. Required deletion order and interrupted cleanup must be demonstrated against that release. |
| Profile changes | A changed protected profile hash rejects reconciliation of an existing nondeleting request. A new request is required. | Editing the platform RGD can change the implementation behind an existing request. Version and review graph changes explicitly. Immutable owner fields do not freeze the RGD. |
| Extensibility | Additional typed checks or lifecycle steps fit in ordinary code. Each addition expands the custom controller's maintenance and review scope. | Adding supported Kubernetes resources usually means graph templates and expressions. Nondeclarative provisioning or cleanup may require another controller or workflow. |
| Diagnosis | Request conditions, the recorded inventory, and dedicated controller logs are specific to this implementation. | RGD state, generated API status, graph resources, and shared controller logs provide the diagnosis. Operators must understand KRO's expression and dependency behavior. |
| Controller permissions | A namespaced Role permits fixed managed kinds. Updates and deletes use exact resource names. Kubernetes cannot restrict `create` by resource name, so admission remains necessary. The composer cannot publish approvals. | The installed KRO chart's controller RBAC is a separate platform review item. A shared generic controller can have authority across more graphs and namespaces. Protect RGD authorship and constrain where requests can exist. Approval publication remains independent. |
| Air-gap inputs | Build the custom composer in the common approved image. Import the Python base, matching native CLI, and source before the offline build. | Import the KRO chart, CRDs, and every referenced controller image. The common front-door image and native CLI are still required. |
| Availability | The POC composer is one replica with a three-second polling loop and `Recreate` updates. No leader election or controller failover is demonstrated. | KRO's shared controller adds its own operational dependency. This POC does not prove KRO failover, scaling, or upgrade behavior. |
| Long-term fit | Agent-specific lifecycle orchestration with a team willing to maintain an operator. | Reusable declarative compositions with a team already responsible for KRO as a platform capability. |

The controller details are in [controller.py](../composition/controller.py). The KRO readiness expressions and request schema are in [compose.py](../composition/compose.py). The namespaced Hosted permissions and shared routing are in [deploy.py](../scripts/deploy.py).

## Security ownership stays separate from composition

Neither controller authenticates callers or makes an agent secure by keeping objects deployed. Both depend on these independently owned controls.

| Responsibility | Owner in both POCs |
| --- | --- |
| Request entitlement | Request-only RBAC, protected namespace assignment, and Kyverno request restrictions. |
| Approved resource contents | Protected profiles and Kyverno checks for model, content, tool, workload, and ownership constraints. |
| Caller and runtime access | The common front door verifies Kubernetes TokenReview, exact account UIDs, approval state and expiry, request and Agent UIDs, Agent spec, and four dependency pins. |
| Runtime isolation | Native sandbox configuration, actual network enforcement, fixed gateway destinations, and the restricted native RPC bridge. |
| Activation and revocation | An independent platform publisher controls approvals. Neither composer can approve its own agent. |
| Provider credentials | The platform supplies the model credential to the front door. Owners and native model configuration do not receive that provider key. |

The request owns namespace-local native configuration, the front-door Deployment and Service, its configuration, and the destination ReferenceGrant. The shared Gateway, central HTTPRoutes, runtime bridge, namespaces, WorkerPools, policies, identities, and approval publication remain platform prerequisites. Their lifecycle is separate from an individual request. [The baseline and profile builder](../lab_resources.py) and [central routing](../scripts/deploy.py) define the boundary.

A ReferenceGrant permits a resource reference. It does not authorize a caller. The grant names the destination Service and permits HTTPRoutes from the protected gateway namespace. Gateway API cannot name one source HTTPRoute in that grant, so the platform must protect the whole source namespace.

Access is denied while required objects or approvals are missing, deleting, expired, revoked, or mismatched. Reconciliation can restore desired resources, but access still requires fresh approval checks. Already-dispatched model work may finish after revocation. Neither option demonstrates instantaneous cancellation. [The runtime contract](../runtime/README.md) and [Kyverno contract](../policies/README.md) explain these common limits.

## What the current lab evidence establishes

The coordinator has observed a completed native run for each path. Both runs called the real skill loaders, read the knowledge reference, used the model, and returned the fixed MCP result. The final shared admission receipt contains 16 passing cases, including trusted worker lineage and forbidden copied identity, image and lineage controls. Network receipts cover a rogue Pod and both actual worker pools with positive gateway controls and denied direct paths. [The acceptance runner](../scripts/acceptance.py), [admission runner](../scripts/admission.py), and [network runner](../scripts/network_proof.py) reproduce those checks.

Those observations establish functional parity for this fixed profile and the tested controls. Both paths also passed 13 lifecycle checks, seven actual actor checks, and five in-flight revocation checks each. Both original and dedicated controller paths were probed. [Final lab results](../evidence/LAB-RESULTS.md) identify the receipts, checkpoint transport anomaly, and remaining gates. These results support the bounded POC comparison; they are not a production selection record.

[Independent closure review](../evidence/REVIEW.md) found no critical blocker for this bounded local comparison. Live ephemeral-container injection is an outstanding target admission gate.

Both candidates share important unproved target requirements. The lab uses Kubernetes tokens rather than Entra. Unattended token renewal, workplace identity integration, cold import of skill OCI artifacts, upgrade compatibility, high availability, and scale require separate evidence. The dedicated native controller is also a common single-replica prerequisite with a separate database schema. Source tests do not establish those operational properties.

Neither POC adds namespace quotas or per-caller rate and concurrency budgets. Fixed workload and model-token limits constrain individual operations; capacity and abuse controls remain common work before broader onboarding.

## How to choose after the POC

Prefer KRO when the approved platform already operates it and the agent remains a fixed declarative composition. Keep activation and authorization in the common services. Review RGD changes as privileged platform changes.

Prefer an extended HostedAgent when the required product needs agent-specific migrations, custom retirement, richer diagnostics, or external identity workflows that would otherwise introduce substantial imperative logic beside KRO. Port the proven behavior into a versioned extension of the existing operator before treating this new adapter as that operator's production successor.

Count common code and prerequisites once in the decision. Both options require the same front door, approval logic, gateway, policy, native runtime, and offline artifact supply. Compare the dedicated reconciliation code against the RGD and KRO operations burden. Select on the completed lifecycle evidence and the workplace's ownership model rather than the number of YAML files the owner applies.
