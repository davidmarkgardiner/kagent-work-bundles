#!/usr/bin/env bash
set -euo pipefail

bundle_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$bundle_root"

echo "== Alloy Kubernetes events Kafka bundle verifier =="
echo "bundle: $bundle_root"
echo "mode: static; no cluster, Kafka, or secret calls"

required=(
  "GITLAB-TICKET.md"
  "README.md"
  "WORK-AGENT-START-PROMPT.md"
  "CHECKLIST.md"
  "evidence/EVIDENCE-TEMPLATE.md"
  "examples/namespace-scoped/01-test-namespace.yaml"
  "examples/namespace-scoped/02-alloy-namespace-scoped.yaml"
  "examples/namespace-scoped/03-argo-kafka-eventsource.yaml"
  "examples/namespace-scoped/04-argo-kafka-sensor.yaml"
  "examples/namespace-scoped/05-argo-workflowtemplate.yaml"
  "examples/namespace-scoped/06-smoke-event-job.yaml"
  "scripts/render-namespace-test.sh"
)

for path in "${required[@]}"; do
  test -f "$path"
  echo "FOUND $path"
done

python3 - <<'PY'
from pathlib import Path
import yaml

for path in Path("examples/namespace-scoped").glob("*.yaml"):
    with path.open() as handle:
        list(yaml.safe_load_all(handle))
    print(f"YAML_OK {path}")
PY

grep -Fq 'namespaces = ["{{TEST_NAMESPACE}}"]' examples/namespace-scoped/02-alloy-namespace-scoped.yaml
grep -Fq 'kind: Role' examples/namespace-scoped/02-alloy-namespace-scoped.yaml
grep -Fq 'kind: RoleBinding' examples/namespace-scoped/02-alloy-namespace-scoped.yaml
grep -Fq 'otelcol.exporter.kafka "confluent"' examples/namespace-scoped/02-alloy-namespace-scoped.yaml
grep -Fq 'groupName: "{{CONSUMER_GROUP_PREFIX}}-alloy-k8s-events-smoke"' examples/namespace-scoped/03-argo-kafka-eventsource.yaml
grep -Fq 'eventSourceName: alloy-k8s-events-kafka' examples/namespace-scoped/04-argo-kafka-sensor.yaml
grep -Fq 'ALLOY_K8S_EVENT_PAYLOAD_BEGIN' examples/namespace-scoped/05-argo-workflowtemplate.yaml
grep -Fq 'AlloyKafkaSmoke' examples/namespace-scoped/06-smoke-event-job.yaml
grep -Fq 'CONFLUENT_BOOTSTRAP' scripts/render-namespace-test.sh
grep -Fq 'ALLOY_NAMESPACE_SCOPED' WORK-AGENT-START-PROMPT.md
grep -Fq 'ARGO_WORKFLOW_TRIGGERED' evidence/EVIDENCE-TEMPLATE.md

if grep -RInE \
  '(Bearer[[:space:]]+[A-Za-z0-9._-]+|token=|password:|secret:|pkc-[A-Za-z0-9-]+|lkc-[A-Za-z0-9-]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' \
  --exclude 'verify-bundle.sh' \
  .; then
  echo "PUBLIC_SAFE_SCAN: failed" >&2
  exit 1
fi

echo "ALLOY_K8S_EVENTS_KAFKA_BUNDLE_VERIFY: passed"
