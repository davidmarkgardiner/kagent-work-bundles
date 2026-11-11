# Meeting runbook

Open `index.html` in Chrome. All decks and the YAML reader work from disk.

## Running order

Allow about 40–45 minutes for the YAML and decks, plus discussion and an optional SRE Lens demonstration. Short version: spend ten minutes on YAML and use the first and last slide of each topic deck.

1. YAML, 10–15 minutes. Walk 01–04, then 05–09 and 11–13. Keep 10 and 14–20 for detailed questions. Files 02/03 patch 01. File 04 is separate. File 20 is a local scorer case. This directory is not a platform apply target.
2. Kafka triage, 3 minutes. Explain collection, normalization, transport, workflow and investigation. Use the scheduling-incident example.
3. Data agents, 3 minutes. Walk question, typed query, bounded result, reasoning and recommendation. Results feed context, not model training.
4. Knowledge, 3 minutes. Explain article chunks, embeddings, retrieval and citations. Distinguish vector search from the Vector telemetry processor. Note standalone querydoc compatibility.
5. GitLab, 3 minutes. Show issue, child, branch, exact-head CI, draft MR and independent review. Keep rig acceptance separate from the rollback POC's human merge gate.
6. Kubernetes fleet, 3 minutes. Explain target scope, tool allow-list, backend arguments and RBAC. Separate read-only triage from approved execution.
7. SRE Lens, 3 minutes. One entry agent selects specialists, combines evidence and answers the SRE. ServiceNow/GitLab routing comes from David's described application scope, not the three specialist bindings in example YAML 04.
8. Durable concept, 5 minutes. Describe event, classifier, admission, durable actor and available incident context. Distinguish standalone SQLite Pi, native Substrate, live-model rollback and portable scripted classifier.
9. Optional live Lens application. Use the read-only question below and inspect actual handoffs.
10. Agentgateway dashboard, about 4 minutes. Use deck 08 beside routes, effective policy, identities and telemetry.

## Opening words

"I will start with the YAML so we can see how an agent gets its instructions, skills, tools and permissions. Then I will show how we use those pieces for triage, data access, knowledge retrieval and delivery. I will finish with the SRE experience and the application-embedded agent concept."

## Live Lens prompt

"Investigate the reported latency in the approved namespace and workload. Ask the permitted telemetry, Kubernetes and incident specialists for relevant evidence. Return one cited timeline, distinguish observations from hypotheses, and propose a next action. Do not change resources or incidents."

The actual namespace and workload come from the prepared environment. Show specialist/task receipts and the cited answer. A plausible response alone does not prove fan-out. If the service is unavailable, return to deck 06 and YAML 04.

## Gateway dashboard checklist

Locate the actual routes and backends. Inspect policy acceptance/attachments and effective configuration. Show separate caller-to-agent and child-agent-to-MCP audiences/roles. Show the MCP allow-list and destination controls. Explain local model limits and selected content guards. Use actual request/tool/token series and correlated traces where present. Missing telemetry stays missing evidence. A direct controller port-forward is a different path from gateway authentication.

## Rehearsal preparation

Enter the actual Lens and dashboard URLs on the launch page. Use prepared, approved application sessions. Confirm current agent/tool inventory and expected read-only behavior. Confirm the dashboard can show the chosen route and policy. Do not start a fault, classifier, model task, merge or deployment merely to prepare this static pack. The app-embedded POC remains a conceptual discussion unless a separate demonstration is specifically arranged.

The slide reader uses arrow keys, N for notes and F for fullscreen. Print produces one slide per page. Decks and copied YAML need no server. Original-source links need the local sibling checkouts. No live application URL or current runtime readiness was supplied or verified.

## Detailed speaker notes

### Triage with Kafka

**1. The incident path.** Explain each system's responsibility. Kafka transports the event. Argo sequences the work. The agent investigates with selected tools. The ticket is the handoff to the operator. This describes the retained evidence-first lab path, not a fresh workplace run.

Sources: [Retained scheduling-incident evidence](sources.html#triage-proof), [Connected triage presenter guide](sources.html#triage-guide)

**2. Metric alerts and direct evidence.** The repository's dual-source document is a routing design. Its proposed topic names are conventions, not a claim about deployed Confluent topics. The retained incident proof uses a specific earlier path. Vector here is the telemetry processor. Vector search in the knowledge deck is a different mechanism.

Sources: [Dual-source Kafka routing design](sources.html#kafka-design)

**3. Replay and duplicate handling.** These are the target routing controls. Kafka delivery alone does not make downstream effects exactly once. Stable workload identity matters because pod names change. Avoid claiming that all proposed controls are installed in the current workplace environment.

Sources: [Dual-source Kafka routing design](sources.html#kafka-design)

**4. A scheduling failure example.** Retained lab example: GitLab issue #453. The phase-5 report also records eight concurrent incidents with a processing limit of five. Do not claim a measured number of minutes saved. Transition: the agent can supplement telemetry with approved business and ownership data.

Sources: [Retained scheduling-incident evidence](sources.html#triage-proof)

### Data agents and decisions

**1. The data query loop.** Tool results enter the agent's context for reasoning. This feedback does not retrain the model. A recommendation remains distinct from permission to execute a change.

Sources: [Bounded PostgreSQL MCP reference bundle](sources.html#postgres), [Actual typed PostgreSQL operations](sources.html#postgres-tools)

**2. A concrete query contract.** These are actual names in adapter/server.py. The reference data product is a synthetic Kubernetes namespace inventory. Do not imply it queries trades or business databases today. The workplace adapter already exists and should receive only a reviewed incremental change.

Sources: [Actual typed PostgreSQL operations](sources.html#postgres-tools)

**3. Limits before model context.** These defaults belong to the reference adapter. The compiled ceilings differ. Do not silently page until the agent has reconstructed an export. The September synthetic test returned 50 of 5,000 matching rows. That proves bounded transport, not measured workplace token savings. Denodo is a separate JDBC adapter with its own identity and driver prerequisites.

Sources: [Bounded PostgreSQL MCP reference bundle](sources.html#postgres), [Data and evaluation presenter guide](sources.html#data-guide)

**4. Evidence in the final answer.** Example narrative, not a captured result: inventory identifies the owning team, while live metrics show when errors began. The agent uses both to propose who should investigate and what to check. Transition: operational data says what is happening, while knowledge retrieval supplies the documented procedure.

Sources: [Bounded PostgreSQL MCP reference bundle](sources.html#postgres), [Data and evaluation presenter guide](sources.html#data-guide)

### Knowledge articles and vector search

**1. Articles become a searchable index.** The repo uses docs/platform-kb, doc2vec and querydoc. Upstream supports SQLite with sqlite-vec and Qdrant. This POC uses the SQLite database path. Here vector means semantic retrieval. It is separate from the Vector telemetry processor in the Kafka deck.

Sources: [Platform knowledge-base POC](sources.html#kb), [Official doc2vec repository](sources.html#doc2vec-upstream)

**2. A question becomes a cited answer.** The local prompt uses productName platform-kb, version current and dbName platform-kb.db. A similarity match does not prove that a runbook applies to the current cluster or software version. Check the article's scope before recommending an action.

Sources: [Platform knowledge-base POC](sources.html#kb)

**3. Article maintenance and access.** The POC refuses to publish a DB after embedding errors and keeps its indexer suspended by default. Its knowledge agent has read-only instructions. Per-document authorization is a production requirement to assess, not a feature proved by this POC.

Sources: [Platform knowledge-base POC](sources.html#kb)

**4. The deployed version matters.** Current release notes explicitly describe the removal. Existing agents that relied on the bundled query_documentation tool need migration or separate wiring. Do not present the integration as automatically available in every kagent installation.

Sources: [Platform knowledge-base POC](sources.html#kb), [Official kagent release notes, querydoc removal in v0.10](sources.html#kagent-release-notes)

### GitLab and the SDLC workflow

**1. An issue becomes an engineering task.** The recorded SDLC rig polls a sandbox board and advances one parent issue by one checkpoint per run. It verifies artifacts before changing labels. The agent's statement that work is complete is not enough.

Sources: [GitLab SDLC rig and checkpoints](sources.html#sdlc)

**2. Tests and review follow the commit.** The SDLC rig exposes named issue, branch, file, pipeline, draft-MR and review-note operations through a scoped GitLab MCP. It exposes no merge, delete or arbitrary API tool. PM acceptance leaves a draft MR for a human.

Sources: [GitLab SDLC rig and checkpoints](sources.html#sdlc)

**3. Merge and rollout authority.** Keep these two demonstrations separate. The SDLC rig does not merge. The durable GitLab rollback POC has a native merge_mr approval and independent decision ledger. A green pipeline or merged MR alone does not prove application recovery.

Sources: [GitLab SDLC rig and checkpoints](sources.html#sdlc), [Completed native GitLab rollback receipt, 14 October](sources.html#rollback-proof)

**4. Recorded delivery examples.** These are historical lab receipts. The rollback completed proof passed at 12:11 UTC on 14 October. That completion supersedes the earlier WAITING table retained in the same file. Neither example proves current workplace readiness.

Sources: [Existing GitLab SDLC presentation](sources.html#sdlc-presentation), [Completed native GitLab rollback receipt, 14 October](sources.html#rollback-proof)

### Kubernetes fleet triage and remediation

**1. The fleet connection path.** This is the platform connection pattern. An allowed tool name does not validate a cluster or namespace argument. Runtime enforcement must validate those arguments and use credentials scoped to the target. AKS-MCP is one bridge in this repository, not blanket permission to every fleet cluster.

Sources: [Kubernetes and AKS tool bridge](sources.html#aks-mcp), [03-agent-tools.patch.yaml](sources.html#yaml-03), [Gateway identity, control and telemetry notes](sources.html#gateway-guide)

**2. Read-only triage.** Show the selected tools in YAML 03 and the read-only triage instructions. The retained scheduling example illustrates the investigation. Keep any apply/delete or resource-changing tool out of the read-only agent's binding.

Sources: [03-agent-tools.patch.yaml](sources.html#yaml-03), [Connected triage presenter guide](sources.html#triage-guide)

**3. A controlled remediation path.** The repo working rules separate the conversational front door from resource-changing workflow permissions. This deck explains the pattern. It does not authorize a change or imply that every fleet cluster already has this remediation integration.

Sources: [Platform execution and permission rules](sources.html#platform-rules), [Completed native GitLab rollback receipt, 14 October](sources.html#rollback-proof)

**4. What the SRE can inspect.** Transition to SRE Lens: operators should not need to choose every specialist manually. Lens can provide a single conversation while the underlying permissions stay distinct.

Sources: [Gateway identity, control and telemetry notes](sources.html#gateway-guide), [Connected triage presenter guide](sources.html#triage-guide)

### SRE Lens orchestration

**1. One conversation for the SRE.** SRE Lens is the application name supplied by David. The public YAML calls its example orchestration Agent sre-chat. The example names Grafana, data/compliance and Kubernetes agents. ServiceNow and GitLab are part of David's described Lens scope, but this YAML does not install those integrations.

Sources: [David's meeting brief, 15 October 2026](sources.html#lens-brief), [04-a2a-orchestrator.yaml](sources.html#yaml-04)

**2. Routing by the question.** This slide describes the intended routing experience from David's briefing. Verify the current Lens agent inventory before treating every route as deployed. The orchestrator can ask more than one specialist when the question needs correlated evidence.

Sources: [David's meeting brief, 15 October 2026](sources.html#lens-brief), [04-a2a-orchestrator.yaml](sources.html#yaml-04)

**3. Delegation keeps each permission boundary.** YAML 04 illustrates native Agent-as-tool delegation and destination allowedNamespaces. That does not establish that every native delegation traverses agentgateway. YAML 12 and 13 describe two separate gateway identity hops. Never equate namespace opt-in with Entra authorization.

Sources: [04-a2a-orchestrator.yaml](sources.html#yaml-04), [12-application-to-agent-policy.yaml](sources.html#yaml-12), [13-agent-to-mcp-policy.yaml](sources.html#yaml-13), [Gateway identity, control and telemetry notes](sources.html#gateway-guide)

**4. The optional Lens demonstration.** This is a read-only rehearsal prompt. Do not request resource or incident changes. A plausible answer without delegation receipts does not prove orchestration. If Lens is unavailable, use YAML 04 and this deck, then continue. The launch page holds a configurable link to the actual Lens URL.

Sources: [Read-only orchestration demo guide](sources.html#lens-demo)

### Application events and durable agents

**1. The application-embedded concept.** Logs and checkout failures exist in the POC. Trades and database events are proposed future sources. Choose ingestion and data classification for each source separately. A newly created agent has configured instructions and supplied context, not an incident history it never observed.

Sources: [David's conceptual application-embedded agent brief](sources.html#future-brief), [Standalone application-embedded Durable Pi demo](sources.html#proactive), [Native kagent and Substrate bridge](sources.html#native-bridge)

**2. Substrate and incident context.** Current 1.x docs distinguish full pause snapshots from data snapshots with cold boot on resume. Avoid promising restoration of all process memory on every path. Skills and memory are distinct. The native demo templates currently declare no skills and use system instructions. The standalone Pi application uses SQLite and is separate from the native kagent/Substrate integration.

Sources: [Official Substrate suspend and resume documentation](sources.html#substrate-upstream), [Native agent workspace and durability limits](sources.html#agent-workspace), [Standalone application-embedded Durable Pi demo](sources.html#proactive), [Native kagent and Substrate bridge](sources.html#native-bridge)

**3. The implemented event-to-agent loop.** The original native comparison uses a scripted agent route and a protected synthetic fixture. The later GitLab rollback workspace uses a live model and real GitLab/Flux tools. Keep the two workspaces separate when demonstrating them. Actor records with saved snapshots exist in the retained native comparison.

Sources: [Native kagent and Substrate bridge](sources.html#native-bridge), [Completed native GitLab rollback receipt, 14 October](sources.html#rollback-proof)

**4. The GitLab rollback result.** Completed capture passed at 12:11 UTC on 14 October. The same evidence file preserves an older waiting-stage table. The completion paragraph supersedes it. This is image rollback through GitOps, not autonomous source-code repair or present workplace proof.

Sources: [Completed native GitLab rollback receipt, 14 October](sources.html#rollback-proof)

**5. The portable demonstration and next proof.** Portable package verification covers source/build checks, a native read-only connection canary and schema checks. It has not completed a new workplace rollback run. Snapshots alone do not prove exactly-once external effects or recovery from complete host loss. Transition to the optional Lens application and gateway dashboard.

Sources: [Portable native demonstration package](sources.html#portable), [Portable package verification and pending target proof](sources.html#portable-verification), [Portable scripted classifier implementation](sources.html#classifier), [Native agent workspace and durability limits](sources.html#agent-workspace)

### Agentgateway dashboard and policies

**1. The gateway demonstration.** Open the prepared dashboard using the launch page. Dashboard product and URL have not been supplied, so the checklist avoids invented navigation labels. Read deployed configuration only. A direct controller invocation does not demonstrate gateway identity enforcement.

Sources: [Gateway identity, control and telemetry notes](sources.html#gateway-guide), [08-http-routes.yaml](sources.html#yaml-08), [12-application-to-agent-policy.yaml](sources.html#yaml-12), [13-agent-to-mcp-policy.yaml](sources.html#yaml-13)

**2. Policy examples beside the dashboard.** The examples use version-dependent schemas. Local request/token limits apply per proxy and route, not a coordinated monetary spending cap. File 20 is local scorer input, not a Kubernetes resource. Network policy requires an enforcing CNI and consideration of additive policies.

Sources: [Gateway identity, control and telemetry notes](sources.html#gateway-guide), [14-mcp-network-boundary.yaml](sources.html#yaml-14), [15-model-traffic-limits.yaml](sources.html#yaml-15), [20-agent-evaluation-case.yaml](sources.html#yaml-20)

**3. Discussion after the demo.** Close with the concrete scope of the next pilot. Keep any environment changes as follow-up work. The meeting pack itself launches no classifier, model, incident, cluster change, merge or deployment.

Sources: [David's conceptual application-embedded agent brief](sources.html#future-brief), [Gateway identity, control and telemetry notes](sources.html#gateway-guide)
