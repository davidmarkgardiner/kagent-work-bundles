# ate-system 1.0.1: next steps (front sheet)

Read this first. For Substrate 1.0.1 it overrides `README.md`; the README still explains why each
piece exists. Work **one stage at a time**: run it, check the exit gate, report back, stop.

## Where you are

Only the three Substrate **CRDs** are installed. Substrate itself is not running. Installing CRDs
only teaches the API server new types. Still needed: workload charts, images, keys, database,
object storage, gVisor archives, then a WorkerPool.

## What looked blocked, and what is not

| Reported blocker | Actual position |
| --- | --- |
| No 1.0.1 PodCert or atelet charts | **They are published.** All four charts exist at `oci://ghcr.io/kagent-dev/substrate/helm/<name>` version `1.0.1`, and are in `charts/` here. Do not mix in 1.0.0 side charts. |
| No 1.0.1 images | Public. List with digests below; import them. |
| RustFS and PostgreSQL Secrets need a provider | **Not for a proof of concept.** The install generates them. The PostgreSQL connection strings contain no password (client-certificate auth). No Key Vault change needed, if your policy allows generated in-cluster Secrets. |
| Admission needs pod label and limits | Handled by `policy/` (stage 3). |
| `00-preflight.sh` cannot be run | Expected to FAIL now: namespace and CRDs exist. Its privileged probe also has no label or limits. Skip it; stage 3 replaces it. |
| GitOps still on 0.0.9 values and `v1alpha1` WorkerPool | Real. Do not resume Flux with those. Prove by direct Helm first, then port (stage 8). |

Installed CRD chart is a `-SNAPSHOT` build. Use the released `1.0.1` for all four charts.

## Evidence level

- Lab-proven: this install sequence with **1.0.0**, kind, Kubernetes 1.37, all egress blocked.
- Checked offline only: 1.0.1 charts render with `policy/`; 11 workloads all get the label and limits.
- 1.0.0 to 1.0.1 chart changes: version, one `keep` annotation on the RustFS volume claim, egress log level.
- **Not tested:** a 1.0.1 install, AKS, ACR pulls by atelet, your admission rules, Flux.

## Stage 1: confirm the starting point (read-only)

```sh
kubectl config current-context
helm list -A
kubectl get crd | grep ate.dev
kubectl get ns ate-system podcertificate-controller-system --show-labels
kubectl get pods -n ate-system
kubectl get pods -A | grep -i kagent
helm template substrate-crds charts/substrate-crds-1.0.1.tgz -n ate-system | kubectl diff -f -
```

**Report:** non-production confirmed by the cluster owner; CRD release name and namespace; the
diff; whether kagent is running **in this context** (the last report does not say); owner approval
for a direct Helm install while Flux stays suspended.

**Gate:** release is `substrate-crds` in `ate-system`; no WorkerPool; approval given. A different
release name or an owner who requires GitOps only: stop and say so.

## Stage 2: get the artifacts in

Charts: in `charts/` (`cd charts && shasum -a 256 -c SHA256SUMS`).

Images. Import with the normal process, keeping the path under `{{REGISTRY}}` and the digest:

