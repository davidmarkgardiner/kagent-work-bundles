# Versions and migration

Checked against official releases and actual OCI charts on **18 November 2026**. A moving `latest` documentation URL is a reference; the release-tagged source and chart digest are the pin.

| Component | Target | Meaning |
| --- | --- | --- |
| kagent controller, CRDs and CLI | 1.0.1 | Latest stable; released 12 November |
| Substrate release-matched baseline | 1.0.0 | kagent 1.0.1 `go/go.mod` pins this release; CLI build derives its Substrate default from it |
| Substrate latest standalone candidate | 1.0.1 | Released 8 November; render separately and complete lifecycle compatibility before promotion |
| kagent-tools | 0.3.0 | Dependency in the actual kagent 1.0.1 chart |
| Platform agentgateway | 1.7.0 | Latest release; verify controller/data plane, Gateway API and policy schemas together |
| Kubernetes for the new lab | 1.37 with required certificate APIs | Current installation guide prerequisite; verify actual API discovery |
| MkDocs | 1.6.1 | Preserves yesterday's build tool and portable theme |

Upstream's version-support page still lists kagent 1.0.0 and a 1.35 CI version, while its current installation guide asks for 1.37 and the release endpoint reports 1.0.1. The lab follows the stricter installation prerequisites and tagged artifacts; this discrepancy must not be hidden behind a broad compatibility claim.

The exact baseline and candidate chart digests are in the [release lock](downloads/versions.lock.json). Never select Substrate independently just because its number matches kagent. See [upstream dependency](https://github.com/kagent-dev/kagent/blob/v1.0.1/go/go.mod), [release build settings](https://github.com/kagent-dev/kagent/blob/v1.0.1/Makefile), [kagent releases](https://github.com/kagent-dev/kagent/releases/tag/v1.0.1), [Substrate releases](https://github.com/kagent-dev/substrate/releases/tag/v1.0.1) and [gateway release](https://github.com/agentgateway/agentgateway/releases/tag/v1.7.0).

## 0.x to 1.0 is a migration

Use a second cluster and a new database. Preserve the old installation while recreating the supported resources and validating the new path. Old conversation history does not automatically migrate. Do not install both release lines side by side on one cluster or attempt an in-place database upgrade. Retire the old cluster only after accepted cutover and retention checks.

| Older contract | 1.0 contract / action |
| --- | --- |
| `kagent.dev/v1alpha2` Agent | `api.kagent.dev/v1alpha3` AgentTemplate + Harness + Agent |
| `SandboxAgent` | Removed; all 1.0 agents use Substrate |
| Old `AgentHarness` | Removed; new Harness is a different API |
| Per-agent Deployment assumptions | Session-backed Actors on platform WorkerPools |
| `ModelConfig.apiKeyPassthrough` | `tokenPassthrough`; review identity and audience handling |
| ToolServer / bundled MCPServer | Approved external MCP deployment plus RemoteMCPServer |
| `/api/a2a/...` and sandbox routes | `/agents/{namespace}/{name}`; retest every caller and transform |
| Old snapshots/worker image names | Fresh matched runtime, identity, storage and lifecycle configuration |

Use the [official migration procedure](https://kagent.dev/docs/kagent/latest/operations/upgrade-from-0x/) and [release mapping](https://kagent.dev/docs/kagent/latest/reference/release-notes/1.0/). For later 1.x upgrades, review backups and skew, upgrade CRDs, then atelet before the Substrate API/control plane, then kagent as documented. Do not downgrade a migrated database as rollback; restore the reviewed backup or route back to the intact old service.
