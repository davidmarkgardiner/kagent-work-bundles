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

printf 'PASS test-refresh-script\n'
