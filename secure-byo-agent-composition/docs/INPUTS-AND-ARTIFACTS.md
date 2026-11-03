# Input and artifact checklist

The source ZIP carries code, manifests generated from reviewed target inputs, tests, and instructions. It carries no image layers, chart archives, executable binaries, Go dependency cache, Python wheels, credentials, or private environment settings. Copying the source ZIP alone does not satisfy the runtime prerequisites.

## Known source pins

| Artifact | Source pin | Transfer or target requirement |
| --- | --- | --- |
| Common image base | `sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30` | Preload the approved internal Python base with this manifest digest |
| Linux AMD64 native CLI | Kagent `1.0.0-alpha17`, SHA-256 `01fb21bc46130dcffac5b5a720d903122563a4d926f4455cd8234c6112d338a3` | Stage the verified binary for the offline image build |
| KRO chart | `0.9.4`, chart digest in [versions.lock.json](../versions.lock.json) | Import chart and every image found by rendering the approved values |
| agentgateway controller and CRD charts | `v1.5.0`, chart digests in [versions.lock.json](../versions.lock.json) | Import both charts, CRDs, and every rendered controller and data-plane image |
| Gateway API CRDs | `v1.6.2` experimental | Import reviewed manifests including GRPCRoute and their transfer checksums |
| PyYAML wheel | `6.0.3` | Import the platform-approved wheel for the actual Python and architecture |
| Actor diagnostic modules | [go.mod](../diagnostics/go.mod), [go.sum](../diagnostics/go.sum), and [dependency inventory](../diagnostics/dependency-inventory.txt) | Import the exact Go dependency cache and approved compiler |
| Network diagnostic | [network_probe.go](../scripts/network_probe.go) | Build with the approved compiler and public network disabled |
| Database migration | [schema.sql](../prerequisites/schema.sql) | Review native role mappings and schema ownership before execution |

These are source identifiers. Each imported artifact needs a separately recorded transfer checksum, internal destination, final digest, architecture, approval reference, and a consumer availability check. Public source locations in the version lock are provenance references, not workplace fetch commands.

[lab-artifact-inventory.json](lab-artifact-inventory.json) records 25 selected observed home-lab image references, their observed image IDs where available, two sandbox assets, and the two reviewed content OCI sources. It preserves source provenance. It omits credentials and private endpoints. The local runtime image name and localhost content source names are lab-only references that must be replaced with approved internal destinations. This partial observed inventory does not cover every dormant hook or platform dependency and does not establish cold import.

## Discover the complete target image inventory

The version lock is not an exhaustive container or sandbox inventory. Enumerate the following from the actual installed versions or the complete approved chart render before import:

- Kubernetes node and infrastructure images if the target does not already provide them.
- Kagent controller, native ADK, initialization containers, and any chart hooks.
- Substrate controllers, workers, credential provider, snapshot services, helper containers, pause image, and downloaded sandbox assets.
- Kyverno admission, background, cleanup, and reports controllers and their hook images.
- KRO controller and hooks.
- agentgateway controller, data planes, certificate or initialization helpers, and hooks.
- The target NetworkPolicy provider when it is not already installed and proven.
- The internally built front-door and composer image, both reviewed content OCI packages, and any approved diagnostic image.

Resolve every reference to an approved internal location. Record the source and internal manifest digests even when a mirror preserves the bytes. Check the resulting manifests for public registries and mutable tags before deployment. The target's approved controller ServiceAccount, registry authentication, snapshot storage, certificate projection, DNS, kernel capabilities, and sandbox assets are prerequisites beyond the image list.

## Private input contract

| Input | Producer | Consumer and required check |
| --- | --- | --- |
| `snapshot.json` | Platform-selected AgentTemplate, ModelConfig, and Harness | `deploy.py`; approved native specs, exact supported schemas, immutable reviewed content |
| `settings.json` | Target platform owner | `deploy.py`, `network.py`; internal image digest, controller endpoints, identities, WorkerPool contract, API CIDRs, selectors, and policy configuration |
| Public JWKS and issuer | Approved identity configuration | `gateway.py`; Kubernetes token profile only, with audience `secure-byo` |
| Model credential | Approved secret source | Front-door `secure-byo-model-token` Secret; provider key readable only by the protected proxy |
| Controller proposal | `controller_setup.py` | Non-overlapping watch scopes, dedicated database schema, runtime origin, and reviewed platform trust |
| Credential-provider proposal | `credential_policy.py` | Exact atespace-to-same-namespace authority for both POCs |
| Approval record | Independent platform publisher | Current request, Agent, caller and dependency UIDs/spec hashes, expiry, and state |
| Runtime token | Approved publisher in the lab | MCP/model lane; four-hour lab token, with renewal and reload still a separate operational requirement |

Store private inputs and raw receipts outside the source tree. The lab discovery helper can export an existing provider Secret into private output and must not be treated as workplace credential provisioning.

## Target gates that require fresh evidence

The target must prove cold content import, registry credentials, current API schemas, actual admission enforcement, actual worker and actor networking, and native task completion. Home-lab content consumption used a warm cache and does not establish cold disconnected import. Entra integration, unattended token renewal, and high availability need separate implementation and receipts before those capabilities can be claimed.
