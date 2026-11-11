# Present the agent lifecycle from the terminal

Allow 12 to 15 minutes, with time for questions. Keep this document on a second screen. The audience sees slides, a terminal, gateway, Grafana and OTel. No Kagent UI is required.

## Before Teams starts recording

Have the workplace agent complete [WORK-AGENT-PROMPT.md](WORK-AGENT-PROMPT.md) and [REHEARSAL-RECORD.md](REHEARSAL-RECORD.md). Load the resolved private environment and the `ask_agent` function. Rehearse the protected route and exact queries once before presenting. Do not repeat model calls just to populate a dashboard.

Open these windows in order: `slides/index.html`, the private GitOps diff, a terminal, the actual gateway UI, Grafana Explore, and the OTel observer. Close unrelated tabs, notifications and terminals containing credentials. Use a large terminal font and a short prompt. Keep token acquisition, secret-bearing files, full environment dumps and raw native receipts off screen.

In Teams, use your organisation's **Record and transcribe** or recording control after starting the meeting. Share the selected presentation screen or application. Exact controls depend on the Teams client and recording policy. Check that the recording captures the selected screen before starting the technical sequence. This bundle does not start a Teams recording or distribute it. The current controls are documented in [Microsoft's recording guide](https://support.microsoft.com/en-us/teams/meetings/start-stop-and-find-meeting-recordings-in-microsoft-teams).

## 1. Explain the journey

Show lifecycle slide 1. Read:

> DICE gives a team a repeatable way to declare an agent and consume its API. I will follow one agent from its reviewed definition in Git, through deployment, into a real request. We will inspect the skill it loads, the MCP operation it invokes, and the evidence left in our observability systems.

Show the source and security architecture sheets from the copied decks only if the audience needs the wider context. Their animated flows are explanations. The terminal and receiving-system receipts establish what ran.

For the design discussion, open [the architecture viewer](architecture/index.html). Its overview shows registry, GitLab skills, Kubernetes agents/MCPs, Gateway, model garden and LLMs, with evaluation beside OTel/LGTM. Its authentication sheet separates caller-to-agent from agent-to-MCP tokens. Its evaluation sheet shows release gates and runtime assessment. [The SCD](architecture/SCD.md) and [ADR](architecture/ADR-0001.md) explain the intended choices. Allow a further five minutes if presenting all three views.

## 2. Show reviewed intent and Flux

Show lifecycle slide 2, then the private GitOps diff. Use **Deployment** in [TERMINAL-COMMANDS.md](TERMINAL-COMMANDS.md).

Read:

> The team submits an agent request using the platform's accepted contract. That request chooses approved capabilities and instructions. The platform's routes and policies are versioned in Git too. Flux reconciles the reviewed revision. KRO then composes the resources defined by the installed graph.

Show the exact delivered source revision and the Flux Kustomization's last applied revision. Compare them with the approved commit. If the owner already existed, say so. If recording a fresh deployment, use the approved new demo request and let the normal Flux reconcile apply it. A manual Flux reconcile is optional only where the receiving workflow permits it.

Expected observation: the intended revision is applied, conditions are current, and the intended owner is present. Do not show a direct `kubectl apply` as proof of Flux delivery.

## 3. Watch the agent come online

Show lifecycle slide 3. Use **Agent online** in the command sheet. Keep the owner and generated runtime names visible.

Read:

> This is the agent owner. These are the generated Agent and runtime workload. Accepted means the controller has accepted the request. Ready and the completed rollout show that this generation of the runtime is available. We also inspect the caller route and its policy attachment before using the API.

Expected observation: Accepted and Ready refer to the current Agent generation, the Deployment rollout succeeds, and the exact route has the expected accepted references and policy. Readiness alone does not prove the model, skill, MCP or identity path.

## 4. Talk to the protected API

Show lifecycle slide 4. In the terminal run:

```sh
ask_agent 'Reply with exactly PONG. Do not call tools.' PONG
```

Read:

> The caller uses the protected API that an application would consume. This function makes one A2A request. It does not use the UI or fall back to an internal controller endpoint. The returned native task and the exact PONG check establish this caller and model path.

Expected observation: PONG, a completed native task ID, context ID and response digest. `DICE_LAST_RECEIPT` points to the private native response. A timeout or non-completed task stops the sequence. Do not resubmit a prompt as a polling mechanism.

## 5. Show the skill source and release

Show lifecycle slide 5. Open the approved GitLab skill revision, `SKILL.md`, and one reference file. Show the private capability sheet prepared by the workplace agent.

Read:

> Skills are versioned guidance. Here is the reviewed source and the release consumed by this runtime. The platform may fetch that revision directly or publish it as an approved artifact. This runtime's effective mount and release record show which content it can read. Instructions and tool permission are separate responsibilities.

Expected observation: an immutable source/release mapping and the actual mounted skill. Do not display Git credentials or claim a startup clone when the platform uses ConfigMaps or another publication mechanism.

## 6. Invoke the skill and MCP operation

Show lifecycle slide 6. Run the reviewed private prompt and verify the result from the native history.

```sh
ask_agent "$(cat "$DEMO_PROMPT_FILE")"
jq --slurpfile expected "$DEMO_EXPECTED_CALLS" \
  -f "$DICE_DEMO_BUNDLE/evidence/tool-calls.jq" "$DICE_LAST_RECEIPT"
```

Read:

> This request loads the selected skill, reads the approved references, and invokes one selected read-only MCP operation. The answer is useful to the caller. These native call IDs and returned results are the evidence that the capabilities were used. The tool service runs in Kubernetes under its own identity and permissions.

Show the MCP server's correlated completion record and bounded result or approved independent read-back. The workplace agent supplies the exact safe command in the resolved sheet. Do not print an entire log stream or private tool data.

Expected observation: the expected skill name, document paths and MCP arguments match native function calls exactly; each has one returned result. A client MCP span alone is an attempt. If server completion is unavailable, say which observations are available and mark backend completion UNKNOWN. Label synthetic records and documentation-only analysis accurately.

## 7. Inspect the gateway and security

Show lifecycle slide 7 and open the gateway URL from the private environment. Inspect the relevant route, selected backend, policy attachment and status. Do not use UI presence as enforcement proof.

Read:

> The gateway is the policy and routing boundary for the paths configured through it. We inspect the actual receiving route and the policies attached to it. The caller's access to the agent and the agent's access to an MCP API are separate checks. Entra identifies the principal; the destination's audience and permissions determine whether that request is allowed.

Use the already rehearsed existing identity test only if it is available. Show its native allowed/denied decisions and backend execution evidence. The generic bundle does not manufacture identity roles or grants. If only policy configuration is available, describe configuration and show the unchecked enforcement item in the rehearsal record.

## 8. Follow the request in Grafana and OTel

Show lifecycle slide 8. Use [OBSERVABILITY.md](OBSERVABILITY.md). Extract the exact task/context IDs from the combined request receipt, correlate them to the observed runtime trace, and use that trace ID in Grafana/Tempo.

Read:

> This is the same request we made from the terminal. The trace shows the observed runtime, model, skill and MCP operations. Grafana adds the relevant logs and metrics. These token figures belong to the selected runtime evidence. A metric over five minutes describes that time window, so I do not present it as the cost of this one request.

Show the waterfall and model/tool spans, token reports and errors. If a discovery request fails while the native task completes, explain both observations. If cost is null, say it is not reported. If a gateway or backend has no correlated span, keep that gap visible.

## 9. Explain registry and identity ownership

Show lifecycle slide 9. Open the existing Entra/registry screens only when they are approved for display and part of the rehearsed environment.

Read:

> The registry records ownership, approved agent, skill and MCP versions, intended connections and acceptance evidence. Registration supports governance. The actual identity grants, gateway decisions and Kubernetes controls establish the permitted access paths. We keep caller-to-agent and agent-to-MCP evidence separate.

A proposed registry is a design item. Existing Entra objects are administrative evidence. Neither substitutes for a real receiving-system token and permission test.

## 10. Close with the API and receipts

Show lifecycle slide 10.

Read:

> The team declares an approved agent through GitOps, receives an API, and uses its selected skills and tools. We can inspect the deployed revision, native task, tool results and observability records. That is the operational journey DICE makes repeatable.

Stop the Teams recording through the meeting's recording controls. Keep the demo resources available for questions unless the agreed runbook says to retire them. Retire through GitOps using the exact scope and pruning checks in the deployment guide. Do not remove shared platform services.
