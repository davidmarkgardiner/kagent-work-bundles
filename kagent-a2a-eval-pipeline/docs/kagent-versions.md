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

## kagent 0.8 to 0.9 (the work cluster, before 1.0)

Read from the kagent 0.9.12 source, **not yet run on a 0.9 cluster**: 0.9 serves the same shapes as 0.7.x. The Agent API is `kagent.dev/v1alpha2` (the CRD also carries a v1alpha1 that is served but not stored); there is no `harnessRef` or `templateRef`; A2A is at `/api/a2a/<ns>/<agent>/` with `message/send`. So the 0.7.x forms in this bundle are the ones to use on 0.9: `--protocol 0.7`, the `type: Agent` evaluator tool for Warden, and the `v1alpha2` Lookout manifests (validated offline against the 0.9.12 CRD schemas). The 0.9 CRDs also include `agentharnesses` and `sandboxagents`, which are the Substrate-era pieces; they do not change the Agent shape. The live demo kit now has a 0.9 path too (25 Nov 2026, offline only):

- Set `KAGENT_API=0.9` in `demo/demo.env` and `A2A_BASE` to the 0.x path (for example `http://127.0.0.1:18083/api/a2a/kagent`). Every scene then reads agents as `agents.kagent.dev` (`spec.declarative.modelConfig`) and calls them with `message/send`; Lookout follows unless `LOOKOUT_KAGENT_API` is set.
- Deploy `demo/lab/v1alpha2/*.yaml` instead of `demo/lab/*.yaml`. They are generated from the 1.x files by `demo/lab/to_v1alpha2.py` (same agents, prompts and tools; no Harness), and a test fails if they are stale or do not fit the 0.9.12 CRD schemas (`tests/fixtures/kagent-0.9.12-v1alpha2-schemas.json`).
- The `sentinel` scene uses the bundle's v1alpha2 Sentinel worker, renamed `demo-sentinel`, and the evaluator Agent the contract names (`completion-evaluator-agent`). That Agent is created only if missing, never overwritten, because it may already exist at work. On 0.x the worker calls it as a tool and can retry after a FAIL (up to `maxAttempts`).
- `guard/remediate.py` already handles both Agent shapes; Warden, Guard detection and the gateway steps do not depend on the kagent version.

Proven offline: the generated manifests against the 0.9.12 schemas, the 0.x A2A call over HTTP against a recorded 0.x run, and Warden passing a recorded 0.x Sentinel run against the demo worker. **Not run on a 0.9 cluster.** The work agent proves it there (`WORK-AGENT-PROMPT.md`, step 15b). Capture one real receipt on the cluster before trusting any of this, as above.

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
