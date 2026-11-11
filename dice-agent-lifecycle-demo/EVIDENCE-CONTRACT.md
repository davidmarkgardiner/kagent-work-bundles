# What each observation establishes

| Observation | Establishes | Additional evidence for the next claim |
| --- | --- | --- |
| Reviewed Git diff and commit | Intended release content | Flux applied that exact revision |
| Flux source Ready | Source was fetched | Kustomization revision and current successful conditions |
| Current owner and UID | Selected request exists | Generated ownership chain and current controller state |
| Current-generation Agent Accepted/Ready and rollout | Runtime is available | Protected caller can complete a semantic request |
| Protected HTTPS PONG and native completed task | Caller/model path worked | Native skill and MCP calls/results |
| Skill release/mount | Content is available | Native skill call with the selected name and returned result |
| Matching `read_file` call/result | A named reference was read | Exact approved source/release mapping |
| Matching native MCP call/result | Runtime made a call and received a result | Backend/server completion, bounded result and independent read-back |
| Client tool span | Client observed an attempt | Correlated server/handler completion evidence |
| Task/context-linked OTel trace | Those spans belong to the request | Instrumentation at every layer claimed in the path |
| Gateway route or policy object | Configuration exists | Attachment/status plus actual allowed and denied decisions |
| HTTP 401/403 | That endpoint rejected that request | Mechanism/principal/audience/permission evidence and no backend execution for a pre-execution denial claim |
| Entra identity/blueprint in the portal | Administrative object exists | Real token exchange and destination authorization |
| Kubernetes `auth can-i` | Evaluated RBAC permission for the specified subject | Actual agent identity, admission/network/application controls and receiving request evidence |
| Registry record | Ownership/version/governance metadata exists | Enforcement and acceptance receipts for its connections |

The native verifier accepts only expected names and exact argument objects with matching nonempty call IDs and returned-result IDs. It emits metadata, not tool bodies. **All expected calls returned** means the native history has those records and no explicit result error. It is not an assertion of independent backend success, complete tracing, network isolation or Entra authorization.

Missing history, ambiguous IDs, null status, missing spans, unavailable cost and untested controls remain UNKNOWN. A model's answer about its own capabilities is not a substitute for these receipts. Keep private native tasks and operational values outside the public checkout.
