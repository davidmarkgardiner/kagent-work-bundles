# Istio 1.31.4 for an air-gapped cluster: images, charts, and a policy-blocker check

The lab in this bundle installs Istio **1.31.4** (`versions.env`), sidecar mode, from `base` + `istiod`. This folder
is what you need to mirror it into your own registry and try it at work.

| File | What |
|---|---|
| `images.txt` | Every image the charts can pull, pinned to multi-arch digests, with the target path to keep |
| `charts.txt` | The five charts with their `.tgz` sha256 |
| `mirror.sh` | Dry run by default; `--apply` pulls, verifies and pushes charts to `oci://<REGISTRY>/helm/istio` and copies images (ACR import, crane, skopeo or docker) |
| `values-airgap.yaml` | One values file for `base`, `istiod`, `cni` and `ztunnel`: your registry as `global.hub`, CNI on |

## What you need

| Mode | Charts | Images |
|---|---|---|
| Sidecar (the lab) | `base`, `istiod` | `pilot`, `proxyv2` (sidecars, init and gateways all use `proxyv2`) |
| + Istio CNI (recommended at work) | `cni` | `install-cni` |
| + Istio ingress gateway | `gateway` | none extra (its image is `auto`: istiod injects `proxyv2`) |
| Ambient (not used in the lab) | `cni`, `ztunnel` | `install-cni`, `ztunnel` |
| Proxyless gRPC only | none | `busybox:1.28` (hard-coded in that injection template) |

Distroless variants of all four Istio images are listed too; set `global.variant: distroless` and mirror those rows.
istiod also has a built-in `agentgateway` GatewayClass whose image (`global.agentgateway.image`) has no default; the lab
installs Agent Gateway from its own chart instead, so it is not in this list.

## Mirror

```sh
REGISTRY=<registry> NEEDS=sidecar,cni ./mirror.sh            # print the plan
REGISTRY=<registry> NEEDS=sidecar,cni ./mirror.sh --apply    # do it (needs Docker Hub + blob.istio.io + registry login)
```

On ACR `mirror.sh` uses `az acr import` (server-side, keeps both architectures). `docker` is the last resort and copies
amd64 only.

## Install (order matters)

```sh
H="helm --kube-context <ctx>"; R=oci://<registry>/helm/istio; V=1.31.4; F=values-airgap.yaml   # with <REGISTRY> filled in
$H upgrade --install istio-base $R/base   --version $V -n istio-system --create-namespace -f $F --wait
$H upgrade --install istio-cni  $R/cni    --version $V -n istio-system -f $F --wait          # before istiod when cni.enabled
$H upgrade --install istiod     $R/istiod --version $V -n istio-system -f $F --wait
# optional ingress: $H upgrade --install istio-ingress $R/gateway --version $V -n istio-ingress --create-namespace --wait
```

Server-side dry-run first (`helm template ... | kubectl apply --dry-run=server -f -`) to see policy denials without
installing anything. Checked offline: rendering every chart with `values-airgap.yaml` points all images at
`<REGISTRY>/istio/...`, and with `cni.enabled` the injector adds the unprivileged `istio-validation` container instead
of the privileged `istio-init`. **Not yet installed from a mirror on any cluster.**

## Policy blockers to expect (check each, report, do not weaken a policy to pass)

| Likely blocker | Where | What to do |
|---|---|---|
| **AKS managed Istio add-on already enabled** (`asm-1-*` revision, `aks-istio-system`) | cluster | Do not install open-source Istio beside it. Report it; decide which one to use |
| Allowed-registries policy | every pod | Images must come from the approved registry: that is what `global.hub` and the mirror do |
| `NET_ADMIN` / `NET_RAW` capabilities, privileged init container (`istio-init`) | every injected pod | Use the Istio CNI (`cni.enabled: true`, already in `values-airgap.yaml`) |
| Privileged pod, `hostPath`, host network | the `istio-cni-node` DaemonSet | Expected: the CNI agent writes the node's CNI config. Needs a scoped policy exemption for `istio-system` (or the CNI namespace) |
| Required resource limits | istiod, sidecars, gateways | Set `resources` for istiod and `global.proxy.resources` if the policy demands limits |
| `runAsNonRoot`, read-only root filesystem, seccomp | istiod, gateways, sidecars | Istio's defaults run non-root with a read-only root; confirm the policy's exact rule against the rendered manifests |
| Webhook-creation or mutating-webhook restrictions | istiod's sidecar injector and validation webhooks | Report; injection and config validation need them |
| CRD-creation restrictions | `base` chart (Istio CRDs) | Report; a platform admin may need to apply `base` |

Report as: policy name, effect (deny or audit), the object it flagged, the rule, and the smallest change that would
satisfy it (Helm value, exemption, or "needs a decision").
