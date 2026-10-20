# OTel agent workflow demo for AKS

Deploy the same application image and Helm chart on one cluster. The browser submits prompts on the left. The right column switches between a workflow map and OTel logs. Native Substrate actor identity links resume, execution, checkpoint, and suspend traces without correlating by timing.

Start with [WORK-BUNDLE-README.md](WORK-BUNDLE-README.md). Give the implementing work agent [WORK-AGENT-PROMPT.md](WORK-AGENT-PROMPT.md). Use [LIVE-INTEGRATION.md](LIVE-INTEGRATION.md) to reuse the existing agent, gateway, Kubernetes MCP tools, and approved skills. Build the backend container from this repository through work CI. No prebuilt archive is required.

The target ingress instructions are in [AKS-ISTIO.md](AKS-ISTIO.md).

## What transfers

- A containerized dashboard with the kagent palette, prompt entry, workflow presets, trace inspection, replay, token usage, and explicit cost estimates.
- One Helm chart with an existing-agent profile for the current platform and a bundled fixture profile.
- Native kagent Agent, Harness, AgentTemplate, ModelConfig, and RemoteMCPServer resources. No arbitrary shell, Kubernetes mutation, SQL, or URL-fetch tools.
- A local HTTPS ingress rehearsal and an AKS managed Istio Gateway/VirtualService profile.
- Build, preflight, deploy, telemetry, HTTPS verification, packaging, and rollback instructions.

The deployed platform prerequisites are kagent **1.0.0-alpha8** and Substrate **0.4.0-alpha1**. The chart uses the installed `api.kagent.dev/v1alpha3` schema. The bundle refuses an automatic platform upgrade. See [PLATFORM-PREREQUISITES.md](PLATFORM-PREREQUISITES.md).

## What is proven

The single-cluster Linux rehearsal served HTTPS with certificate validation. Inventory, change review, and intentional dependency failure traversed real HTTP/MCP calls and a real Substrate sandbox. A live Kimi model also completed the inventory workflow through the in-cluster gateway, with the old host bridge disabled. See [evidence/portable-fixture-verification.json](evidence/portable-fixture-verification.json) and [evidence/portable-live-verification.json](evidence/portable-live-verification.json).

AKS, the managed Istio ingress runtime, enterprise certificate delivery, corporate access controls, and network-policy enforcement still require target-cluster verification. The local proxy rehearses HTTPS termination and route selection. It does not emulate the Istio control plane or prove Azure networking.

## Operator inputs

Fill the AKS values example with the internal image repository/digest, approved WorkerPool and snapshot location, demo hostname, TLS Secret, and demo user partition. Supply approved model DNS and a pre-existing Secret only for live-model mode. Keep populated work values, certificate private keys, kubeconfigs, model credentials, and rollback state outside the public bundle.

This is a shared, single-user demonstration. The configured user ID selects a kagent data partition and is not authentication. Put the demo behind the work environment's approved authenticated edge/access policy before admitting an audience. TLS alone does not provide user authorization.

Each prompt starts a fresh session. Fixture mode labels its model and tool data as simulated. Live mode uses a real provider with simulated read-only tools. No UI animation is triggered by the prompt itself; component activity comes from received OTel spans. Replay is labelled separately.
