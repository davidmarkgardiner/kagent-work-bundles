# HostedAgent operator and standalone KRO

Both approaches need the same platform controls: approved runtime/model/content/tool profiles, independent verification, current authorization, Gateway policies and an enforced workload/network baseline. Neither reconciliation mechanism establishes tenant security by itself.

| Decision | Existing HostedAgent operator | This standalone KRO reference |
| --- | --- | --- |
| Owner experience | Domain-specific HostedAgent fields and controller behavior | One immutable approved-profile request and instructions |
| Composition | Controller code owns lifecycle and status decisions | ResourceGraphDefinition templates and CEL own object creation/readiness |
| Runtime | Preserve the workplace's existing runtime contract and approved images | Ordinary long-running Deployment using the existing compatible Python helper plus immutable approved code; no Substrate or new image-build dependency |
| Existing model/skill/knowledge contracts | Extend the existing catalog and four-CRD integration seams | Reference ConfigMaps/pinned packaged content; office integration still needs an explicit adapter |
| Gateway onboarding | Controller must generate route, grant and policy consistently | Graph generates central route/policy and exact destination grant per name |
| Cross-namespace ownership | Controller must implement a correct ownership/finalization protocol | Protected cluster-scoped request with KRO ApplySet inventory/finalizer |
| Independent security verification | Controller readiness must consume trusted fresh results | Separate verification Job owns approval data; graph observes its result |
| New object types or fields | Code, tests, image and controller rollout | Graph/schema/CEL update, compatibility tests and controlled graph rollout |
| Terminal Job cleanup | Controller can request foreground/background propagation explicitly | KRO 0.9.4 defaults can retain orphaned terminal verifier Pods as audit records |
| Complex lifecycle | Code can implement staged migrations, renewal and detailed recovery | Simple immutable onboarding fits well; complex state transitions may require another trusted service/controller |
| Operational dependency | Maintain the custom operator, permissions and upgrade path | Maintain KRO, graph/schema compatibility and the shared authorization/verifier services |
| Failure diagnosis | Domain status/events can be purpose-built | Inspect graph node state, generated objects and verifier receipts together |
| Security trust | Operator/controller and profile authors are privileged | Generic KRO controller, RGD/profile authors and shared services are privileged |

KRO reduces object-composition code and makes the generated inventory reviewable. It does not remove application authorization, trusted verification, admission, identity or live lifecycle checks. This reference deliberately keeps those responsibilities explicit instead of encoding an entire security state machine in CEL.

The existing operator is attractive when maintaining the workplace's established ModelConfig, Skill, KnowledgeBase and GoldenScenario semantics is the main requirement, or when renewal/migration behavior needs a purpose-built controller. Reuse its established contract rather than replacing it to match the reference.

Use the lab evidence in this folder to evaluate the standalone KRO implementation. Earlier native KRO/HostedAgent results remain historical evidence for their recorded runtime and source revisions. They are not proof that this standalone bundle has integrated the office operator or the office's four CRDs.
