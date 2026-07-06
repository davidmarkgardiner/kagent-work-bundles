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
- NORMALIZED_KAFKA_RECORD_HAS_CLUSTER:
- NORMALIZED_KAFKA_RECORD_HAS_EVENT_REASON:
- NORMALIZED_KAFKA_RECORD_HAS_RICH_CONTEXT:
- Normalized `cluster`:
- Normalized `event_reason`:
- Normalized `event_context`:
- Normalized `suggested_kubectl`:
- Normalized `suggested_log_query`:
- Topic/partition/offset evidence:

## Grafana MCP End-To-End Evidence

- GRAFANA_TEST_ALERT:
- GRAFANA_ALERT_FIRED_FROM_GRAFANA_ALERTING:
- Grafana alert rule name/UID:
- MANAGER_CONTACT_POINT_DELIVERY:
- Notification route/policy:
- ARGO_SENSOR_TRIGGER:
- ARGO_SENSOR_PAYLOAD_HAS_CLUSTER:
- ARGO_SENSOR_PAYLOAD_HAS_EVENT_REASON:
- ARGO_SENSOR_PAYLOAD_HAS_RICH_CONTEXT:
- Argo workflow name:
- Argo alert payload field evidence:
- TRIAGE_WORKFLOW:
- KIT_AGENT_ANALYSIS:
- GITLAB_TICKET:
- GITLAB_TICKET_INCLUDES_CLUSTER:
- GITLAB_TICKET_INCLUDES_EVENT_REASON:
- GITLAB_TICKET_INCLUDES_RICH_CONTEXT:
- GitLab issue/ticket URL or ID:
- GitLab ticket rich-context excerpt:
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

## Chaos Gameday Evidence

- CHAOS_PREFLIGHT:
- GRAFANA_MCP_ALERT_WRITE:
- GRAFANA_CHAOS_ALERT_RULES:
- Grafana chaos folder UID:
- Grafana chaos rule group:
- Grafana alert rule UIDs:
- Grafana create paused:
- CHAOS_TARGET_NAMESPACE:
- CHAOS_TARGET_WORKLOAD:
- CHAOS_SCENARIO:
- GRAFANA_ALERT_FIRED:
- EVENT_DELIVERY:
- VECTOR_NORMALIZED_EVENT:
- VECTOR_ROUTE_AGENT:
- SPECIALIST_AGENT_SELECTED:
- EVIDENCE_PACK_CREATED:
- TICKET_CREATED_OR_UPDATED:
- REMEDIATION_GATE:
- CHAOS_ROLLBACK:
- ALERT_RESOLUTION:
- GRAFANA_DASHBOARD:
- DAILY_GAMEDAY_PROPOSAL:
- Dashboard URL or UID:
- Ticket URL or ID:
- Workflow name:
- Selected agent:
- Route key:
- Rollback evidence:

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
- SHOWCASE_DASHBOARD:
- Dashboard UID:
- Daily gameday CronWorkflow dry-run:
- Baseline workflow count:
- Suppressed event count plan:
- MTTA/MTTR capture plan:
- Deflection tracking plan:

## Failure Modes And Promotion

- FAILURE_MODE_TESTS:
- PROMOTION_GATE:
- Scenario count passed:
- Unsafe write actions before HITL:
- Ticket quality accepted:

## Cleanup

- CLEANUP:
- Temporary resources:

## Gaps

- Remaining blockers:
- Production no-go items:
