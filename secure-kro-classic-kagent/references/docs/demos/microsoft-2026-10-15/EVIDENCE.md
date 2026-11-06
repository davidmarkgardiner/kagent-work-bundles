# Claim and evidence map

Prepared 14 October 2026 for the 15 October discussion. Sources were read from the current working tree, based on Git revision `620108e9`, which includes existing modified and untracked work. That revision alone does not identify every source artifact. No runtime, Entra tenant, VM, cluster or external ticket was revalidated for this preparation.

| Slides | Claim / evidence | Limit |
|---|---|---|
| 2–3 | [Gateway routes and ModelConfigs](../../../platform/agentgateway/README.md), [schema gate](../../../platform/agentgateway/DEMO-SCHEMA-GATE.md) | Configured model-garden / failover patterns need installed-version runtime proof. |
| 4 | [Grafana MCP demo](../../../docs/ai-grafana/kagent-grafana-mcp-demo.md), [GitLab MCP handoff](../../../work-agent-bundles/gitlab-mcp-gitops-pr/README.md) | Grafana direct MCP and agent-mediated model calls are separate. GitLab writes need approved project scope. |
| 5–6 | [Triage tracker](../../../work-agent-bundles/evidence-first-worker-triage/next-phase-end-to-end/ROLLOUT-TRACKER.md), [recorded value example](../../../work-agent-bundles/evidence-first-worker-triage/next-phase-end-to-end/evidence/phase5-value.md), [live tickets](../../../work-agent-bundles/evidence-first-worker-triage/next-phase-end-to-end/evidence/phase5-live-tickets.md) | Recorded sandbox path. Stable identity under pod churn, durable storage and broker-outage accounting remain promotion gaps. |
| 6, 14 | [Hybrid Azure SRE Agent recommendation](../../../agents/kagent-triage/docs/HYBRID-AZURE-SRE-AGENT-KAGENT-RECOMMENDATION.md) | ServiceNow and managed SRE escalation are design discussion, without a ServiceNow transaction receipt in this pack. |
| 7 | [Postgres Azure/UAMI proof, 19 August](../../../work-agent-bundles/postgres-fastmcp-entra-uami/evidence/FASTMCP-ENTRA-AKS-UAMI-POC-2026-08-19.md) | Synthetic data. Direct MCP / TLS / approved-view permissions proved. No kagent / gateway integration. Azure resources later deleted. |
| 7 | [Bounded transport, 8 September](../../../work-agent-bundles/postgres-fastmcp-entra-uami/evidence/TOKEN-EFFICIENCY-GEEKOM-POC-2026-09-08.md) | 5,000 matching rows, 50 returned, 24,963-byte complete MCP envelope. No measured workplace token savings or model-backed skill execution. |
| 7 | [Denodo reference](../../../work-agent-bundles/denodo-fastmcp-uami/README.md) | Synthetic JDBC driver and patched token acquisition. Real VDP, private driver, TLS, permissions and UAMI acceptance remain open. |
| 8–10 | [Isolation runtime receipt, 16 September](../../../work-agent-bundles/kagent-agentgateway-tenant-isolation/evidence/red/2026-09-16-runtime.md), [35-gate summary](../../../work-agent-bundles/kagent-agentgateway-tenant-isolation/evidence/red/2026-09-16-summary.tsv), [claim map](../../../work-agent-bundles/kagent-agentgateway-tenant-isolation/video-explainer/CLAIM-TO-EVIDENCE.md) | Synthetic MCP fixtures, disposable JWTs, exact scoped tests. Entra resources passed schema validation only. Different ordinary and Substrate version lanes. |
| 9 | [Entra policy example](../../../work-agent-bundles/kagent-agentgateway-tenant-isolation/profiles/aks-entra/event-mcp-policy.yaml), [Entra overlay](../../../work-agent-bundles/kagent-agentgateway-tenant-isolation/profiles/aks-entra/README.md) | Existing role / tool policy does not establish live child-Agent-ID authorization, token refresh or revocation. |
| 11 | [AKS evaluation, 7 October](../../../work-agent-bundles/agent-substrate/AKS-EVAL-WORK-AGENT-HANDOFF.md), [Public runsc baseline, 6 October](../../../work-agent-bundles/runsc-public-baseline/README.md), [isolated-network guidance](../../../work-agent-bundles/agent-substrate/AIRGAPPED-AKS-README.md) | Separate ARM64 kind and AMD64 Azure Linux AKS runs. AKS pairs: 1.35.8 / Substrate 0.0.9 / kagent 0.10 patch 1, and 1.37 preview / Substrate 0.4.0-alpha1 / kagent 1.0.0-alpha8. Lab internal-asset patches, Internet-connected clusters, no model/MCP/chat or changed-data test. Resources deleted. Workplace equivalence remains unproved. |
| 12 | Local sibling source `../durable-pi/PI-HOME-LAB-DEMO.md`, dated 14 October, inspected during preparation | Records a VM-hosted synthetic queue job and approval persistence. The raw source contains private operations detail and is deliberately not copied into this pack. Current UI / VM state was not verified. |
| 12, 15 | [Paired comparison design](../../../docs/agentic-delivery-factory/pi-durable-comparison/README.md), [scorecard](../../../docs/agentic-delivery-factory/pi-durable-comparison/SCORECARD.md) | Trial scorecard remains NOT_RUN. The local Pi observations are not native-kagent comparison results. |
| 13 | [Eval scorer](../../../observability/agent-evals/README.md), [repo overview](../../../README.md) | Local labelled-sample scoring establishes evaluation behavior, not live model quality, productivity or cost savings. |

## Official documentation checked during preparation

- [Microsoft agent identities](https://learn.microsoft.com/en-us/entra/agent-id/agent-identities), https://learn.microsoft.com/en-us/entra/agent-id/agent-identities. Supports the blueprint-backed identity / token-acquisition distinction.
- [agentgateway Entra MCP setup](https://agentgateway.dev/docs/kubernetes/latest/documentation/mcp/auth/entra/), https://agentgateway.dev/docs/kubernetes/latest/documentation/mcp/auth/entra/. Current docs are newer than the v1.5 rehearsal. Do not infer schema compatibility from a current example.
- [DAB SQL MCP overview](https://learn.microsoft.com/en-us/azure/data-api-builder/mcp/overview), https://learn.microsoft.com/en-us/azure/data-api-builder/mcp/overview. Additional researched option only. The deck interprets the spoken Dodo reference as Denodo, rather than substituting DAB.

## Existing presentation material

- [Demo index](../../../DEMOS.md).
- [Tenant isolation presentation source](../../../work-agent-bundles/kagent-agentgateway-tenant-isolation/video-explainer/private-preview/index.html).
- [Grafana incident walkthrough](../../../docs/ai-grafana/iteration-review-chaos-agent-demo.html).
- [Triage walkthrough](../../../SMART-TRIAGE-FANOUT-PRESENTER.html).

The combined slideshow is self-contained for sharing. Its source links resolve in this checkout; send this folder with repository context if the recipient needs the underlying local sources. No private identifiers, tokens, endpoints or raw VM receipts belong in the shared pack.
