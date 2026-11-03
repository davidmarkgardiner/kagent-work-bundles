# Agent Gateway onboarding and OTel amendment

Copy **only this amendment folder** beside the folders already given to the office agent. Give it [the amendment prompt](WORK-AGENT-AMENDMENT.md). Merge the reviewed delta into its ongoing work. Do not replace its checkout or add files inside the base bundle's hash-verified inventory.

The baseline is `secure-byo-agent-composition` at `4bfb61fc197a94157dcbebcaf1143cbf9f398b13`, plus `agent-platform-four-crds`. Reuse the existing Gateway, OTel collector and LGTM services where compatible. No dashboard implementation or platform upgrade is assigned here.

The base includes strict JWT issuer/audience/subject checks, agent/model/MCP HTTPRoutes, ReferenceGrants, call-time authorization, RBAC, Kyverno, network controls and exact native runtime RPC routes. This amendment adds automated Gateway onboarding and fresh telemetry evidence as delivery requirements.

The lab used fixed/prestaged routes, not onboarding of a newly named office agent. Read-only inspection found no frontend tracing on the four secure Gateway policies. Its collector exported to the viewer and old demo, with no Tempo/Loki exporter there. Other LGTM paths may exist; the office path remains unverified.

Use [the prerequisites](PREREQUISITES.md), the render-only telemetry proposal from `render_telemetry.py`, and [the demo run sheet](DEMO-RUNBOOK.md). The new secure Gateway-to-LGTM path and existing-operator automation need target receipts before a success claim.

[Onboarding automation](ONBOARDING-AUTOMATION.md) defines the generated Gateway closure and independent activation. [OTel integration](OTEL-INTEGRATION.md) gives render, privacy/fan-out, producer and trace-query steps. [Validation](VALIDATION.md) separates source/server-dry-run checks from unproved office outcomes. Run `python3 verify.py --tests` after copying this folder.

This demonstration uses Kubernetes JWT TokenRequest identities compatible with the base TokenReview checks. **Entra is deferred to a later iteration.** JWT validation does not replace subject authorization, backend approval or network containment.
