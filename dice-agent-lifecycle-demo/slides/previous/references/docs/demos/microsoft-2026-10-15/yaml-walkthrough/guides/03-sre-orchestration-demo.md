# Optional SRE chatbot demonstration

Use [04-a2a-orchestrator.yaml](../04-a2a-orchestrator.yaml) to explain the orchestration Agent. It selects named Grafana, data/compliance and Kubernetes specialists and combines evidence into one response. The second Agent object illustrates the destination's namespace opt-in; it is a minimal example, with its actual tool integration supplied separately.

## Show the architecture without a live dependency

1. Open [file 04](../04-a2a-orchestrator.yaml) and explain the orchestration Agent.
2. Point at each `type: Agent` reference and the destination namespace.
3. Point at the destination `allowedNamespaces` selector and explain that the labelled source namespace must be platform-controlled.
4. Explain that the gateway's incoming A2A policy and each specialist's tool/resource grants remain separate checks. A native Agent-as-tool reference does not prove that every delegation traverses the gateway.

## Prompt for a separately rehearsed live environment

> Investigate the reported latency in {{APPROVED_NAMESPACE}}/{{APPROVED_WORKLOAD}}. Ask the permitted Grafana specialist for application metrics, Kubernetes specialist for runtime health, and data/incident specialist for relevant approved context. Return one cited timeline, distinguish observations from hypotheses, and propose a next action. Do not change resources or incidents.

Expected evidence: the chatbot's response contains specialist results, source references and a shared investigation summary. Retain the actual delegation/tool receipts; a plausible response alone is not proof of fan-out.

If using the existing repository helper in an explicitly selected environment, its interface can be inspected offline with:

```sh
scripts/kagent-a2a-invoke.sh --help
```

The helper's direct controller port-forward is useful runtime proof but does not demonstrate gateway/Entra enforcement. For that claim, use the named gateway route with a correctly acquired application access token and separately verify the negative cases. Never show credentials or private identifiers while screen sharing.

No agent was invoked while packaging this walkthrough.
