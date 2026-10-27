# AgentShield: benefits and security posture

AgentShield could strengthen our kagent platform by connecting workloads, identities, policies, and supported traffic observations into an evidence-backed security graph. This would help us find risky paths, explain security changes, and prioritize reviewed fixes. These are expected benefits to validate in a PoC, not improvements already demonstrated in our environment.

## How it improves our posture

| Benefit | Improvement for our platform |
|---|---|
| Clearer visibility and blast radius | Join workload identity, services, and governing policies so we can assess supported paths to sensitive systems and identify coverage gaps. |
| Earlier detection of security drift | With detection enabled, flag relevant policy changes and unexpected observed communication rather than relying on a manual review after an incident. |
| Faster, better-supported investigation | Give kagent current findings with resource identities, graph revisions, and evidence references. Reduce manual correlation and make conclusions easier to challenge. |
| More focused least-privilege changes | Use findings to propose specific policy changes. Verify reduced reach with denied unauthorized requests and successful legitimate requests. |
| Controlled, reviewable response | Keep human approval and scoped Argo/Flux execution in our existing delivery flow. Capture approval identity, the reviewed diff, verification, and rollback externally. |

## How it fits

Infrastructure observations feed AgentShield. A proposed bounded read-only adapter passes findings to a kagent security specialist. The specialist explains the evidence and proposes a change. Human review authorizes scoped Argo/Flux delivery, followed by traffic and rollback tests.

The security gain comes from detecting supported risky changes and closing verified paths. Inventory and policy declarations alone do not establish effective enforcement.

## What we must prove

Start in an isolated Proxmox test cluster with dummy services. Detect a new path from a narrow-role workload to a dummy sensitive service, pass the finding to kagent, and prepare a reviewed fix. Test a benign control, block the unauthorized request, preserve required traffic, and prove rollback. Measure detection time, evidence quality, false alarms, model cost, and time to a reviewable change.

Carry the reviewed image/chart, evidence contract, fixtures, and receipts into an AKS lower environment. Configure workplace identities, telemetry, model routing, and GitOps locally.

## Current limits

The API needs external authentication/access controls. The default collector can read all Kubernetes Secrets. Agentgateway access-log and Cilium Hubble transports are unwired in the reviewed source. Azure cloud identity/network coverage is absent. Detection needs explicit activation. The findings adapter and our runtime integration remain proposed.

Research snapshot: 27 October 2026. Upstream commit `b179824e455401783f031a370b8794358a10dd8c`. No installation or measured risk reduction is claimed.

Sources: [pinned source](https://github.com/agentshield-dev/agentshield/tree/b179824e455401783f031a370b8794358a10dd8c), [security model](https://agent-shield.dev/docs/operations/security/), [Helm deployment](https://agent-shield.dev/docs/operations/helm/). See [the full assessment](assessment.html) for supporting detail.
