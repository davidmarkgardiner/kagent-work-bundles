# Read-aloud talk track

Use this beside PRESENTER-WALKTHROUGH.md. Show and verify each observation before reading its corresponding result. The workplace agent resolves the exact screen and commands in the private rehearsal copy.

For the design discussion, use [the architecture talk track](architecture/PRESENTER-NOTES.md) with the diagram viewer.

## 1. Explain the journey

DICE gives a team a repeatable way to declare an agent and consume its API. I will follow one agent from its reviewed definition in Git, through deployment, into a real request. We will inspect the skill it loads, the MCP operation it invokes, and the evidence left in our observability systems.

## 2. Show reviewed intent and Flux

The team submits an agent request using the platform's accepted contract. That request chooses approved capabilities and instructions. The platform's routes and policies are versioned in Git too. Flux reconciles the reviewed revision. KRO then composes the resources defined by the installed graph.

## 3. Watch the agent come online

This is the agent owner. These are the generated Agent and runtime workload. Accepted means the controller has accepted the request. Ready and the completed rollout show that this generation of the runtime is available. We also inspect the caller route and its policy attachment before using the API.

## 4. Talk to the protected API

The caller uses the protected API that an application would consume. This function makes one A2A request. It does not use the UI or fall back to an internal controller endpoint. The returned native task and the exact PONG check establish this caller and model path.

## 5. Show the skill source and release

Skills are versioned guidance. Here is the reviewed source and the release consumed by this runtime. The platform may fetch that revision directly or publish it as an approved artifact. This runtime's effective mount and release record show which content it can read. Instructions and tool permission are separate responsibilities.

## 6. Invoke the skill and MCP operation

This request loads the selected skill, reads the approved references, and invokes one selected read-only MCP operation. The answer is useful to the caller. These native call IDs and returned results are the evidence that the capabilities were used. The tool service runs in Kubernetes under its own identity and permissions.

## 7. Inspect the gateway and security

The gateway is the policy and routing boundary for the paths configured through it. We inspect the actual receiving route and the policies attached to it. The caller's access to the agent and the agent's access to an MCP API are separate checks. Entra identifies the principal; the destination's audience and permissions determine whether that request is allowed.

## 8. Follow the request in Grafana and OTel

This is the same request we made from the terminal. The trace shows the observed runtime, model, skill and MCP operations. Grafana adds the relevant logs and metrics. These token figures belong to the selected runtime evidence. A metric over five minutes describes that time window, so I do not present it as the cost of this one request.

## 9. Explain registry and identity ownership

The registry records ownership, approved agent, skill and MCP versions, intended connections and acceptance evidence. Registration supports governance. The actual identity grants, gateway decisions and Kubernetes controls establish the permitted access paths. We keep caller-to-agent and agent-to-MCP evidence separate.

## 10. Close with the API and receipts

The team declares an approved agent through GitOps, receives an API, and uses its selected skills and tools. We can inspect the deployed revision, native task, tool results and observability records. That is the operational journey DICE makes repeatable.
