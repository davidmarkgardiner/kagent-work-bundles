# Evidence Template: Vector Kafka Routing Normalization

STATUS: PASS | PARTIAL | BLOCKED

## Bundle

- BUNDLE_VERIFY:
- Bundle path:
- Commit/branch:

## Environment

- ENV_PREFLIGHT:
- Management cluster:
- Argo namespace:
- EXISTING_VECTOR:
- VECTOR_NAMESPACE:
- VECTOR_DEPLOYMENT_OR_RELEASE:
- VECTOR_IMAGE:
- VECTOR_CONFIG_SOURCE:
- VECTOR_SERVICE_ACCOUNT:
- VECTOR_SECRET_REFS_NAMES_ONLY:
- CONFLUENT_CONNECTION_SECRET:
- GRAFANA_MCP:
- MANAGER_CONTACT_POINT:
- SAFE_TEST_ALERT_PATH:
- Kafka raw topics:
- Kafka normalized topics:
- Tooling available:
- Sanitization confirmed:

## Vector

- VECTOR_CONFIG:
- K8S_DRY_RUN:
- VECTOR_ROLLOUT:
- Image:
- Probes:
- Filter stage:
- Dedupe stage:

## Kafka Evidence

- RAW_KAFKA_RECORD:
- NORMALIZED_KAFKA_RECORD:
- Topic/partition/offset evidence:

## Grafana MCP End-To-End Evidence

- GRAFANA_TEST_ALERT:
- Grafana alert rule name/UID:
- MANAGER_CONTACT_POINT_DELIVERY:
- Notification route/policy:
- ARGO_SENSOR_TRIGGER:
- TRIAGE_WORKFLOW:
- KIT_AGENT_ANALYSIS:
- GITLAB_TICKET:
- GitLab issue/ticket URL or ID:
- Temporary alert cleanup:

## Routing Evidence

- ROUTE_APP:
- ROUTE_PLATFORM:
- ROUTE_SECURITY:
- ROUTE_FALLBACK:
- Workflow names:
- Captured `target_agent` values:
- Captured `route_key` values:
- Captured `dedupe_key` values:

## Filtering And Dedupe

- RESOLVED_FILTER:
- DEDUPE:
- Duplicate raw records sent:
- Normalized workflows created:

## Existing Webhook/Proxy Assessment

- CURRENT_CHAIN:
- Sanitized current-state diagram:
- CLEAN_CHAIN:
- AUTH_OPTIONS:
- OAUTH_DECISION:
- API_KEY_FALLBACK:
- VECTOR_DIRECT_KAFKA:
- KAFKA_FIRST_SOURCE:
- PROXY_SERVICE_ROLE:
- PROXY_REMOVAL_DECISION:
- ROLLBACK_PLAN:
- HOME_LAB_REPLICATION:
- Components proposed for removal:
- Components retained and why:

## Workflow Contract

- FULL_ENVELOPE_WORKFLOW:
- Existing workflow behavior:
- Required change:

## Safety

- AUTOMATION_GATE:
- Kafka principal split:
- Replay/retention notes:

## Metrics And Value

- METRICS_PLAN:
- Baseline workflow count:
- Suppressed event count plan:
- MTTA/MTTR capture plan:
- Deflection tracking plan:

## Cleanup

- CLEANUP:
- Temporary resources:

## Gaps

- Remaining blockers:
- Production no-go items:
