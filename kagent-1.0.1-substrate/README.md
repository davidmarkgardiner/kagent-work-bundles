# kagent 1.0.1 + Agent Substrate 1.0.0 (gVisor): reinstall bundle

## Answer: Substrate is required, and is not bundled

Checked on 26 November 2026 against the `v1.0.1` tag and the published charts.

- **Not bundled.** The upstream [`helm/README.md`](https://github.com/kagent-dev/kagent/blob/v1.0.1/helm/README.md)
  says: "The Kagent chart does not deploy or initialize PostgreSQL, and it does not
  install Substrate. A direct Helm install needs a prepared database, a connection
  Secret in the Kagent namespace, and Substrate installed as its own release."
- The `kagent` chart depends only on `kagent-tools` and `oauth2-proxy`.
- **Required.** In kagent 1.0 every agent runs on Substrate
  ([release notes](https://kagent.dev/docs/kagent/latest/reference/release-notes/1.0/)).
- `kagent install` (the CLI) installs Substrate **for** you as separate releases.
  That is not the same as the chart bundling it.
- kagent 0.10.x could pull Substrate in as a subchart (`substrate.enabled=true`).
  Do not carry that into 1.0.1.

Re-check it yourself, with no cluster access:

```sh
./scripts/verify-not-bundled.sh
```

## What is in this bundle

| File | Purpose |
| --- | --- |
| `charts.lock` | Six charts with versions and OCI digests |
| `images.txt` | Images to bring in |
| `gvisor-assets.txt` | gVisor release archives with SHA-256 (not container images) |
| `values/` | CLI config and registry overrides; replace `{{REGISTRY}}` |
| `scripts/` | Verify, seed gVisor assets, point at the internal copies |
| `WORK-AGENT-PROMPT.md` | Prompt for the agent doing the reinstall |

Also bring: the `kagent` CLI 1.0.1 binary and its `.sha256` from the
[release page](https://github.com/kagent-dev/kagent/releases/tag/v1.0.1), `helm`
3.17 or later, `kubectl`, and the `aws` CLI for the asset upload.

## Cluster prerequisites

- Certificate APIs: `PodCertificateRequest`, `ClusterTrustBundle`,
  `ClusterTrustBundleProjection`. The chart README names `certificates.k8s.io/v1beta1`;
  our earlier 1.37 AKS run served `v1`. Check discovery on the target. Kubernetes 1.37
  is what the upstream install guide asks for.
- Admission must allow privileged pods and `hostPath` for `atelet` and the workers.
- A default StorageClass (RustFS has a PVC, 1Gi by default).
- PostgreSQL. `kagent install` deploys a development one. For anything else, prepare it
  yourself for **both** kagent and Substrate and pass `--skip-database-setup`.
- A model endpoint reachable from the cluster.
- No Istio.

## Releases, in the order the CLI applies them

| # | Release | Namespace |
| --- | --- | --- |
| 1 | `kagent-crds` | `kagent` |
| 2 | `substrate-crds` | `ate-system` |
| 3 | prerequisites: CA and JWT pool Secrets, RustFS credentials (not a chart) | `ate-system`, `podcertificate-controller-system` |
| 4 | `substrate-podcert` | `podcertificate-controller-system` |
| 5 | PostgreSQL (development only) | `kagent` |
| 6 | `substrate-atelet`, then wait for the DaemonSet | `ate-system` |
| 7 | `substrate` with `atelet.enabled=false` | `ate-system` |
| 8 | `kagent` | `kagent` |

## Install

Recommended for a lab reinstall: use the CLI, because it also creates step 3 and the
Substrate settings a direct Helm install needs.

1. Mirror `images.txt` and `charts.lock` into the internal registry, keeping repository
   paths and digests. Record the digest of every tag-only image.
2. Replace `{{REGISTRY}}` in `values/`.
3. Preview, with no cluster change: from `values/`,
   `kagent --config kagent-cli-config.yaml install --dry-run --output-dir /path/to/new-dir`.
   Review every file; it can contain credentials. The export does not create step 3 or 5.
4. Install into an explicitly checked kube context:
   `kagent --config kagent-cli-config.yaml install` (set the provider key variable,
   for example `OPENAI_API_KEY`, first).
5. Seed gVisor and repoint it (next section).

### Direct Helm or GitOps instead

The CLI does this for you; by hand you must set all of it:

- Namespace label `ate.dev/api-access=true` on `kagent`.
- `preview: [PerTemplateSnapshotLocation, GoldenEgressPolicy]` on Substrate.
- `ateApi.authorization.bootstrapOwners` and `atenetRouter.ingressAllowedSPIFFEIDs`
  include `spiffe://cluster.local/ns/kagent/sa/kagent-controller`.
- `controller.substrateClientCertificate.enabled=true` on kagent.
- `credentialProvider.namespacePolicies` for the `kagent` atespace.
- `substrate-atelet` object-store settings and its credentials Secret.
- CA and JWT pools (step 3), and both database connection Secrets.

Source of truth: `helm/README.md` and `go/core/pkg/install/` at tag `v1.0.1`.

## gVisor assets: your old `runsc` import does not carry over

Substrate 1.0.0 downloads a `gvisor.tar.zstd` release archive. A bare `runsc` binary
is no longer accepted. By default `SandboxConfig/gvisor-default` points at the public
`gs://gvisor` bucket.

```sh
./scripts/seed-gvisor-assets.sh download ./gvisor      # connected host
kubectl -n ate-system port-forward svc/rustfs 9000:9000 &
./scripts/seed-gvisor-assets.sh upload ./gvisor        # after step 4 above
./scripts/use-internal-gvisor.sh                       # mutates the cluster
```

The scripts use `s3://` URLs. An S3-backed object-store plugin serves these and has no
public fallback for them, so **no `atelet` patch is needed** (verified in the lab run
below). A `gs://` URL for an internal bucket is **not** equivalent: it falls back to an
anonymous public download.

**Order matters when egress is denied.** With the stock config, `atelet` downloads
gVisor from public Google Storage during the install, as soon as the WorkerPool appears.
`kagent install` installs `substrate` and `kagent` in one run, so there is no built-in
pause to repoint in between. In the lab the repoint was done after the install. Whether
the install completes with public access already blocked is **not tested**.

## Storage

Nothing extra to provision for a lab: the chart brings RustFS and its bucket
(`ate-snapshots`). The default credentials are the well-known `rustfsadmin` pair; change
`rustfs.accessKey` and `rustfs.secretKey` for anything shared. Snapshot retention and
encryption still need a decision.

## Acceptance

1. All pods Ready in `ate-system`, `podcertificate-controller-system` and `kagent`.
2. A tool-free `Agent` reaches Ready
   ([example](../agent-platform-mkdocs/labs/kagent-1.0.1/agent-canary.yaml)).
3. A2A call returns `TASK_STATE_COMPLETED`: `POST /agents/{namespace}/{name}`, method
   `SendMessage`, header `A2A-Version: 1.0`. HTTP 200 alone is not success.
4. Suspend and resume: the same session still knows a marker you gave it.
5. With egress denied: a fresh node cache fetches gVisor from RustFS, with no public
   request in `atelet` logs.

## Lab run, 26 November 2026

Fresh Ubuntu 24.04 x86_64 VM, single-node kind, Kubernetes 1.37.0, upstream
[`kind-config.yaml`](https://github.com/kagent-dev/kagent/blob/v1.0.1/scripts/kind/kind-config.yaml)
at `v1.0.1` (feature gates `ClusterTrustBundle`, `ClusterTrustBundleProjection`,
`PodCertificateRequest`; `certificates.k8s.io/v1beta1` on). `kagent install` with this
bundle's CLI config, pulling from public registries.

| Check | Result |
| --- | --- |
| All six releases deployed, pods Ready | PASS |
| Running platform images are all listed in `images.txt` | PASS |
| gVisor seeded into RustFS and `SandboxConfig` repointed with the bundle scripts | PASS |
| Node cache wiped, `storage.googleapis.com` blocked in cluster DNS: both releases fetched from RustFS, no anonymous download | PASS |
| `Agent` Ready with a golden snapshot | PASS |
| A2A `SendMessage`, two turns, `TASK_STATE_COMPLETED` | PASS, **mock model** |
| Second turn saw the first turn's marker; `atelet` logged checkpoint and restore calls | PASS. This shows session continuity, not that process memory or files survived |

Lab-only fixes, not part of the bundle: the kind node needed a working
`/etc/resolv.conf`, and etcd fsync was disabled because the lab disk timed out installs.
Never disable etcd fsync on a real cluster.

## Still not tested

| Item | Note |
| --- | --- |
| Internal registry mirror (`{{REGISTRY}}`) | Registry override checked by rendering only |
| Full egress deny | Only the gVisor host was blocked |
| Real model provider, MCP tools | Mock model only |
| AKS, admission policy, managed StorageClass | Run on the target |
| External PostgreSQL, direct Helm or GitOps install | Only the CLI path was run |

Earlier runs, for context: kagent 1.0.1 passed on private AKS on 24 November, but with
**microVM** and the upstream `agent-substrate` build of v1.0.0, not the `kagent-dev`
build locked here. gVisor passed on AKS on 7 October on kagent 1.0.0-alpha8.
