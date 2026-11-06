# DICE review sheets and connected presentation chapters

Open [START-HERE.html](START-HERE.html) first for the complete offline demo menu.
Use [showcase.html](showcase.html) for the 6 November review sheets.
It gives the two stories an explicit order: the platform we build and how teams
consume it, followed by how our own teams use it. Its eight sheets cover the
product, KRO lifecycle and API consumption, current JWT security, planned Entra
identity, Gateway models/tools/cost/telemetry, three observability iterations,
GitLab SDLC, and SRE Lens. It works offline and prints one sheet per A3 landscape
page. Source disclosures stay available on screen; the printable copy retains
the main proof boundaries and source links.

The existing decks link back to these review sheets. Component names “GEF” and
“Node.js MCP” await owner clarification. The sheets use generic classifier/data
labels and identify the inspected Kimi/Denodo sources in their review notes.
Entra and Gateway-mediated MCP remain planned integrations for the classic demo.
The review sheets contain no new runtime verification. The current work-bundle
distribution contains the checked presentation edits and offline references.
Local browser checks and the remaining review points are recorded in
[the showcase validation receipt](evidence/showcase-review-validation-2026-11-06.json).

## Story 1 resources and hardening

Start with [resources.html](resources.html). Its two main sheets answer
**what gets deployed and why** and **how the agent is hardened**. The inventory
shows all seven kinds in the 14-resource KRO graph and names the purpose of the
three HTTPRoutes. Shared platform setup and kagent-generated runtime objects
have separate ownership labels.

Full before/after resource selection and exact YAML remain under the closed
**Optional resource-by-resource YAML** disclosure. Use it when someone wants
the implementation detail. The main presentation and print path contain the
two explanatory sheets.

Rebuild the resource sheet from the bundle sources with
`python3 build_resource_comparison.py`. It contains no live status or backend
actions. The optional initial deployment is an illustrative comparison, not a historical
snapshot or a claim that every ordinary kagent agent is unprotected.

Journey slide 3 is now **Deploy, use, update, and remove**. It describes how to
close caller access before a material change, run fresh verification, and
remove access and owned resources when retiring an agent.

