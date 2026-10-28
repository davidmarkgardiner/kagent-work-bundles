#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GRAPH_PYTHON="${GRAPH_PYTHON:-python3.12}"
cd "$ROOT"
"$GRAPH_PYTHON" -m pip check
"$GRAPH_PYTHON" -m pytest -q -p no:cacheprovider
"$GRAPH_PYTHON" -m unittest discover -s scripts -p 'test_*.py'
bash "$ROOT/scripts/public-safe-scan.sh" "$ROOT" --allowlist "$ROOT/scripts/public-safe-allowlist.txt" --json
