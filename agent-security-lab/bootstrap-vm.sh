#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=versions.env
source "$root/versions.env"
[[ $(uname -m) == x86_64 ]] || { echo 'This lock supports x86_64 only.' >&2; exit 1; }
case "$(hostname)" in agent-tls-test|agent-tls-lab-[0-9]*) ;; *) echo 'Refusing to bootstrap a host that is not named as a dedicated agent TLS lab.' >&2; exit 1 ;; esac
[[ "${1:-}" == '--apply' ]] || { echo 'Dry-run: install Docker and pinned kind, kubectl, Helm and kagent binaries on this dedicated VM. Pass --apply to execute.'; exit 0; }
cloud_status=0
cloud-init status --wait || cloud_status=$?
if (( cloud_status == 2 )); then
  # Ubuntu's current cloud-init reports deprecated template syntax as degraded.
  # Accept only that known warning; stop on actual errors or other warnings.
  (cloud-init status --format json || true) | python3 -c 'import json,sys; s=json.load(sys.stdin); ok=s.get("status")=="done" and not s.get("errors") and set(s.get("recoverable_errors",{})) <= {"DEPRECATED"}; sys.exit(0 if ok else 1)' || { echo 'cloud-init has errors or unexpected warnings; inspect before proceeding.' >&2; exit 1; }
  echo 'cloud-init finished with deprecation warnings only.'
elif (( cloud_status != 0 )); then
  echo 'cloud-init did not finish successfully; inspect before proceeding.' >&2
  exit 1
fi
sudo -n apt-get update
sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io curl ca-certificates openssl python3
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
curl -fsSL -o "$work/kind" "https://github.com/kubernetes-sigs/kind/releases/download/${KIND_VERSION}/kind-linux-amd64"
curl -fsSL -o "$work/kubectl" "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"
curl -fsSL -o "$work/helm.tar.gz" "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz"
curl -fsSL -o "$work/kagent" "https://github.com/kagent-dev/kagent/releases/download/v${KAGENT_VERSION}/kagent-linux-amd64"
printf '%s  %s\n' "$KIND_SHA256" "$work/kind" "$KUBECTL_SHA256" "$work/kubectl" "$HELM_ARCHIVE_SHA256" "$work/helm.tar.gz" "$KAGENT_BIN_DIGEST" "$work/kagent" | sha256sum -c -
tar -xzf "$work/helm.tar.gz" -C "$work" linux-amd64/helm
sudo -n install -m 0755 "$work/kind" "$work/kubectl" "$work/linux-amd64/helm" "$work/kagent" /usr/local/bin/
sudo -n usermod -aG docker "$(id -un)"
echo 'Bootstrap complete; reconnect before using Docker so the group change takes effect.'
