#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REFRESH_SCRIPT="$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT

make_exec_kubeconfig() {
  local output="$1" context="$2"
  sed "s/__CONTEXT__/$context/g" >"$output" <<'EOF'
apiVersion: v1
kind: Config
clusters:
  - name: __CONTEXT__
    cluster:
      server: https://example.invalid
      insecure-skip-tls-verify: true
users:
  - name: __CONTEXT__
    user:
      exec:
        apiVersion: client.authentication.k8s.io/v1
        command: /bin/true
        interactiveMode: Never
contexts:
  - name: __CONTEXT__
    context:
      cluster: __CONTEXT__
      user: __CONTEXT__
current-context: __CONTEXT__
EOF
}

make_exec_kubeconfig "$TEST_DIR/one.config" source-one
make_exec_kubeconfig "$TEST_DIR/two.config" source-two

cat >"$TEST_DIR/registry.json" <<'EOF'
{"clusters":[
  {"alias":"cluster-one","provider":"static","sourceFile":"one.config"},
  {"alias":"cluster-two","provider":"static","sourceFile":"two.config"}
]}
EOF

positive_output="$(
  REGISTRY_PATH="$TEST_DIR/registry.json" \
  STATIC_SOURCE_DIR="$TEST_DIR" \
  WORK_DIR="$TEST_DIR/work-positive" \
  ALLOW_STATIC_SOURCES=true \
  SKIP_CONNECTIVITY=true \
  VALIDATE_ONLY=true \
  "$REFRESH_SCRIPT"
)"
grep -q '^VALIDATION_OK contexts=2 sha256=' <<<"$positive_output"

cat >"$TEST_DIR/duplicate.json" <<'EOF'
{"clusters":[
  {"alias":"same","provider":"static","sourceFile":"one.config"},
  {"alias":"same","provider":"static","sourceFile":"two.config"}
]}
EOF
if REGISTRY_PATH="$TEST_DIR/duplicate.json" STATIC_SOURCE_DIR="$TEST_DIR" \
  WORK_DIR="$TEST_DIR/work-duplicate" ALLOW_STATIC_SOURCES=true \
  SKIP_CONNECTIVITY=true VALIDATE_ONLY=true "$REFRESH_SCRIPT" >/dev/null 2>&1; then
  echo "expected duplicate alias validation to fail" >&2
  exit 1
fi

sed '/exec:/,$d' "$TEST_DIR/one.config" >"$TEST_DIR/token.config"
cat >>"$TEST_DIR/token.config" <<'EOF'
      token: definitely-not-a-real-token
contexts:
  - name: token-source
    context:
      cluster: source-one
      user: source-one
current-context: token-source
EOF
cat >"$TEST_DIR/token-registry.json" <<'EOF'
{"clusters":[
  {"alias":"token-cluster","provider":"static","sourceFile":"token.config"}
]}
EOF
if REGISTRY_PATH="$TEST_DIR/token-registry.json" STATIC_SOURCE_DIR="$TEST_DIR" \
  WORK_DIR="$TEST_DIR/work-token" ALLOW_STATIC_SOURCES=true \
  SKIP_CONNECTIVITY=true VALIDATE_ONLY=true "$REFRESH_SCRIPT" >/dev/null 2>&1; then
  echo "expected embedded credential validation to fail" >&2
  exit 1
fi

REAL_KUBECTL_BIN="$(command -v kubectl)"
export REAL_KUBECTL_BIN
export MOCK_CONTROL_DIR="$TEST_DIR/mock-control"
mkdir -p "$TEST_DIR/bin" "$MOCK_CONTROL_DIR/deployments"
cat >"$TEST_DIR/bin/kubectl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != "--context" || "${2:-}" != "mock-control" ]]; then
  exec "$REAL_KUBECTL_BIN" "$@"
fi
shift 2
[[ "${1:-}" == "--namespace" ]] || exit 2
shift 2

if [[ "${1:-}" == "get" && "${2:-}" == "secret" ]]; then
  cat "$MOCK_CONTROL_DIR/live-secret.json"
  exit 0
fi
if [[ "${1:-}" == "create" && "${2:-}" == "secret" && "${3:-}" == "generic" ]]; then
  printf '%s\n' '{"apiVersion":"v1","kind":"Secret","metadata":{"name":"aks-mcp-fleet-kubeconfig","namespace":"mock-target"},"type":"Opaque","data":{"candidate":"Y2FuZGlkYXRl"}}'
  exit 0
fi
if [[ "${1:-}" == "replace" ]]; then
  manifest=""
  server_dry_run=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run=server) server_dry_run=true; shift ;;
      -f) manifest="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  [[ -n "$manifest" ]] || exit 2
  if [[ "$server_dry_run" == "false" ]]; then
    cp "$manifest" "$MOCK_CONTROL_DIR/live-secret.json"
    printf 'replace secret\n' >>"$MOCK_CONTROL_DIR/operations.log"
  fi
  exit 0
