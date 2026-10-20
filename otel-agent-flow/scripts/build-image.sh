#!/usr/bin/env bash
set -euo pipefail
bundle_dir=$(cd "$(dirname "$0")/.." && pwd)
image=${FLOW_IMAGE:?Set FLOW_IMAGE to your target image tag}
arch=${TARGETARCH:-amd64}
case "$arch" in
  amd64) archive_arch=x86_64; checksum=a926b62a85787ccf73ef8736b3ae554f1242e39d92bb8767a79d6dd23b11d1d5 ;;
  arm64) archive_arch=arm64; checksum=b20a00c1cb82ab81ec32696766d4076e99b4cb5ca0823a71767ba64dbea0f263 ;;
  *) echo "TARGETARCH must be amd64 or arm64" >&2; exit 2 ;;
esac
mkdir -p "$bundle_dir/.build"
archive="$bundle_dir/.build/grpcurl-1.9.3-$arch.tar.gz"
if [[ ! -f "$archive" ]]; then
  curl --fail --location --silent --show-error "https://github.com/fullstorydev/grpcurl/releases/download/v1.9.3/grpcurl_1.9.3_linux_${archive_arch}.tar.gz" --output "$archive"
fi
python3 - "$archive" "$checksum" <<'PY'
import hashlib, sys
from pathlib import Path
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != sys.argv[2]:
    raise SystemExit("grpcurl archive checksum mismatch")
PY
tar -xzf "$archive" -C "$bundle_dir/.build" grpcurl
chmod 755 "$bundle_dir/.build/grpcurl"
docker build --platform "linux/$arch" -t "$image" "$bundle_dir"
