# Add an observability proposal without replacing the office work

The existing HostedAgent/profile code creates native or standalone execution through its selected path. The secure native lab adds call-time approval and fixed protected Gateway routes; the route-targeted policy performs strict JWT validation and subject checks, while backend authorization and network containment remain separate. The office integration of those controls into the old operator is still its work-agent task.

Existing OTel source demonstrates telemetry paths but does not prove this new secure Gateway exports to LGTM. The old platform telemetry helper also targets different versions and mutates shared services. The amendment therefore consumes target snapshots and emits proposals, never automatic installation or platform mutation.

Two shapes were considered. Documentation alone is low risk but leaves schema translation and evidence capture manual. A generic installer would require unknown office ownership, exporter credentials and merge semantics. The selected middle path is a small typed, snapshot-driven renderer plus a bounded metadata evidence probe. Actual operator/routing and producer instrumentation changes remain adapted to the office source, with explicit delivery gates.

`render_telemetry.py` accepts protected settings, the installed policy CRD and a complete policy snapshot. It emits a separate Gateway frontend telemetry policy, exact destination consent, network rule fragments and an unverified review record. It refuses unknown fields, unapproved scope, unsupported schema and conflicting existing telemetry policies. It does not modify its inputs, replace JWT policy or create a partial network isolation baseline.

`probe_trace.py` accepts a reviewed request payload and private credential file, emits a fresh requested W3C context, and retains a bounded status/hash receipt. Tempo lookup checks actual trace/service identity and projects allowlisted metadata. Neither command declares a verified workflow. Unknown or absent telemetry stays unknown. The selected command interfaces are documented in [the OTel guide](OTEL-INTEGRATION.md).

This separate sibling folder preserves base manifest integrity and the agent's already modified office checkout. Copy it beside the existing folders and merge its reviewed changes. Shared Gateway/collector ownership, the old four CRDs and no-Substrate requirement remain unchanged. No dashboard or collector replacement is introduced.
