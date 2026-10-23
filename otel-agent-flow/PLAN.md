# OTel agent flow POC

1. `how` over the affected subsystem. Done. Local kind runs kagent 0.10.1 and agentgateway 1.5.0. Agent Substrate is not installed there. Existing tools use direct MCP, while models use agentgateway.
2. `architect` for parallel design exploration. Done. Native architect compared direct OTLP JSON ingestion with a Jaeger query projection. Choose direct ingestion for a small, low latency POC. External provider exploration was reduced because the configured Grok CLI is unavailable.
3. Write the throughput checkpoint as four todo items.
   - Blocking first steps. Discover installed CRDs, telemetry switches, exporter format, and current runtime before configuration changes.
   - Independent workstreams. Dashboard and telemetry adapter can be built independently of the namespaced collector and dedicated agent wiring.
   - Shared mutable state. One bounded ActivityStore owns retained spans. New files stay in this bundle. Existing user changes are preserved.
   - Smallest safe decomposition. One implementation owner keeps the small backend/UI contract together; runtime wiring and browser verification follow sequentially.
4. Delegate code-writing through provider dispatch. The configured Grok writer returned unavailable-cli before execution. Receipt is private under /tmp/otel-flow-pstack/. No provider substitution or successful external review is claimed. The parent continues the user's explicitly requested local POC implementation.
5. Verify on the matching surface. Passed actual OTLP reception, one correlated local caller/runtime/gateway/tool path, browser invocation, replay, cost estimates, component filtering, and span inspection. Substrate remains an explicitly unconnected lane because it is absent locally and the previous remote host is unreachable. See evidence/verification.json.
6. Rebase into small, ordered commits. Skip. User work is already present on the current branch; no commit or branch change is requested.
7. If the design is contested, `interrogate` before shipping. Not contested.
8. Run Opening a PR. Skip. No PR was requested.

## Data contract

An immutable Span records trace/span/parent IDs, timestamps, service, operation, status, role, and bounded allowlisted metadata. ActivityStore deduplicates transport retries and derives per-trace graph edges, token usage, and cost. Missing usage and price stay unknown. Gateway and runtime usage for the same parent/child model call are counted once. Uncorrelated traces remain separate.

The collector receives OTLP gRPC/HTTP and exports JSON to the dashboard. The dashboard receives telemetry metadata and accepts a validated user prompt for one dedicated read-only agent. The invocation endpoint returns a preallocated trace ID so the UI follows that request. Native agent and gateway spans must arrive independently of the caller span. Replay reads recorded spans and is explicitly labelled.

## Substrate connection milestone

- Blocking first steps. Located the existing isolated VM, verified host capacity and SSH identity, started VM 201, and checked installed charts, CRDs, client APIs, and live resource readiness.
- Independent workstreams. Existing dashboard assets and installed chart inspection were read independently. One owner serialized cluster changes and invocation adapter changes.
- Shared mutable state. The bounded ActivityStore remains the telemetry owner. Exact native actor identity links original traces into a session view; trace details and token accounting retain their original scope.
- Smallest safe decomposition. Reused the existing model credential at the laptop gateway through an SSH tunnel. Added a dedicated tool-free native kagent agent, the installed-release gRPC caller, and a separate dashboard on port 8788.

Model the Domain shaped the explicit session activity projection. Fix Root Causes led to enabling the missing Substrate egress tracing hop so parent-based model report reconciliation works. Prove It Works required a real prompt, native worker restore/checkpoint records, a final suspended actor state, and the served UI/API checks. See `evidence/substrate-verification.json`. The configured external implementation provider remains unavailable as recorded earlier; no substitute provider review is claimed.

## Portable work bundle milestone