| Public source | Path under `{{REGISTRY}}` | Digest |
| --- | --- | --- |
| `ghcr.io/kagent-dev/substrate/ate-idp-server:v1.0.1` | `kagent-dev/substrate/ate-idp-server:v1.0.1` | `sha256:f27e38b0616c22caf067612105f569bd8ec54860bb6a6bb36862fd1d6130060a` |
| `ghcr.io/kagent-dev/substrate/ateapi:v1.0.1` | `kagent-dev/substrate/ateapi:v1.0.1` | `sha256:fb8e2c71e8f8c2f22748ae0994ea1313b16fb774d626bf0cdcfce5fb335b6f47` |
| `ghcr.io/kagent-dev/substrate/atecontroller:v1.0.1` | `kagent-dev/substrate/atecontroller:v1.0.1` | `sha256:7a535bc5fe22e4db18d7444ecb2d4da9c5d344e69383ca79347932790b724829` |
| `ghcr.io/kagent-dev/substrate/atelet:v1.0.1` | `kagent-dev/substrate/atelet:v1.0.1` | `sha256:f72d7bf21d6424548330c75815e9efa94680bda7b40c2bbbc5e4007aabb7c043` |
| `ghcr.io/kagent-dev/substrate/ateworker-gvisor:v1.0.1` | `kagent-dev/substrate/ateworker-gvisor:v1.0.1` | `sha256:97ca74cd2cabc3fd28ac67790ed3b1f25b7b4247709a316ff374a428822c420e` |
| `ghcr.io/kagent-dev/substrate/kubernetes-secrets:v1.0.1` | `kagent-dev/substrate/kubernetes-secrets:v1.0.1` | `sha256:6953ba2b57f8886dc9fb9122bb2ab098c3debe3b0cce5b14929f8efeb29f8c5b` |
| `ghcr.io/kagent-dev/substrate/objectstore-plugin:v1.0.1` | `kagent-dev/substrate/objectstore-plugin:v1.0.1` | `sha256:7396d01fdbf162158fdd2a24649b780fcb5b161c724e6a6824efdcb6d2442107` |
| `ghcr.io/kagent-dev/substrate/podcertcontroller:v1.0.1` | `kagent-dev/substrate/podcertcontroller:v1.0.1` | `sha256:f6c4a40f9afedc46df580470ca12cc309b135543cda64396968936800fd4ee7f` |
| `cr.agentgateway.dev/agentgateway:v1.7.0` | `agentgateway:v1.7.0` | `sha256:60216aafb03d37f94e952ff3d51d2f630a65b10ecaebdc0a864882f92610c45b` |
| `docker.io/rustfs/rustfs:1.0.3` | `rustfs/rustfs:1.0.3` | `sha256:9ca9559533b537d10482fe923288b676ad08f92a7069d9a17327fbae3cab688b` |
| `docker.io/amazon/aws-cli:2.38.5` | `amazon/aws-cli:2.38.5` | `sha256:c8156a0e74e13929a42d7e60f0d4e14e7d28d980cd21822505d4bff80e5460c1` |
| `docker.io/library/postgres:18-alpine` | `library/postgres:18-alpine` | `sha256:9a8afca54e7861fd90fab5fdf4c42477a6b1cb7d293595148e674e0a3181de15` |
| `docker.io/library/python:3.13-alpine` | `library/python:3.13-alpine` | `sha256:9ef1a599f863231c3d91e941389bfdc4a2d6070557243d54df1a4e57015b960e` |

Files, transferred to the jumpbox:

- `kubectl-ate` 1.0.1 linux-amd64 and its `.sha256`, from
  <https://github.com/kagent-dev/substrate/releases/tag/v1.0.1>
- gVisor, saved as `<ASSETS_DIR>/<release>/x86_64/gvisor.tar.zstd`:

| URL | sha256 |
| --- | --- |
| `https://storage.googleapis.com/gvisor/releases/release/20261026.0/x86_64/gvisor.tar.zstd` | `708afc62f2ee82d19930c703e85f9dab4f27a78c0aec40c0f55eb1040107f1a7` |
| `https://storage.googleapis.com/gvisor/releases/release/20261102.0/x86_64/gvisor.tar.zstd` | `a1439ffbba7d212e0fde32ea79fa9bb51cbc4c5f6c16af1f047260290b861d42` |

**Gate:** every image digest in the registry matches; both archive checksums match;
`kubectl-ate` runs. An old bare `runsc` binary does not work.

## Stage 3: set up and pass admission

```sh
cp env.example env.sh      # never commit env.sh
# in env.sh set KUBE_CONTEXT, REGISTRY, ASSETS_DIR, STORAGE_CLASS=managed-csi, and add:
export SUBSTRATE_VERSION=1.0.1
export POST_RENDERER="$PWD/policy/post-render.sh"
export POLICY_FILTER="$PWD/policy/post-render.sh"
export EXTRA_VALUES="$PWD/policy/resources.yaml"
source env.sh
helm version --short        # needs Helm 3; Helm 4 changed post-renderers
```

Ask the policy owner for a **privileged + hostPath** exemption in `ate-system` and `ate-smoke`.
Then probe every pod the charts will create (server dry run, nothing is created):

```sh
D=$(mktemp -d); C=charts; V=values; G="--set global.imageRegistry=$REGISTRY -f $EXTRA_VALUES --post-renderer $POST_RENDERER"
helm template substrate-podcert $C/substrate-podcert-1.0.1.tgz -n podcertificate-controller-system $G > $D/podcert.yaml
helm template substrate-atelet $C/substrate-atelet-1.0.1.tgz -n ate-system $G -f $V/common.yaml -f $V/atelet.yaml > $D/atelet.yaml
helm template substrate $C/substrate-1.0.1.tgz -n ate-system $G -f $V/common.yaml -f $V/substrate.yaml > $D/substrate.yaml
sed -e "s#image: postgres:18-alpine@sha256:[0-9a-f]*#image: $REGISTRY/library/postgres:18-alpine#" vendor/postgres.yaml \
  | "$POLICY_FILTER" > $D/postgres.yaml
for f in $D/*.yaml; do
  kubectl create --dry-run=client -f "$f" -o json \
  | jq -c 'if .kind=="List" then .items[] else . end
      | select(.kind|IN("Deployment","DaemonSet","StatefulSet","Job"))
      | [.spec.volumeClaimTemplates[]?.metadata.name] as $claims
      | {apiVersion:"v1",kind:"Pod",metadata:{name:(.metadata.name+"-probe"),labels:.spec.template.metadata.labels},
         spec:(.spec.template.spec|del(.serviceAccountName,.serviceAccount,.priorityClassName)
               + {volumes:((.volumes//[]) + [$claims[]|{name:.,emptyDir:{}}])})}' \
  | while read -r pod; do echo "$pod" | kubectl apply --dry-run=server -n ate-system -f -; done
done
```

