# What 1.7 adds

These are available capabilities, not features automatically enabled or proved by this upgrade. Sources are the [official 1.7 release](https://github.com/agentgateway/agentgateway/releases/tag/v1.7.0) and [Kubernetes release notes](https://agentgateway.dev/docs/kubernetes/latest/release-notes/release-notes/). Source tag `v1.7.0` resolves to `26f5aebe99a36a037fe54f8080a608aca5547e15`.

| Capability | Relevance to our demo |
| --- | --- |
| Agent-session detection in logs and CEL | Correlate requests using supported session headers. Correlation does not authenticate callers. |
| CEL MCP guardrails and conditional Kubernetes MCP targets | Filter or transform supported MCP traffic without adding a remote guardrail service. Requires actual MCP backend/policy configuration. |
| JWT-preserving MCP authentication and browser-or-bearer OIDC | Useful for identity integration later. Keep our existing strict JWT contract now. |
| Richer model metadata and service-tier pricing | Discover capabilities and improve attribution when actual model pricing is configured. |
| Decisions, SystemOne and audio APIs; Perplexity and Kubernetes Copilot support | Additional provider options, outside this demo's activation scope. |
| Native histogram and relabeling support | Additional monitoring options. Preserve the existing metrics path. |
| `agctl bug-report` and standalone administration/analytics | Additional diagnostics. Archives and request stores require private handling. |
| Broader guardrail scope and improved MCP session cleanup | Useful governance and session lifecycle capabilities after explicit configuration review. |

## Review before upgrading from 1.5

The [1.6 release](https://github.com/agentgateway/agentgateway/releases/tag/v1.6.0) changes provider URL/path handling and Anthropic-to-OpenAI conversion preference. Check explicit API paths, supported formats, cost-based limits, policy conflicts and changed CRD defaults. Preserve the existing `agentgatewayModels.enabled` decision rather than silently accepting its new default. OTLP access-log scope becomes `agentgateway.access`.

Version 1.7 removes `AGENTGATEWAY_MESSAGES_PREFER_COMPLETIONS`. Find and remove reliance on that compatibility flag. For an OpenAI-compatible server without `/v1/responses`, use a custom provider advertising only Chat Completions rather than expecting the old flag to work.

In 1.7, repeated header lookups can produce lists. Audit header-based deny rules and test repeated headers. Error response text hides internal details, so tests must verify enforcement and status rather than old strings. Dynamic backends block loopback/link-local destinations; do not enable a global bypass to reach cloud metadata. Tool output joins default vendor guardrail scope, potentially exporting more content. Review scope before activation.

For standalone Gateways, immutable config can prevent automatic session-key persistence. Supply a protected, stable `SESSION_KEY`; plan client reconnection when sessions become invalid. Database migrations need private backups. Do not confuse these proxy settings with a requirement for Substrate.

The lab preserved existing routing and JWT configuration. It did not activate all new features, change the model provider or demonstrate Entra, new vendor guardrails, standalone agent onboarding or Tempo ingestion.
