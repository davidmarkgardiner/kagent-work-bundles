# Sources and downloads

The current pages synthesise the selected platform work. Original documents retain their dated implementation/evidence scope. The catalog pins a Git revision and source hashes; it is deliberately not a blanket copy of local files. Public links need connectivity; the current handbook, theme and lab downloads work without this monorepo.

## Downloadable handoff assets

- [Work-agent prompt](downloads/WORK-AGENT-PROMPT.md.txt)
- [Release/version lock](downloads/versions.lock.json)
- [Source manifest](downloads/source-manifest.json)
- [Validation receipt](downloads/validation.json)
- [Canary AgentTemplate and Agent](downloads/agent-canary.yaml)
- [kagent render-test values](downloads/kagent-values.yaml)
- [Latest Substrate candidate render values](downloads/kagent-values-candidate.yaml)
- [1.0 ServiceNow A2A route](downloads/servicenow-a2a-route.yaml)
- [A2A gRPC request](downloads/a2a-request.json)
- [Read-only explicit-context preflight](downloads/preflight.py)
- [Offline chart/schema verifier](downloads/verify_offline.py)

Copy the whole source folder for maintenance; these individual downloads are supporting files, not an automatically deployable production package.

## Stakeholder delivery sources

- [Roadmap source](downloads/roadmap.yml)
- [Published updates source](downloads/updates.yml)
- [Next-update template](downloads/update-template.yml)

## Reviewed source catalog

| Source | Handbook topic | Immutable reference |
| --- | --- | --- |
| Six-month modernisation draft | direction | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/STATEMENT-OF-WORK.md) |
| Pod direction and quarterly outcomes | direction | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/ai-platform-pod-direction/README.md) |
| KRO composition and extension design | architecture | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/agent-platform-four-crds/DESIGN.md) |
| Reviewed BYO onboarding patterns | architecture | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/infra/byo-kagent/README.md) |
| Experimental four-CRD platform | knowledge | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/agent-platform-four-crds/README.md) |
| Tenant isolation entrypoint | isolation | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/kagent-agentgateway-tenant-isolation/README.md) |
| Tenant administrative and network boundaries | isolation | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/kagent-agentgateway-tenant-isolation/ARCHITECTURE.md) |
| Isolation regression matrix | labs | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/kagent-agentgateway-tenant-isolation/TEST-MATRIX.md) |
| Classic phase-one evidence | evidence | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/kagent-agentgateway-tenant-isolation/PHASE1-WORK-EVIDENCE.md) |
| Workplace runtime promotion gates | deploy | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/kagent-agentgateway-tenant-isolation/AKS-SUBSTRATE-PROMOTION.md) |
| Dated AKS Agent ID test | identity | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/kagent-agentgateway-tenant-isolation/poc/azure-agent-id/AKS-FULL-E2E-EVIDENCE-2026-09-25.md) |
| Caller-to-agent ownership request | identity | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/kagent-agentgateway-tenant-isolation/poc/azure-agent-id/WORK-REQUEST-1-CALLER-UAMI-A2A.md) |
| Agent-to-MCP ownership request | identity | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/kagent-agentgateway-tenant-isolation/poc/azure-agent-id/WORK-REQUEST-2-AGENT-BLUEPRINT-MCP.md) |
| Agent ID and app-only/OBO comparison | identity | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/docs/entra-agent-id/README.md) |
| Policy exception and fleet guardrails | isolation | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/docs/security/agent-substrate-sys-admin-security-review.md) |
| Dated alpha runtime privilege inventory | isolation | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/docs/security/agent-substrate-security-context-README.md) |
| Runtime blast radius | isolation | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/docs/security/agent-substrate-blast-radius-README.md) |
| Kyverno admission and report evidence | labs | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/kyverno-runtime-permissions-lab/README.md) |
| Audit-first workplace policy adaptation | labs | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/kyverno-runtime-permissions-lab/WORKPLACE-START-HERE.md) |
| Runtime stakeholder brief | architecture | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/docs/agent-substrate-business-brief.md) |
| Runtime comparison | architecture | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/docs/agent-sandbox-vs-substrate.md) |
| Independent maturity review | direction | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/docs/platform-kb/aks/platform-maturity-independent-review-2026-11-10.md) |
| Historical air-gap runtime assets | deploy | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/agent-substrate/AIRGAPPED-AKS-README.md) |
| Bounded MCP transport and token measurement | knowledge | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/work-agent-bundles/postgres-fastmcp-entra-uami/WORK-AGENT-TOKEN-EFFICIENCY-HANDOFF.md) |
| Logs/events triage and correlation | operations | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/docs/observability/dual-source-kafka-triage-routing.md) |
| Incident ingress options and original proof | servicenow | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/platform/agentgateway/servicenow-incident-ingress/README.md) |
| AKS ingress and Entra handoff | servicenow | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/platform/agentgateway/servicenow-incident-ingress/aks/README.md) |
| Dated transformation proof | evidence | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/platform/agentgateway/servicenow-incident-ingress/poc/README.md) |
| Existing MkDocs build conventions | handoff | [Pinned source](https://github.com/davidmarkgardiner/kagent-public/blob/cfb3b22950ee7290d1aea4bf125e561cdfaede64/platform/agentgateway/servicenow-incident-ingress/mkdocs/mkdocs.yml) |

## Air-gap and dependency note

Mirroring an OCI image does not necessarily mirror runtime binaries, guest assets, snapshot dependencies, fonts, wheels or trusted CA material. The old runsc 0.0.9 workaround is historical. Inventory every image and runtime asset from the selected release; verify architecture, checksum, internal source and actual startup without public egress. The new chart verifier inventories rendered image references but does not prove a complete air-gap import or working runtime.
