# Replicate the native 0.x demo without Substrate

Use this bundle instead of `secure-kro-native-owner-form` for work systems that
use the normal kagent Deployment runtime. Do not port AgentTemplate, Harness,
actor or snapshot resources from the other bundle.

1. Run the read-only preflight against the actual workplace classic controller.
   Establish KRO 0.9.4 and inspect the served `kagent.dev/v1alpha2` schema. The lab
   reference is kagent 0.8.0-beta4. Report a different work version rather than
   silently assuming it has the same capabilities.
2. Read README.md and fill a private platform profile. Reuse the existing model,
   MCP servers and credentials. Keep explicit MCP operation lists and exact
   egress paths. Begin with the model-only PONG profile.
3. Build and publish only the small Golden verifier image in runtime/. The agent
   uses the installed kagent runtime image. It needs no custom security-frontdoor
   image or 1.x native CLI.
4. Install the strict verifier and caller Gateway listener policies before the
   RGD and customer instance. Validate the full graph against the work API.
5. Apply the one ClassicSecureAgent file. Observe the normal Agent, Deployment,
   Service and Golden Job. Require the actual completed model-generated PONG
   receipt, then confirm KRO created the protected caller route.
6. Run query.py through the caller route with the approved caller JWT. Save the
   native task ID and response digest. Verify a missing token and a verifier
   token cannot use the caller route.
7. Add reviewed skill and tool catalogs using the existing workplace contracts.
   Run separate positive backend queries for Kubernetes, GitLab and Denodo before
   calling those integrations verified. The PONG Job proves model connectivity.

Return installed controller images, the resolved receiving-cluster manifests,
actual native Deployment and Service evidence, Job receipt, caller task ID and
negative-control results. Keep environment endpoints and credentials private.
Do not build an orchestration workflow, UI or builder agent for this replication.
