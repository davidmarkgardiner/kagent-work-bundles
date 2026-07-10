#!/usr/bin/env bash
set -euo pipefail

bundle_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_root="$(cd "$bundle_dir/../.." && pwd)"

required_files=(
  "README.md"
  "FRONT-SHEET.md"
  "SMOKE-RUNBOOK.md"
  "ALERTMANAGER-EVENT-ROUTING.md"
  "SOURCE-TYPE-ALERT-EXAMPLES.md"
  "CHECKLIST.md"
  "WORK-AGENT-START-PROMPT.md"
  "SCORECARD.md"
  "evidence/EVIDENCE-TEMPLATE.md"
  "evidence/PROXMOX-EVENT-ALERTMANAGER-ROUTING-2026-07-09.md"
  "evidence/PROXMOX-TIER-TWO-MCP-TRIAGE-2026-07-10.md"
  "evidence/PROXMOX-TIER-TWO-KAFKA-E2E-2026-07-10.md"
  "examples/k8s/failed-scheduling-smoke-target.yaml"
  "examples/monitoring/agentic-triage-event-routing.yaml"
  "examples/score/proxmox-2026-07-09-smoke-run.json"
  "examples/score/periodic-daily-smoke-run.json"
  "requests/agentic-triage-smoke-request.yaml"
  "prompts/CRITIQUE-PROMPT.md"
  "examples/grafana/source-type-alert-rules.yaml"
  "examples/alertmanager-payloads/metric-crashloop.json"
  "examples/alertmanager-payloads/log-errorburst.json"
  "examples/alertmanager-payloads/event-failedscheduling.json"
  "examples/alertmanager-payloads/trace-latency.json"
  "examples/monitoring/agentic-triage-smoke-rules.yaml"
  "examples/kagent/aks-mcp-readonly-values.yaml"
  "examples/kagent/grafana-mcp-host-validation-values.yaml"
  "examples/kagent/tier-two-mcp-triage-agent.yaml"
  "examples/argo/tier-two-mcp-triage-workflow-template.yaml"
  "scripts/score-smoke-run.py"
  "scripts/replay-alert-payload.sh"
)

for file in "${required_files[@]}"; do
  test -f "$bundle_dir/$file" || {
    echo "missing required file: $file" >&2
    exit 1
  }
done

for referenced in \
  "work-agent-bundles/kagent-agentic-cluster-smoke-tests.md" \
  "a2a/smart-triage-fanout-demo/scripts/replay-alert.sh" \
  "observability/agent-evals/grafana/kagent-fleet-overview-dashboard.json" \
  "observability/agent-evals/alerting/agent-eval-rules.yaml"; do
  test -e "$repo_root/$referenced" || {
    echo "missing referenced repo asset: $referenced" >&2
    exit 1
  }
done

if command -v python3 >/dev/null 2>&1; then
  python3 - <<PY
from pathlib import Path
root = Path("$bundle_dir")
needles = [
    "metric-crashloop",
    "log-errorburst",
    "event-failedscheduling",
    "trace-latency",
    "negative-agent-health",
    "agent_lifecycle_eval_score",
    "agentic_triage_smoke_score",
]
text = "\n".join(p.read_text() for p in root.rglob("*.md"))
missing = [n for n in needles if n not in text]
if missing:
    raise SystemExit("missing expected bundle terms: " + ", ".join(missing))

import json
for path in (root / "examples" / "alertmanager-payloads").glob("*.json"):
    json.loads(path.read_text())
PY
fi

echo "agentic triage smoke bundle verification: ok"
