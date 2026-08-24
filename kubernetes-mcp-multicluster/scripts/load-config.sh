#!/usr/bin/env bash

load_bundle_config() {
  local bundle_dir=$1
  local variable_name variable_value
  local required_variables=(
    HOST_CONTEXT SOURCE_CONTEXTS SMOKE_CONTEXTS HOST_NAMESPACE
    KAGENT_NAMESPACE AGENTGATEWAY_NAMESPACE AGENTGATEWAY_NAME
    AGENTGATEWAY_SERVICE MODEL_CONFIG MCP_SERVICE_HOST DIRECT_MCP_URL
    AGENTGATEWAY_MCP_URL IMAGE_REGISTRY IMAGE_REPOSITORY
    IMAGE_VERSION CHART_REF CHART_VERSION REPLICA_COUNT
    RESOURCE_REQUEST_CPU TOKEN_DURATION ALLOW_PUBLIC_IMAGE_FOR_TEST
  )

  WORK_VALUES_FILE="$bundle_dir/work-values.env"
  if test ! -f "$WORK_VALUES_FILE"; then
    echo "missing customization file: $WORK_VALUES_FILE" >&2
    echo "copy $bundle_dir/work-values.env.template to work-values.env and replace its placeholders" >&2
    return 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "$WORK_VALUES_FILE"
  set +a

  for variable_name in "${required_variables[@]}"; do
    variable_value=${!variable_name:-}
    test -n "$variable_value" || {
      echo "missing required customization value: $variable_name" >&2
      return 1
    }
    case "$variable_value" in
      *'{{'*|*'}}'*)
        echo "unresolved placeholder in customization value: $variable_name" >&2
        return 1
        ;;
    esac
  done

  case "$ALLOW_PUBLIC_IMAGE_FOR_TEST" in
    0|1) ;;
    *)
      echo "ALLOW_PUBLIC_IMAGE_FOR_TEST must be 0 or 1" >&2
      return 1
      ;;
  esac

  SOURCE_CONTEXTS_LIST=${SOURCE_CONTEXTS//,/ }
  SMOKE_CONTEXTS_LIST=${SMOKE_CONTEXTS//,/ }
  export SOURCE_CONTEXTS_LIST SMOKE_CONTEXTS_LIST

  RENDER_DIR=${RENDER_DIR:-"$bundle_dir/rendered"}
  export WORK_VALUES_FILE RENDER_DIR
}
