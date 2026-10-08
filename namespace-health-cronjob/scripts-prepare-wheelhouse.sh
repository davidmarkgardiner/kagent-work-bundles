#!/usr/bin/env bash
set -euo pipefail

bundle_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$#" -ne 1 || ( "$1" != amd64 && "$1" != arm64 ) ]]; then
  echo "Usage: $0 amd64|arm64" >&2
  exit 2
fi

arch="$1"
case "$arch" in
  amd64) platform=manylinux_2_28_x86_64 ;;
  arm64) platform=manylinux_2_28_aarch64 ;;
esac

destination="$bundle_dir/wheelhouse/$arch"
if [[ -e "$destination" ]]; then
  echo "Refusing to replace existing $destination" >&2
  exit 1
fi

scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
python3 -m pip download \
  --disable-pip-version-check \
  --no-deps \
  --only-binary=:all: \
  --require-hashes \
  --platform "$platform" \
  --python-version 3.12 \
  --implementation cp \
  --abi cp312 \
  --dest "$scratch" \
  -r "$bundle_dir/requirements.lock"

python3 - "$scratch" "$arch" "$bundle_dir/evidence/IMAGE-INVENTORY.json" <<'PY'
import hashlib
import json
import pathlib
import sys

directory = pathlib.Path(sys.argv[1])
arch = sys.argv[2]
inventory = json.loads(pathlib.Path(sys.argv[3]).read_text())
prefix = f"wheelhouse/{arch}/"
expected = {
    pathlib.Path(path).name: digest
    for path, digest in inventory["wheels"].items()
    if path.startswith(prefix)
}
actual = {
    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
    for path in directory.iterdir()
    if path.is_file()
}
if actual != expected:
    raise SystemExit(f"wheel filename/checksum mismatch for {arch}")
print(f"Verified {len(actual)} pinned {arch} wheels")
PY

mkdir -p "$bundle_dir/wheelhouse"
mv "$scratch" "$destination"
trap - EXIT