1. Ground the affected subsystem. Installed alpha CRDs, native telemetry parent chains, ingress contracts, and capacity were checked.
2. Choose the architecture. One application image plus a Helm chart places dashboard, collector, model gateway, and fixture tools on one cluster. The local TLS proxy and AKS Istio ingress share the same application routes.
3. Throughput checkpoint. Blocking checks are installed platform versions, TLS Secret, exact RemoteMCPServer schema, and native worker readiness. Independent reads cover ingress docs and runtime inventory. One ActivityStore owns telemetry. One implementation owner serializes the coupled chart, fixture protocol, and UI contracts.
4. Implementation provider. The configured provider remains unavailable as recorded earlier; parent continues the authorized bundle work. No external provider review is claimed.
5. Verify the built artifact. Passed 47 unit tests, all three fixture workflows over certificate-validated HTTPS, and one live-model inventory workflow on the final poc-3 image. Native restore/checkpoint, final suspended actor, eight component roles, and zero host bridges were observed. Served UI assets were checked in a Node DOM model; no new browser visual recheck is claimed. Local and AKS chart profiles render. Portable receipts record target-cluster limitations.
6. Commits. Skip because no commit or branch change is requested and unrelated user changes are present.
7. Review. Check the chart and application boundaries against the deployed artifact.
8. Pull request. Skip because none was requested.

## Repository handoff and existing-platform integration

1. Ground. Read the chart ownership, invocation environment, OTel projection, verifier, and current work repo layout.
2. Sketch. Compared sharing a ModelConfig while deploying another gateway with attaching the dashboard to an existing agent. Choose the existing-agent profile because the existing agent already owns its model/gateway/MCP/skill wiring.
3. Agree. Continue the user's explicit source-repository handoff request. No target deployment is performed.
4. Implement. Model the Domain led to one integration mode, bundled or existing. Existing mode renders no agent, gateway, model, or tools. An optional existing Istio Gateway reference makes the VirtualService the only ingress resource owned by this demo. Blocking inputs are the approved agent and tool names, image digest, Gateway, and OTel fan-out. Independent checks cover chart render and source safety. One owner serializes files and publication.
5. Verify. Prove It Works requires rendered ownership checks, unchanged bundled behavior, a connected-verifier guard, and read-back of the published source. Historical poc-3 runtime receipts remain explicitly scoped to that rehearsal. The configured external provider remains unavailable as previously recorded.
6. Scrap. Not needed. Keep the existing local running demo unchanged and hand off source for the work build.

## Triage, SDLC, and identity-isolation scenarios

1. Ground. Checked fixture protocol, OTel allowlist, session graph scope, source publication, and the older JWT/Entra evidence boundary. Read current Microsoft primary identity and claims documentation.
2. Sketch. Compared separate uncorrelated demo pages with shared scenario presets and OTel operation cards. Choose shared presets and received-span cards. Keep real identity probes outside the prompt caller because the internal gRPC path does not test the protected front door.
3. Agree. Continue the requested example demos and source handoff. No Entra identity, app role, or tenant mutation is authorized or needed.
4. Implement. Model the Domain puts fixture tool sequences and system labels in bounded registries, and real security test cases in a private plan. Independent checks cover source/UI and identity-probe behavior. One owner handles runtime deployment and publication. Blocking live inputs remain existing Entra credentials, gateway policy, metrics, and work cluster access.
5. Verify. Prove It Works requires actual native sessions and MCP/OTel for new fixture scenarios, denial-with-backend-hit failure tests, and GitHub read-back. Native Entra proof remains NOT RUN without the work tenant.
6. Scrap. Not needed. Do not fold authentication, authorization, network isolation, and sandbox isolation into one inferred success flag.

Scenario result. All six fixture cases passed certificate-validated HTTPS on poc-6. Actual served UI/API DOM checks confirmed per-span card pulses, original-span inspection, presets, errors, and simulation labels. Runtime source/UI hashes match the repository sources. 57 unit tests passed. The Entra probe has behavioral tests but no work-tenant runtime receipt.

## Live homelab Kubernetes and GitLab MCP

