#!/usr/bin/env bash
set -euo pipefail

bundle_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
repo_dir=$(cd "${bundle_dir}/../.." && pwd)

test -f "${bundle_dir}/FRONT-SHEET.md"
test -f "${bundle_dir}/daily-health/README.md"
test -f "${bundle_dir}/daily-health/cronworkflow.yaml"
test -f "${bundle_dir}/daily-health/VERIFICATION.md"

python3 - "${bundle_dir}/daily-health/cronworkflow.yaml" <<'PY'
import pathlib
import sys
import yaml

path = pathlib.Path(sys.argv[1])
documents = list(yaml.safe_load_all(path.read_text()))
assert len(documents) == 1
workflow = documents[0]
assert workflow["kind"] == "CronWorkflow"
assert workflow["spec"]["schedules"] == ["0 7 * * *"]
assert workflow["spec"]["timezone"] == "Europe/London"
assert workflow["spec"]["suspend"] is True
assert workflow["spec"]["concurrencyPolicy"] == "Forbid"
assert workflow["spec"]["workflowSpec"]["workflowTemplateRef"]["name"] == "cluster-certification"
print("DICE_DAILY_HEALTH_CONTRACT_OK")
PY

"${repo_dir}/scripts/public-safe-scan.sh" "${bundle_dir}"
echo "DICE_PROGRAMME_BUNDLE_VERIFY_OK"
