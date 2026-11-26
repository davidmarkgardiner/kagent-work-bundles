#!/usr/bin/env bash
# Read-only. Reports what is ready and what is missing.
set -uo pipefail
. "$(dirname "$0")/lib.sh"
fail=0
ok() { echo "PASS  $1"; }; bad() { echo "FAIL  $1"; fail=1; }; note() { echo "CHECK $1"; }
for c in kubectl helm python3 openssl curl kubectl-ate; do command -v "$c" >/dev/null && ok "tool $c" || bad "tool $c missing"; done
(cd "$HERE/charts" && { command -v sha256sum >/dev/null && sha256sum -c --quiet SHA256SUMS || shasum -a 256 -c SHA256SUMS >/dev/null; }) && ok "chart checksums" || bad "chart checksums"
while read -r rel arch sum; do
  case "$rel" in ''|\#*) continue ;; esac
  f="${ASSETS_DIR:-}/$rel/$arch/gvisor.tar.zstd"
  got="$( { sha256sum "$f" 2>/dev/null || shasum -a 256 "$f" 2>/dev/null; } | awk '{print $1}')"
  [ "$got" = "$sum" ] && ok "gVisor $rel $arch" || bad "gVisor file missing or wrong: $f"
done < "$HERE/gvisor-assets.txt"
k version >/dev/null 2>&1 && ok "cluster reachable" || { bad "cannot reach context $KUBE_CONTEXT"; exit 1; }
k version 2>/dev/null | grep Server
res="$(k api-resources --api-group=certificates.k8s.io -o name 2>/dev/null)"
for r in podcertificaterequests clustertrustbundles; do grep -q "^$r\." <<<"$res" && ok "API $r" || bad "API $r not served (needs AKS 1.37)"; done
k get storageclass -o jsonpath='{range .items[*]}{.metadata.name}{" default="}{.metadata.annotations.storageclass\.kubernetes\.io/is-default-class}{"\n"}{end}' | sed 's/^/      /'
k get nodes -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.nodeInfo.osImage}{" "}{.status.nodeInfo.architecture}{" taints="}{.spec.taints[*].key}{"\n"}{end}' | sed 's/^/      /'
for ns in ate-system podcertificate-controller-system; do
  k get ns "$ns" >/dev/null 2>&1 && bad "namespace $ns already exists: inventory it before going on" || ok "namespace $ns free"
done
k get crd -o name | grep -qE 'ate\.dev' && bad "ate.dev CRDs already present" || ok "no ate.dev CRDs"
issuer="$(k get --raw /.well-known/openid-configuration 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["issuer"])' 2>/dev/null)"
note "ServiceAccount issuer: ${issuer:-unknown}. If it is not an in-cluster https://kubernetes.default.svc address, ate-api must reach it on 443."
printf 'apiVersion: v1\nkind: Pod\nmetadata: {name: ate-priv-probe}\nspec:\n  containers:\n  - name: c\n    image: %s/library/python:3.13-alpine\n    securityContext: {privileged: true}\n    volumeMounts: [{name: h, mountPath: /h}]\n  volumes: [{name: h, hostPath: {path: /var/lib/ate}}]\n' "$REGISTRY" \
  | k apply --dry-run=server -n default -f - >/dev/null 2>&1 && ok "privileged + hostPath admitted (server dry run, default namespace)" || bad "privileged or hostPath pod rejected by admission"
echo; [ $fail = 0 ] && echo "PREFLIGHT PASS" || echo "PREFLIGHT FAIL"
exit $fail
