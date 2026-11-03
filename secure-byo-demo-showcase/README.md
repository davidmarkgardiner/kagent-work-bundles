# Present and hand over the secure agent onboarding demo

Start with [the HTML briefing](SHOWCASE.html) or [printable PDF](SHOWCASE.pdf). Use [the presenter walkthrough](PRESENTER-WALKTHROUGH.md) for the live session. Give the work agent [WORK-AGENT-HANDOVER.md](WORK-AGENT-HANDOVER.md), then fill [the team handover report](TEAM-HANDOVER-TEMPLATE.md) from its actual receipts.

Copy this folder beside `secure-byo-agentgateway-jwt-otel-amendment`, `agentgateway-1-7-upgrade`, `secure-byo-agent-composition`, `agent-platform-four-crds` and the existing `otel-agent-flow` folder. It is a separate addition; preserve their manifests and ongoing office changes.

The outcome is one newly named owner YAML producing a complete agent, secured Gateway wiring, automatic security checks and a passing GoldenScenario, **without Substrate**. The team watches actual creation, readiness and calls. Shared infrastructure and imported images/content are prerequisites.

This addition authorizes the small read-only onboarding/evidence view needed for that demonstration. It supersedes earlier dashboard exclusions only for this bounded view. Reuse the existing OTel/LGTM and dashboard; do not build a replacement observability stack or redesign unrelated Grafana dashboards.

The HTML and PDF are prepared briefing materials, not a live dashboard or a completed office case study. [The live-view handoff](LIVE-OBSERVABILITY-HANDOFF.md) defines what the work agent must connect and verify. [The claim map](CLAIM-EVIDENCE.md) separates actual lab results from remaining office gates.

Opening HTML/PDF needs no packages, Internet access or public fonts. The optional PDF builder uses the supplied editable content and pinned Python dependencies; acquire wheels through the office's approved process only if rebuilding there. Use `sha256sum -c SHA256SUMS` after transfer, or `shasum -a 256 -c SHA256SUMS` on macOS. Verify the reviewed repository revision independently.
