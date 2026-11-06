# Replicate the live onboarding demo in AKS

For a browser-free fallback, use [TERMINAL-DEMO.md](TERMINAL-DEMO.md). The included
terminal console uses the same live backend gates, agent endpoint and UID-bound teardown.

Use this bundle instead of `secure-kro-native-owner-form` for work systems that
use the normal kagent Deployment runtime. Do not port AgentTemplate, Harness,
actor or snapshot resources from the other bundle.

For the interactive demo, host the supplied UI/backend in the same AKS cluster
as the agent. Follow [hosted/README.md](hosted/README.md): it includes the image
build, private inputs, scoped ServiceAccount permissions, admission guard,
NetworkPolicy and separate Istio VirtualServices for the UI and protected agent API.
This is prepared for receiving-cluster validation; the home rehearsal is not AKS proof.

1. Read the version installation section in README.md. Preserve the existing
   Helm release, approved PostgreSQL database and credentials. Back up the database
   before controller migrations. Use helm-values-no-substrate.yaml as reviewed
   overrides only if a separately approved platform installation is needed, not as a
   replacement for private values.
   Run the read-only preflight against the actual workplace classic controller.
   Discover the installed versions first; do not change shared controllers for this demo.
   Confirm KRO 0.9.4 and inspect the served `kagent.dev/v1alpha2` schema. The lab
   reference is kagent 0.10.4. Read IMAGES.md and versions.lock.json. Upgrade the
   matching controller, CRD chart and runtime image family together only as a
   separately approved migration; otherwise report incompatible installed versions. The read-only
   preflight must report NonSubstrateParityEstablished after the rollout.
   Do not use the 1.x api.kagent.dev API for this bundle.
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
Reuse live-onboarding.html and live_demo.py; do not build a second UI or an
orchestration workflow. The backend creates the same single customer owner YAML.

The overall release observed on 2026-11-04 was 1.0.0-rc1 and its native
agent path requires Substrate. 0.10.4 is the parity target for this non-Substrate
bundle. Do not swap only the controller image or change YAML API strings to
imitate the other release. The earlier 0.8.0-beta4 receipt is historical evidence;
use evidence/live-classic-0.10.4-2026-11-04.json for the current reference.

For the showcase, follow DEMO-WALKTHROUGH.md. Open presentation.html and
examples/agent-demo.yaml in VS Code. Use demo.py apply/watch/verify/show/query
to display the exact file, observe actual resources, match Golden to this owner
UID and invoke through the protected Gateway. YAML-GUIDE.md explains every
resource. The customer template and portable request-builder skill are included.
The static decks illustrate reconciliation and display dated receipts. The separate
live-onboarding.html uses its running backend for actual deploy, status, caller checks,
chat and teardown; opening the file alone does not connect to a cluster. GitLab writes are not included
in these read-only adapters.

Keep the next iteration in NEXT-STEPS.md. Prioritize Entra ID caller validation
and UAMI/Workload Identity for approved agent-to-MCP access. Reuse the existing
Gateway authentication, observability, token reporting, model catalog and policy
services. Capture their actual evidence and the separate tool/network checks.
The supplied live UI already produces the customer payload. A builder agent remains
a future optional producer of that same contract.
