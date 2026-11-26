#!/usr/bin/env bash
# Usage:
#   seed-gvisor-assets.sh download <dir>   on a connected host
#   seed-gvisor-assets.sh upload <dir>     where the RustFS S3 API is reachable
# For upload: kubectl -n ate-system port-forward svc/rustfs 9000:9000
# and export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY with the RustFS credentials.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
mode="${1:?download|upload}"; dir="${2:?directory}"
sum() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | awk '{print $1}'; }

while read -r release arch want; do
  case "$release" in ''|\#*) continue ;; esac
  file="$dir/$release/$arch/gvisor.tar.zstd"
  if [ "$mode" = download ]; then
    mkdir -p "$(dirname "$file")"
    curl -fsSL "https://storage.googleapis.com/gvisor/releases/release/$release/$arch/gvisor.tar.zstd" -o "$file"
  fi
  [ "$(sum "$file")" = "$want" ] || { echo "checksum mismatch: $file" >&2; exit 1; }
  if [ "$mode" = upload ]; then
    aws --endpoint-url "${S3_ENDPOINT:-http://127.0.0.1:9000}" --region us-east-1 \
      s3 cp "$file" "s3://ate-snapshots/gvisor/$release/$arch/gvisor.tar.zstd"
  fi
  echo "ok $release $arch"
done < "$HERE/gvisor-assets.txt"