After the cover, comparison and lifecycle, slides 4 and 5 show [resource kinds and their purposes](journey.html#resource-purpose)
and [agent hardening](journey.html#hardening), with arrows connecting their controls. The visible cards explain why
each object or control exists. Clicking a card opens optional source detail;
the resource cards include the exact graph templates.

[The resource-comparison validation receipt](evidence/resource-comparison-validation-2026-11-06.json)
records the offline selector, source-fidelity, keyboard, mobile, and navigation checks.

## Story 1 desired state

The optional [tomorrow.html](tomorrow.html) expands the desired-state discussion.
The first sheet summarises where DICE is going. Six further sheets explain the
desired architecture, Entra and Kubernetes controls, a checkpoint/wait/resume
illustration, the separate types of memory, intended benefits and measurements,
and the staged adoption path.

The identity and Kubernetes sheet incorporates the earlier shared-cluster
isolation explanation. It links the original
[agent-isolation page](../kagent-agentgateway-tenant-isolation/AGENT-ISOLATION-EXPLAINER.html)
and [animated boundaries demo](../../docs/agent-isolation-slides/index.html).
Entra owns identity, federation, and grants; Gateway validates and authorizes
requests; Kubernetes controls admission, API rights, and network paths. The
full-namespace-admin target and restricted classic-demo role remain distinct.

This is a proposed direction, not a promise of next-day delivery. Current classic
demo proof, separate historical or fixture work, and desired integrated behaviour
have separate labels. The document does not migrate the classic runtime or deploy
durable workflows, memory services, Entra identity, or Substrate.

The roadmap distinguishes persisted task/session state, semantic recall, and
actor execution state. Current kagent documentation describes data-scope actor
snapshots with fresh processes on resume. Fuller process-memory snapshots are a
separate runtime/configuration capability and must be tested on the selected
version. Neither actor snapshots nor memory retrieval authorise external writes.

Benefits include continuity, security, reuse of reviewed lessons, responsiveness,
self-service, auditability, and total cost. They are intended outcomes with
proposed measures; the sheets contain no fabricated savings or recovery results.

[The desired-state validation receipt](evidence/tomorrow-validation-2026-11-06.json)
records document/browser checks, the original explainer links, and the boundary
between current proof, historical experiments, and the proposed service.

For the animated walkthrough, open `journey.html` first. All four decks work offline as standalone HTML files.
Keep them in the same folder to use the Journey / Triage / SDLC links in each
slide footer. `index.html` remains the earlier architecture deep dive;
`presentation.html` remains the actual YAML explorer with dated receipts.

| Chapter | Presentation | Main message |
| --- | --- | --- |
| 1 | [Secure agent journey](journey.html) | Compare an ordinary native Agent with the KRO security composition, then explain tool selection, native skills, Gateway policies, OTel/LGTM and the lifecycle. |
| 2 | [SRE Lens asks the right specialists](sre-lens.html) | Select permitted specialists by the question, gather scoped MCP evidence, and return one answer with sources and uncertainty. |
| 3 | [SRE triage and application recovery](triage.html) | Explain the original Kafka evidence path and the newer application-owned specialist, bounded classification, reviewable MR, human approval and measured recovery. |
| 4 | [Agent-assisted SDLC](sdlc.html) | Follow an approved task through PM, builder, tester and reviewer roles, artifact-backed checkpoints, bounded rework and human merge. |

Journey has nine slides, SRE Lens has five, and Triage and SDLC each have six. They include clickable
source/details, presenter notes and landscape printing. All diagram states and
examples are **illustrations**.
No presentation invokes a model, sends Kafka messages, creates an MR, approves a
change or changes a cluster. Use the terminal walkthrough and receiving-system
receipts to establish live behaviour.

## Running the visual flow

Choose **Repeat after** and select **3, 5 or 10 seconds**. The current slide's
flow plays immediately and repeats after that pause following completion.
Select **Off** to stop automatic replay. This does not advance slides.

Replay and automatic motion stop when a dialog is open, the page is hidden or
printing starts. Repeating can resume after returning to the page or closing
the dialog. Reduced-motion preferences disable automatic replay and travelling
markers. Selecting a scenario replays that scenario. Navigation changes the
active diagram and cancels the previous animation.

Use arrows or Page Up / Page Down to navigate, Home / End for first / last,
**R** for Replay and **N** for notes. Native buttons and selectors retain their
normal keyboard behaviour. On mobile, scroll the diagram sideways inside its
labelled region. Print exports every slide in the selected chapter.

## Keep the implementation boundaries clear

- Native kagent runs both the ordinary and composed agent. A normal Agent can
  also be secured manually. KRO provides repeatable assembly, not a new runtime.
- Denodo, GitLab, Kubernetes and kagent tool families are catalog examples,
  not a claim that every backend is installed. Actual tool names and permissions
  must come from the receiving deployment.
- Native skills load from approved sources into `/skills`. Skill selection
  does not grant tool access. Prove the source revision, compatible runtime,
  fetch authorization and actual use separately.
- The secure bundle composes JWT route controls and verification. Other Gateway
  policy families, token budgets and observability wiring are explicitly
  presented as configuration choices. The diagrams contain no fabricated usage.
- The original Kafka investigator creates an evidence-backed issue. The newer
  recovery specialist has a distinct MR and approval flow. These are separate
  patterns, not proof that every historical component forms one deployed system.
- The application-owned specialist runs alongside the application, not inside
  its binary. The inspected recovery code uses a bounded Kimi classification
  call before native agent dispatch; the diagrams use the generic name
  **Model classifier**. The hourly top-N selector is deterministic, not an LLM.
- In the application recovery flow, a separate executor may merge only against
  the bound human approval and current reviewed head. In the SDLC rig, agents
  have no merge tool and a human merges the draft MR.
- The inspected SDLC rig routes model traffic through Agent Gateway and reaches
  GitLab MCP directly. Gateway-mediated MCP authorization and telemetry require
  a separate verified integration.
- OTel/LGTM is a reference topology. Received traces, real usage counters and
  application probes are the evidence, not animated markers or a green badge.

## Source map for the implementing agent

These repository files grounded the stories. They are implementation references,
not embedded workplace data or fresh execution evidence.

| Topic | Source in `kagent-public` |
| --- | --- |
| Secure service and exact runtime version | `work-agent-bundles/secure-kro-classic-kagent/README.md`, `IMAGES.md`, `MONDAY-COMPONENTS-AND-POLICIES.md` |
| Original Kafka evidence path | `work-agent-bundles/evidence-first-worker-triage/README.md` |
| Later deterministic hourly selection | `work-agent-bundles/hourly-topn-worker-triage/README.md` |
| Application-owned specialist | `work-agent-bundles/kyverno-application-specialist/README.md` |
| Classifier and admission | `work-agent-bundles/kyverno-application-specialist/live/CLASSIFIER.md`, `live/README.md` |
| Human approval and recovery | `work-agent-bundles/kyverno-application-specialist/live/DASHBOARD-FLOW.md`, `live/DESIGN.md` |
| SDLC roles and checkpoints | `work-agent-bundles/kind-kagent-sdlc-rig/README.md` |
| Observability and next identity iteration | `MONDAY-COMPONENTS-AND-POLICIES.md`, `NEXT-STEPS.md` |

Official Gateway references are included as plain URLs in the clickable policy
and token-usage details. Exact available fields must match the installed CRD.
The native skill excerpt is abbreviated and uses synthetic values; it is not a
replacement for the complete runnable bundle templates.

Validation is recorded in [the presentation-series check receipt](evidence/presentation-series-validation-2026-11-05.json). It covers HTML/browser/print behaviour, not a new live infrastructure rehearsal.

The existing [mock IDP](presentation.html#configure) accepts the form or its exported customer YAML. **Send simulation** illustrates controller/KRO assembly and Golden checks, then returns an example protected API with its JWT caller contract. Applications and optional VirtualServices use that authenticated Gateway route. Location and requested IAM/Entra identity remain planned onboarding metadata outside the current schema. No cluster or model calls run in the page.

The current Journey order is cover, comparison, lifecycle/API handoff, resource purposes, hardening, tools, skills, Gateway and observability. The no-code cover uses an agent-and-capability constellation, adapted from the HyperFrames hub blueprint in the deck's existing SVG/WAAPI engine. Its paths loop with a three-second pause by default; select Off to stop automatic replay. Reduced-motion and print remain static.

## Work bundle

Open `START-HERE.html` after extracting the complete folder. No server or install is needed. All primary pages use the inline `demo-theme.css` palette. Re-run `prepare_demo_bundle.py` after regenerating the mock IDP or resource sheet. The `references/` snapshots are offline support material, and external upstream links are optional online reading.

## SRE Lens

Open `sre-lens.html`. The first slide selects Kubernetes/GitLab for a workload incident, Data for a data question, SNOW/KB for incident guidance, KB alone for a knowledge question, or all five for a cross-system question. A dedicated sheet shows ServiceNow incident reads and KB vector retrieval, including the article indexing flow. Later slides show evidence synthesis with missing/denied-source cases and consumption through the DICE API. These are synthetic routing examples. The older native A2A YAML uses Grafana/data/Kubernetes references and does not install every integration shown by the product illustration. Rebuild with `python3 build_sre_lens.py`, then `python3 prepare_demo_bundle.py`.

## Live onboarding frontend

[Live onboarding](live-onboarding.html) is separate from the synthetic slide flows. Launch `python3 live_demo.py --context {{APPROVED_DEMO_CONTEXT}}` and open its loopback URL. It supports create, connect-existing, current-instance Golden/access checks, API handoff, evidence-backed chat and UID-guarded owner deletion. See [LIVE-ONBOARDING.md](LIVE-ONBOARDING.md) for scope, prerequisites and the current validation boundary.
