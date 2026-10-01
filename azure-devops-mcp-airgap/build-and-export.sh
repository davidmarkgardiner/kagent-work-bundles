#!/usr/bin/env bash
set -euo pipefail
[[ $# == 1 ]] || { echo 'Usage: build-and-export.sh /absolute/transfer-directory'; exit 2; }
ROOT=$(cd "$(dirname "$0")" && pwd)
OUT=$1
[[ "$OUT" = /* ]] || { echo 'Use an absolute output directory outside the repository'; exit 2; }
case "$OUT/" in "$ROOT/"*) echo 'Write binary archives outside this bundle'; exit 2;; esac
mkdir -p "$OUT"
docker build --platform linux/amd64 --target dependencies -t azure-devops-mcp-dependencies:2.10.0-poc1 "$ROOT"
docker build --platform linux/amd64 -t azure-devops-mcp:2.10.0-poc1 "$ROOT"
docker run --rm --platform linux/amd64 --network none azure-devops-mcp:2.10.0-poc1 node --test
docker run --rm --platform linux/amd64 --network none azure-devops-mcp:2.10.0-poc1 node -e 'require("keytar"); console.log("native keytar loaded")'
docker run --rm --platform linux/amd64 --network none --read-only azure-devops-mcp:2.10.0-poc1 node image-smoke.mjs
docker image save -o "$OUT/azure-devops-mcp-images.tar" azure-devops-mcp:2.10.0-poc1 azure-devops-mcp-dependencies:2.10.0-poc1
tar -czf "$OUT/azure-devops-mcp-source.tar.gz" --exclude='node_modules' --exclude='.env*' --exclude='__pycache__' -C "$ROOT" README.md WORK-START-HERE.md WORK-AGENT-BUILD-INSTRUCTIONS.md AGENTS.md Dockerfile Dockerfile.offline .dockerignore .gitignore build-and-export.sh render.py install-secrets.py config.example.json kubernetes.template.json app scripts evidence
(cd "$OUT"; shasum -a 256 azure-devops-mcp-images.tar azure-devops-mcp-source.tar.gz > SHA256SUMS)
docker image inspect azure-devops-mcp:2.10.0-poc1 azure-devops-mcp-dependencies:2.10.0-poc1 --format '{{.RepoTags}} {{.Id}} {{.Architecture}}' > "$OUT/image-ids.txt"
echo "Transfer artifacts: $OUT"
