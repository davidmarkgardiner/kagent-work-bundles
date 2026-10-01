# Azure DevOps MCP air-gap replication bundle

Download the focused source ZIP:
https://github.com/davidmarkgardiner/kagent-work-bundles/releases/download/azure-devops-mcp-airgap-v1/azure-devops-mcp-work-bundle.zip

Unzip, then give your work agent WORK-AGENT-BUILD-INSTRUCTIONS.md. The build
installs Microsoft's official pinned npm package; no application image import
is required. The builder needs approved package/base-image sources or mirrors.

For building and publishing inside work, start with
[WORK-AGENT-BUILD-INSTRUCTIONS.md](WORK-AGENT-BUILD-INSTRUCTIONS.md).
For deployment and the live demo, use [WORK-START-HERE.md](WORK-START-HERE.md).

| File | Purpose |
|---|---|
| Dockerfile | Connected build of complete Linux amd64 image |
| Dockerfile.offline | Offline application rebuild using imported dependencies image |
| build-and-export.sh | Build, test and export images/source/checksums outside the repo |
| app/ | Snapshot of the validated bridge, policy and pinned dependencies lockfile |
| kubernetes.template.json | No-download Deployment, Service, NetworkPolicy, RemoteMCPServer and Agent |
| config.example.json / render.py | Secret-free configuration and reviewed manifest rendering |
| install-secrets.py | Hidden-input PAT installation into the selected cluster |
| scripts/ | Shared kagent readiness and A2A invocation helpers |
| evidence/ | Sanitized lab proof and local image verification |

This bundle installs a scoped draft-PR integration alongside an existing kagent
platform. It requires approved network reachability to Azure DevOps Services or
a connected tool zone; a fully disconnected cluster cannot create cloud PRs.
