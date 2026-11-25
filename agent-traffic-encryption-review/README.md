# Agent traffic encryption review

Give the work agent [WORK-AGENT-REVIEW.md](WORK-AGENT-REVIEW.md). It contains the complete read-only request, component checklist and report template for the deployed AKS, Istio, Agent Gateway, kagent, MCP, model and telemetry paths.

For a visual version, open [index.html](index.html). Both handoffs ask for configured and observed transport evidence separately, and for unknowns and access blockers to be reported. They do not establish the current state of any workplace environment.

## Desired security design and lab evidence

- [HTML sequence diagrams](encryption-sequences.html) and [PDF](agent-identity-and-encryption.pdf) show the target UAMI, HTTPS and mesh mTLS flows and the controls needed at each boundary. These describe a target architecture, not the deployed workplace configuration.
- [Repeatable agent security lab](../agent-security-lab/README.md) contains the pinned lab stack, scripts, scenarios, skill and dated test evidence. Its synthetic model task and several protected hops have been tested; the Substrate egress-to-model-gateway HTTP hop and an MCP task remain open. The full clean-VM rebuild has not yet been tested.

Use the diagrams to guide the review, then follow the actual workplace routes and report evidence per connection in the work-agent checklist.
