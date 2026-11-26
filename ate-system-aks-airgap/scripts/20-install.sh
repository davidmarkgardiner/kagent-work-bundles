#!/usr/bin/env bash
# Installs ate-system (Substrate) from the charts in this bundle. Safe to re-run.
# MUTATES the cluster. Run 00-preflight.sh first.
# EXTRA_ATELET_ARGS: optional extra helm args for substrate-atelet (lab registries).
set -euo pipefail
. "$(dirname "$0")/lib.sh"
: "${ASSETS_DIR:?set ASSETS_DIR}"
C="$HERE/charts"; V="$HERE/values"; N=ate-system; P=podcertificate-controller-system
REG=(--set "global.imageRegistry=$REGISTRY")
WAIT=(--wait --wait-for-jobs --timeout 10m)

say "1/8 CRDs"
h upgrade --install substrate-crds "$C/substrate-crds-$SUBSTRATE_VERSION.tgz" -n $N --create-namespace "${WAIT[@]}"

say "2/8 namespaces and signing keys"
k create namespace $P --dry-run=client -o yaml | k apply -f -
python3 "$HERE/scripts/create-keys.py" "$KUBE_CONTEXT"

say "3/8 RustFS credentials"
if ! k -n $N get secret ate-rustfs-credentials >/dev/null 2>&1; then
  k -n $N create secret generic ate-rustfs-credentials \
    --from-literal=AWS_ACCESS_KEY_ID="ate$(openssl rand -hex 6)" \
    --from-literal=AWS_SECRET_ACCESS_KEY="$(openssl rand -hex 24)"
fi
rustfs_value() { k -n $N get secret ate-rustfs-credentials -o "jsonpath={.data.$1}" | python3 -c 'import base64,sys;sys.stdout.write(base64.b64decode(sys.stdin.read()).decode())'; }

say "4/8 pod certificate controller"
h upgrade --install substrate-podcert "$C/substrate-podcert-$SUBSTRATE_VERSION.tgz" -n $P "${REG[@]}" "${WAIT[@]}"

say "5/8 development PostgreSQL"
sed -e "s#image: postgres:18-alpine@sha256:[0-9a-f]*#image: $REGISTRY/library/postgres:18-alpine#" \
    -e "s#storage: 500Gi#storage: ${PG_STORAGE:-32Gi}#" "$HERE/vendor/postgres.yaml" \
  | python3 "$HERE/scripts/size-postgres.py" "${STORAGE_CLASS:-}" | k apply -f -
k -n $N rollout status statefulset/postgres --timeout=10m
k -n $N exec -i postgres-0 -c postgres -- psql --no-psqlrc --set=ON_ERROR_STOP=1 --single-transaction \
  --username=postgres --dbname=atepg \
  --set=substrate_schema=substrate \
  --set=substrate_owner_role=substrate_owner --set=substrate_owner_user=substrate_owner_user --set=substrate_owner_password="" \
  --set=substrate_readwrite_role=substrate_readwrite --set=substrate_readwrite_user=substrate_readwrite_user --set=substrate_readwrite_password="" \
  < "$HERE/vendor/setup.sql"
base="postgresql://%s@postgres.$N.svc:5432/atepg?sslmode=verify-full&sslrootcert=/run/servicedns.podcert.ate.dev/trust-bundle.pem&sslcert=/run/postgres.podcert.ate.dev/%s.pem&sslkey=/run/postgres.podcert.ate.dev/%s.pem"
for pair in "readwrite readWriteConnectionString substrate_readwrite_user" "owner ownerConnectionString substrate_owner_user"; do
  set -- $pair
  # shellcheck disable=SC2059
  k -n $N create secret generic "substrate-postgres-$1" --from-literal="$2=$(printf "$base" "$3" "$3" "$3")" --dry-run=client -o yaml | k apply -f -
done

say "6/8 atelet"
ATELET=(-f "$V/common.yaml" -f "$V/atelet.yaml")
[ "${AKS_ACR_PROVIDER:-false}" = true ] && ATELET+=(-f "$HERE/aks/acr-credential-provider-values.yaml")
# shellcheck disable=SC2086
h upgrade --install substrate-atelet "$C/substrate-atelet-$SUBSTRATE_VERSION.tgz" -n $N "${REG[@]}" "${ATELET[@]}" ${EXTRA_ATELET_ARGS:-}
[ "${AKS_ACR_PROVIDER:-false}" = true ] && k -n $N patch daemonset atelet --type=strategic --patch-file "$HERE/aks/azure-json-patch.yaml"
k -n $N rollout status daemonset/atelet --timeout=10m

say "7/8 substrate control plane"
creds="$(mktemp)"; trap 'rm -f "$creds"' EXIT
printf 'rustfs:\n  accessKey: "%s"\n  secretKey: "%s"\n' "$(rustfs_value AWS_ACCESS_KEY_ID)" "$(rustfs_value AWS_SECRET_ACCESS_KEY)" > "$creds"
h upgrade --install substrate "$C/substrate-$SUBSTRATE_VERSION.tgz" -n $N "${REG[@]}" -f "$V/common.yaml" -f "$V/substrate.yaml" -f "$creds" "${WAIT[@]}"

say "8/8 gVisor into RustFS, then point SandboxConfig at it (before any WorkerPool exists)"
k -n $N port-forward svc/rustfs 19000:9000 >/dev/null 2>&1 & PF=$!
trap 'rm -f "$creds"; kill $PF 2>/dev/null || true' EXIT
sleep 5
for rel in $GVISOR_RELEASES; do
  AWS_ACCESS_KEY_ID="$(rustfs_value AWS_ACCESS_KEY_ID)" AWS_SECRET_ACCESS_KEY="$(rustfs_value AWS_SECRET_ACCESS_KEY)" \
    python3 "$HERE/scripts/s3put.py" http://127.0.0.1:19000 "ate-snapshots/gvisor/$rel/x86_64/gvisor.tar.zstd" "$ASSETS_DIR/$rel/x86_64/gvisor.tar.zstd"
done
k get sandboxconfig gvisor-default -o yaml | sed 's#gs://gvisor/releases/release/#s3://ate-snapshots/gvisor/#g' | k replace -f -
k get sandboxconfig gvisor-default -o yaml | grep 'url:'
say "installed"; k -n $N get pods