The podcert pod is probed in `ate-system` because its namespace does not exist yet.

**Gate:** every probe accepted. A rejection: report the exact message; the fix goes in `policy/`.

## Stage 4: prove the paths that only fail late

1. **atelet image pulls.** atelet pulls worker and actor images itself, not through the kubelet.
   On AKS set `AKS_ACR_PROVIDER=true` in `env.sh` and review `aks/` first: it mounts the node's
   credential provider and `/etc/kubernetes/azure.json`. A successful kubelet pull proves nothing here.
2. **OIDC egress.** If the issuer from
   `kubectl get --raw /.well-known/openid-configuration` is public, a pod in `ate-system` must reach
   it on 443. Test from a labelled, limited pod.
3. **Disk.** `managed-csi` is allowed to provision (the install creates 32Gi and 20Gi claims).

**Gate:** issuer reachable; platform owner accepts the AKS provider mount. Item 1 is only truly
proven in stage 7.

## Stage 5: decide the PoC choices

Owner says yes or no to each: single development PostgreSQL in cluster; RustFS in cluster; generated
Secrets; signing CAs that **expire after one year with no auto-renewal**. Any "no" stops here: it
needs an external design, and the `ATE-SYSTEM-1.0.1-SECRET-REQUIREMENTS.md` work applies.

## Stage 6: install (changes the cluster)

```sh
source env.sh && ./scripts/20-install.sh
```

It upgrades the CRD release to 1.0.1, creates signing keys once (never overwrites them), RustFS
credentials, pod certificate controller, PostgreSQL, atelet, control plane, then loads gVisor into
RustFS and repoints `SandboxConfig` before any WorkerPool exists. Safe to re-run.

```sh
kubectl get pods -n ate-system
kubectl get pods -n podcertificate-controller-system
kubectl get pvc -n ate-system
kubectl get sandboxconfig gvisor-default -o yaml | grep url:
```

**Gate:** all pods Ready, claims Bound, every gVisor URL starts `s3://`. On failure stop at that
step and report pod events and logs; the README failure table covers the common ones.

## Stage 7: smoke test (the real proof)

Put `kubectl-ate` 1.0.1 on `PATH`.

```sh
source env.sh && KEEP=true ./scripts/30-smoke-test.sh
kubectl get workerpool,pods -n ate-smoke
```

It creates a 2-replica WorkerPool (`ate.dev/v1`, `workerImage`), a stateful actor, a golden
snapshot, suspends, deletes the workers and resumes. For your own pool use a digest-pinned image:

```yaml
apiVersion: ate.dev/v1
kind: WorkerPool
metadata: {name: default, namespace: <namespace>}
spec:
  replicas: 2
  workerImage: <REGISTRY>/kagent-dev/substrate/ateworker-gvisor:v1.0.1@sha256:97ca74cd2cabc3fd28ac67790ed3b1f25b7b4247709a316ff374a428822c420e
  sandboxClasses: [{name: gvisor}]
  template:
    labels: {istio-injection: disabled, sidecar.istio.io/inject: "false"}
    resources:
      requests: {cpu: 100m, memory: 1Gi}
      limits: {cpu: "1", memory: 1Gi}
```

**Gate:** script reports pass. This proves atelet pulls, gVisor, snapshots and storage. Re-run
without `KEEP` to clean up.

## Stage 8: move into GitOps (only after stage 7)

1. Replace the 0.0.9 values with `values/` plus `policy/resources.yaml`; chart version `1.0.1` for all four releases.
2. Add the same label and limit patches as `postRenderers.kustomize.patches` on each HelmRelease.
3. Keep release names and namespaces identical so Flux adopts them.
4. Keys, credentials and the `ate-api-authentication` ConfigMap are not chart-managed: keep them out
   of pruning, and never regenerate keys.
5. Keep the gVisor `s3://` repoint in Git or a documented step: a chart upgrade can restore `gs://`.
6. Update the WorkerPool to `ate.dev/v1`.

**Gate:** diff shows no unexpected change before Flux is resumed. kagent wiring comes after this.

## Report template

```
Stage:        Result: PASS / FAIL / BLOCKED
Commands run:
Evidence (sanitized):
Exact error:
Decision needed, and from whom:
```
