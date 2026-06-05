#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BUNDLE_ROOT}"

echo "== SRE Grafana MCP observability work-agent bundle verifier =="
echo "bundle: ${BUNDLE_ROOT}"
echo "mode: local/static; no Grafana, GitLab, cluster, or Flux calls"

required=(
  "FRONT-SHEET.md"
  "WORK-AGENT-START-PROMPT.md"
  "CHECKLIST.md"
  "requests/cert-manager-observability-request.yaml"
  "requests/cert-manager-observability-request.json"
  "prompts/01-cert-manager-observability.md"
  "evidence/EVIDENCE-TEMPLATE.md"
  "payload/docs/observability/sre-grafana-mcp-observability/README.md"
  "payload/docs/observability/sre-grafana-mcp-observability/cert-manager-observability-request.json"
  "payload/docs/observability/grafana-mcp-home-lab.md"
  "payload/docs/observability/k-agent-alloy-grafana.md"
  "payload/docs/ai-grafana/README.md"
  "payload/docs/ai-grafana/shared-grafana-evidence-agent.md"
  "payload/docs/ai-grafana/agent-dashboard-evidence-pattern.md"
  "payload/docs/ai-grafana/work-agent-implementation-prompt.md"
  "payload/agents/skills/grafana-incident-evidence-pack/SKILL.md"
  "payload/agents/skills/grafana-chaos-incident-triage/SKILL.md"
  "payload/agents/grafana-evidence-agent/README.md"
  "payload/agents/grafana-evidence-agent/agent.yaml"
  "payload/agents/kagent-triage/cert-manager-agent.yaml"
  "payload/observability/grafana/dashboard-registry.yaml"
  "payload/observability/grafana/dashboards/k8s-pod-crash-evidence.json"
  "payload/observability/managed-lgtm-integration/rule-sync/README.md"
  "payload/observability/managed-lgtm-integration/alloy-snippets/00-common-labels.alloy"
  "payload/observability/managed-lgtm-integration/alloy-snippets/01-metrics-to-mimir.alloy"
  "payload/observability/managed-lgtm-integration/alloy-snippets/02-logs-to-loki.alloy"
  "payload/observability/managed-lgtm-integration/alloy-snippets/04-rule-sync.alloy"
  "payload/observability/managed-lgtm-integration/alloy-snippets/05-alertmanager-webhook-bridge.alloy"
  "payload/observability/grafana-argo-pipeline/README.md"
  "payload/observability/grafana-argo-pipeline/argo/eventsources/grafana-alert-webhook-eventsource.yaml"
  "payload/observability/grafana-argo-pipeline/argo/sensors/grafana-alert-sensor.yaml"
  "payload/observability/grafana-argo-pipeline/k8s/alerting/argo-alert-sensor-rbac.yaml"
)

for rel in "${required[@]}"; do
  if [[ ! -f "${rel}" ]]; then
    echo "MISSING ${rel}" >&2
    exit 1
  fi
  echo "FOUND ${rel}"
done

grep -q "Use \`agents/skills/grafana-incident-evidence-pack/SKILL.md\`" \
  "payload/docs/observability/sre-grafana-mcp-observability/README.md"
echo "PROMPT_SKILL_PATH_OK: yes"

grep -q "grafana-evidence-agent" \
  "payload/docs/ai-grafana/shared-grafana-evidence-agent.md"
grep -q "cert-manager-agent" \
  "payload/agents/kagent-triage/cert-manager-agent.yaml"
grep -q "cert-manager" \
  "payload/observability/grafana/dashboard-registry.yaml"
grep -q "cert-manager" \
  "payload/observability/managed-lgtm-integration/rule-sync/README.md"
echo "CERT_MANAGER_REFERENCES_OK: yes"

for marker in \
  "BUNDLE_VERIFY: passed" \
  "KAGENT_FRONT_DOOR: ui_or_a2a" \
  "LOCAL_MCP_REQUIRED_FOR_SRE: no" \
  "GRAFANA_MCP_TOOLS: discovered" \
  "CERT_MANAGER_METRICS: discovered" \
  "GITLAB_MR: created_or_not_available" \
  "LIVE_PROOF: yes_or_blocked"; do
  grep -q "${marker}" "WORK-AGENT-START-PROMPT.md"
  echo "MARKER_OK ${marker}"
done

grep -q "localMcpInstallRequired: false" \
  "requests/cert-manager-observability-request.yaml"
grep -q '"mode": "durable-gitops"' \
  "requests/cert-manager-observability-request.json"
grep -q "observability-work-agent" \
  "prompts/01-cert-manager-observability.md"
echo "KAGENT_FRONT_DOOR_CONTRACT_OK: yes"

if grep -RInE \
  '(Bearer[[:space:]]+[A-Za-z0-9._-]+|token=|password:|secret:|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' \
  --exclude='verify-bundle.sh' .; then
  echo "PUBLIC_SAFETY_HITS: review output above" >&2
  exit 1
fi
echo "PUBLIC_SAFE_SCAN_OK: yes"

echo "SRE_GRAFANA_MCP_OBSERVABILITY_BUNDLE_VERIFY: passed"
