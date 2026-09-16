#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${1:?usage: build-fox-image.sh PATH_TO_INTERNAL_FOX_CHECKOUT REGISTRY/IMAGE:TAG GO_BUILDER_IMAGE@sha256:DIGEST RUNTIME_IMAGE@sha256:DIGEST}"
IMAGE="${2:?usage: build-fox-image.sh PATH_TO_INTERNAL_FOX_CHECKOUT REGISTRY/IMAGE:TAG GO_BUILDER_IMAGE@sha256:DIGEST RUNTIME_IMAGE@sha256:DIGEST}"
BUILDER="${3:?usage: build-fox-image.sh PATH_TO_INTERNAL_FOX_CHECKOUT REGISTRY/IMAGE:TAG GO_BUILDER_IMAGE@sha256:DIGEST RUNTIME_IMAGE@sha256:DIGEST}"
RUNTIME="${4:?usage: build-fox-image.sh PATH_TO_INTERNAL_FOX_CHECKOUT REGISTRY/IMAGE:TAG GO_BUILDER_IMAGE@sha256:DIGEST RUNTIME_IMAGE@sha256:DIGEST}"
PINNED="7c785b574c36f7100ae321ec0f880782dfead311"

for base in "$BUILDER" "$RUNTIME"; do
  [[ "$base" =~ @sha256:[0-9a-f]{64}$ ]] || {
    echo "Fox builder and runtime base images must be pinned by sha256 digest" >&2
    exit 1
  }
done

test -d "$SOURCE/.git"
git -C "$SOURCE" merge-base --is-ancestor "$PINNED" HEAD
test -z "$(git -C "$SOURCE" status --porcelain)" || {
  echo "Fox checkout must be clean and the local state-only adaptation committed" >&2
  exit 1
}
rg -q 'PUBLISH_FINDINGS_ENABLED' "$SOURCE/config.go"
rg -q 'PublishFindingsEnabled|publishFindingsEnabled' "$SOURCE"/*.go

(cd "$SOURCE" && go test ./...)
docker build \
  --pull=false \
  --build-arg "GO_BUILDER_IMAGE=$BUILDER" \
  --build-arg "RUNTIME_IMAGE=$RUNTIME" \
  --file "$ROOT/images/fox/Dockerfile" \
  --tag "$IMAGE" \
  "$SOURCE"

docker image inspect "$IMAGE" --format '{{json .RepoDigests}}'
