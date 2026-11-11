# Prepare David's workplace recording

Prepare one complete terminal-first DICE demonstration that David can record through Teams. Give him a resolved runbook, words to read aloud, copyable commands, working slides, and actual receiving-system receipts. Use the public package as a starting point and preserve existing workplace naming and controls.

## Inspect before changing

1. Read this bundle and the target repository's instructions. Discover the selected Kubernetes context, installed KRO/kagent/agentgateway/Flux versions and CRD schemas, existing agent profiles, GitOps source and Kustomization, protected A2A route, approved model, native skill source, MCP binding, and observability routes.
   Read `architecture/SCD.md` and `architecture/ADR-0001.md`. Keep target design, approved implementation decisions and observed receiving-system behavior distinct. Resolve the API exposure profile, caller/delegated flow, agent credential adapter, registry enforcement and evaluation ownership with the platform's existing review process. The proposed ADR itself grants no tenant or cluster-change authority.
2. Inspect the current owner contract. Record the owner resource, the generated Agent name, workload name, graph name, caller route, policy objects, and verification job separately. Do not assume they share a name.
3. Confirm a compatible native runtime supports the selected skill, reference reads, and read-only MCP operation. A model-only classic graph with `skills` and `tools` bounded to empty lists cannot demonstrate those capabilities. Use an already approved compatible profile, or prepare the smallest platform change for the normal review flow. Do not widen an owner schema, role, network policy, or tool allowlist to force the demo through.
4. Preserve existing controller, model, identity, MCP, Gateway, storage, images and telemetry configuration. Do not copy home-lab resource names, the recording agent's 1m CPU request, direct-apply method, synthetic record, or permissive namespace networking into the workplace.

## Prepare the recording assets

1. Put a resolved `recording.env`, `expected-calls.json`, tool prompt, approved query sheet, action scripts and private receipts outside the public checkout. Set file permissions before recording. Resolve the base variables in `config/demo.env.example` and the selected scenes in `config/recording-actions.env.example`. Remove optional unused variables and sections from the private runbook.
2. Copy one existing valid owner request into a dedicated approved demo slot in the private GitOps repository. Select only approved skill/catalog/profile inputs accepted by the installed graph. Keep the caller and agent-to-MCP policies in the appropriate platform GitOps path. Use the existing pipeline, review and delivery process.
3. Verify the skill's immutable GitLab revision or published artifact digest and the runtime's effective mount. Keep GitLab credentials out of the owner request and screen. If the platform publishes reviewed ConfigMaps or OCI content, explain that release path rather than claiming the runtime performs a GitLab clone.
4. Choose one bounded read-only MCP operation with safe display data. Put its exact arguments in the prompt and the same object in the expected call contract. The prompt is not an adapter-enforced result limit. Confirm the adapter's limits independently. Include two approved document reads only if the runtime exposes that native tool.
5. Resolve the caller's exact HTTPS A2A invoke URL and credential acquisition method. Prepare a short-lived caller token using the existing approved process. Store it privately with mode 0600. The bundle deliberately does not mint identities, assign roles, or hardcode an Entra acquisition flow.
6. Fill Grafana data-source names, actual label names, observed metric names and a rehearsed task-to-trace query. Preserve existing Alloy/collector exporters. Do not install a replacement dashboard or collector just for the recording.
7. Copy the slides intact. Open `slides/index.html` and choose the lifecycle deck plus the relevant existing architecture/security sheets. Keep explanatory animation distinct from live terminal/browser evidence.
8. Add the SCD/ADR and three architecture views to the private meeting pack. Map the approved identities/audiences and actual ingress enforcement points without copying tokens. Record the exact release evaluation gate and runtime assessment path beside the OTel/LGTM observations. Do not mark a registry entry or administrative identity object as authorization proof.
9. Resolve and rehearse the actual deployment action and later scoped policy promotion action using the existing approved delivery process. Keep the policy revision inactive at the baseline. Prefer a dedicated demo route that removes an existing approved test caller while retaining the main caller. Preserve shared production policies. Inspect installed schemas before preparing the diff; do not paste guessed policy YAML from another version.
10. Supply real action/readback scripts for each selected hook, with their literal contents and expected outcome in the private guide. No stubs, fake success scripts, unresolved placeholders or TODOs. The before/after probes use a rehearsed non-inference endpoint, make no model/tool invocation, assert the native receiving-endpoint decision and identify its mechanism. Retain native policy correlation and backend execution deltas when claiming denial before execution. Do not silently retry. Map compiled route/filter configuration to the policy in the actual Gateway version; an external-controller UI may not list Kubernetes policy objects. Use a safe effective-config projection, never credentials from a full configuration dump.
11. Keep the original video, editable project, complete slide library, guide and architecture folder together. Use `START-HERE.html`; the original MP4 needs no new synthesis or render. Preserve historical labels. Inspect all screens for private data before the workplace recording.

