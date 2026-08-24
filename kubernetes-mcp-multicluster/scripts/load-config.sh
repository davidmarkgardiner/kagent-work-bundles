#!/usr/bin/env bash

load_bundle_config() {
  local bundle_dir=$1
  local variable_name variable_value
  local required_variables=(
    HOST_CONTEXT SOURCE_CONTEXTS SMOKE_CONTEXTS HOST_NAMESPACE
    KAGENT_NAMESPACE AGENTGATEWAY_NAMESPACE AGENTGATEWAY_NAME
    AGENTGATEWAY_SERVICE MODEL_CONFIG AGENTGATEWAY_MCP_URL
    IMAGE_REGISTRY IMAGE_REPOSITORY
    IMAGE_VERSION CHART_REF CHART_VERSION REPLICA_COUNT
    RESOURCE_REQUEST_CPU TOKEN_DURATION MIN_TOKEN_VALIDITY_SECONDS
    ALLOW_PUBLIC_IMAGE_FOR_TEST APPROVED_IMAGE_PREFIX TOOL_ALLOWLIST
    TARGET_API_CIDRS
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

  local expected_gateway_url image_path
  expected_gateway_url="http://$AGENTGATEWAY_SERVICE.$AGENTGATEWAY_NAMESPACE.svc.cluster.local/mcp/kubernetes-mcp-fleet"
  test "$AGENTGATEWAY_MCP_URL" = "$expected_gateway_url" || {
    echo "AGENTGATEWAY_MCP_URL must equal $expected_gateway_url" >&2
    return 1
  }

  image_path="$IMAGE_REGISTRY/$IMAGE_REPOSITORY"
  if test "$ALLOW_PUBLIC_IMAGE_FOR_TEST" != "1"; then
    case "$image_path" in
      "$APPROVED_IMAGE_PREFIX"/*) ;;
      *)
        echo "image $image_path is outside APPROVED_IMAGE_PREFIX=$APPROVED_IMAGE_PREFIX" >&2
        return 1
        ;;
    esac
  fi

  case "$MIN_TOKEN_VALIDITY_SECONDS" in
    *[!0-9]*|'')
      echo "MIN_TOKEN_VALIDITY_SECONDS must be a positive integer" >&2
      return 1
      ;;
  esac
  test "$MIN_TOKEN_VALIDITY_SECONDS" -gt 0 || {
    echo "MIN_TOKEN_VALIDITY_SECONDS must be greater than zero" >&2
    return 1
  }

  SOURCE_CONTEXTS_LIST=${SOURCE_CONTEXTS//,/ }
  SMOKE_CONTEXTS_LIST=${SMOKE_CONTEXTS//,/ }
  TOOL_ALLOWLIST_LIST=${TOOL_ALLOWLIST//,/ }
  TARGET_API_CIDRS_LIST=${TARGET_API_CIDRS//,/ }
  # shellcheck disable=SC2206
  local tools=( $TOOL_ALLOWLIST_LIST )
  # shellcheck disable=SC2206
  local target_cidrs=( $TARGET_API_CIDRS_LIST )
  TOOL_COUNT=${#tools[@]}
  test "$TOOL_COUNT" -eq 8 || {
    echo "TOOL_ALLOWLIST must contain exactly eight entries" >&2
    return 1
  }
  test "${#target_cidrs[@]}" -eq 12 || {
    echo "TARGET_API_CIDRS must contain exactly twelve entries; pad unused slots with 0.0.0.0/32" >&2
    return 1
  }
  case ",$TARGET_API_CIDRS," in
    *,0.0.0.0/0,*|*,::/0,*)
      echo "TARGET_API_CIDRS must not contain a default route" >&2
      return 1
      ;;
  esac
  EXPECTED_TOOLS_JSON=$(printf '%s\n' "${tools[@]}" | jq -Rsc 'split("\n") | map(select(length > 0)) | sort')
  export SOURCE_CONTEXTS_LIST SMOKE_CONTEXTS_LIST TOOL_ALLOWLIST_LIST
  export TARGET_API_CIDRS_LIST TOOL_COUNT EXPECTED_TOOLS_JSON

  export WORK_VALUES_FILE
}
