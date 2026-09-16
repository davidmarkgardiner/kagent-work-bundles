#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUNDLE_ROOT="$(cd "$ROOT/.." && pwd)"
IMAGE="${1:?usage: build-assessor-image.sh REGISTRY/IMAGE:TAG [PYTHON_BASE_IMAGE]}"
BASE="${2:-python:3.11-slim@sha256:d1053354624536b044162aaab1e418bd000ea35184fb1ae098ab3166b1072e72}"

[[ "$BASE" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "PYTHON_BASE_IMAGE must be pinned by sha256 digest" >&2
  exit 1
}

docker build \
  --pull=false \
  --build-arg "PYTHON_BASE_IMAGE=$BASE" \
  --file "$ROOT/images/assessor/Dockerfile" \
  --tag "$IMAGE" \
  "$BUNDLE_ROOT"

docker image inspect "$IMAGE" --format '{{json .RepoDigests}}'
