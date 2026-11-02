#!/usr/bin/env bash
set -euo pipefail
context=${KUBE_CONTEXT:?Set KUBE_CONTEXT explicitly}
namespace=${FLOW_NAMESPACE:-agent-flow-demo}
tls_dir=${FLOW_TLS_DIR:?Set FLOW_TLS_DIR to a private directory outside the bundle}
python3 - "$tls_dir" "$(dirname "$0")/.." <<'PY'
from pathlib import Path
import sys
destination, bundle = (Path(p).resolve() for p in sys.argv[1:])
if destination == bundle or bundle in destination.parents:
    raise SystemExit("TLS material must be outside the public bundle")
PY
umask 077
mkdir -p "$tls_dir"
if [[ ! -f "$tls_dir/ca.crt" ]]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj /CN=Agent-Flow-Lab-CA -keyout "$tls_dir/ca.key" -out "$tls_dir/ca.crt" >/dev/null 2>&1
  openssl req -newkey rsa:2048 -nodes -subj /CN=localhost -keyout "$tls_dir/tls.key" -out "$tls_dir/tls.csr" >/dev/null 2>&1
  printf 'subjectAltName=DNS:localhost,DNS:flow.demo.test,IP:127.0.0.1\nextendedKeyUsage=serverAuth\n' > "$tls_dir/extensions.cnf"
  openssl x509 -req -days 30 -in "$tls_dir/tls.csr" -CA "$tls_dir/ca.crt" -CAkey "$tls_dir/ca.key" -CAcreateserial -extfile "$tls_dir/extensions.cnf" -out "$tls_dir/tls.crt" >/dev/null 2>&1
fi
kubectl --context "$context" create namespace "$namespace" --dry-run=client -o yaml | kubectl --context "$context" apply -f -
kubectl --context "$context" -n "$namespace" create secret tls flow-demo-tls --cert="$tls_dir/tls.crt" --key="$tls_dir/tls.key" --dry-run=client -o yaml | kubectl --context "$context" apply -f -
echo "Local TLS Secret ready. Public test CA is $tls_dir/ca.crt"
