# Three connected presentation chapters

Open `journey.html` first. All three decks work offline as standalone HTML files.
Keep them in the same folder to use the Journey / Triage / SDLC links in each
slide footer. `index.html` remains the earlier architecture deep dive;
`presentation.html` remains the actual YAML explorer with dated receipts.

| Chapter | Presentation | Main message |
| --- | --- | --- |
| 1 | [Secure agent journey](journey.html) | Compare an ordinary native Agent with the KRO security composition, then explain tool selection, native skills, Gateway policies, OTel/LGTM and the lifecycle. |
| 2 | [SRE triage and application recovery](triage.html) | Explain the original Kafka evidence path and the newer application-owned specialist, bounded classification, reviewable MR, human approval and measured recovery. |
| 3 | [Agent-assisted SDLC](sdlc.html) | Follow an approved task through PM, builder, tester and reviewer roles, artifact-backed checkpoints, bounded rework and human merge. |

Each chapter has six slides, clickable source/details, presenter notes and
landscape printing. All diagram states and examples are **illustrations**.
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
labelled region. Print exports all six slides in the selected chapter.

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
