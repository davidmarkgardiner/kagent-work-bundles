# kagent 0.7.x and 1.x differences

The bundle handles both. These are the differences found by running it live. Always capture one real receipt on your version.

| | kagent 0.7.x | kagent 1.x (A2A 1.0) |
|---|---|---|
| Agent API | `kagent.dev/v1alpha2` Agent | `api.kagent.dev/v1alpha3` AgentTemplate + Harness + Agent |
| A2A path | `/api/a2a/<ns>/<agent>/` (trailing slash required) | `/agents/<ns>/<agent>` |
| Method | `message/send` | `SendMessage`, with header `A2A-Version: 1.0` |
| Message | `role: user`, parts `{"kind":"text","text":...}` | `role: ROLE_USER`, parts `{"text":...}` |
| `contextId` | any unique string; **reuse across agents returns 403** | **do not send one**; it maps to a Substrate session and is rejected |
| Where tool calls are | `result.history[].parts` (`kagent_type`) | `result.task.artifacts[].parts` (`kagent.dev/a2a/part-type`) |
| Task state | `completed` | `TASK_STATE_COMPLETED` |
| Evaluator | `type: Agent` tool; call `kagent__NS__<agent>`, response `{"result": "<verdict JSON>"}` | `subAgent` binding; an ADK `transfer_to_agent` **handoff** |
| Retry on evaluator FAIL | worker can fix and call again (up to `maxAttempts`) | **not possible**: control does not return after the handoff, so a FAIL is final |
| Errors | HTTP 200 with `kagent_error_code` in history | JSON-RPC error bodies, also HTTP 200 |

## The 1.x worker and evaluator

```yaml
apiVersion: api.kagent.dev/v1alpha3
kind: Agent
spec:
  harnessRef: {name: <approved-harness>}
  template:
    inline:
      modelConfig: {name: <model-config>}
      systemPrompt: <see completion-gate/manifests/sentinel-investigator-agent.yaml>
      tools:
        - mcp:
            server: {kind: RemoteMCPServer, name: <read-only-tools>}
            tools: [k8s_get_resources, k8s_describe_resource, k8s_get_events, k8s_get_pod_logs]   # always list tools; the verifier treats an empty list as unrestricted
        - subAgent:
            name: completion-evaluator
            description: Independent evaluator
            templateRef: {name: completion-evaluator}   # an AgentTemplate with no tools
```

Set `evaluator.subAgent` in the contract so the verifier knows the handoff target.

## Substrate lab pitfalls seen on 1.x

- Agent calls refused with `KAGENT_SEND_NOT_ACCEPTED` for minutes meant the actor could not restore. Read the `ate-api-server` and `atelet` logs,
  not the controller. The causes seen: an unreachable local image registry for a skill volume, and a stale worker registration (restart the worker deployment).
- kind nodes that inherit a Docker resolver of `0.0.0.0` leave CoreDNS in a forwarding loop. Point CoreDNS and the node at a real resolver.
- Admission webhooks (Kyverno) that are down block every apply, including the RemoteMCPServer.