fi
if [[ "${1:-}" == "get" && "${2:-}" == "deployment" ]]; then
  deployment_name="$3"
  marker_file="$MOCK_CONTROL_DIR/deployments/$deployment_name"
  marker=""
  [[ ! -f "$marker_file" ]] || marker="$(<"$marker_file")"
  jq -cn --arg marker "$marker" '{spec:{template:{metadata:{annotations:(if $marker == "" then {} else {"platform.example.com/kubeconfig-sha256":$marker} end)}}}}'
  exit 0
fi
if [[ "${1:-}" == "patch" && "${2:-}" == "deployment" ]]; then
  deployment_name="$3"
  patch_body=""
  shift 3
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -p) patch_body="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  printf 'patch %s\n' "$deployment_name" >>"$MOCK_CONTROL_DIR/operations.log"
  if [[ "$deployment_name" == "aks-mcp-cluster-two" && ! -f "$MOCK_CONTROL_DIR/failure-used" ]]; then
    touch "$MOCK_CONTROL_DIR/failure-used"
    exit 1
  fi
  jq -r '.spec.template.metadata.annotations["platform.example.com/kubeconfig-sha256"]' \
    <<<"$patch_body" >"$MOCK_CONTROL_DIR/deployments/$deployment_name"
  exit 0
fi
if [[ "${1:-}" == "rollout" && "${2:-}" == "status" && "${3:-}" == "deployment" ]]; then
  printf 'status %s\n' "$4" >>"$MOCK_CONTROL_DIR/operations.log"
  exit 0
fi

exit 2
EOF
chmod +x "$TEST_DIR/bin/kubectl"

cat >"$MOCK_CONTROL_DIR/live-secret.json" <<'EOF'
{"apiVersion":"v1","kind":"Secret","metadata":{"name":"aks-mcp-fleet-kubeconfig","namespace":"mock-target","resourceVersion":"1","annotations":{"platform.example.com/kubeconfig-sha256":"bootstrap"}},"type":"Opaque","data":{"bootstrap":""}}
EOF

if PATH="$TEST_DIR/bin:$PATH" REGISTRY_PATH="$TEST_DIR/registry.json" \
  STATIC_SOURCE_DIR="$TEST_DIR" WORK_DIR="$TEST_DIR/work-reconcile" \
  ALLOW_STATIC_SOURCES=true SKIP_CONNECTIVITY=true CONTROL_CONTEXT=mock-control \
  TARGET_NAMESPACE=mock-target ROLLOUT_MAX_PARALLEL=1 \
  "$REFRESH_SCRIPT" >"$TEST_DIR/first-reconcile.out" 2>"$TEST_DIR/first-reconcile.err"; then
  echo "expected first rollout reconciliation to fail" >&2
  exit 1
fi

candidate_hash="$(jq -r '.metadata.annotations["platform.example.com/kubeconfig-sha256"]' \
  "$MOCK_CONTROL_DIR/live-secret.json")"
[[ "$candidate_hash" != "bootstrap" && -n "$candidate_hash" ]]
[[ "$(<"$MOCK_CONTROL_DIR/deployments/aks-mcp-cluster-one")" == "$candidate_hash" ]]
[[ ! -f "$MOCK_CONTROL_DIR/deployments/aks-mcp-cluster-two" ]]
grep -E '^(patch|status) ' "$MOCK_CONTROL_DIR/operations.log" | head -n 3 \
  >"$TEST_DIR/first-rollout-order"
diff -u - "$TEST_DIR/first-rollout-order" <<'EOF'
patch aks-mcp-cluster-one
status aks-mcp-cluster-one
patch aks-mcp-cluster-two
EOF

second_output="$(
  PATH="$TEST_DIR/bin:$PATH" REGISTRY_PATH="$TEST_DIR/registry.json" \
  STATIC_SOURCE_DIR="$TEST_DIR" WORK_DIR="$TEST_DIR/work-reconcile" \
  ALLOW_STATIC_SOURCES=true SKIP_CONNECTIVITY=true CONTROL_CONTEXT=mock-control \
  TARGET_NAMESPACE=mock-target ROLLOUT_MAX_PARALLEL=1 \
  "$REFRESH_SCRIPT"
)"
grep -q '^UNCHANGED contexts=2 sha256=' <<<"$second_output"
[[ "$(<"$MOCK_CONTROL_DIR/deployments/aks-mcp-cluster-one")" == "$candidate_hash" ]]
[[ "$(<"$MOCK_CONTROL_DIR/deployments/aks-mcp-cluster-two")" == "$candidate_hash" ]]
[[ "$(grep -c '^replace secret$' "$MOCK_CONTROL_DIR/operations.log")" == "1" ]]

printf 'PASS test-refresh-script\n'
