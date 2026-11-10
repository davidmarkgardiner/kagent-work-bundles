# Demo 1: Onboard an agent and inspect what the controllers create

Allow 10 to 15 minutes. The audience sees bounded agent intent become running resources and a protected API.

## Prepare the slot

Complete the [shared setup](TERMINAL-COMMANDS.md). Use the dedicated `classic-agents/demo` slot. The create action needs an empty slot and approval for this demo deployment. For an occupied slot, use `connect` and describe the existing deployment.

In terminal A, inspect the example intent and watch actual resources.

```sh
cat "$CLASSIC_BUNDLE/examples/agent-demo.yaml"
cat "$CLASSIC_BUNDLE/examples/onboarding-payload.json"
python3 "$CLASSIC_BUNDLE/demo.py" --context "$DEMO_CONTEXT" watch
```

Say, "The owner supplies intent. KRO reconciles the graph, kagent runs the agent, and the configured gateway routes control access."

## Submit one reviewed request

In terminal B, open the protected client using the shared setup. At `dice>`, inspect the platform.

```text
platform
```

For an approved empty slot, submit one privately reviewed payload. It must select the installed approved model and match the displayed profile.

```text
deploy "{{PRIVATE_REVIEWED_PAYLOAD_JSON}}"
```

Alternatively, enter `connect` for an existing owner. Do not run both starting actions. ADO can remain the application team's source repository. This direct create is the dedicated demonstration route. Permanent deployments use the platform's reviewed delivery process.

Inspect progress one command at a time.

```text
status
```

Expect an owner UID, named generated resources, and actual readiness stages. Poll `status` until the first four stages pass. The Golden Job performs its own real model check. If it fails, stop.

```text
verify
```

Expect verification bound to this owner's UID, caller rejection results, one authenticated PONG, and an API endpoint. A Ready Pod alone is not this acceptance result.

## Inspect the generated configuration

Stop terminal A's watcher with Ctrl-C. Run these commands individually.

```sh
python3 "$CLASSIC_BUNDLE/demo.py" --context "$DEMO_CONTEXT" show instance
python3 "$CLASSIC_BUNDLE/demo.py" --context "$DEMO_CONTEXT" show agent
python3 "$CLASSIC_BUNDLE/demo.py" --context "$DEMO_CONTEXT" show deployment
python3 "$CLASSIC_BUNDLE/demo.py" --context "$DEMO_CONTEXT" show callerRoute
python3 "$CLASSIC_BUNDLE/demo.py" --context "$DEMO_CONTEXT" show callerPolicy
kubectl --context "$DEMO_CONTEXT" -n classic-agents logs job/demo-golden --tail=1
```

Show the declared model and tool selection, Pod security context, route target, caller policy, and verification receipt. Distinguish the small owner request from platform-owned resource definitions.

At `dice>`, make one short request if a readable answer is useful.

```text
ask Describe the supplied platform facts in three short bullets. Distinguish configured controls from checks we have observed. Do not call tools.
```

Use the deployed objects and verification output as the evidence. The model's description of itself is explanatory text.

## Close or show lifecycle cleanup

Enter `quit` to leave the agent running for the next demo. Existing immutable intent fields need an approved migration or controlled recreate for changes.

If deleting this demo instance is explicitly in scope, enter `status`, then `delete demo`. Require "Teardown complete for captured UIDs". Use `demo.py show model` and `kubectl get rgd classic-secure-agent` to confirm shared resources remain. Confirm the installed shared Gateway separately. Do not delete the namespace or shared controllers.

This demo proves onboarding and the tested model and caller path. Continue with [demo 3](03-FOLLOW-A-TOOL-CALL.md) for actual MCP execution evidence.
