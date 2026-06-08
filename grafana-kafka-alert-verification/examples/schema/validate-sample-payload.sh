#!/usr/bin/env bash
set -euo pipefail

bundle_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
schema_path="${bundle_root}/payload/grafana-kafka-alert.schema.json"
payload_path="${1:-${bundle_root}/examples/schema/sample-grafana-kafka-alert.json}"

python3 - <<PY
import json
from pathlib import Path
from jsonschema import Draft202012Validator

schema = json.loads(Path("${schema_path}").read_text())
payload = json.loads(Path("${payload_path}").read_text())

validator = Draft202012Validator(schema)
errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))

if errors:
    for error in errors:
        path = "/".join(map(str, error.path)) or "<root>"
        print(f"{path}: {error.message}")
    raise SystemExit(1)

print("SAMPLE_PAYLOAD_SCHEMA_VALIDATION: passed")
PY
