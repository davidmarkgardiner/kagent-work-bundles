#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BUNDLE_ROOT}"

echo "== Grafana Kafka alert verification work-agent bundle verifier =="
echo "bundle: ${BUNDLE_ROOT}"
echo "mode: local/static; no Grafana, Kafka, Confluent, cluster, or schema calls"

required=(
  "FRONT-SHEET.md"
  "README.md"
  "WORK-AGENT-START-PROMPT.md"
  "CHECKLIST.md"
  "GITLAB-TICKET.md"
  "VISUAL.html"
  "requests/grafana-kafka-alert-verification-request.yaml"
  "requests/grafana-kafka-alert-verification-request.json"
  "prompts/01-preflight-env-tools.md"
  "prompts/02-configure-firing-alert.md"
  "prompts/03-consume-capture-schema.md"
  "prompts/04-cluster-consumer-and-schema-decision.md"
  "payload/grafana-kafka-alert.schema.json"
  "evidence/EVIDENCE-TEMPLATE.md"
)

for rel in "${required[@]}"; do
  if [[ ! -f "${rel}" ]]; then
    echo "MISSING ${rel}" >&2
    exit 1
  fi
  echo "FOUND ${rel}"
done

python3 -m json.tool "payload/grafana-kafka-alert.schema.json" >/dev/null
python3 -m json.tool "requests/grafana-kafka-alert-verification-request.json" >/dev/null
echo "JSON_OK: yes"

for marker in \
  "ENV_PREFLIGHT: passed_or_blocked" \
  "GRAFANA_MCP_TOOLS: discovered_or_blocked" \
  "GRAFANA_CONTACT_POINT: verified" \
  "ALERT_RULE: firing" \
  "KAFKA_RECORD: consumed" \
  "PAYLOAD_CAPTURED: yes" \
  "SCHEMA_VALIDATION: passed_or_update_required" \
  "CLUSTER_CONSUMER: proven_or_blocked" \
  "BROKER_SCHEMA_DECISION: consumer_side_or_bridge_required_or_proven_native" \
  "OUTPUT_SANITIZED: yes"; do
  grep -q "${marker}" "WORK-AGENT-START-PROMPT.md" "GITLAB-TICKET.md" "evidence/EVIDENCE-TEMPLATE.md"
  echo "MARKER_OK ${marker}"
done

grep -q "Do not proceed unless the required variables" "WORK-AGENT-START-PROMPT.md"
grep -q "If any required variable is missing, stop and return BLOCKED" "prompts/01-preflight-env-tools.md"
grep -q "ConfluentKafkaFiringSmoke" "prompts/02-configure-firing-alert.md"
grep -q "payload/grafana-kafka-alert.schema.json" "prompts/03-consume-capture-schema.md"
grep -q "bridge/normalizer" "prompts/04-cluster-consumer-and-schema-decision.md"
echo "PROMPT_CONTRACT_OK: yes"

if grep -RInE \
  '(Bearer[[:space:]]+[A-Za-z0-9._-]+|token=|password:|secret:|pkc-[A-Za-z0-9-]+|lkc-[A-Za-z0-9-]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' \
  --exclude='verify-bundle.sh' .; then
  echo "PUBLIC_SAFETY_HITS: review output above" >&2
  exit 1
fi
echo "PUBLIC_SAFE_SCAN_OK: yes"

echo "GRAFANA_KAFKA_ALERT_VERIFICATION_BUNDLE_VERIFY: passed"
