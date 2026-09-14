#!/bin/sh
set -eu

bundle_dir=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
values_file=${1:-"$bundle_dir/config/work-values.env"}
output_dir=${2:-"$bundle_dir/rendered"}

if [ ! -f "$values_file" ]; then
  echo "values file not found: $values_file" >&2
  exit 1
fi
if ! command -v envsubst >/dev/null 2>&1; then
  echo "envsubst is required (gettext package)" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$values_file"
set +a

required='INCIDENT_NAMESPACE ARGO_EVENTS_NAMESPACE ARGO_WORKFLOWS_NAMESPACE KAFKA_BOOTSTRAP_SERVERS KAFKA_TOPIC KAFKA_CREDENTIALS_SECRET COORDINATOR_IMAGE KAGENT_A2A_URL KAGENT_EXECUTOR_A2A_URL INVESTIGATOR_AGENT_NAME EXECUTOR_AGENT_NAME MODEL_LABEL REMEDIATION_NAMESPACE REMEDIATION_DEPLOYMENT REMEDIATION_LABEL_KEY REMEDIATION_LABEL_VALUE GITLAB_PROJECT_PATH GITLAB_TARGET_BRANCH'
for key in $required; do
  value=$(printenv "$key" 2>/dev/null || true)
  case "$value" in
    ""|*"{{"*|*"}}")
      echo "missing or unresolved value: $key" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$output_dir"
substitutions='$INCIDENT_NAMESPACE $ARGO_EVENTS_NAMESPACE $ARGO_WORKFLOWS_NAMESPACE $KAFKA_BOOTSTRAP_SERVERS $KAFKA_TOPIC $KAFKA_CREDENTIALS_SECRET $COORDINATOR_IMAGE $KAGENT_A2A_URL $KAGENT_EXECUTOR_A2A_URL $GITLAB_MCP_URL $TEAMS_APPROVAL_URL $SERVICENOW_RELAY_URL $APPROVAL_CALLBACK_BASE_URL $ARGO_APPROVAL_CALLBACK_URL $ARGO_UI_BASE_URL $INVESTIGATOR_AGENT_NAME $EXECUTOR_AGENT_NAME $MODEL_LABEL $REMEDIATION_NAMESPACE $REMEDIATION_DEPLOYMENT $REMEDIATION_LABEL_KEY $REMEDIATION_LABEL_VALUE $GITLAB_PROJECT_PATH $GITLAB_TARGET_BRANCH $GITOPS_FILE_PATH'
for template in "$bundle_dir"/manifests/*.yaml.tpl; do
  output="$output_dir/$(basename "$template" .tpl)"
  envsubst "$substitutions" <"$template" >"$output"
done

if grep -R -n -E '\{\{[A-Z0-9_]+\}\}|\$\{[A-Z0-9_]+\}' "$output_dir"; then
  echo "rendered output still contains placeholders" >&2
  exit 1
fi
echo "Rendered manifests to $output_dir"
