# ate-system (Agent Substrate 1.0.0, gVisor) on air-gapped AKS

Goal of this phase: **`ate-system` installed and proven working.** kagent comes later.
Hand [`WORK-AGENT-PROMPT.md`](WORK-AGENT-PROMPT.md) to the work agent.

## Where it comes from

Substrate has its own repository, [`kagent-dev/substrate`](https://github.com/kagent-dev/substrate)
(the kagent team's fork of `agent-substrate/substrate`), tag `v1.0.0`. It is not part of
the kagent repository and the kagent chart does not contain it.

## What you need to bring in

| Item | How | In this bundle |
| --- | --- | --- |
| 4 Helm charts | Already here. They are **not** GitHub release downloads; they were `helm pull`ed from `oci://ghcr.io/kagent-dev/substrate/helm` | `charts/` + `SHA256SUMS` |
| 13 images (12 + 1 for the smoke test) | Your image import process. Keep the paths and digests | `images.txt`, `images.lock` |
| 2 gVisor archives, about 57 MB each | **File transfer**, not images | `gvisor-assets.txt` |
| `kubectl-ate` v1.0.0 (linux-amd64) | File transfer from the [release page](https://github.com/kagent-dev/substrate/releases/tag/v1.0.0), check its `.sha256` | no |
| PostgreSQL manifest and SQL | Already here | `vendor/` |

gVisor download, on a connected machine, for each line of `gvisor-assets.txt`:

```
https://storage.googleapis.com/gvisor/releases/release/<release>/x86_64/gvisor.tar.zstd
```

Save as `<ASSETS_DIR>/<release>/x86_64/gvisor.tar.zstd`. An old bare `runsc` binary does
not work with 1.0.0.

Charts install straight from the `.tgz` files, so they do not have to be in the registry.
If policy says they must be: `helm push charts/<file>.tgz oci://<registry>/kagent-dev/substrate/helm`.
The scripts as written use the local files, and the push was not tested.

## Prerequisites (sort these first)

| # | Prerequisite | Value / owner |
| --- | --- | --- |
| P1 | A **non-production** AKS cluster, Kubernetes **1.37**, amd64 nodes. Confirm with `az aks get-versions --location {{AZURE_REGION}}` | `{{AKS_CLUSTER}}` |
| P2 | Cluster-admin for the install (CRDs, ClusterRoles, admission policies) | `{{WHO}}` |
| P3 | **Policy exemption**: privileged pods and `hostPath` in `ate-system` and in any namespace running a WorkerPool (`ate-smoke` for the test). Azure Policy, Kyverno and Pod Security all apply | `{{POLICY_OWNER}}` |
| P4 | ACR with the images, and `AcrPull` for the AKS kubelet identity | `{{ACR_NAME}}` |
| P5 | The node must have `/etc/kubernetes/azure.json` and `/var/lib/kubelet/credential-provider/acr-credential-provider`. `atelet` uses them to pull actor images | confirm on a node |
| P6 | A StorageClass for two disks: PostgreSQL (32Gi) and RustFS (20Gi) | `{{STORAGE_CLASS}}` |
| P7 | If the cluster's ServiceAccount issuer is the public AKS OIDC URL, `ate-api` must reach it on 443 | `{{FIREWALL_OWNER}}` |
| P8 | Jumpbox with `kubectl`, `helm` 3.17+, `python3`, `openssl` 3, `curl`, `kubectl-ate` | `{{JUMPBOX}}` |
| P9 | Accept for this PoC: development PostgreSQL (one replica), snapshots in in-cluster RustFS, signing CAs that **expire after one year with no renewal** | `{{DECISION_OWNER}}` |

## The plan

Each step has a gate. Do not pass a failed gate.

| Step | Action | Gate |
| --- | --- | --- |
| 1 | Import images; transfer gVisor and `kubectl-ate` | Every `images.lock` line exists in ACR with the same digest |
| 2 | `cp env.example env.sh`, fill it in, `. ./env.sh` | no `{{...}}` left |
| 3 | `./scripts/00-preflight.sh` (read-only) | `PREFLIGHT PASS`; the `CHECK` line resolved against P7 |
| 4 | Owner approves | written approval |
| 5 | `./scripts/20-install.sh` | exits 0; all pods in `ate-system` Running or Completed; `url:` lines start `s3://` |
| 6 | `./scripts/30-smoke-test.sh` | `SMOKE TEST PASS` |
| 7 | Report | table of steps with PASS / FAIL / NOT RUN and evidence |

Check one image digest in ACR:

```sh
az acr repository show -n {{ACR_NAME}} --image kagent-dev/substrate/ateapi:v1.0.0 --query digest -o tsv
```

## What the install does

1. `substrate-crds` chart.
2. Creates the signing-key Secrets and `ate-api-authentication` ConfigMap, which **no chart
   creates** (`scripts/create-keys.py` mirrors the kagent installer's code).
3. Random RustFS credentials in a Secret (not the chart's `rustfsadmin` default).
4. `substrate-podcert` chart.
5. Development PostgreSQL from `vendor/`, sized down.
6. `substrate-atelet` chart, plus the AKS ACR credential provider.
7. `substrate` chart.
8. Uploads gVisor into RustFS and repoints `SandboxConfig` to `s3://`, **before any
   WorkerPool exists**, so nothing tries to reach the internet.

A later `helm upgrade` of `substrate` resets `SandboxConfig`; re-running
`20-install.sh` repoints it. Under GitOps, carry that rewrite as a post-renderer.

## If a step fails

| Symptom | Likely cause |
| --- | --- |
| `ImagePullBackOff` on platform pods | Image path or `AcrPull` (P4) |
| Golden snapshot or actor start fails pulling an image | `atelet` ACR credential provider (P5): `kubectl -n ate-system logs ds/atelet -c atelet` |
| `ate-api-server` / `ate-idp-server` crash loop mentioning the JWT or CA pool | A signing Secret is malformed. Report it; do not delete Secrets without approval |
| `ate-api` errors about issuer or JWKS | P7 |
| Pods Pending on a `podCertificate` volume | `podcertificate-controller` logs; Kubernetes version (P1) |
| Actor create says image `must be pinned by digest` | Use `image@sha256:...` |
| `atelet` logs `downloading it anonymously` | `SandboxConfig` still has `gs://` URLs |
| Smoke test needs debugging | `KEEP=true ./scripts/30-smoke-test.sh`, then `kubectl-ate get actors -A` |

## Removal (needs explicit approval; **not tested**)

Delete the smoke resources, then `helm uninstall` `substrate`, `substrate-atelet`,
`substrate-podcert`, `substrate-crds`. PersistentVolumeClaims, Secrets, namespaces and the
host directory `/var/lib/ate` stay behind and each needs its own approval. Easiest on a
disposable cluster: delete the cluster.

## What was tested at home, 26 November 2026

Ubuntu x86_64 VM, kind, Kubernetes 1.37.0, a local registry standing in for ACR (images
copied with digests preserved), **all traffic from the cluster network to anywhere else
rejected**: `ghcr.io`, `docker.io` and `storage.googleapis.com` unreachable.

| Check | Result |
| --- | --- |
| `00-preflight.sh` on an empty cluster | PASS (and it refused an existing install) |
| `20-install.sh` from empty, from this bundle's chart files | PASS, all pods Running |
| `20-install.sh` re-run over the install | PASS, signing keys unchanged |
| gVisor loaded from RustFS only, no anonymous download | PASS |
| `30-smoke-test.sh`: golden snapshot, suspend to object storage, all workers deleted, resume: memory, volume and root filesystem counters continued | PASS |

**Not tested, because there is no AKS at home:** ACR pulls and the ACR credential provider
(rendered and patch-applied offline only), Azure Policy, Azure disks, the AKS OIDC issuer,
multiple nodes, node restarts. Also not tested: the chart push to ACR, removal.

Lab-only settings that do not apply at work: etcd fsync off (slow lab disk), a registry
rewrite flag on `atelet`, node DNS override.

Earlier related evidence: gVisor Substrate on AKS passed on 7 October with older versions
([handoff](../agent-substrate/AKS-EVAL-WORK-AGENT-HANDOFF.md)).

## Later: kagent

Not part of this phase. When it comes:

- kagent needs its own database and connection Secrets.
- Add `spiffe://cluster.local/ns/kagent/sa/kagent-controller` to
  `atenetRouter.ingressAllowedSPIFFEIDs` and `ateApi.authorization.bootstrapOwners`
  (keep `system:serviceaccount:ate-system:ate-client`), add `credentialProvider.namespacePolicies`,
  and label the namespace `ate.dev/api-access=true`.
- [`../kagent-1.0.1-substrate`](../kagent-1.0.1-substrate/README.md) installs **both** with
  the kagent CLI. Adding kagent on top of this phase's manual install is **not tested**.
