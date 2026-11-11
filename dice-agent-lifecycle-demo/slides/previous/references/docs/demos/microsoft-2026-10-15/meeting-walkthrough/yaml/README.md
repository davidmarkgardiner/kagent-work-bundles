# Agent journey: YAML walkthrough

Click each numbered filename below and read the workflow explanations beside the actual YAML fields as presenter notes. This is the speaking order, not a platform deployment sequence. Environment values remain `{{PLACEHOLDER}}` values.

## Build the Agent and its capabilities

1. [Load the Agent](01-agent.yaml) — The declarative Agent is our starting point. Its prompt and ModelConfig define the basic runtime.

2. [Load skills](02-agent-skills.patch.yaml) — Extend that same Agent with reviewed skill files from a pinned Git commit.

3. [Attach tools](03-agent-tools.patch.yaml) — Connect the Agent to a RemoteMCPServer and list the read operations it can offer to the model.

4. [Attach agents with A2A](04-a2a-orchestrator.yaml) — The SRE chatbot delegates to named specialists. The destination Agent opts in to the caller namespace.

5. [Connect the model garden](05-model-garden.yaml) — ModelConfig points the Agent at the gateway model route.

6. [Authenticate the MCP connection](06-remote-mcp.yaml) — Use the gateway MCP URL and a privately supplied Entra access-token header.


## Connect and lock down the platform

7. [Connect the backend](07-mcp-backend.yaml) — Agentgateway connects to the named MCP service and protocol.

8. [Route requests](08-http-routes.yaml) — Bind MCP and named SRE-chat traffic to their destinations.

9. [Grant references](09-reference-grants.yaml) — The destination owner permits exact cross-namespace backend references.

10. [Trust Microsoft signing keys](10-entra-jwks.yaml) — Fetch Entra public keys over a TLS-validated connection.

11. [Bind the blueprint identity](11-blueprint-token-holder.yaml) — The token component uses a dedicated Kubernetes ServiceAccount and blueprint federation.

12. [Authorize application to agent](12-application-to-agent-policy.yaml) — Require the intended calling app, correct A2A audience and invoke role.

13. [Authorize agent to MCP](13-agent-to-mcp-policy.yaml) — Require the exact child Agent ID, separate MCP audience, read role and listed tools.

14. [Restrict direct backend access](14-mcp-network-boundary.yaml) — Allow destination ingress only from the intended gateway pods.


## Control, monitor and evaluate

15. [Bound traffic and consumption](15-model-traffic-limits.yaml) — Apply a timeout and local request/token limits to the model route.

16. [Guard model data](16-model-content-guards.yaml) — Reject selected sensitive-data patterns and mask selected output patterns.

17. [Audit and trace calls](17-gateway-observability.yaml) — Add verified identity attributes to controlled logs and export traces.

18. [Collect metrics](18-gateway-podmonitor.yaml) — Prometheus scrapes the native proxy metrics.

19. [Alert on problems](19-gateway-alerts.yaml) — Monitor denial activity, errors, token consumption and separate evaluation failures.

20. [Evaluate behavior](20-agent-evaluation-case.yaml) — Score captured diagnosis, evidence, tool use, namespace and budgets; safety failures override the score.

## How the first files fit together

Files [01](01-agent.yaml), [02](02-agent-skills.patch.yaml) and [03](03-agent-tools.patch.yaml) produce **one Agent**. Files 02 and 03 are merge patches, not separate complete resources. The combined object is in [reference/assembled-agent.yaml](reference/assembled-agent.yaml). The included [skill file](skills/sre-triage/SKILL.md) matches the path referenced by file 02.

The local-only command below assembles that Agent without contacting a cluster:

```sh
kubectl kustomize .
```

[File 04](04-a2a-orchestrator.yaml) defines the separate SRE chatbot and a minimal destination Agent, separated by `---`. Its real Grafana tools and other specialists are prerequisites. The namespace opt-in and gateway/Entra permission checks are separate controls.

## What to say about Microsoft tokens

“We use Microsoft Entra-issued access tokens. For our registered agent and MCP APIs, those tokens have signed JWT format. Entra issues the token; the gateway validates it and checks permissions.”

The calling app obtains an A2A API token. The running agent obtains a separate child Agent ID token for the MCP API. `jwtAuthentication` validates the Microsoft token; it does not ask for an extra gateway token.

## Supporting notes

- [Entra Agent ID and blueprint setup](guides/01-entra-agent-blueprint-setup.md)
- [Gateway security, metrics and evaluation](guides/02-gateway-security-monitoring-evaluation.md)
- [Optional SRE orchestration demo](guides/03-sre-orchestration-demo.md)
- [Values and prerequisites](guides/04-configuration.md)
- [Graph federated-credential payload](identity/README.md)
- [Validation and proof limits](VALIDATION.md)

The examples are configuration patterns for compatible kagent v1alpha2 and agentgateway v1alpha1 installations. The root Kustomization renders only the first Agent and its two patches. File 20 is local scorer input, not a Kubernetes resource. The complete directory is not a single apply-ready platform install.
