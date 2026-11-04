# Image inventory for non-Substrate parity

Verified from official registries on 2026-11-04. The tested native API is
`kagent.dev/v1alpha2`. Use kagent and CRD Helm charts **0.10.4**, KRO **0.9.4**,
and agentgateway **1.7.0**. The latest overall kagent release observed was
`1.0.0-rc1`; its native agent lifecycle uses Substrate. It is not this bundle.

| Role | Image tag | Needed when |
| --- | --- | --- |
| kagent controller | `ghcr.io/kagent-dev/kagent/controller:0.10.4` | Always |
| Go agent runtime | `ghcr.io/kagent-dev/kagent/golang-adk:0.10.4` | Model-only Go agents, tested live |
| Go agent with skills | `ghcr.io/kagent-dev/kagent/golang-adk:0.10.4-full` | Go agents with Git or OCI skills |
| Skills loader | `ghcr.io/kagent-dev/kagent/skills-init:0.10.4` | Native skills enabled |
| Python agent runtime | `ghcr.io/kagent-dev/kagent/app:0.10.4` | Only when selecting runtime python |
| Python agent with skills | `ghcr.io/kagent-dev/kagent/app:0.10.4-full` | Only Python agents with skills |
| UI | `ghcr.io/kagent-dev/kagent/ui:0.10.4` | Optional, base values set replicas to zero |
| KRO controller | `registry.k8s.io/kro/kro:v0.9.4` | Always |
| Gateway controller | `cr.agentgateway.dev/controller:v1.7.0` | Always |
| Gateway data plane | `cr.agentgateway.dev/agentgateway:v1.7.0` | Always |
| Bundled PostgreSQL | `docker.io/library/postgres:18.6-alpine3.23` | Lab/demo only; work may reuse approved PostgreSQL |

The only custom image is the Golden verifier. Build `runtime/Dockerfile`, push it
to the approved registry, and put its resulting manifest digest into
`verifierImage` in the private platform profile. This bundle does not claim that
a public Golden image has been published. Its reference Python base is
`python@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c`.

The Kubernetes, GitLab and Denodo examples select existing RemoteMCPServer
objects. Their images belong to the receiving platform and are not installed
or versioned by this composition. Keep their existing approved deployment and
authentication. Native OCI skill content references also need mirroring when used.

## Digest-pinned image references

- kagent controller: `ghcr.io/kagent-dev/kagent/controller:0.10.4@sha256:e284fbddd327b06649f7e5ea4bc9df5e840c4b493538f07b4a36d9fa154e4af3`.
- Go agent runtime: `ghcr.io/kagent-dev/kagent/golang-adk:0.10.4@sha256:89d5a7df2c5da68797e2d9d78fa2f6531260f3836f51d2ac2fd9b4119fe518ed`.
- Go agent with skills: `ghcr.io/kagent-dev/kagent/golang-adk:0.10.4-full@sha256:aa068ef1c3a76b8a030268ac08707f356aa07a5738cd0a4e19fe457f2bbb9c8d`.
- Skills loader: `ghcr.io/kagent-dev/kagent/skills-init:0.10.4@sha256:5be7cb94c912a2f1b6d84450b31f1e2592d96c38e8a7ef65cbe1f270e01ee2fd`.
- Python agent runtime: `ghcr.io/kagent-dev/kagent/app:0.10.4@sha256:b811b0ddbf30d75976e2d29c2c9a0e8a604dcc04076f6eebda0f2dca9667f4f8`.
- Python agent with skills: `ghcr.io/kagent-dev/kagent/app:0.10.4-full@sha256:77ed9a2e43b84920119746cf8bdb9d9ff95167a22e11a78a1b4d5d9634d65cd0`.
- UI: `ghcr.io/kagent-dev/kagent/ui:0.10.4@sha256:a6edf70c6e8e76a94582ee563652cfa2a8c5f74f5df5d4832b2f250e49655899`.
- KRO controller: `registry.k8s.io/kro/kro:v0.9.4@sha256:eaf9fbaddd9d7f6cf400a8d47ab066b14cbef22b92a79be7bbdc7b3673376fb9`.
- Gateway controller: `cr.agentgateway.dev/controller:v1.7.0@sha256:87c1363bf0cbc7fdb375866e592294114c8763097d2d0c9fc45fcb1fe00a4ab8`.
- Gateway data plane: `cr.agentgateway.dev/agentgateway:v1.7.0@sha256:60216aafb03d37f94e952ff3d51d2f630a65b10ecaebdc0a864882f92610c45b`.
- Bundled PostgreSQL: `docker.io/library/postgres:18.6-alpine3.23@sha256:1a0c23d53c1ad77468c8653fa6eed4f4105cfbef9e6f027bc1dfeb16949a8c29`.

The machine-readable source is [versions.lock.json](versions.lock.json).
`helm-values-no-substrate.yaml` pins the controller, normal runtimes, full skills
runtimes and skills loader. A tag alone is insufficient when mirroring an image.
Preserve the manifest digest, or record and review the mirror manifest mapping.
The preflight accepts a mirror repository when its digest matches the lock.

Upstream 0.10.4 provides the runtime artifacts and charts but no matching CLI
binary. This demo uses Helm, kubectl and its own A2A query script. Do not substitute
a 1.x CLI to apply or interpret classic manifests.

Official release and implementation references:

- https://github.com/kagent-dev/kagent/releases/tag/v0.10.4
- https://github.com/kagent-dev/kagent/releases/tag/v1.0.0-rc1
- https://github.com/kagent-dev/kagent/blob/v0.10.4/helm/kagent/values.yaml
- https://github.com/kagent-dev/kagent/blob/v1.0.0-rc1/go/core/internal/controller/status.go
