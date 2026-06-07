# Shared Variables For Work-Agent Bundles

Fill this sheet in the private work environment before asking an implementation
agent to run the bundles. Keep real values out of this public repo. Use
placeholders here and only provide live values inside the approved work context.

The bundles should still be usable one at a time, but this sheet avoids making
a low-token work agent rediscover the same names across every folder.

## Minimum Required Before Live Work

These are the values most likely to be needed before any real implementation or
proof run:

| Variable | Purpose | Example placeholder |
|---|---|---|
| `{{KUBE_CONTEXT}}` | Approved non-prod Kubernetes context for validation and proof commands. | `{{WORK_NONPROD_KUBE_CONTEXT}}` |
| `{{KAGENT_NAMESPACE}}` | Namespace where kagent agents, tools, and model configs are installed. | `{{WORK_KAGENT_NAMESPACE}}` |
| `{{ARGO_NAMESPACE}}` | Namespace for Argo Workflows/Events, if used by the bundle. | `{{WORK_ARGO_NAMESPACE}}` |
| `{{CHAT_MODEL_CONFIG}}` | kagent ModelConfig name approved for these agents. | `{{WORK_CHAT_MODEL_CONFIG}}` |
| `{{GITLAB_PROJECT}}` | GitLab project path used for KB, GitOps, or evidence updates. | `{{GROUP/PROJECT}}` |
| `{{TARGET_BRANCH}}` | Base branch for agent-created branches or merge requests. | `{{MAIN_OR_INTEGRATION_BRANCH}}` |
| `{{GITLAB_MCP_REMOTE_SERVER_NAME}}` | Installed GitLab MCP remote server name visible to kagent. | `{{WORK_GITLAB_MCP_SERVER}}` |
| `{{GRAFANA_MCP_REMOTE_SERVER_NAME}}` | Installed Grafana MCP remote server name visible to kagent. | `{{WORK_GRAFANA_MCP_SERVER}}` |
| `{{MIMIR_OR_PROMETHEUS_DATASOURCE_UID}}` | Metrics datasource UID for PromQL evidence. | `{{WORK_METRICS_DATASOURCE_UID}}` |
| `{{LOKI_DATASOURCE_UID}}` | Loki datasource UID for LogQL evidence. | `{{WORK_LOKI_DATASOURCE_UID}}` |
| `{{TEMPO_OR_TRACE_DATASOURCE_UID_OR_NONE}}` | Trace datasource UID, or explicit `none` when traces are unavailable. | `{{WORK_TRACE_DATASOURCE_UID_OR_NONE}}` |
| `{{MEMORY_MCP_REMOTE_SERVER_NAME}}` | Installed memory MCP remote server name visible to kagent. | `{{WORK_MEMORY_MCP_SERVER}}` |
| `{{APPROVAL_CHANNEL}}` | Human approval route for remediation, PR review, and risky actions. | `{{TEAMS_OR_GITLAB_APPROVAL_ROUTE}}` |

## Core Runtime

| Variable | Purpose |
|---|---|
| `{{KUBE_CONTEXT}}` | Kubernetes context for approved lower-env testing. |
| `{{KAGENT_NAMESPACE}}` | kagent runtime namespace. |
| `{{KAGENT_NAMESPACE_OR_PLATFORM_SCOPE}}` | Namespace or scope used by governance audits. |
| `{{ARGO_NAMESPACE}}` | Argo namespace for workflow/event proof. |
| `{{CHAT_MODEL_CONFIG}}` | Default model config used by newly created agents. |
| `{{KAGENT_MODEL_CONFIG}}` | Existing Grafana bundle synonym for `{{CHAT_MODEL_CONFIG}}`; prefer one name in work docs. |
| `{{KAGENT_A2A_ENDPOINT}}` | Agent-to-agent endpoint used for direct A2A proof, if exposed. |
| `{{AGENTGATEWAY_HOST}}` | Agent Gateway host or route, if runtime/model readiness proof is added. |

## GitLab And GitOps

| Variable | Purpose |
|---|---|
| `{{GITLAB_PROJECT}}` | Target GitLab project for KB, docs, manifests, or GitOps proof. |
| `{{TARGET_BRANCH}}` | Base branch for agent-created branches and merge requests. |
| `{{RUN_ID}}` | Unique suffix for demo branches, KB docs, and evidence files. |
| `{{GITLAB_MCP_REMOTE_SERVER_NAME}}` | GitLab MCP server name configured in kagent. |
| `{{GITLAB_MR_URL}}` | Evidence placeholder for the merge request URL created during proof. |

Do not give general triage agents broad GitLab write tools. GitLab write access
should sit with a GitOps, KB author, or issue/reporting specialist and should
leave changes behind a human-reviewed merge request.

## Grafana And Observability

| Variable | Purpose |
|---|---|
| `{{GRAFANA_MCP_REMOTE_SERVER_NAME}}` | Grafana MCP server name configured in kagent. |
| `{{GRAFANA_URL}}` | Browser URL for dashboards and evidence review. |
| `{{GRAFANA_FOLDER}}` | Dashboard folder or folder UID for generated/verified dashboards. |
| `{{MIMIR_OR_PROMETHEUS_DATASOURCE_UID}}` | Metrics datasource UID. |
| `{{LOKI_DATASOURCE_UID}}` | Logs datasource UID. |
| `{{TEMPO_OR_TRACE_DATASOURCE_UID_OR_NONE}}` | Trace datasource UID or explicit `none`. |
| `{{CLUSTER_NAME}}` | Cluster label expected by metrics, logs, and dashboards. |
| `{{ENVIRONMENT}}` | Environment label such as dev, test, staging, or nonprod. |
| `{{GRAFANA_NAMESPACE}}` | Namespace where Grafana runs, if port-forward proof is needed. |
| `{{GRAFANA_SERVICE}}` | Grafana service name, if port-forward proof is needed. |
| `{{GRAFANA_PORT}}` | Grafana service port, if port-forward proof is needed. |
| `{{GRAFANA_SERVICE_ACCOUNT_TOKEN}}` | Token reference only; never paste a real token into this repo. |
| `{{LOKI_HOST}}` | Loki endpoint or host placeholder for Alloy/log forwarding snippets. |
| `{{MIMIR_OR_PROMETHEUS_REMOTE_WRITE_URL}}` | Metrics remote-write endpoint placeholder for Alloy snippets. |

Read-first Grafana proof is the default posture. Dashboard writes, incident
creation, plugin changes, or alert-rule mutation should be separate,
approval-gated work.

## Chaos And Remediation

| Variable | Purpose |
|---|---|
| `{{DEMO_TARGET_NAMESPACE}}` | Lower-env namespace approved for chaos proof. |
| `{{DEMO_TARGET_WORKLOAD}}` | Workload approved for controlled failure injection. |
| `{{CHAOS_NAMESPACE}}` | Namespace where chaos tooling runs. |
| `{{BOUNDED_REMEDIATION_ACTION}}` | Specific remediation action allowed for a demo. |
| `{{APPROVAL_CHANNEL}}` | Human approval route for remediation steps. |

Production chaos is blocked by default. Keep chaos targets narrow, reversible,
and linked to explicit recovery criteria.

## Knowledge Base And Memory

| Variable | Purpose |
|---|---|
| `{{MEMORY_MCP_REMOTE_SERVER_NAME}}` | Memory MCP server configured in kagent. |
| `{{OPENAI_API_KEY_OR_APPROVED_PROVIDER_ENV}}` | Environment variable or approved provider reference for embeddings; do not paste key material. |

Memory writes should go through a curator/review path. KB writes should go
through GitLab MCP and a human-reviewed branch or merge request.

## App, Incident, And Fleet Inputs

| Variable | Purpose |
|---|---|
| `{{INCIDENT_ID}}` | Incident or demo run identifier. |
| `{{ALERT_SOURCE}}` | Alert source, alert name, or incoming event route. |
| `{{APPLICATION_NAMESPACE}}` | Application namespace for incident evidence. |
| `{{APPLICATION_WORKLOAD}}` | Application workload for incident evidence. |
| `{{INCIDENT_TIME_WINDOW}}` | Time window for metrics, logs, and traces. |
| `{{APPLICATION_NAME}}` | Application name used by SRE adoption and first-contact onboarding. |
| `{{FLEET_SCOPE}}` | Fleet, cluster group, or namespace set for day-2 reporting. |
| `{{SRE_OWNER}}` | SRE owner or delegate for an adoption run. |
| `{{SRE_TEAM}}` | SRE team or rota associated with the app. |
| `{{ADOPTION_WINDOW}}` | Time window for trial, game day, or adoption review. |
| `{{GAME_DAY_ID}}` | Controlled exercise, game-day, or incident identifier. |
| `{{FEEDBACK_ISSUE_PROJECT}}` | GitLab/Jira/project location for feedback issues. |
| `{{FEEDBACK_LABEL_TRIAGE_V2}}` | Label used for Kagent triage v2 feedback. |
| `{{FEEDBACK_LABEL_SRE_ADOPTION}}` | Label used for SRE adoption feedback. |
| `{{TEAM_NAME}}` | Team onboarding through BYO kagent. |
| `{{TEAM_NAMESPACE}}` | Team namespace for BYO kagent. |
| `{{PASSING_LIFECYCLE_CASE}}` | Known-good eval case. |
| `{{FAILING_LIFECYCLE_CASE}}` | Known-bad eval case that should fail gates. |

## Query And Workflow Inputs

These values are usually supplied per incident, dashboard, or demo prompt rather
than once globally:

| Variable | Purpose |
|---|---|
| `{{CLUSTER}}` | Cluster label used by Grafana evidence skills. |
| `{{NAMESPACE}}` | Namespace used by PromQL, LogQL, or workflow proof. |
| `{{WORKLOAD}}` | Workload name used by dashboards, chaos, or triage. |
| `{{POD}}` | Pod name used by logs, metrics, or trace lookup. |
| `{{CONTAINER}}` | Container name used by logs or metrics. |
| `{{WINDOW}}` | Query time window such as `30m`, `2h`, or an incident interval. |
| `{{WORKFLOW_NAME}}` | Argo Workflow name used in chaos or triage proof. |
| `{{DOMAIN_AGENT_NAME}}` | Domain triage agent being connected to shared evidence workflows. |
| `{{EXISTING_DASHBOARDS_OR_NONE}}` | Existing dashboard links or explicit `none`. |
| `{{EXISTING_ALERTS_OR_NONE}}` | Existing alert names/routes or explicit `none`. |
| `{{EXISTING_RUNBOOKS_OR_NONE}}` | Existing runbook links or explicit `none`. |
| `{{KNOWN_FAILURE_MODES_OR_NONE}}` | Known risks/failure modes or explicit `none`. |

## Evidence Template Placeholders

Some placeholders only appear in evidence templates or example prompts. They do
not need global values before handover, but the agent should replace them when
writing final evidence:

`{{COMMAND_OR_TOOL_CALL}}`, `{{TOOLS}}`, `{{TOOLS_OR_NOT_AVAILABLE}}`,
`{{KAGENT_UI_PATH_OR_NOT_AVAILABLE}}`,
`{{A2A_ENDPOINT_PLACEHOLDER_OR_NOT_AVAILABLE}}`, `{{DATASOURCE_UID}}`,
`{{DATASOURCE_OR_API}}`, `{{SUMMARY}}`, `{{PATH}}`, `{{UID_OR_URL}}`,
`{{ALERT_NAME}}`, `{{ROUTE_LABELS}}`,
`{{GRAFANA_ALERTING_OR_ALERTMANAGER_OR_ARGO}}`, `{{MR_URL_OR_NOT_AVAILABLE}}`,
`{{QUERY}}`, `{{LINKS}}`, `{{GAP_OR_NONE}}`, `{{NEXT_ACTION}}`,
`{{KNOWN_GAPS_OR_NONE}}`, `{{PLACEHOLDER}}`, `{{ALERT_START}}`,
`{{ALERT_END_OR_NOW}}`, `{{ALERT_NAMES}}`, `{{POD_NAME_OR_UNKNOWN}}`,
`{{CONTAINER_OR_UNKNOWN}}`, `{{WORKLOAD_OR_UNKNOWN}}`,
`{{SERVICE_OR_UNKNOWN}}`, `{{NODE_OR_UNKNOWN}}`,
`{{CALLER_OBSERVED_POD_STATUS_OR_UNKNOWN}}`,
`{{CALLER_OBSERVED_EVENTS_OR_UNKNOWN}}`,
`{{CALLER_OBSERVED_LOG_EXCERPT_OR_UNKNOWN}}`, `{{FILES}}`,
`{{FILES_OR_NOT_REQUIRED}}`, `{{GRAFANA_DASHBOARD_URL_OR_UID}}`,
`{{ROUTING_LABELS_OR_WORKFLOW}}`, `{{FIRST_CONTACT_PROMPT_OR_TRANSCRIPT}}`,
`{{FAILURE_MODES}}`, `{{EXISTING_CONTEXT_SUMMARY}}`,
`{{TOOLING_SUMMARY}}`, `{{EXERCISE_TYPE}}`, `{{RUN_OR_WORKFLOW_ID}}`,
`{{BLOCKER_OR_NONE}}`, `{{EVIDENCE_PACK_LINK_OR_PATH}}`,
`{{EVAL_RESULT_OR_NOT_AVAILABLE}}`, `{{SRE_ACTION_SUMMARY}}`,
`{{SRE_REVIEW_LINK_OR_NOT_AVAILABLE}}`, `{{FEEDBACK_CAPTURE_LOCATION}}`,
`{{FEEDBACK_CATEGORIES}}`, `{{TOP_FEEDBACK_ITEM}}`,
`{{MISSING_OR_WEAK_AREAS}}`, `{{IMPROVEMENT_ITEM_LINK_OR_PATH}}`,
`{{IMPROVEMENT_OWNER}}`, `{{ADOPTION_REPORT_LOCATION}}`,
`{{DASHBOARD_OR_METRICS_LOCATION_OR_NOT_AVAILABLE}}`,
`{{OPEN_BLOCKERS_OR_NONE}}`.

## Work-Agent Instruction

Before starting a bundle, replace only the variables it needs. If a required
tool, datasource, namespace, or approval path is not available, record that as
`NOT_AVAILABLE` in the evidence and do not claim live proof.
