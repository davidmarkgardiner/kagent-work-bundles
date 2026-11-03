#!/usr/bin/env sh
set -eu
output=${1:?Usage: build.sh /approved/output/actor-probe}
source_root=$(cd "$(dirname "$0")/.." && pwd)
case "$output" in
  "$source_root"/*) echo "Output must be outside the source bundle" >&2; exit 2 ;;
  /*) ;;
  *) echo "Output must be an absolute external path" >&2; exit 2 ;;
esac
cd "$(dirname "$0")"
GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off go test ./...
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off go build -mod=readonly -trimpath -o "$output" .