Include the existing agent-evaluation runner's literal invocation/readback commands and its native version-bound verdict in the resolved private sheet. The bundle's helper tests validate the caller and receipt filters, not the deployed agent's task quality or policy enforcement. If an evaluation service or registry integration is absent, record it as a target-design gap and prepare its scoped change through the normal review flow.

## Rehearse one request path

Follow `RECORDING-WALKTHROUGH.md` from start to finish. First observe the approved commit, Flux revision, owner UID, current-generation Agent readiness, rollout, route status and endpoint. Run one semantic PONG, one combined skill/document/MCP request before the scoped policy change and one after. Retain raw tasks and run the native call verifier and backend readback for both. This is three agent invocations; provider model calls and existing evaluation/Golden jobs can add traffic. Record the approved rehearsal budget. Call `ask_agent` directly, without a pipeline, so its exported receipt/answer variables remain in the parent shell. Closing re-displays the cached answer and does not invoke the agent again.

Correlate the exact native task or context ID to the observed trace. The included OTel query recognises `gen_ai.task.id`, `a2a.task.id`, `gen_ai.conversation.id`, and `kagent.session.id`. Adapt only to observed exporter fields. Do not pick the newest trace by time. If the caller receives no tool history, use the runtime's approved native audit export with its original call IDs. Do not synthesize a history from answer text.

For MCP completion, retain backend/server execution evidence and an independent read-back where applicable. If backend and client trace IDs differ, record the shared execution ID and the limitation. Keep missing telemetry, null cost and explicit error spans visible. A client span alone proves an attempt.

Test identity only through the intended receiving endpoint. Distinguish caller-to-agent from agent-to-MCP. Use existing approved identities and test permissions. Allowed and denied decisions need native policy receipts and, for denial-before-execution claims, no backend execution delta. A 401 naming API-key failure is not an Entra test. Operator impersonation/RBAC checks are configuration evidence, not an agent identity exchange. Never use the observer's internal invoke endpoint as a front-door bypass.

If any request returns quota exhaustion, failed native state, missing expected calls, or an unavailable telemetry match, stop that sequence and diagnose before a separately authorised new invocation. Do not silently retry or switch models, credentials or security controls. Do not use apply/delete tools or perform a real incident investigation during this recording.

## Return a usable handoff

Return these private workplace artifacts to David:

- One private `RECORD-ME.md`, fully resolved from the primary walkthrough, with exact URLs, repo paths, filenames, actual copy/paste commands, action script contents, expected output, spoken words and screen order. Include literal GitOps revision and ownership/attachment checks plus actual Grafana data-source names, queries, time ranges and click paths. Resolve every placeholder; do not leave the generic public hooks as David's final script.
- The private `recording.env`, reviewed action/probe/readback scripts, token-acquisition instructions and optional approved policy rollback. Keep credentials off screen.
- The GitOps diff/MR and observed delivered revision, owner UID, generated object mapping and route decisions.
- Native task/context IDs, exact expected call matches, MCP completion evidence, trace IDs and source queries.
- The filled rehearsal record with each step PASS, FAIL, UNKNOWN, or NOT RUN, its timestamp, and proof source.
- A note naming retained demo resources and the exact GitOps rollback/removal process. Do not run cleanup or delete shared resources merely to finish this preparation.

Keep private values and receipts inside the workplace. Commit only sanitized adaptations that the target repository permits. Do not send messages, publish recordings, or install additional controllers as part of this preparation.