1. Ground. Native tools 0.3.0 serves k8s_get_resources and k8s_get_events. The old SDLC cluster is unreachable; the existing glab OAuth refresh restored a verified private project read. No GitLab content changes are needed.
2. Sketch. Compare forwarding the old write-capable MCP with deploying a fixed GET-only GitLab reader and a namespace-scoped instance of the existing Kubernetes tool image. Choose the latter to enforce the read boundary in the servers and RBAC.
3. Agree. Configure the live homelab demo requested by David. Retain fixture mode as an alternative. No Entra changes are included.
4. Implement. One explicit tools mode controls agent instructions, MCP resources, and UI data labels. Kubernetes has get/list only in the demo namespace. GitLab has three no-argument reads bound to one configured project. Blocking checks are actual model/provider readiness and tool OTel. Independent checks cover adapter bounds and chart RBAC. One owner serializes the runtime switch and publication.
5. Verify. Prove It Works requires UI submission to a real model, successful server-side Kubernetes/GitLab tool spans, independent API read-back, native Substrate lifecycle, and observed UI labels. Missing or expired credentials fail visibly rather than using fixtures.
6. Scrap. Not needed. Existing platform resources and the old SDLC queue remain untouched.

Live result. Four expected server calls passed with a real model on poc-8. Independent reads matched all six deployment names, five issue IIDs, project name, and latest pipeline ID. Actual RBAC checks denied writes, Secrets, nodes, and another namespace. 65 tests passed. Model the Domain kept live and fixture tools explicit. Attack the Premise tested application TLS independently of the repeatedly resetting local port-forward; direct in-cluster HTTPS passed with normal CA and hostname checks. Prove It Works checked the actual served UI and runtime source hashes.

## MCP-specific live scenario milestone

Ground: the existing generic MCP role showed tool cards, but live mode hid scenario choices and discarded OTLP span kind. Sketches considered splitting the eight-role topology into tool-specific graph nodes, or retaining the role topology with separate MCP service panels. Chose the latter to keep existing component/session semantics stable and expose exact tools without inventing edges.

Implementation: backend supplies namespace-aware live presets and preserves span kind, exported status, and explicit execution evidence. Kubernetes tools 0.3.0 uses internal handler spans, confirmed against the pinned upstream source. Only its exact service, allowlisted tool, and matching handler operation qualify. Server spans qualify directly. Client attempts never activate a confirmed MCP panel. Panels and cards use completed received spans; no in-flight claim.

Verification: 69 offline tests; real single-MCP and combined scenarios; HTTPS-served UI behavior via Node DOM, including client-only negative control and batched-call pulse regression. No new interactive browser visual check. No AKS runtime, Entra isolation, or native Kubernetes OTel logs claim.

## Dual-runtime comparison

- Ground: installed alpha8 Harness requires substrate; native app.New also requires a controller-backed actor TaskStore. The lower-level native runner, executor, and A2A server can use an in-memory session/task store without a controller or actor. Verify this boundary in a normal Deployment.
- Sketch: compare a second older kagent control plane against a thin standalone wrapper over the same pinned alpha8 native ADK libraries. Prefer the wrapper to isolate execution runtime while keeping the model, tool allowlists, prompt, gateway, and versions comparable.
- Agree: user explicitly requested both demonstrations; proceed without an approval checkpoint.
- Implement: runtime targets are an operator-owned registry; submitted IDs select existing targets, never caller-supplied URLs. Standalone and substrate modes have explicit labels and independent evidence rules.
- Scrap: if native standalone still requires actor identity, reject it instead of labelling a Substrate-dependent deployment standalone.

Throughput checkpoint:
- Blocking first steps: confirm native alpha8 runtime can execute independently and identify A2A wire format.
- Independent workstreams: read-only native architecture review runs separately from parent-owned backend/chart/UI work.
- Shared mutable state: parent owns all source writes and one live Helm release; agent only reads public sources.
- Smallest safe decomposition: one writer avoids conflicting registry, UI, and deployment changes. Grok architect lane dropped out because its executable is absent; no substitute was presented as a Grok review.

Dual-runtime result: native alpha8 wrapper compiled from pinned upstream source, standalone and Substrate calls passed against the same real Kubernetes/GitLab tools, native lifecycle arrived only for the Substrate path. 80 offline tests pass, including standalone preflight/installer independence, no automatic input approval, bounded response size, configured target routing, and retaining both requested runs under background traffic. HTTPS-served Node DOM tests passed for switching, historical labels, inactive standalone lanes, scoped actor lifecycle, and unexpected actor evidence. Runtime/source/native-binary hashes matched. No fresh browser visual check, absent-platform cluster runtime, AKS deployment, CNI enforcement, or Entra isolation claim.
